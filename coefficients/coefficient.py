import argparse
import pathlib
import sys
import time

import pint
import numpy

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'main'))
from phys import Simulation, Configuration
from config_io import *



# UNITS

ureg = pint.UnitRegistry()
pint.set_application_registry(ureg)
Quant = ureg.Quantity    # type: ignore[misc]

def si_mag(quantity):
    return quantity.to_base_units().magnitude

const_units = {
    "report displacement"   : "inch",
    "report velocity"       : "miles per hour",

    "drag absorbs all"      : "kg / m",
    "magnus absorbs all"    : "kg * s / m",
    "air density"           : "kg per cubic meter"
}

