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

    p(f"{question}")
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

def load_dir(dir, pattern= '*.yaml', load_training=False):
    dir = pathlib.Path(dir)
    paths = sorted(dir.glob(pattern))

    cfgs = []
    for path in paths:
        with open(path) as f:
            cfg = yaml.safe_load(f)
        if load_training and 'training' not in cfg:
            print(f"Warning: {path} has no 'training' block — skipping.")
            continue
        cfgs.append(cfg)

    if not cfgs:
        raise ValueError("No config files with a 'training' block were found.")
   
    print(f"{dir.name}: {len(cfgs)} pitches loaded.")
    return cfgs

def extract_plate(cfgs):
    result = []
    for cfg in cfgs:
        t = cfg['training']
        plate_x = _Q(t['plate_x']).to_base_units().magnitude
        plate_z = _Q(t['plate_z']).to_base_units().magnitude
        result.append([plate_x, plate_z])
    return numpy.array(result)

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
