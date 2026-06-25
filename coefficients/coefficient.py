import argparse
import pathlib
import sys
import pint
import numpy

repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / 'main'))
from phys import Simulation, Configuration
from config_io import load_dir, extract_true_acc, clear_cli, extract_plate, delete_lines

# UNITS and CONSTANTS
ureg = pint.UnitRegistry()
pint.set_application_registry(ureg)
Quant = ureg.Quantity    # type: ignore[misc]
const_units = {
    "alpha absorbs all"     : "kg / m",
    "beta absorbs all"      : "kg * s / m",
    "air density"           : "kg per cubic meter",
    "displacement err"      : "inch"
}

plate_y = Quant(8.5, "inch")        # middle of plate; Statcast 2026+



# MATH HELPERS

def squared_err(prediction, reference):
    # pred, ref: 1D array with x, y, z.
    # Returns scalar error
    diff = numpy.asarray(prediction) - numpy.asarray(reference)
    return numpy.sum(diff**2)

def percent_diff(a, b):
    return abs((a - b) / b)

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
        else:
            self.c_s        = []
            self.power      = 3     # default to v**3
            for i in range(self.power + 1):
                self.c_s.append(init_value)
            self.get_value  = self._compute_polynomial
            self.set_value  = self._new_polynomial

    def _new_scalar(self, new_value):
        self.value = new_value

    def _new_polynomial(self, c_s):
        self.c_s = c_s

    def _compute_polynomial(self, v):
        sum = 0
        for i, term_coeff in enumerate(self.c_s):
            sum += term_coeff * (v ** i)
        return sum

def find_scalar(kind, cfgs):
    delta = 1.0e-4

    k_0 = Coefficient(kind, False)
    k_delta = Coefficient(kind, False)
    k_0.set_value(0)
    k_delta.set_value(delta)
    refs = extract_true_acc(cfgs)
    A, B = [], []

    print(f"computing k for {kind}...")
    for config, ref in zip(cfgs, refs):
        launch = Configuration()
        launch.configure(config['launch'])

        sim = Simulation()
        setattr(sim.config, k_0.attr, Quant(k_0.get_value(), k_0.unit))
        pred_0 = sim.point_run(launch)
        err_0 = pred_0 - ref

        setattr(sim.config, k_delta.attr, Quant(k_delta.get_value(), k_delta.unit))
        pred_1 = sim.point_run(launch)
        err_1 = pred_1 - ref

        A.append((err_1 - err_0) / delta)
        B.append(err_0)
    
    A = numpy.array(A)
    B = numpy.array(B)
    k = Coefficient(kind, False)
    k.set_value(-1 * numpy.sum(A*B)/numpy.sum(A*A))

    rms_errs = []
    print(f"computing RMS error...")
    for config, ref in zip(cfgs, refs):
        launch = Configuration()
        launch.configure(config['launch'])
        sim = Simulation()
        setattr(sim.config, k.attr, Quant(k.get_value(), k.unit))
        pred = sim.point_run(launch)
        rms_errs.append(numpy.sqrt(squared_err(pred, ref)))

    return k, numpy.mean(numpy.array(rms_errs))

def check_goferr(k, cfgs):
    new_coefficient = Quant(k.get_value(), k.unit)

    i = 1
    total = len(cfgs)
    errs = []
    plates = extract_plate(cfgs)
    for config, plate in zip(cfgs, plates):
        print(f"  {i}/{total}")
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
        delete_lines(1)

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

    if args.complex:
        new_coefficient = None
    else:
        new_coefficient, err = find_scalar(args.type, cfgs)
    print(f"\nFINAL:")
    print(f"  K         = {new_coefficient.get_value():.8e} ({new_coefficient.unit})")
    print(f"  RMS       = {err:.8e} ({new_coefficient.unit})")

    if args.goferr:
        print("\nComputing displacement error...")
        error = check_goferr(new_coefficient, cfgs)
        error = Quant(error, 'meter').to('inch').magnitude
        print(f"  Avg. Δx   =  {error:.4e} {const_units['displacement err']}")



if __name__ == '__main__':
    main()