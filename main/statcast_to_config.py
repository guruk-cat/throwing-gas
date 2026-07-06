#!/usr/bin/env python3

# Functions used by other scripts to fetch Statcast data via `pybaseball`

import datetime as dt
import functools
import io
import math
import re
import sys
import pandas as pd
import requests

try:
    from pybaseball import statcast_pitcher, playerid_lookup
    import pybaseball.cache as pb_cache
    pb_cache.enable()
except ImportError:
    sys.exit("pybaseball is not installed. Run: pip install pybaseball")

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
    if full_name.strip().isdigit():
        return int(full_name.strip())
    parts = full_name.strip().split()
    if len(parts) < 2:
        raise ValueError(f"Provide a full name (first + last) or a numeric MLBAM ID, got: {full_name!r}")
    first, last = parts[0], " ".join(parts[1:])
    results = playerid_lookup(last, first)
    if results is None or results.empty:
        raise ValueError(
            f"No player found for {full_name!r}.\n"
            "If the player is missing from the Chadwick register, pass their MLBAM ID directly\n"
            "(find it on Baseball Savant) instead of a name."
        )
    if len(results) > 1:
        results = results.sort_values('mlb_played_last', ascending=False)
    return int(results.iloc[0]['key_mlbam'])


def _require(row, col, label):
    val = row.get(col) if hasattr(row, 'get') else (row[col] if col in row.index else None)
    if val is None or (isinstance(val, float) and math.isnan(val)):
        raise ValueError(f"Statcast row is missing '{col}' ({label}).")
    return val


def _build_training(row):
    ax = float(_require(row, 'ax', 'acceleration x'))
    ay = float(_require(row, 'ay', 'acceleration y'))
    az = float(_require(row, 'az', 'acceleration z'))
    plate_x = float(_require(row, 'plate_x', 'position x at plate'))
    plate_z = float(_require(row, 'plate_z', 'position z at plate'))
    return {
        'ax': f"{ax:.6f} ft/s**2",
        'ay': f"{ay:.6f} ft/s**2",
        'az': f"{az:.6f} ft/s**2",
        'plate_x': f"{plate_x:.6f} ft",
        'plate_z': f"{plate_z:.6f} ft",
    }


def _build_metadata(row):
    # Identifying info for debugging a config. pitch_count is the pitch's position
    # in the game for this pitcher: fetch_pitches() returns a chronological,
    # reset-indexed df, so row.name (0-based) + 1 is that count.
    name = str(row.get('player_name', '')).strip()
    if ',' in name:                       # Statcast gives "Last, First"
        last, first = (p.strip() for p in name.split(',', 1))
        name = f"{first} {last}"
    return {
        'pitch_type': str(row.get('pitch_type', 'UNK')),
        'pitcher':    name,
        'game_date':  str(row.get('game_date', ''))[:10],
        'pitch_count': int(row.name) + 1,
    }


_STATS_API = "https://statsapi.mlb.com/api/v1"
_ARCHIVE_METEO_API = "https://archive-api.open-meteo.com/v1/archive"
_ACTIVE_SPIN_API = "https://baseballsavant.mlb.com/leaderboard/active-spin"

# Statcast pitch-type code -> active-spin leaderboard column suffix.
# Codes absent here (or below the leaderboard threshold) have no active-spin value.
_ACTIVE_SPIN_COL = { 
    'FF': 'fourseam', 'SI': 'sinker', 'FC': 'cutter', 'CH': 'changeup', 
    'FS': 'splitter', 'CU': 'curve', 'KC': 'curve', 'SL': 'slider', 
    'ST': 'sweeper', 'SV': 'slurve' 
}


@functools.lru_cache(maxsize=None)
def _fetch_active_spin_table(year):
    # Seasonal active-spin leaderboard, indexed by pitcher MLBAM id (entity_id).
    r = requests.get(_ACTIVE_SPIN_API, params={'year': year, 'csv': 'true'}, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text)).set_index('entity_id')


