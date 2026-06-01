#!/usr/bin/env python3
"""
Fetch a specific pitch from Statcast (via pybaseball) and emit a YAML config
file for the pitch simulator.

USAGE
List pitches for a pitcher on a given date so you can pick one:
    python src/statcast_to_config.py "Yoshinobu Yamamoto" 2026-05-18

Export pitch #89 to stdout:
    python src/statcast_to_config.py "Yoshinobu Yamamoto" 2026-05-18 89

Export pitch #89 to a file:
    python src/statcast_to_config.py "Yoshinobu Yamamoto" 2026-05-18 89 -o yoshi.yaml

OPTIONS
--height STR
    Pitcher height. Defaults to "6 ft 2 in" with a warning if omitted.
    Statcast does not track this; look it up on Baseball Savant or elsewhere.
    Use units. The config setup uses pint to automatically convert and strip units.

--arm-slot DEGREES
    Required if Statcast did not record arm_angle for this pitch (common for older data).
    Arm slot in degrees (0 = sidearm, 90 = straight overhead).
    Overrides Statcast arm_angle.

-o / --output PATH
    Write YAML to this file. Defaults to stdout.

--no-verify-ssl
    Disable SSL certificate verification for all outbound requests.
    Use this if you are behind a corporate proxy with a self-signed certificate
    and see SSL errors when connecting to baseballsavant.mlb.com.
    TEMPORARY: remove this flag (and _disable_ssl_verification below) once the
    SSL situation is resolved.
"""

import argparse
import math
import pathlib
import sys

import pandas as pd
import requests
import urllib3
import yaml

try:
    from pybaseball import statcast_pitcher, playerid_lookup
    import pybaseball.cache as pb_cache
    pb_cache.enable()
except ImportError:
    sys.exit("pybaseball is not installed. Run: pip install pybaseball")


# TEMPORARY: remove this function (and its call in main) once SSL is resolved.
# See --no-verify-ssl in the argparser.
def _disable_ssl_verification():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _orig = requests.Session.request
    def _patched(self, method, url, **kwargs):
        kwargs.setdefault('verify', False)
        return _orig(self, method, url, **kwargs)
    requests.Session.request = _patched
    print("Warning: SSL verification disabled (--no-verify-ssl).", file=sys.stderr)


_DEFAULT_HEIGHT = "6 ft 2 in"

_LIST_COLS = [
    'pitch_type', 'release_speed', 'release_spin_rate', 
    'spin_axis', 'arm_angle', 'description',
    'balls', 'strikes'
]

_DISPLAY_NAMES = {
    'pitch_type':        'pitch type',
    'release_speed':     'speed',
    'release_spin_rate': 'spin rate',
    'spin_axis':         'spin axis',
    'arm_angle':         'arm angle',
}


def _lookup_mlbam(full_name):
    parts = full_name.strip().split()
    if len(parts) < 2:
        raise ValueError(f"Provide a full name (first + last), got: {full_name!r}")
    first, last = parts[0], " ".join(parts[1:])
    results = playerid_lookup(last, first)
    if results is None or results.empty:
        raise ValueError(f"No player found for {full_name!r}.")
    if len(results) > 1:
        results = results.sort_values('mlb_played_last', ascending=False)
    return int(results.iloc[0]['key_mlbam'])


def _clock_angle_from_statcast(spin_axis_deg, arm_slot, handedness_num):
    '''
    Convert Statcast spin_axis to simulator clock_angle.

    Statcast: counter-clockwise from catcher's view, 0° = +X (topspin).
    handedness_num: 1 for righty, -1 for lefty

    Approximation: pitch frame ≈ world frame for X-Z components.
    The pitcher's lateral release offset (~0.5 m) is small relative to the
    ~16 m mound-to-plate distance, so the pitch frame's X-Z plane is 
    nearly aligned with the world frame.
    '''
    return 180.0 - spin_axis_deg - handedness_num * (arm_slot - 90.0)


def _require(row, col, label):
    val = row.get(col) if hasattr(row, 'get') else (row[col] if col in row.index else None)
    if val is None or (isinstance(val, float) and math.isnan(val)):
        raise ValueError(f"Statcast row is missing '{col}' ({label}).")
    return val


