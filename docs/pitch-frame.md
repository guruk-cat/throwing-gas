# Pitch Frame

## About

The pitch frame is a rotational coordinate system whose primary purpose is to allow spin axes to be specified relative to the pitcher's delivery angle, rather than in absolute world coordinates. It is not used for the simulation or plotting — only for interpreting spin axis configuration before the simulation runs.

A separate concern — estimating the release point from pitcher geometry — shares some inputs with the pitch frame (arm slot, handedness) but is conceptually independent. See [Release Point](#release-point) below.

## World frame

The world frame (or world coordinates) follow Statcast conventions:

* Origin at home plate.
* `+x` points to the right side of the catcher/ump (= left side of the pitcher).
* `+y` towards pitcher (i.e., pitcher throws towards `-y`).
* `+z` points to the sky.

## Pitch frame

The pitch frame axes are defined as follows:

* `y` axis: unit vector from home plate toward the release point (`+y` pointing toward the pitcher).
* `x` axis: perpendicular to the plane containing `y_pitch` and the pitcher's arm direction. This is the pure backspin/topspin axis for a given arm slot. (`+x` still points roughly to the catcher/ump's right side; `+x` points to the sky for a righty side-arm pitcher.)
* `z` axis: right-hand completion of `x` and `y`; points roughly upward for non-underhand deliveries.

The pitch frame shares its origin with the world frame, so transforming between them is a pure rotation — no translation involved.

The practical value of this frame is that spin axes have intuitive, arm-slot-independent descriptions:

* `[-1, 0, 0]` — pure backspin (four-seam fastball shape)
* `[1, 0, 0]` — pure topspin
* `[0, 0, -1]` — arm-side sidespin (sinker/two-seam shape for a righty)
* `[0, 0, 1]` — glove-side sidespin

These descriptions remain stable even if the arm slot changes, which makes them useful for "what if" comparisons.

## Release point

The release point defines `y_pitch` and is therefore required to build the pitch frame. It can be provided in two ways:

**Direct (Statcast):** `position.release_pos` supplies world-frame coordinates directly.

**Estimated (hypothetical pitcher):** `position.height` triggers a geometry derivation. The shoulder position is estimated from pitcher height and rubber position; the release point is then computed as `shoulder + arm_length * arm_dir(arm_slot)`.

In both cases, `arm_slot` is always required — it determines `arm_dir`, which defines the pitch frame orientation for spin axis transformation. If the release point is provided directly and you also want to tweak the arm slot, providing `position.height` (or `arm_length` explicitly) allows the shoulder to be back-computed so a new release point can be derived.

## Spin axis and clock angle

`spin_axis` in the config is specified in pitch-frame coordinates. Before being transformed to world coordinates, it can be rotated around `y_pitch` by `clock_angle`, which shifts the axis clockwise or counterclockwise as seen from the pitcher's perspective. The final world-frame spin direction is:

```
spin_dir_world = M @ rot_y(clock_angle) @ spin_axis_pitch
```

where `M` is the pitch-to-world rotation matrix.

## What the pitch frame does not cover

Velocity direction and speed are specified independently of the pitch frame:

* `velocity.target` aims the ball at a world-frame point.
* `velocity.vector` supplies the velocity directly.
* `speed` always controls the magnitude; if `velocity.vector` is provided without `speed`, the magnitude is taken from the vector norm.