def _active_spin_in(pitcher_id, col, year):
    table = _fetch_active_spin_table(year)
    if pitcher_id not in table.index:
        return None
    val = table.loc[pitcher_id, f'active_spin_{col}']
    return None if pd.isna(val) else float(val)


def _lookup_active_spin(pitcher_id, pitch_type, year):
    # Active spin for a pitcher's pitch type in a season, or None on any miss.
    # The current season may be only partly filled, so fall back to the prior year on a miss.
    col = _ACTIVE_SPIN_COL.get(pitch_type)
    if col is None:
        return None
    hit = _active_spin_in(pitcher_id, col, year)
    if hit is None and int(year) == dt.date.today().year:
        hit = _active_spin_in(pitcher_id, col, str(int(year) - 1))
    return hit

'''
Statcast home_team abbreviation -> (latitude, longitude) of the home ballpark.

This assumes the home team plays in its own park. 
It is wrong for neutral-site games (London, Tokyo, Mexico City, Field of Dreams) 
and for temporary relocations (2025 Athletics in West Sacramento, 2025 Rays at Steinbrenner Field). 
The game_pk schedule response carries the true venue if precise handling is ever needed.
'''
_TEAM_LATLON = {
    'AZ':  (33.4455, -112.0667), 'ATL': (33.8907, -84.4677),
    'BAL': (39.2839, -76.6217),  'BOS': (42.3467, -71.0972),
    'CHC': (41.9484, -87.6553),  'CWS': (41.8299, -87.6338),
    'CIN': (39.0975, -84.5069),  'CLE': (41.4962, -81.6852),
    'COL': (39.7559, -104.9942), 'DET': (42.3390, -83.0485),
    'HOU': (29.7572, -95.3556),  'KC':  (39.0517, -94.4803),
    'LAA': (33.8003, -117.8827), 'LAD': (34.0739, -118.2400),
    'MIA': (25.7781, -80.2197),  'MIL': (43.0280, -87.9712),
    'MIN': (44.9817, -93.2776),  'NYM': (40.7571, -73.8458),
    'NYY': (40.8296, -73.9262),  'OAK': (37.7516, -122.2005),
    'ATH': (38.5802, -121.5130), 'PHI': (39.9061, -75.1665),
    'PIT': (40.4469, -80.0057),  'SD':  (32.7073, -117.1566),
    'SEA': (47.5914, -122.3325), 'SF':  (37.7786, -122.3893),
    'STL': (38.6226, -90.1928),  'TB':  (27.7682, -82.6534),
    'TEX': (32.7473, -97.0832),  'TOR': (43.6414, -79.3894),
    'WSH': (38.8730, -77.0074),
}


def _reshape_height(s):
    # MLB Stats API returns height like  5' 10"  ->  pint-friendly  "5 ft 10 in".
    m = re.match(r"""\s*(\d+)'\s*(\d+)"?\s*$""", s)
    if not m:
        raise ValueError(f"Unexpected height format from Stats API: {s!r}")
    return f"{m.group(1)} ft {m.group(2)} in"


@functools.lru_cache(maxsize=None)
def _game_start_utc(game_pk):
    # First-pitch time (UTC) for a game, from the MLB Stats API schedule.
    r = requests.get(f"{_STATS_API}/schedule", params={'gamePk': game_pk}, timeout=15)
    r.raise_for_status()
    iso = r.json()['dates'][0]['games'][0]['gameDate']   # ISO-8601, e.g. 2026-04-24T22:05:00Z
    return dt.datetime.fromisoformat(iso.replace('Z', '+00:00'))


def _pick_hour(hourly, dt_utc):
    # Open-Meteo hourly times are UTC; select the (floored) first-pitch hour.
    i = hourly['time'].index(dt_utc.strftime('%Y-%m-%dT%H:00'))
    return (hourly['temperature_2m'][i],
            hourly['surface_pressure'][i],
            hourly['relative_humidity_2m'][i])


