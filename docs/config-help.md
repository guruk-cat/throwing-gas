# Configuration Reference

A config file is a YAML document with up to two top-level blocks: `launch` (required) and `simulation` (optional). All physical quantities are strings parsed by `pint` — units can be in any compatible form (e.g. `"97 mph"`, `"43.3 m/s"`).

## `launch`

Configures the initial state of the ball.

### Arm geometry

`handedness` and `arm_slot` are required. `arm_extension` and `arm_length` are optional with sensible defaults.

All four keys feed into `arm_dir`, which is used everywhere: back-computing shoulder from a Statcast release point, estimating the release point from pitcher geometry, and building the pitch frame for spin axis transformation.

| Key | Type | Default | Description |
|---|---|---|---|
| `handedness` | string | `right` | `right` or `left` |
| `arm_slot` | quantity (angle) | `45 degree` | Angle of the arm above horizontal at release. `0` is sidearm, `90` is straight overhead. |
| `arm_extension` | quantity (length) | derived | Forward lean of the arm toward the plate at release. If omitted, estimated as `0.082 * height` (~15 cm for a 182 cm pitcher). |
| `arm_length` | quantity (length) | derived | Explicit arm length. If omitted, estimated as `0.37 * height`. Only needed to override the estimate. |

### Position

`position.height` is always required — it is used to derive `arm_length` (unless overridden explicitly), which is needed to back-compute the shoulder position regardless of how the release point is provided.

`position.release_pos` is optional. If given, it is used directly as the release point and the shoulder is back-computed from it. If omitted, the release point is estimated from `height`, `rubber`, and `arm_slot`.

```yaml
position:
  height: "6 ft 2 in"                          # required
  release_pos: ["1.5 ft", "55 ft", "6.2 ft"]   # optional; world-frame [x, y, z]
  rubber: ["0 m", "18.44 m"]                    # optional; [x, y]; only used when release_pos is absent
```

`rubber` defaults to `[0 m, 18.44 m]` (centre of rubber, 60.5 ft from home plate) if omitted.

### Velocity

`speed` controls the magnitude. `velocity` controls the direction. Both are required unless `velocity.vector` is provided without `speed`, in which case the magnitude is taken from the vector norm.

| Key | Type | Description |
|---|---|---|
| `speed` | quantity (speed) | Ball speed at release. Overrides the magnitude of `velocity.vector` if both are present. |

Provide exactly one of these two options under `velocity`:

**Option A (direct velocity vector):**

```yaml
velocity:
  vector: ["-1 m/s", "-43 m/s", "1.5 m/s"]   # world-frame [vx, vy, vz]
```

**Option B (aim initial velo at a world-frame point):**

```yaml
velocity:
  target: ["0.3 m", "0 m", "1.7 m"]   # world-frame [x, y, z]
```

### Spin

| Key | Type | Default | Description |
|---|---|---|---|
| `spin` | quantity (angular velocity) | `0 rpm` | Spin rate magnitude. |
| `spin_axis` | list of 3 numbers | `[1, 0, 0]` | Unit vector in **pitch-frame** coordinates. See [pitch-frame.md](pitch-frame.md) for axis conventions. |
| `clock_angle` | quantity (angle) | `0 degree` | Rotates `spin_axis` around `y_pitch` before transforming to world frame. Positive = counterclockwise from pitcher's perspective. |

Common `spin_axis` values (pitch frame, righty pitcher):

| Value | Shape |
|---|---|
| `[-1, 0, 0]` | Pure backspin (four-seam fastball) |
| `[1, 0, 0]` | Pure topspin |
| `[0, 0, -1]` | Arm-side sidespin (sinker/two-seam) |
| `[0, 0, 1]` | Glove-side sidespin (cut fastball) |

## `simulation`

All keys are optional. Omitted keys keep their defaults.

| Key | Default | Description |
|---|---|---|
| `drag_coefficient` | `0.000788 kg/m` | Coefficient in the drag force term `F_d = -C_d * speed * v`. |
| `magnus_coefficient` | `2.2075e-06 kg·s/m` | Coefficient in the Magnus force term. |
| `magnus_model` | `squared velocity` | Force model. `squared velocity`: Magnus force scales with `speed * (ω × v)`. `linear velocity`: scales with `(ω × v)` only. |
| `ball_mass` | `145 g` | |
| `ball_diameter` | `3 in` | Not currently used in force calculations; reserved. |
| `gravitational_acceleration` | `9.8 m/s²` | |
| `time_step` | `1 ms` | Initial RK4 integration step size. |
| `time_step_growth_rate` | `1` (dimensionless) | Multiplicative factor applied to `time_step` after each step. Values > 1 coarsen the step over time. |
| `error_tolerance` | `1 percent` | Relative error threshold for adaptive step size. If the error between a full step and two half-steps exceeds this, the step is halved. |
| `auto_converge_time_step` | `true` | Whether to apply adaptive step-size halving at all. |
| `wind_speed` | `0 mph` | Not yet implemented in force calculations; reserved. |
| `wind_direction` | `0 degree` | Not yet implemented; reserved. |

## Full example

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
