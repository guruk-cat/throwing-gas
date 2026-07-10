# Configuration Reference

A pitch config file is a YAML document that configures a single pitch. It has up to five top-level blocks: `format` (optional), `launch` (required), `simulation` (optional), `training` (optional), and `metadata` (optional). All physical quantities are strings parsed by `pint`, and units can be in any compatible form (e.g. `"97 mph"`, `"43.3 m/s"`).

A "pitch config" file is different from a "list config" file, which is used for producing batches of multiple pitch configs. See [CLI help](./cli-help.md) for details on the latter.

<!-- toc -->
## Table of Contents
- [1. `format`](#1-format)
- [2. `launch`](#2-launch)
    - [2.1. Arm geometry](#21-arm-geometry)
    - [2.2. Position](#22-position)
    - [2.3. Velocity](#23-velocity)
        - [Option A (direct velocity vector)](#option-a-direct-velocity-vector)
        - [Option B (aim initial velo at a world-frame point)](#option-b-aim-initial-velo-at-a-world-frame-point)
    - [2.4. Spin](#24-spin)
        - [`statcast`](#statcast)
        - [`manual`](#manual)
    - [2.5. Scene](#25-scene)
- [3. `simulation`](#3-simulation)
- [4. `training`](#4-training)
- [5. `metadata`](#5-metadata)
<!-- /toc -->

## 1. `format`

Selects which input grammar the rest of the file uses. 

| Key | Type | Default | Description |
|---|---|---|---|
| `type` | string | `manual` | `statcast` or `manual`. |

`statcast` marks a config generated from Statcast tracking. `velocity.vector` is the y=50 ft tracking velocity, and `Configuration.velo_correction()` back-computes the release velocity over the untracked gap before use. Written automatically by Statcast-related scripts.

`manual` marks a hand-made config. `velocity.vector` or `velocity.target` is taken as-is at the release point, with no correction.

## 2. `launch`

Configures the initial state of the ball.

### 2.1. Arm geometry

`handedness` and `arm_slot` are required. `arm_extension` and `arm_length` are optional with sensible defaults.

All four keys feed into `arm_dir`, which is used everywhere: back-computing shoulder from a Statcast release point, estimating the release point from pitcher geometry, and building the pitch frame for spin axis transformation.

| Key | Type | Default | Description |
|---|---|---|---|
| `handedness` | string | `right` | `right` or `left` |
| `arm_slot` | quantity (angle) | `45 degree` | Angle of the arm above horizontal at release. `0` is sidearm, `90` is straight overhead. |
| `arm_extension` | quantity (length) | derived | Forward lean of the arm from shoulder toward the plate at release. If omitted, estimated as `0.082 * height` (~15 cm for a 182 cm pitcher). |
| `arm_length` | quantity (length) | derived | Explicit arm length. If omitted, estimated as `0.37 * height`. |

### 2.2. Position

`position.height` is the pitcher's height, and is always required — it is used to derive `arm_length` (unless overridden explicitly), which is needed to back-compute the shoulder position regardless of how the release point is provided.

`position.release_pos` is optional. If given, it is used directly as the release point and the shoulder is back-computed from it. If omitted, the release point is estimated from `height`, `rubber`, and `arm_slot`.

```yaml
position:
  height: "6 ft 2 in"                          # required
  release_pos: ["1.5 ft", "55 ft", "6.2 ft"]   # optional; world-frame [x, y, z]
  rubber: ["0 m", "18.44 m"]                   # optional; [x, y]; only used when release_pos is absent
```

`rubber` defaults to `[0 m, 18.44 m]` if omitted.

### 2.3. Velocity

`speed` sets the magnitude and is always required. `velocity` sets the direction only.

Provide exactly one of these two options under `velocity`:

#### Option A (direct velocity vector)

```yaml
velocity:
  vector: ["-1 m/s", "-43 m/s", "1.5 m/s"]   # world-frame [vx, vy, vz]
```

#### Option B (aim initial velo at a world-frame point)

Manual only.

```yaml
velocity:
  target: ["0.3 m", "0 m", "1.7 m"]   # world-frame [x, y, z]
```

### 2.4. Spin

The spin keys depend on `format.type`. `spin_rate` specifies the magnitude (e.g., "2200 rpm") and is shared. The direction is given differently in each grammar.

#### `statcast`

`spin_angle` specifies the world-frame tilt of the spin axis in the x-z plane, measured counter-clockwise from `+x` (catcher's view). `0` is topspin, `180` is backspin. This follows the conventions for Statcast's `spin_axis` column.

`active_spin` is the pitcher's average active spin for each pitch type. Fetched from Savant leaderboard. If not available, `phys` assumes 100%.

#### `manual`

| Key | Type | Description |
|---|---|---|
| `spin_axis` | list of 3 numbers | Unit vector in **pitch-frame** coordinates. See [pitch-frame.md](pitch-frame.md) for axis conventions. |
| `clock_angle` | quantity (angle) | Rotates `spin_axis` around `y_pitch` before transforming to world frame. Positive = clockwise from catcher's perspective (counter-clockwise from pitcher's perspective). |

Both keys are required. Common `spin_axis` values (pitch frame, righty pitcher):

| Value | Shape |
|---|---|
| `[-1, 0, 0]` | Pure backspin (four-seam fastball) |
| `[1, 0, 0]` | Pure topspin |
| `[0, 0, -1]` | Arm-side sidespin (sinker/two-seam) |
| `[0, 0, 1]` | Glove-side sidespin (cut fastball) |

### 2.5. Scene

Optional `scene` sub-block describing the environmental conditions at the ballpark, used to compute air density. Written by `statcast_to_config.py` / `command.py` when weather lookup is enabled; inferred from the home team (ballpark coordinates) and first-pitch time, with conditions fetched from the [Open-Meteo](https://open-meteo.com/) historical archive. If omitted, ISA sea-level conditions (15 °C, 1013.25 hPa, dry) are assumed.

| Key | Type | Description |
|---|---|---|
| `temperature` | quantity (temperature) | Air temperature at first pitch. Open-Meteo reports °C (e.g. `"13.3 degC"`). |
| `pressure` | quantity (pressure) | Surface pressure at first pitch, in hPa (e.g. `"1011.0 hPa"`). Already reflects ballpark altitude. |
| `humidity` | quantity | Relative humidity at first pitch, as a percentage (e.g. `"77 percent"`). |

```yaml
scene:
  temperature: "24.9 degC"
  pressure: "1000.6 hPa"
  humidity: "65 percent"
```

## 3. `simulation`

All keys are optional. Omitted keys keep their defaults. 

| Key | Default | Description |
|---|---|---|
| `drag_coefficient` | See code | Coefficient in the drag force term `F_d = -C_d * speed * v`. |
| `magnus_coefficient` | See code | Coefficient in the Magnus force term. |
| `magnus_model` | `squared velocity` | Force model. `squared velocity`: Magnus force scales with `speed * (ω × v)`. `linear velocity`: scales with `(ω × v)` only. |
| `ball_mass` | `145 g` | |
| `ball_diameter` | `3 in` | Not currently used in force calculations; reserved. |
| `gravitational_acceleration` | `9.8 m/s²` | |
| `time_step` | `0.5 ms` | Initial RK4 integration step size. The simulation actually uses `time_step / 2` and completes two iterations of compute per time step, due to adaptive stepping. |
| `time_step_growth_rate` | `1` (dimensionless) | Multiplicative factor applied to `time_step` after each step. Values > 1 coarsen the step over time. |
| `error_tolerance` | See code | Relative error threshold for adaptive step size. If the error between a full step and two half-steps exceeds this, the step is halved. |
| `auto_converge_time_step` | `true` | Whether to apply adaptive step-size halving at all. |
| `wind_speed` | `0 mph` | Not yet implemented in force calculations; reserved. |
| `wind_direction` | `0 degree` | Not yet implemented; reserved. |

## 4. `training`

Optional block written by `statcast_to_config.py --training` or the `command.py` CLI tool when selecting the appropriate option. Stores the ground-truth plate crossing position from Statcast, used by the optimizer as the target output (s₂) for a pitch.

| Key | Type | Description |
|---|---|---|
| `ax` | quantity (acceleration) | Instantaneous acceleration in x at the y=50ft tracking start position. |
| `ay` | quantity (acceleration) | Instantaneous acceleration in y at the y=50ft tracking start position. |
| `az` | quantity (acceleration) | Instantaneous acceleration in z at the y=50ft tracking start position. |

```yaml
training:
  ax: "-5.123456 ft/s**2"
  ay: "-23.456789 ft/s**2"
  az: "-15.678901 ft/s**2"
```

This block can also contain `plate_x` and `plate_z` from Statcast data. These are the `x` and `z` positions when ball is crossing the strike zone. Whether this is included depends on which kind of error calculation is intended on the sample.

The block is not read by `launch.py` or `Simulation` — ignored outside the optimizer.

## 5. `metadata`

Optional block written by `statcast_to_config.py` / `command.py` to identify where a config came from. 

| Key | Type | Description |
|---|---|---|
| `pitch_type` | string | Two-letter Statcast pitch-type abbreviation (e.g. `FF`, `SL`). |
| `pitcher` | string | Pitcher name, as `First Last`. |
| `game_date` | string | Game date, `YYYY-MM-DD`. |
| `pitch_count` | int | The pitch's position in the game for this pitcher (1-based, chronological). |