@functools.lru_cache(maxsize=None)
def _fetch_weather(lat, lon, dt_utc):
    # Hourly archive weather at (lat, lon) for the first-pitch hour.
    # Units: temperature °C, surface_pressure hPa, relative_humidity %. 
    # The date is taken from the UTC timestamp (a night game is the next UTC day).
    date = dt_utc.strftime('%Y-%m-%d')
    r = requests.get(_ARCHIVE_METEO_API, params={
        'latitude': lat, 'longitude': lon,
        'start_date': date, 'end_date': date,
        'hourly': 'temperature_2m,surface_pressure,relative_humidity_2m',
    }, timeout=30)
    r.raise_for_status()
    temp, press, humid = _pick_hour(r.json()['hourly'], dt_utc)
    return {
        'temperature': f"{temp} degC",
        'pressure':    f"{press} hPa",
        'humidity':    f"{humid} percent",
    }


def _build_scene(row):
    # Raw weather conditions at first pitch, inferred from home team + game time.
    # The simulator/configurator reads these (with pint) to compute air density.
    team = row['home_team']
    if team not in _TEAM_LATLON:
        raise ValueError(f"No ballpark coordinates for home team {team!r}.")
    lat, lon = _TEAM_LATLON[team]
    start = _game_start_utc(int(row['game_pk']))
    return _fetch_weather(lat, lon, start)



# PUBLIC FUNCTIONS

def fetch_pitcher_height(mlbam_id):
    # Look up a pitcher's listed height from the MLB Stats API, as a pint string.
    r = requests.get(f"{_STATS_API}/people/{mlbam_id}", timeout=15)
    r.raise_for_status()
    return _reshape_height(r.json()['people'][0]['height'])

def fetch_pitches(pitcher_name, date):
    mlbam_id = _lookup_mlbam(pitcher_name)
    df = statcast_pitcher(date, date, player_id=mlbam_id)
    if df is None or df.empty:
        raise ValueError(f"No pitch data found for {pitcher_name} on {date}.")
    return df.iloc[::-1].reset_index(drop=True)

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

def pitch_to_config(row, height, arm_slot_override=None, include_training=False, include_scene=False, include_metadata=False):
    handedness = 'right' if row['p_throws'] == 'R' else 'left'
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

    speed = float(_require(row, 'release_speed', 'release speed'))

    # Statcast vx0/vy0/vz0 are in ft/s at the y=50ft tracking-start position
    vx = float(_require(row, 'vx0', 'velocity x'))
    vy = float(_require(row, 'vy0', 'velocity y'))
    vz = float(_require(row, 'vz0', 'velocity z'))

    spin_rate = float(_require(row, 'release_spin_rate', 'spin rate'))
    spin_angle = float(_require(row, 'spin_axis', 'spin axis'))

    # Active spin
    pitch_type = str(row.get('pitch_type', ''))
    year = str(_require(row, 'game_date', 'game date'))[:4]
    active_spin = _lookup_active_spin(int(_require(row, 'pitcher', 'pitcher id')), pitch_type, year)
    if active_spin is None:
        print(f"Warning: no active-spin value for pitcher {row.get('player_name', '?')} "
              f"pitch type {pitch_type!r}; simulation will assume 100%.")

    cfg = {
        'format': {'type': 'statcast'},
        'launch': {
            'handedness': handedness,
            'arm_slot': arm_slot_str,
            'position': {
                'height': height,
                'release_pos': [f"{rx} ft", f"{ry} ft", f"{rz} ft"],
            },
            'speed': f"{speed} mph",
            'spin_rate': f"{spin_rate} rpm",
            'spin_angle': f"{spin_angle} degree",
            'velocity': {
                'vector': [f"{vx} ft/s", f"{vy} ft/s", f"{vz} ft/s"],
            },
        }
    }
    if active_spin is not None:
        cfg['launch']['active_spin'] = f"{active_spin} percent"
    if include_scene:
        cfg['launch']['scene'] = _build_scene(row)
    if include_training:
        cfg['training'] = _build_training(row)
    if include_metadata:
        cfg['metadata'] = _build_metadata(row)

    return cfg
