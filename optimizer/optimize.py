import argparse
import glob
import pathlib
import sys
import pint
import numpy
import yaml
import os

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'src'))
from phys import Simulation, Configuration



# UNIT HELPERS

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity
pint.set_application_registry(ureg)

xhat = numpy.array([1, 0, 0], dtype=float)
yhat = numpy.array([0, 1, 0], dtype=float)
zhat = numpy.array([0, 0, 1], dtype=float)

def si_mag(quant):
  # Strip pint quantity to its SI base-unit magnitude.
  return quant.to_base_units().magnitude 



# OPTIMIZER SETUP CONSTANTS

k_init = Q_(1e-4, 'kg * s / m')     # arbitrary initial value for constant K
lr_init = abs(si_mag(k_init)) / 4   # initial learning rate (dimensionless)
err_goal = Q_(0.5, "inch")          # target for error, based on error margins in Statcast trackings
delta_k_ratio = 0.01                # delta K is 1% of K



# SIMULATION SETUP

y_plate = Q_(8.5, "inch")   # strike zone at middle of home plate

def terminate_sim(record):
    # This is used to terminate a single instance of the simulation
    # Don't confuse it with terminating the optimization
    state = record[-1]
    if state[3] < 0:        # z < 0: ball hit the ground
        return True
    if state[2] < -0.5:     # y < -0.5: ball is past home plate
        return True
    if state[0] > 10:       # t > 10s: safety valve
        return True
    return False



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

def extract_true_xz(cfgs):
    # Pull plate_x and plate_z from each config's 'training' block.
    # Returns an (N, 2) numpy array of [x, z] in metres.
    result = []
    for cfg in cfgs:
        t = cfg['training']
        x = si_mag(Q_(t['plate_x']))
        z = si_mag(Q_(t['plate_z']))
        result.append([x, z])
    return numpy.array(result)

def select_batches():
    # Lists subdirectories of `learning samples/` and prompts the user to 
    # choose which ones to include in the training run.

    samples_dir = pathlib.Path(__file__).parent / 'learning samples'
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

def interpolate_at_plate(record, y_plate_m):
    # Linear interpolation to find (x, z) at exactly y = y_plate_m.
    # Scans for the first consecutive pair of states that bracket the plate.
    # Returns a numpy array [x, z] in metres, or None if the ball never reaches the plate.
    for i in range(len(record) - 1):
        y_a, y_b = record[i][2], record[i+1][2]
        if y_a >= y_plate_m > y_b:
            t = (y_plate_m - y_a) / (y_b - y_a)
            x = record[i][1] + t * (record[i+1][1] - record[i][1])
            z = record[i][3] + t * (record[i+1][3] - record[i][3])
            return numpy.array([x, z])
    return None

def squared_err(pred_xz, true_xz):
    # pred_xz, true_xz: (N, 2) arrays of [x, z] plate-crossing positions in metres.
    # Returns a length-N array of per-sample squared errors.
    diff = numpy.asarray(pred_xz) - numpy.asarray(true_xz)
    return numpy.sum(diff**2, axis=1)

def de_dk(errs_k, errs_k_delta, delta_k):
    # Numerical finite-difference gradient of mean squared error w.r.t. K.
    # errs_k, errs_k_delta: per-sample error arrays at K and K+delta_k.
    # delta_k: finite-difference step in SI units (kg·s/m).
    return (numpy.mean(errs_k_delta) - numpy.mean(errs_k)) / delta_k

def run_single(cfg, k):
    # cfg: full YAML dict (with 'launch', optionally 'simulation').
    # k: magnus_coefficient as a pint Quantity.
    # Returns numpy [x, z] at plate crossing in metres, or None if ball never reaches the plate.
    sim = Simulation()
    if 'simulation' in cfg:
        sim.configure(cfg['simulation'])
    sim.config.magnus_coefficient = k

    launch = Configuration()
    launch.configure(cfg['launch'])

    record = sim.run(launch, terminate_sim, adaptive=False)
    return interpolate_at_plate(record, si_mag(y_plate))

