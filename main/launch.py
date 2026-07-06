import argparse
import glob
import numpy
import pathlib
import sys
import yaml
import pint

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from phys import Simulation, Configuration, magnus_acc
from plotting import Trajectory3DPlot

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity  # type: ignore[misc]
pint.set_application_registry(ureg)

def si_mag(quantity):
    return quantity.to_base_units().magnitude

# middle of plate; Statcast 2026+
PLATE_Y = Q_(8.5, "inch")

def terminate(record):
    state = record[-1]
    if state[3] < 0:
        return True
    if state[2] < -1:  
        return True
    if state[0] > 5:    # safety valve  
        return True
    return False

def crossing_point(traj):
    y = traj[:, 2]
    i = numpy.argmin(numpy.abs(y - si_mag(PLATE_Y)))
    return i

def main():
    parser = argparse.ArgumentParser(description='Baseball pitch simulator')
    parser.add_argument('configs', nargs='+', help='Path(s) to YAML launch configuration file(s); glob patterns are supported')
    parser.add_argument('--plot', '-p', nargs='?', const='animated', choices=['static', 'animated'], help='Display 3D trajectory plot')
    args = parser.parse_args()

    # Expand any glob patterns (handles shells that don't expand them, e.g. Windows cmd)
    config_paths = []
    for pattern in args.configs:
        matched = sorted(glob.glob(pattern))
        config_paths.extend(matched if matched else [pattern])

    trajectories = []
    for config_path in config_paths:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        sim = Simulation()

        launch = Configuration()
        launch.configure(cfg)

        trajectory = sim.run(launch, terminate)
        # Annotate each point with its Magnus acceleration (derived, not recorded).
        c = launch.constants()
        trajectory = [numpy.append(state, magnus_acc(state, c)) for state in trajectory]
        trajectories.append(trajectory)

        name = pathlib.Path(config_path).name
        plate_i = crossing_point(numpy.array(trajectory))
        print(f"[{name}] {len(trajectory)} steps")
        print(f"t when crossing plate   = {trajectory[plate_i][0]:.3f}s")
        print(f"pos when crossing plate =({trajectory[plate_i][1]:.2f}, {trajectory[plate_i][2]:.2f}, {trajectory[plate_i][3]:.2f}) m\n")

    if args.plot:
        labels = [pathlib.Path(p).stem for p in config_paths]
        plotter = Trajectory3DPlot()
        plotter.plot(trajectories, labels=labels, animate=(args.plot == 'animated'), show_magnus=True)


if __name__ == '__main__':
    main()