# Configuration Reference

A config file is a YAML document with up to four top-level blocks: `launch` (required), `scene` (optional), `simulation` (optional), and `training` (optional). All physical quantities are strings parsed by `pint` — units can be in any compatible form (e.g. `"97 mph"`, `"43.3 m/s"`).

## 1. `launch`

Configures the initial state of the ball.

### 1.1. Arm geometry

`handedness` and `arm_slot` are required. `arm_extension` and `arm_length` are optional with sensible defaults.

All four keys feed into `arm_dir`, which is used everywhere: back-computing shoulder from a Statcast release point, estimating the release point from pitcher geometry, and building the pitch frame for spin axis transformation.

| Key | Type | Default | Description |
|---|---|---|---|
| `handedness` | string | `right` | `right` or `left` |
| `arm_slot` | quantity (angle) | `45 degree` | Angle of the arm above horizontal at release. `0` is sidearm, `90` is straight overhead. |
| `arm_extension` | quantity (length) | derived | Forward lean of the arm from shoulder toward the plate at release. If omitted, estimated as `0.082 * height` (~15 cm for a 182 cm pitcher). |
| `arm_length` | quantity (length) | derived | Explicit arm length. If omitted, estimated as `0.37 * height`. |

### 1.2. Position

`position.height` is the pitcher's height, and is always required — it is used to derive `arm_length` (unless overridden explicitly), which is needed to back-compute the shoulder position regardless of how the release point is provided.

`position.release_pos` is optional. If given, it is used directly as the release point and the shoulder is back-computed from it. If omitted, the release point is estimated from `height`, `rubber`, and `arm_slot`.

```yaml
position:
  height: "6 ft 2 in"                          # required
  release_pos: ["1.5 ft", "55 ft", "6.2 ft"]   # optional; world-frame [x, y, z]
  rubber: ["0 m", "18.44 m"]                    # optional; [x, y]; only used when release_pos is absent
```

`rubber` defaults to `[0 m, 18.44 m]` if omitted.

### 1.3. Velocity

`speed` controls the magnitude. `velocity` controls the direction. Both are required unless `velocity.vector` is provided without `speed`, in which case the magnitude is taken from the vector norm.

| Key | Type | Description |
|---|---|---|
| `speed` | quantity (speed) | Ball speed at release. Overrides the magnitude of `velocity.vector` if both are present. |

Provide exactly one of these two options under `velocity`:

#### Option A (direct velocity vector)

```yaml
velocity:
  vector: ["-1 m/s", "-43 m/s", "1.5 m/s"]   # world-frame [vx, vy, vz]
```

Add `statcast: true` when the vector comes from Statcast `vx0/vy0/vz0` (recorded at y=50 ft, not at the release point). `Configuration.velo_correction()` will back-compute the true release velocity over the untracked gap before applying it.

```yaml
velocity:
  vector: ["-3.45 ft/s", "-141.2 ft/s", "-2.1 ft/s"]
  statcast: true
```

`statcast_to_config.py` sets this flag automatically. Manual configs that use a directly-measured release velocity should leave it out (or set it to `false`).

#### Option B (aim initial velo at a world-frame point)

```yaml
velocity:
  target: ["0.3 m", "0 m", "1.7 m"]   # world-frame [x, y, z]
```

### 1.4. Spin

| Key | Type | Default | Description |
|---|---|---|---|
| `spin` | quantity (angular velocity) | `0 rpm` | Spin rate magnitude. |
| `spin_axis` | list of 3 numbers | `[1, 0, 0]` | Unit vector in **pitch-frame** coordinates. See [pitch-frame.md](pitch-frame.md) for axis conventions. |
| `clock_angle` | quantity (angle) | `0 degree` | Rotates `spin_axis` around `y_pitch` before transforming to world frame. Positive = clockwise from catcher's perspective (counter-clockwise from pitcher's perspective). |

Common `spin_axis` values (pitch frame, righty pitcher):

| Value | Shape |
|---|---|
| `[-1, 0, 0]` | Pure backspin (four-seam fastball) |
| `[1, 0, 0]` | Pure topspin |
| `[0, 0, -1]` | Arm-side sidespin (sinker/two-seam) |
| `[0, 0, 1]` | Glove-side sidespin (cut fastball) |

## 2. `scene`

Optional block describing the environmental conditions at the ballpark. Written by `statcast_to_config.py` / `command.py` when weather lookup is enabled; inferred from the home team (ballpark coordinates) and first-pitch time, with conditions fetched from the [Open-Meteo](https://open-meteo.com/) historical archive.

| Key | Type | Description |
|---|---|---|
| `temperature` | quantity (temperature) | Air temperature at first pitch. Open-Meteo reports °C (e.g. `"13.3 degC"`). |
| `pressure` | quantity (pressure) | Surface pressure at first pitch, in hPa (e.g. `"1011.0 hPa"`). Already reflects ballpark altitude. |
| `humidity` | quantity | Relative humidity at first pitch, as a percentage (e.g. `"77 percent"`). |

## 3. `simulation`

All keys are optional. Omitted keys keep their defaults.

| Key | Default | Description |
|---|---|---|
| `drag_coefficient` | `0.000788 kg/m` | Coefficient in the drag force term `F_d = -C_d * speed * v`. |
| `magnus_coefficient` | `2.2075e-06 kg·s/m` | Coefficient in the Magnus force term. |
| `magnus_model` | `squared velocity` | Force model. `squared velocity`: Magnus force scales with `speed * (ω × v)`. `linear velocity`: scales with `(ω × v)` only. |
| `ball_mass` | `145 g` | |
| `ball_diameter` | `3 in` | Not currently used in force calculations; reserved. |
| `gravitational_acceleration` | `9.8 m/s²` | |
| `time_step` | `0.5 ms` | Initial RK4 integration step size. The simulation actually uses `time_step / 2` and completes two iterations of compute per time step, due to adaptive stepping. |
| `time_step_growth_rate` | `1` (dimensionless) | Multiplicative factor applied to `time_step` after each step. Values > 1 coarsen the step over time. |
| `error_tolerance` | `1 percent` | Relative error threshold for adaptive step size. If the error between a full step and two half-steps exceeds this, the step is halved. |
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

## 4. Full example

```yaml
launch:
  handedness:    right
  arm_slot:      "52 degree"
  arm_extension: "6 in"

  position:
    height: "6 ft 2 in"
    rubber: ["0 m", "18.44 m"]

  speed:       "97 mph"
  spin:        "2100 rpm"
  spin_axis:   [0, 0, -1]
  clock_angle: "0 degree"

  velocity:
    target: ["0.3 m", "0 m", "1.7 m"]

simulation:
  time_step:       "0.5 ms"
  error_tolerance: "0.5 percent"
```
