# Back-Computing $\vec{V_0}$ at $t=0$ from Statcast Data

## Coordinates

In this document, unless otherwise noted, we use the *world frame*, which follows Statcast convention for the coordinate system:

* Origin at home plate (the back point).
* `+x` points to the right side of the catcher/ump (= left side of the pitcher).
* `+y` towards pitcher (i.e., pitcher throws towards `-y`).
* `+z` points to the sky.

## The Problem

The pitcher's rubber is 60' 6" in away from the origin, and 10 inches high. Because of the pitcher's extension (stride + arm lean), the `y` component of the release position typically ranges 53 ~ 55 feet. However, Statcast begins to track the velocity vector of the ball (as opposed to release speed, which is typically what we mean by "velocity" in baseball) at `y` = 50 ft, and thus we lose 3 ~ 5 feet of data.

The configuration could simply use Statcast's 50-feet velocity vector as the initial velocity at release point. This requires an assumption that this is a reasonable approximation. Below, we test this assumption and look for alternatives.

## Kinematics 

The following test uses a real pitch tracked by Statcast: a changeup thrown by Landen Roupp, on 2026-04-26 (pitch count # 100). First, we load the config into the simulator and check the pseudo-initial velocity and spin vectors (which would've been recorded at the earliest Statcast tracking point). They are:

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

With $A = \frac{1}{2}a_y \approx 3.9255$, $B = -v_{f,y} \approx 38.4866$, $C = s_y = -1.2649$, the quadratic formula gives two roots; we take the positive one:

$$t = \frac{-B + \sqrt{B^2 - 4AC}}{2A} \approx \frac{-38.487 + \sqrt{1501.08}}{7.851} \approx 0.03276 \text{ s} \approx 32.8 \text{ ms}$$

Over this interval, the change in velocity is $\Delta\vec{v} = \vec{a}\,t$:

| Component | $\Delta v$ (m/s) |
| --------- | --------------- |
| $x$       | $-0.151$        |
| $y$       | $+0.257$        |
| $z$       | $-0.287$        |
| **magnitude** | **0.414**   |

The pseudo-initial speed was $|\vec{v_0}| \approx 38.53$ m/s, so the velocity change over the untracked 4.15 ft is roughly 1.1%. This seems like a small number, but we need to know how much this error *compounds* throughout the whole flight of the baseball.

## Computing the Compound Error

We prepare two config files that are otherwise identical, but one uses the pseudo-initial velocity and the other uses a back-computed initial velocity, from the $\Delta v$ calculated above. (Again, this assumes that the acceleration stays relatively constant during the first 100 ms or so of the pitch.) You can find the config files in `init-v-tests\`. 

Now, we run simulations with those two configs. At the end of the simulations, we take their `x` and `z` positions when they cross the strike zone, and calculate the error. `test_compound_error.py` was prepared for this purpose. The terminal output is as follows:

```
Adjusted trajectory crossed plate at    (x, z) = (-8.4171, 9.5696) inches
Pseudo trajectory crossed plate at      (x, z) = (-6.0540, 14.4960) inches

The difference is (2.3631, 4.9264) inches
```

That's pretty significant. It's enough to make a strike call a ball, or vice versa.

## Conclusion

The simulation should back-compute the initial velocity from the Statcast tracking's `y` = 50 ft velocity...

But there's another issue. While the 3D velocity vector is logged at `y` = 50 ft, the *speed* of the ball (commonly referred to simply as "velocity") is reported out-of-hand, that is, at the release point. Hence, it seems that the most robust way to back-compute the initial velocity vector is as follows.

First, we use the raw Statcast `vx0`, `vy0`, and `vz0`, without any meddling such as unit conversions or normalizations, to compute the projected velocity vector at the release point (as described above). Let's call this `init_v_proj`, a three-dimensional vector. Then, we use this vector to calculate the unit vector of the true initial velocity. We use the `release_speed` key from Statcast tracking to override the magnitude. 
