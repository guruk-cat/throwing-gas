import argparse
import pathlib
import sys
import pint
import numpy
import math

repo_root = pathlib.Path(__file__).parent.parent.parent
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
const_units['alpha'] = (Quant(1, const_units["alpha absorbs all"]) / Quant(1, const_units["air density"])).to_base_units().units
const_units['beta'] = (Quant(1, const_units["beta absorbs all"]) / Quant(1, const_units["air density"])).to_base_units().units

plate_y     = Quant(8.5, "inch")    # middle of plate; Statcast 2026+
fastballs   = ['FF', 'SI', 'FC']
offspeeds  = ['CH', 'FS', 'FO', 'SC']
curveballs  = ['CU', 'KC', 'CS']
sliders     = ['SL', 'ST', 'SV']

err_kind_str = {
    1   : 'overbreak',
    -1  : 'underbreak',
    0   : 'near-orthogonal'
}

# shared sim instance
sim = Simulation()
sim.config.magnus_coefficient = Quant(1.0e-05, const_units['beta'])
sim.config.drag_coefficient   = Quant(1.0e-05, const_units['alpha']) 


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

def clock_angle(x, z):
    angle = numpy.degrees(numpy.arctan2(x, z)) % 360
    return int((angle + 15) // 30)



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
            self.unit = const_units['beta']
        elif kind == 'drag':
            self.unit = const_units['alpha']

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

        # The shared sim's coefficient is reset here
        setattr(sim.config, k.attr, Quant(k.get_value(), k.unit))
        pred = sim.point_run(launch)
        rms_errs.append(numpy.sqrt(squared_err(pred, ref)))

    return k, numpy.mean(numpy.array(rms_errs))

def check_goferr(cfgs, detailed=False):

    i = 1
    total = len(cfgs)
    errs = []
    full_list = []
    plates = extract_plate(cfgs)
    for config, plate in zip(cfgs, plates):
        if detailed:
            print(f"\n{i}/{total}")
        else:
            print(f"  {i}/{total}")
        launch = Configuration()
        launch.configure(config['launch'])
        sim.record_clean()  # must be cleaned since same instance is reused
        sim.record_magnus()
        trajectory = sim.run(launch)
        plate_i = crossing_point(numpy.array(trajectory))
        plate_pred = numpy.array([trajectory[plate_i][1], trajectory[plate_i][3]])

        err         = plate_pred - plate
        magnus_xz   = numpy.array([sim.extra.record[plate_i][0], sim.extra.record[plate_i][2]])
        cos_xz      = numpy.dot(err, magnus_xz) / (numpy.linalg.norm(err) * numpy.linalg.norm(magnus_xz))
        if cos_xz > 0.1:
            err_kind = 1    # overbreak
        elif cos_xz < -0.1:
            err_kind = -1   # underbreak
        else:
            err_kind = 0    # near-orthogonal

        clock_angle_err = clock_angle(err[0], err[1])
        clock_angle_magnus = clock_angle(magnus_xz[0], magnus_xz[1])

        err = numpy.linalg.norm(err)    # magnitude for general report
        errs.append(err) 

        md = config['metadata']
        pitch_type      = md['pitch_type']
        pitcher_name    = md['pitcher']
        pitch_count     = md['pitch_count']
        game_date       = md['game_date']
        full_list.append([pitch_type, pitcher_name, pitch_count, game_date, err_kind, err])
        
        if detailed:
            print(f"  Pitch type    : {pitch_type}")
            print(f"  Identifier    : {pitcher_name}, #{pitch_count}, on {game_date}\n")
            print(f"  Offshot       : {Quant(err, 'meter').to('inch').magnitude:.4e} inches")
            print(f"    kind        : {err_kind_str[err_kind]}")
            print(f"    disp. angle : {clock_angle_err} o'clock")
            print(f"    magn. angle : {clock_angle_magnus} o'clock")
        else:
            delete_lines(1)
        
        i += 1

    return numpy.mean(numpy.array(errs)), full_list

def run(cfgs, kind, complex):
    if complex:
        new_coefficient = None
    else:
        new_coefficient, err_rms = find_scalar(kind, cfgs)
    print(f"FINAL:")
    print(f"  K         = {new_coefficient.get_value():.8e} ({new_coefficient.unit})")
    print(f"  RMS       = {err_rms:.8e} ({new_coefficient.unit})")

    return new_coefficient

def main():
    parse = argparse.ArgumentParser(description="Optimize coefficients via gradient descent.")
    parse.add_argument('-type', choices=['magnus', 'drag', 'alternate'], default='alternate', help="Which coefficient to optimize")
    parse.add_argument('-path', type=pathlib.Path, help="Path to directory holding config files")
    parse.add_argument('--complex', action='store_true', help="Coefficient is a polynomial of velocity")
    parse.add_argument('--goferr', action='store_true', help="Check good ole-fashioned error after determining K")
    parse.add_argument('--detailed', action='store_true', help="Print details for GOFErr")
    args = parse.parse_args()
    clear_cli()

    samples_dir = args.path.resolve()
    cfgs = load_dir(samples_dir, load_training=True)
    if args.type == 'alternate':
        print("")
        run(cfgs, 'drag', args.complex)
        print("")
        run(cfgs, 'magnus', args.complex)
    else:
        run(cfgs, args.type, args.complex)

    if args.goferr:
        print("\nComputing displacement error...")
        error, err_details = check_goferr(cfgs, args.detailed)
        error = Quant(error, 'meter').to(const_units['displacement err']).magnitude
        print(f"\nΔx avg. (all samples)    : {error:.4e} ({const_units['displacement err']})")

        names = ['FASTBALLS ', 'OFFSPEEDS ', 'CURVEBALLS', 'SLIDERS   ']
        pitches = [fastballs, offspeeds, curveballs, sliders]

        # Deets: pitch_type, pitcher_name, pitch_count, game_date, err_kind, err
        for name, pitch_type in zip(names, pitches):
            filtered = [row for row in err_details if row[0] in pitch_type]
            filtered_errs = [row[-1] for row in filtered]
            filtered_err_mean = Quant(numpy.mean(filtered_errs), 'meter').to(const_units['displacement err']).magnitude if filtered_errs else float('nan')
            print(f"  \nΔx avg. for {name}   : {filtered_err_mean:.4e} ({const_units['displacement err']})")
            
            break_type_filtered = [row[-2] for row in filtered]
            break_type_agg = numpy.sum(numpy.array(break_type_filtered))
            if break_type_agg != 0:
                break_type_id = math.copysign(1, break_type_agg)
            else:
                break_type_id = 0
            print(f"  Dominant break side    : {err_kind_str[break_type_id]} ({break_type_agg})")

if __name__ == '__main__':
    main()