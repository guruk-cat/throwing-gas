import glob
import pathlib
import sys
import pint
import numpy
import yaml
import os

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / 'main'))
from phys import Simulation, Configuration, DEFAULT_TIME_STEP

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity
pint.set_application_registry(ureg)

def terminate(record):
    state = record[-1]
    if state[3] < 0:  
        return True
    if state[2] < -1:   
        return True
    if state[0] > 10:   # t > 10s: safety valve
        return True
    return False

def main():
    tests_dir = pathlib.Path(__file__).parent / 'configs'
    config_path = tests_dir / 'Webb-SI.yaml'

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    sim_no_drag = Simulation()
    sim_no_drag.config.drag_coefficient = Q_(0, 'kg/m')

    sim_only_grav = Simulation()
    sim_only_grav.config.drag_coefficient = Q_(0, 'kg/m')
    sim_only_grav.config.magnus_coefficient = Q_(0, 'kg * s / m')
    
    launch = Configuration()
    launch.configure(cfg['launch'])

    sinker_no_drag = numpy.array(sim_no_drag.run(launch, terminate))
    sinker_only_grav = numpy.array(sim_only_grav.run(launch, terminate))

    os.system('cls' if os.name == 'nt' else 'clear')
    init = sinker_no_drag[0]
    print(f"spin = ( {init[7]:.3f}, {init[8]:.3f}, {init[9]:.3f} )\n")
    time_step = DEFAULT_TIME_STEP.to_base_units().magnitude
    interval = round(0.05 / time_step)
    print(f" time |    velo without drag    | velo with only gravity  |")
    print(f"______|_________________________|_________________________|")
    for i in range(sinker_no_drag.size):
        if i % interval == 0:
            s1 = sinker_no_drag[i]
            s2 = sinker_only_grav[i]
            print(f" {i*time_step:.2f} |", end="")
            print(f" ( {s1[4]:.2f}, {s1[5]:.2f}, {s1[6]:.2f} ) |", end="")
            print(f" ( {s2[4]:.2f}, {s2[5]:.2f}, {s2[6]:.2f} ) |")

            if s1[2] < 0 or s2[2] <0:
                break

if __name__ == '__main__':
    main()