def _build_config(row, height, arm_slot_override):
    handedness = 'right' if row['p_throws'] == 'R' else 'left'
    handedness_num = 1 if row['p_throws'] == 'R' else -1
    arm_slot_float = 0.0

    # Arm slot
    if arm_slot_override is not None:
        arm_slot_str = f"{arm_slot_override} degree"
        arm_slot_float = arm_slot_override
    else:
        arm_angle = row['arm_angle'] if 'arm_angle' in row.index else None
        if arm_angle is not None and pd.notna(arm_angle):
            arm_slot_float = float(arm_angle)
            arm_slot_str = f"{arm_slot_float} degree"
        else:
            raise ValueError(
                "Statcast did not record arm_angle for this pitch (common for older data).\n"
                "Re-run with --arm-slot DEGREES "
                "(look it up on Baseball Savant's pitcher leaderboard)."
            )

    # Release position (Statcast XYZ matches the simulator's world frame; values in feet)
    rx = float(_require(row, 'release_pos_x', 'release position x'))
    ry = float(_require(row, 'release_pos_y', 'release position y'))
    rz = float(_require(row, 'release_pos_z', 'release position z'))

    # Speed
    speed = float(_require(row, 'release_speed', 'release speed'))

    # Spin rate
    spin = float(_require(row, 'release_spin_rate', 'spin rate'))

    # Spin axis → clock_angle
    statcast_axis = float(_require(row, 'spin_axis', 'spin axis'))
    clock_angle = _clock_angle_from_statcast(statcast_axis, arm_slot_float, handedness_num)

    '''
    Velocity direction from Statcast's vx0/vy0/vz0 
    (ft/s at the y=50ft tracking-start position, ~5 ft closer to the plate than release). 
    Direction is a small approximation.
    Magnitude is overridden by release_speed so the speed at release is exact.
    '''
    vx = float(_require(row, 'vx0', 'velocity x'))
    vy = float(_require(row, 'vy0', 'velocity y'))
    vz = float(_require(row, 'vz0', 'velocity z'))

    return {
        'launch': {
            'handedness': handedness,
            'arm_slot': arm_slot_str,
            'position': {
                'height': height,
                'release_pos': [f"{rx} ft", f"{ry} ft", f"{rz} ft"],
            },
            'speed': f"{speed} mph",
            'spin': f"{spin} rpm",
            # spin_axis is the pure-backspin reference in pitch frame.
            # clock_angle rotates it to match the Statcast spin direction.
            'spin_axis': [-1, 0, 0],
            'clock_angle': f"{clock_angle:.4f} degree",
            'velocity': {
                'vector': [f"{vx} ft/s", f"{vy} ft/s", f"{vz} ft/s"],
            },
        }
    }


def fetch_pitches(pitcher_name, date, no_verify_ssl=False):
    # Fetch all pitches for a pitcher on a date. 
    # Returns a chronological DataFrame.
    if no_verify_ssl:
        _disable_ssl_verification()
    mlbam_id = _lookup_mlbam(pitcher_name)
    print(f"Fetching Statcast data for {pitcher_name} on {date}...", file=sys.stderr)
    df = statcast_pitcher(date, date, player_id=mlbam_id)
    if df is None or df.empty:
        raise ValueError(f"No pitch data found for {pitcher_name} on {date}.")
    return df.iloc[::-1].reset_index(drop=True)

def pitch_to_config(row, height, arm_slot_override=None):
    # public function that does the same thing
    # different name to avoid confusion outside of this file
    return _build_config(row, height, arm_slot_override)

def print_pitch_list(df, pitcher):
    cols = [c for c in _LIST_COLS if c in df.columns]
    summary = df[cols].rename(columns=_DISPLAY_NAMES)
    summary.index = range(1, len(summary) + 1)
    summary.index.name = '#'
    print(f"\n{len(df)} pitches found for {pitcher}:\n")
    lines = summary.to_string().splitlines()
    print(lines[0])  # header
    print(lines[1])
    at_bat = 'balls' in df.columns and 'strikes' in df.columns
    for i, line in enumerate(lines[2:]):
        if i > 0 and at_bat and df.iloc[i]['balls'] == 0 and df.iloc[i]['strikes'] == 0:
            print() # insert empty line for new at-bat
        print(line)
    
    print(f"\n****** end of list ******")


def main():
    parser = argparse.ArgumentParser(
        description='Generate a simulator YAML config from a Statcast pitch.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('pitcher', help='Pitcher full name (e.g. "Clayton Kershaw")')
    parser.add_argument('date', help='Game date (YYYY-MM-DD)')
    parser.add_argument('pitch_number', nargs='?', type=int,
                        help='Pitch to export (# from the list, 1-based). Omit to list pitches.')
    parser.add_argument('--height', default=None,
                        help=f'Pitcher height (e.g. "6 ft 2 in"). Defaults to {_DEFAULT_HEIGHT!r}.')
    parser.add_argument('--arm-slot', dest='arm_slot', type=float, default=None,
                        help='Arm slot in degrees (0=sidearm, 90=overhead). '
                             'Overrides Statcast arm_angle.')
    parser.add_argument('--output', '-o', default=None,
                        help='Output YAML file path. Defaults to stdout.')
    # TEMPORARY: remove this argument (and the _disable_ssl_verification call below)
    # once the SSL situation is resolved.
    parser.add_argument('--no-verify-ssl', dest='no_verify_ssl', action='store_true',
                        help='Disable SSL certificate verification (corporate proxy workaround).')
    args = parser.parse_args()

    try:
        df = fetch_pitches(args.pitcher, args.date, no_verify_ssl=args.no_verify_ssl)
    except ValueError as e:
        sys.exit(str(e))

    if args.pitch_number is None:
        print_pitch_list(df, args.pitcher)
        print("Re-run with a pitch number (# column, 1-based) to generate a config.")
        return

    idx = args.pitch_number - 1
    if idx < 0 or idx >= len(df):
        sys.exit(f"Pitch #{args.pitch_number} is out of range (1–{len(df)}).")

    row = df.iloc[idx]

    if args.height is None:
        print(f"Warning: --height not provided, defaulting to {_DEFAULT_HEIGHT!r}.", file=sys.stderr)
        height = _DEFAULT_HEIGHT
    else:
        height = args.height

    try:
        config = pitch_to_config(row, height, args.arm_slot)
    except ValueError as e:
        sys.exit(str(e))

    yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)

    if args.output:
        out_path = pathlib.Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml_str)
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        print(yaml_str)


if __name__ == '__main__':
    main()
