import glob
import pathlib
import os
import sys

import pint
import numpy
import yaml



# UNITS

_ureg = pint.UnitRegistry()
pint.set_application_registry(_ureg)
_Q = _ureg.Quantity    # type: ignore[misc]

def _si_mag(quantity):
    return quantity.to_base_units().magnitude



# CLI HELPERS

def clear_cli():
    os.system('cls' if os.name == 'nt' else 'clear')

def exit_cli():
    clear_cli()
    print("Goodbye!")
    sys.exit()

def user_input():
    u = input("\n\n\n> ").strip()
    return u

def delete_lines(n):
    for _ in range(n):
        # \033[F moves cursor up one line; \033[K clears that line
        sys.stdout.write("\033[F\033[K")

def simple_question(question):
    lines = 0
    def p(s=''):
        nonlocal lines
        print(s)
        lines += s.count('\n') + 1   # +1 for the newline print() always appends

    p(f"\n{question}")
    u = user_input()
    lines += 4
    delete_lines(lines)
    return u

def yes_or_no(question):
    lines = 0
    def p(s=''):
        nonlocal lines
        print(s)
        lines += s.count('\n') + 1
    
    p(f"{question} [y/n]")
    u = user_input()
    lines += 4
    delete_lines(lines)

    if u == "y" or u == "Y":
        return True
    elif u == "n" or u == "N":
        return False
    else:
        yes_or_no(question)



# CONFIG I/O

def select_batches(dir):
    all_batches = sorted([d for d in dir.iterdir() if d.is_dir()])

    if not all_batches:
        raise ValueError(f"No subdirectories found in {dir}")

    clear_cli()
    print("\nAvailable batches:")
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

def load_training(patterns):
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
        ax = _si_mag(_Q(t['ax']))
        ay = _si_mag(_Q(t['ay']))
        az = _si_mag(_Q(t['az']))
        result.append([ax, ay, az])
    return numpy.array(result)
