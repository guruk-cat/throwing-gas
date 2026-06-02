import pathlib
import sys
import yaml
import numpy
import pint

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / 'main'))
from phys import Configuration

ureg = pint.UnitRegistry()
pint.set_application_registry(ureg)

def m_to_in(quantity_m):
    return ureg.Quantity(quantity_m, "meter").to("inch").magnitude

def main():
    tests_dir = pathlib.Path(__file__).parent / 'init-v-tests'
    config_paths = [
        tests_dir / 'pseudo.yaml',
        tests_dir / 'adjusted.yaml'
    ]
    names = ['Pseudo', 'Adjusted']

    for i, config_path in enumerate(config_paths):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        config = Configuration()
        config.configure(cfg['launch'])
        velo = numpy.array(config.get_velocity())
        spin = numpy.array(config.get_spin())
        speed = numpy.linalg.norm(velo)

        print(f"\n{names[i]}-initial values")
        print(f"  init speed  : {speed}")
        print(f"  init velo   : [ {velo[0]}, {velo[1]}, {velo[2]} ]")
        print(f"  init spin   : [ {spin[0]}, {spin[1]}, {spin[2]} ]")

if __name__ == '__main__':
    main()