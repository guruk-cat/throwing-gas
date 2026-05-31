import argparse
import glob
import pathlib
import sys
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from phys import Simulation, Configuration
from plotting import Trajectory3DPlot

def terminate(record):
    state = record[-1]
    if state[3] < 0:    # z < 0: ball hit the ground
        return True
    if state[2] < -1:   # y < -1: ball is at catcher position
        return True
    if state[0] > 10:   # t > 10s: safety valve
        return True
    return False

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

        if 'simulation' in cfg:
            sim.configure(cfg['simulation'])
        launch.configure(cfg['launch'])

        trajectory = sim.run(launch, terminate)
        trajectories.append(trajectory)

        name = pathlib.Path(config_path).name
        print(f"[{name}] {len(trajectory)} steps, "
              f"final t={trajectory[-1][0]:.3f}s, "
              f"final pos=({trajectory[-1][1]:.2f}, {trajectory[-1][2]:.2f}, {trajectory[-1][3]:.2f}) m")

    if args.plot:
        labels = [pathlib.Path(p).stem for p in config_paths]
        plotter = Trajectory3DPlot()
        plotter.plot(trajectories, labels=labels, animate=(args.plot == 'animated'))


if __name__ == '__main__':
    main()