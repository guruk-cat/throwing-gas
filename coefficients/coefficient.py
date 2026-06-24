import argparse
import pathlib
import sys
import pint
import numpy

repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / 'main'))
from phys import Simulation, Configuration
from config_io import load_dir, extract_true_acc, clear_cli, extract_plate

# UNIT HELPERS
ureg = pint.UnitRegistry()
pint.set_application_registry(ureg)
Quant = ureg.Quantity    # type: ignore[misc]
const_units = {
    "alpha absorbs all"     : "kg / m",
    "beta absorbs all"      : "kg * s / m",
    "air density"           : "kg per cubic meter",
    "displacement err"      : "inch"
}

# SETUP CONSTANTS
init_step_rate          = 1.0e-2    # large value just for the first run
default_delta_rate      = 1.0e-3    # for delta k
armijo_constant         = 1.0e-4    # for step calibration
default_gradient_thresh = 1.0e-8    # for declaring convergence
plate_y = Quant(8.5, "inch")        # middle of plate; Statcast 2026+



# MATH HELPERS

def squared_err(prediction, reference):
    # pred, ref: 1D array with x, y, z.
    # Returns scalar error
    diff = numpy.asarray(prediction) - numpy.asarray(reference)
    return numpy.sum(diff**2)

def percent_diff(a, b):
    return abs((a - b) / b)

def armijo_condition(c, alpha, gradient):
    return c * alpha * (gradient ** 2)

def crossing_point(traj):
    y = traj[:, 2]
    i = numpy.argmin(numpy.abs(y - plate_y.to_base_units().magnitude))
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
            self.set_value  = self._new_scalar
            self.nudge      = self._simple_gradient
        else:
            self.c_s        = []
            self.power      = 3     # default to v**3
            for i in range(self.power + 1):
                self.c_s.append(init_value)
            self.get_value  = self._compute_polynomial
            self.set_value  = self._new_polynomial
            self.nudge      = self._complex_gradient

    def _new_scalar(self, new_value):
        self.value = new_value

    def _new_polynomial(self, c_s):
        self.c_s = c_s

    def _compute_polynomial(self, v):
        sum = 0
        for i, term_coeff in enumerate(self.c_s):
            sum += term_coeff * (v ** i)
        return sum

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

        return (new_k, numpy.mean(errs), de_dk)

    def _complex_gradient(self, step_rate, delta_rate, cfgs, refs):
        pass
            


# OPTIMIZERS

def simple_optimization(type, epochs, cfgs, refs):
    k_1 = Coefficient(type, False)
    k_2 = Coefficient(type, False)

    step_rate = init_step_rate
    delta_rate = default_delta_rate
    grad_thresh = default_gradient_thresh

    for i in range(1, epochs + 1):
        print(f"\nRunning {i}/{epochs}\n")
        attempts = 0
        keep_going = True
        while keep_going:
            attempts += 1
            print(f"  Attempting ({attempts})")
            print(f"    Step rate           = {step_rate:4e}")
            new_value_1, error_1, gradient_1 = k_1.nudge(step_rate, delta_rate, cfgs, refs)
            if new_value_1 <= 0:
                print(f"    Coefficient is not positive")
                step_rate = step_rate / 2
                continue
            
            k_2.set_value(new_value_1)
            _, error_2, _ = k_2.nudge(step_rate, delta_rate, cfgs, refs)
            condition = armijo_condition(armijo_constant, step_rate, gradient_1)
            print(f"    Armijio condition   = {condition:.4e}")

            if error_1 - error_2 <= condition:
                print(f"    Step too big")
                step_rate = step_rate / 2
                continue
            else:
                k_1.set_value(new_value_1)
                step_rate = step_rate * 1.2
                keep_going = False

        print(f"  K         = {new_value_1:.4e}")
        print(f"  RMS error = {numpy.sqrt(error_1):.4e}")
        print(f"  Gradient  = {gradient_1:.4e}")
        if abs(gradient_1) < grad_thresh:
            print(f"  Error is not getting any smaller... declaring convergence")
            break

    return k_1

def complex_optimization():
    return

def check_goferr(k, cfgs):
    new_coefficient = Quant(k.get_value(), k.unit)

    i = 1
    total = len(cfgs)
    errs = []
    plates = extract_plate(cfgs)
    for config, plate in zip(cfgs, plates):
        print(f"{i}/{total}")
        sim = Simulation()
        setattr(sim.config, k.attr, new_coefficient)
        launch = Configuration()
        launch.configure(config['launch'])
        trajectory = sim.run(launch)
        plate_i = crossing_point(numpy.array(trajectory))
        plate_pred = numpy.array([trajectory[plate_i][1], trajectory[plate_i][3]])
        err = numpy.linalg.norm(plate - plate_pred)
        errs.append(err)
        i += 1

        # DEBUG
        # print(f"  Plate reference   : {plate}")
        # print(f"  Plate prediction  : ({trajectory[plate_i][1]:.2e}, {trajectory[plate_i][2]:.2e}, {trajectory[plate_i][3]:.2e})")

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