import argparse
import pathlib
import sys
import time

import pint
import numpy

repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / 'main'))
from phys import Simulation, Configuration
from config_io import load_dir, extract_true_acc, clear_cli, extract_plate, user_input



ureg = pint.UnitRegistry()
pint.set_application_registry(ureg)
Quant = ureg.Quantity    # type: ignore[misc]

const_units = {
    "alpha absorbs all"     : "kg / m",
    "beta absorbs all"      : "kg * s / m",
    "air density"           : "kg per cubic meter",
    "displacement err"      : "inch"
}

default_step_rate       = 1.0e-13   # for gradient descent
default_delta_rate      = 1.0e-3    # for delta k
default_gradient_thresh = 1.0e-3
displc_err_goal = Quant(1, 'inch').to_base_units().magnitude

def squared_err(prediction, reference):
    # pred, ref: 1D array with x, y, z.
    # Returns scalar error
    diff = numpy.asarray(prediction) - numpy.asarray(reference)
    return numpy.linalg.norm(diff**2)

def percent_diff(a, b):
    return abs((a - b) / b)

# middle of plate; Statcast 2026+
PLATE_Y = Quant(8.5, "inch")

def crossing_point(traj):
    y = traj[:, 2]
    i = numpy.argmin(numpy.abs(y - PLATE_Y.to_base_units().magnitude))
    return i



class Coefficient():
    '''
    The "coefficient" is either for the drag term or the Magnus term.
    It can either by a real constant (i.e., a scalar value), or it may 
    be a polynomial of velocity. To accomodate for these variations, 
    retrieving or changing the value of the coefficient from outside of
    the class should use dedicated functions. 

    str kind            : 'magnus' or 'drag'
    bool complex        : treat coefficient as polynomial
    float init_value    : arbitrary starting point
    '''
    def __init__(self, kind, complex, init_value=1.0e-4):
        self.attr = f"{kind}_coefficient"

        if kind == 'magnus':
            self.unit = (Quant(1, const_units["beta absorbs all"]) / Quant(1, const_units["air density"])).to_base_units().units
        elif kind == 'drag':
            self.unit = (Quant(1, const_units["alpha absorbs all"]) / Quant(1, const_units["air density"])).to_base_units().units

        if not complex:
            self.value      = init_value
            self.get_value  = lambda: self.value
            self.nudge      = self._simple_gradient
        else:
            self.c_a        = init_value
            self.c_b        = init_value
            self.c_c        = init_value
            self.c_d        = init_value
            self.get_value  = lambda v: self.c_a + self.c_b * v + self.c_c * (v**2) + self.c_d * (v**3)
            self.nudge      = self._complex_gradient

    def _simple_gradient(self, step_rate, delta_rate, cfgs, refs):
        k = Quant(self.value, self.unit)
        delta_k = k * delta_rate
        k_prime = k + delta_k

        errs = []
        errs_prime = []

        for config, reference in zip(cfgs, refs):
            sim_k = Simulation()
            sim_k_prime = Simulation()

            setattr(sim_k.config, self.attr, k)
            setattr(sim_k_prime.config, self.attr, k_prime)

            launch = Configuration()
            launch.configure(config['launch'])

            dv_dt = sim_k.point_run(launch)
            dv_dt_prime = sim_k_prime.point_run(launch)
            errs.append(squared_err(dv_dt, reference))
            errs_prime.append(squared_err(dv_dt_prime, reference))
        
        errs = numpy.array(errs)
        errs_prime = numpy.array(errs_prime)
        de_dk = (numpy.mean(errs_prime) - numpy.mean(errs)) / delta_k.magnitude
        new_k = k.magnitude - step_rate * de_dk
        rms = numpy.sqrt(numpy.mean(errs))

        self.value = new_k
        return (new_k, rms, de_dk)

    def _complex_gradient(self, step_rate, delta_rate, cfgs, refs):
        pass
            


def set_goal(max_displacement, time):
    return 2 * max_displacement / (time**2)

def check_epoch(errs, gradient, noise, cvg_thershold):
    if len(errs) < 3:
        return 'continue'
    elif abs(gradient) < noise:
        return 'terminate'
    elif errs[-1] > errs[-2]:
        return 'reduce step'
    elif errs[-1] < cvg_thershold and errs[-2] < cvg_thershold:
        return 'converge'
    
def simple_optimization(type, epochs, cfgs, refs):
    k = Coefficient(type, False)

    step_rate = default_step_rate
    delta_rate = default_delta_rate
    grad_thresh = default_gradient_thresh
    convergence_thresh = set_goal(displc_err_goal, 0.4)

    errs = []
    for i in range(1, epochs + 1):
        print(f"\nRunning {i}/{epochs}\n")
        new_value, rms, gradient = k.nudge(step_rate, delta_rate, cfgs, refs)
        errs.append(rms)
        print(f"  K         = {new_value:.4e}")
        print(f"  RMS error = {rms:.8e}")
        print(f"  Gradient  = {gradient:.8f}")

        check = check_epoch(errs, gradient, grad_thresh, convergence_thresh)
        if check == 'terminate':
            print("  Error is not getting smaller... terminating\n")
            break
        if check == 'converge':
            print("  Hit error goal... terminating\n")
            break
    return k

def check_goferr(k, cfgs):
    errs = []
    plates = extract_plate(cfgs)    # TODO: pint units??
    for config, plate in zip(cfgs, plates):
        sim = Simulation()
        setattr(sim.config, k.attr, k)
        launch = Configuration()
        launch.configure(config['launch'])
        trajectory = sim.run(launch)
        plate_i = crossing_point(trajectory)
        plate_pred = numpy.array([trajectory[plate_i][1], trajectory[plate_i][3]])
        err = numpy.linalg.norm(plate - plate_pred)
        errs.append(err)

    return numpy.mean(numpy.array(errs))

def main():
    parse = argparse.ArgumentParser(description="Optimize coefficients via gradient descent.")
    parse.add_argument('type', choices=['magnus', 'drag'], help="Which coefficient to optimize")
    parse.add_argument('path', type=pathlib.Path, help="Relative path from repo root to directory holding config files")
    parse.add_argument('--air-density', type=bool, default=True, help="Factor in air density")
    parse.add_argument('--complex', type=bool, default=False, help="Coefficient is a polynomial of velocity")
    parse.add_argument('--epochs', type=int, default=100, help="Number of optimization epochs")
    parse.add_argument('--goferr', type=bool, default=False, help="Check good ole-fashioned error after optimization")
    args = parse.parse_args()
    clear_cli()

    samples_dir = repo_root / args.path
    cfgs = load_dir(samples_dir, load_training=True)
    true_acc = extract_true_acc(cfgs)
    if args.complex:
        new_coefficient = None
    else:
        new_coefficient = simple_optimization(args.type, args.epochs, cfgs, true_acc)
        print(f"FINAL: {new_coefficient.get_value():.4e} ({new_coefficient.unit})")
    
    if args.goferr:
        print("Computing displacement error...")
        error = check_goferr(new_coefficient, cfgs)
        error = Quant(error, 'meter').to('inch').magnitude
        print(f"Good ole-fashioned error: {error} {const_units['displacement err']}")



if __name__ == '__main__':
    main()