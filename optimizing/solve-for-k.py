import glob
import pathlib
import sys
import pint
import numpy
import yaml
import os
import time
from math import sqrt

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'main'))
from phys import Simulation, Configuration



# UNIT HELPERS

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity  
pint.set_application_registry(ureg)

xhat = numpy.array([1, 0, 0], dtype=float)
yhat = numpy.array([0, 1, 0], dtype=float)
zhat = numpy.array([0, 0, 1], dtype=float)

report_d_error = 'inch'
k_unit = 'kg*s/m'

def si_mag(quant):
  # Strip pint quantity to its SI base-unit magnitude.
  return quant.to_base_units().magnitude 



# CLI HELPERS

def clear_cli():
    os.system('cls' if os.name == 'nt' else 'clear')

def delete_lines(n):
    for _ in range(n):
        # \033[F moves cursor up one line; \033[K clears that line
        sys.stdout.write("\033[F\033[K")



# FILE I/O

def load_configs(patterns):
    # Expand glob patterns, load each YAML, and return a list of config dicts.
    # Files without a 'training' block are skipped with a warning.
    paths = []
    for pattern in patterns:
        matched = sorted(glob.glob(pattern))
        paths.extend(matched if matched else [pattern])

    cfgs = []
    for path in paths:
        with open(path) as f:
            cfg = yaml.safe_load(f)
        if 'training' not in cfg:
            print(f"Warning: {path} has no 'training' block — skipping.")
            continue
        cfgs.append(cfg)

    if not cfgs:
        raise ValueError("No config files with a 'training' block were found.")
    return cfgs

def extract_true_acc(cfgs):
    # Pull ax, ay, az from each config's 'training' block.
    # Returns an (N, 3) numpy array of [ax, ay, az] in m/s².
    result = []
    for cfg in cfgs:
        t = cfg['training']
        ax = si_mag(Q_(t['ax']))
        ay = si_mag(Q_(t['ay']))
        az = si_mag(Q_(t['az']))
        result.append([ax, ay, az])
    return numpy.array(result)

def select_batches():
    samples_dir = pathlib.Path(__file__).parent / 'samples'
    all_batches = sorted([d for d in samples_dir.iterdir() if d.is_dir()])

    if not all_batches:
        raise ValueError(f"No subdirectories found in {samples_dir}")

    clear_cli()
    print("\nAvailable training batches:")
    for i, b in enumerate(all_batches, 1):
        n = len(list(b.glob('*.yaml')))
        print(f"  [{i}] {b.name}  ({n} pitches)")

    while True:
        raw = input("\nBatches to include (e.g. '1 3 4'), or Enter for all: ").strip()
        if not raw:
            selected = all_batches
            break
        try:
            indices  = [int(x) - 1 for x in raw.split()]
            if any(i < 0 or i >= len(all_batches) for i in indices):
                raise IndexError
            selected = [all_batches[i] for i in indices]
            break
        except (ValueError, IndexError):
            print(f"  Invalid input. Enter numbers between 1 and {len(all_batches)}, separated by spaces.")

    clear_cli()
    print(f"\nSelecting {len(selected)} batches...")
    return selected



# MATH STUFF

def compute_single_sim(cfg):
    # Run simulation with Magnus term = 0.
    sim = Simulation()
    sim.config.magnus_coefficient = Q_(0, k_unit)
    launch = Configuration()
    launch.configure(cfg['launch'])

    spin = launch.get_spin()
    velo = launch.get_velocity()
    cross = numpy.cross(spin, velo)
    dv_dt = sim.point_run(launch)

    return cross, dv_dt

def check_with_k(k, cfg):
    # Run simulation with Magnus coefficient k
    sim = Simulation()
    sim.config.magnus_coefficient = Q_(k, k_unit)
    launch = Configuration()
    launch.configure(cfg['launch'])
    return sim.point_run(launch)

def squared_err(prediction, reference):
    # pred, true: (N, M) arrays. Returns a length-N array of per-sample squared errors.
    diff = numpy.asarray(prediction) - numpy.asarray(reference)
    return numpy.sum(diff**2, axis=1)

def percent_error(reference, new):
    return abs((reference - new) / reference)

def rms_to_displacement(rms_acc, t):
    # Estimates max displacement error
    return 0.5 * rms_acc * t ** 2

def main():
    batch_dirs = select_batches()
    batches = []
    for d in batch_dirs:
        cfgs = load_configs([str(d / '*.yaml')])
        true_acc = extract_true_acc(cfgs)
        batches.append((d.name, cfgs, true_acc))
        print(f"  {d.name}: {len(cfgs)} pitches loaded.")
    time.sleep(1)

    r_dot_c_sum = 0 
    c_squared_sum = 0
    for batch in batches:
        name, cfgs, refs = batch
        print(f"Computing for: [{name}]")
        crosses = []
        dv_dts = []
        for cfg in cfgs:
            cross, dv_dt = compute_single_sim(cfg)
            crosses.append(cross)
            dv_dts.append(dv_dt)
        crosses = numpy.array(crosses)
        dv_dts = numpy.array(dv_dts)
        r_s = refs - dv_dts
        for i in range(len(r_s)):
            r_dot_c_sum += numpy.dot(r_s[i], crosses[i])
            c_squared_sum += numpy.dot(crosses[i], crosses[i])
        delete_lines(1)
    
    m = si_mag(Q_(145, 'g'))
    k = m * r_dot_c_sum / c_squared_sum
    print(f"\nCompute complete. Calculating errors...")
    
    rms_sum = 0
    for batch in batches:
        preds = []
        name, cfgs, refs = batch
        for cfg in cfgs:
            pred = check_with_k(k, cfg)
            preds.append(pred)
        rms_sum += sqrt(numpy.mean(squared_err(preds, refs)))
    rms_total = rms_sum / len(batches)
    d_1 = Q_(rms_to_displacement(rms_total, 0.40), "meter").to(report_d_error).magnitude
    d_2 = Q_(rms_to_displacement(rms_total, 0.45), "meter").to(report_d_error).magnitude
    
    delete_lines(1)
    print(f"Final K                             = {k:.12e} ({k_unit})")
    print(f"Final RMS error across all bacthes  = {rms_total:.12f} m/s²")
    print(f"Est. ceiling of displacement error  = {d_1:.1f} ~ {d_2:.1f} ({report_d_error})")


if __name__ == '__main__':
    main()