def run_batch(cfgs, k):
    # cfgs: list of YAML config dicts.
    # k: magnus_coefficient as a pint Quantity.
    # Returns a list parallel to cfgs; each entry is [x, z] in metres or None.
    return [run_single(cfg, k) for cfg in cfgs]

def run_batch_with_progress(cfgs, k, label):
    # Like run_batch, but prints a single updating progress line via delete_lines().
    # Clears the line when done so the caller can print its own output beneath.
    results = []
    total   = len(cfgs)
    for i, cfg in enumerate(cfgs):
        if i > 0:
            delete_lines(1)
        print(f'  {label}: {i}/{total}')
        results.append(run_single(cfg, k))

    delete_lines(1)
    return results

def correct_k_from_err(lr, grad):
    # Gradient descent correction: the additive update to apply to K.
    # Caller does: k += correct_k_from_err(lr, grad)
    return -lr * grad

def gradient_step(cfgs, true_xz, k, lr):
    # Run one gradient descent step over a batch.
    # Returns updated k (float, SI) and the RMS error before the update.
    delta_k   = k * delta_k_ratio
    k_q       = Q_(k,           'kg * s / m')
    k_delta_q = Q_(k + delta_k, 'kg * s / m')

    pred_k       = run_batch_with_progress(cfgs, k_q,       'K')
    pred_k_delta = run_batch_with_progress(cfgs, k_delta_q, 'K+δ')

    valid = [i for i, (a, b) in enumerate(zip(pred_k, pred_k_delta))
             if a is not None and b is not None]
    if not valid:
        return k, None, len(cfgs)

    pred_k_arr       = numpy.array([pred_k[i]       for i in valid])
    pred_k_delta_arr = numpy.array([pred_k_delta[i] for i in valid])
    true_xz_arr      = numpy.array([true_xz[i]      for i in valid])

    errs_k       = squared_err(pred_k_arr,       true_xz_arr)
    errs_k_delta = squared_err(pred_k_delta_arr, true_xz_arr)

    grad    = de_dk(errs_k, errs_k_delta, delta_k)
    k      += correct_k_from_err(lr, grad)
    rms_err = numpy.sqrt(numpy.mean(errs_k))
    dropped = len(cfgs) - len(valid)
    return k, rms_err, dropped

def main():
    parser = argparse.ArgumentParser(description='Optimize magnus coefficient K via gradient descent.')
    parser.add_argument('--epochs', type=int, default=10,
                        help='Number of full passes over all selected batches (default: 10).')
    args = parser.parse_args()

    batch_dirs = select_batches()

    # Pre-load all configs and ground-truth positions so disk I/O isn't repeated each epoch.
    batches = []
    for d in batch_dirs:
        cfgs    = load_configs([str(d / '*.yaml')])
        true_xz = extract_true_xz(cfgs)
        batches.append((d.name, cfgs, true_xz))
        print(f"  {d.name}: {len(cfgs)} pitches loaded.")

    k  = si_mag(k_init)
    lr = lr_init
    converged = False

    for epoch in range(1, args.epochs + 1):
        print(f"\n--- Epoch {epoch}/{args.epochs} ---")

        for batch_name, cfgs, true_xz in batches:
            k, rms_err, dropped = gradient_step(cfgs, true_xz, k, lr)

            if rms_err is None:
                print(f"  [{batch_name}]  No pitches reached the plate — skipping.")
                continue

            drop_note = f"  ({dropped} dropped)" if dropped else ""
            print(f"  [{batch_name}]  K={k:.4e}  RMS={rms_err*100:.2f} cm{drop_note}")

            if rms_err <= si_mag(err_goal):
                converged = True
                break

        if converged:
            print(f"\nConverged at epoch {epoch}.")
            break
    else:
        print(f"\nReached {args.epochs} epoch(s) without converging.")

    print(f"Final K = {k:.6e} kg·s/m")



if __name__ == '__main__':
    main()