import argparse
import glob
import pathlib
import sys
import pint
import numpy

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

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
k_init = Q_(1e-2, 'kg * s / m')         # arbitrary initial value for constant K
lr_init = abs(si_mag(k_init)) / 4       # initial learning rate (dimensionless)
squared_err_goal = 0.01                 # target for squared error (dimensionless)



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

def squared_err():
    # Calculate squared error between two arrays of vectors
    # and return an array of errors (n_arg1 = n_arg2 = n_return)
    return

def de_dk():
    # Calculate the partial derivative of a error function E 
    # respect to constant K at K=K'.
    return

def run_single():
    # Run a single instance of Simulation with a specified constant K.
    # Take initial state vector S and return final state vector S'
    return

def run_batch():
    # Run a batch of multiple Simulations with a specified constant K.
    # Take an array of initial state vectors [S] 
    # and return an array final state vectors [S']
    return

def correct_k_from_err():
    # Calculate how much constant K must be corrected:
    # (alpha) * (de_dk)
    # de_dk includes sign
    return

def main():

    return


if __name__ == '__main__':
    main()