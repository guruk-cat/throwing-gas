# Back-Computing $\vec{V_0}$ at $t=0$ from Statcast Data

## Coordinates

In this document, unless otherwise noted, we use the *world frame*, which follows Statcast conventions for coordinate system:

* Origin at home plate (the back point).
* `+x` points to the right side of the catcher/ump (= left side of the pitcher).
* `+y` towards pitcher (i.e., pitcher throws towards `-y`).
* `+z` points to the sky.

## The Problem

The pitcher's rubber is 60 ft 6 in away from the origin, and 10 inches high. Because of the pitcher's extension (stride + arm lean), the `y` component of the release position typically ranges 53 ~ 55 feet. However, Statcast begins to track the velocity of the ball at `y` = 50 ft, and thus we lose 3 ~ 5 feet of data.

Right now, the configuration simply uses Statcast's 50-feet velocity vector as the initial velocity. This requires an assumption that this is a reasonably approximation. We can use `point_run()` from `Simulation` to test this idea.

## Analytic Testing

The following test uses a real pitch tracked by Statcast: a changeup (#100 in the game) thrown by Landen Roupp, on 2026-04-26. The pseudo-initial velocity and spin vectors, at the earliest Statcast tracking point, are:

```
init velo: [1.7559473536712067, -38.486628117326106, -0.7941129849602245]
init spin: [-39.890919498709984, 16.411640761495466, -187.47176493878413]
```

These are expressed in SI base units. Given a time step of 0.5 ms, the acceleration vector comes out to be:

```
dv_dt: [-4.607394470849271, 7.851070767055077, -8.749286207450119]
```

The release point of this pitch was tracked to be `(1.69, 54.15, 5.1)` in feet. Given that Statcast begins to track the velocity vector at `y` = 50 ft, we are loosing 4.15 ft of information, or 1.2649 meters. Thus, the question becomes: **Is the change in the velocity vector reasonably small during the first 1.2649 meters of travel?**

If we assume that acceleration stays relatively constant during this span of time, we can use kinematics equations to find out. First, we know that the displacement vector $\vec{s}$ is

$$ \vec{s} = \vec{v_0}t + \frac{1}{2}\vec{a}t^2. $$

since $\vec{v_0} = \vec{v_f} - \vec{a}t$, we can say:

$$ \vec{s} = (\vec{v_f} - \vec{a}t) + \frac{1}{2}\vec{a}t^2 $$
$$ \vec{s} = \vec{v_f}t - \frac{1}{2}\vec{a}t^2 $$

and we solve for $t$, assuming that $\vec{s} \approx [ 0, -1.2649, 0 ]$ (negative because the ball travels in $-y$). Taking only the $y$-component and rearranging into standard quadratic form:

$$\tfrac{1}{2}a_y\,t^2 - v_{f,y}\,t + s_y = 0$$

with $A = \frac{1}{2}a_y \approx 3.9255$, $B = -v_{f,y} \approx 38.4866$, $C = s_y = -1.2649$. The quadratic formula gives two roots; we take the positive one:

$$t = \frac{-B + \sqrt{B^2 - 4AC}}{2A} \approx \frac{-38.487 + \sqrt{1501.08}}{7.851} \approx 0.03276 \text{ s} \approx 32.8 \text{ ms}$$

Over this interval, the change in velocity is $\Delta\vec{v} = \vec{a}\,t$:

| Component | $\Delta v$ (m/s) |
|-----------|-----------------|
| $x$       | $-0.151$        |
| $y$       | $+0.257$        |
| $z$       | $-0.287$        |
| **magnitude** | **0.414**   |

The initial speed is $|\vec{v_0}| \approx 38.53$ m/s, so the velocity change over the untracked 4.15 ft is roughly 1.1%. This seems like a small number, but we need to know how much this error *compounds* throughout the whole flight of the baseball.

## Computing the Compound Error
