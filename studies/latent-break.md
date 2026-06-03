# Considering Latent Breaking of Certain Pitch Types

## Quick review of basic stuff

### Coordinate system

The world frame (or world coordinates) follow Statcast conventions:

* Origin at home plate (the back point).
* `+x` points to the right side of the catcher/ump (= left side of the pitcher).
* `+y` towards pitcher (i.e., pitcher throws towards `-y`).
* `+z` points to the sky.

### Spin axis

Use the right-hand rule for determining the spin axis. For example, a pure back-spin ball according to world frame thrown by a righty pitcher:

* Top of the ball moves towards the pitcher (`+y`) and bottom of the ball moves towards home plate (`-y`).
* For an observer standing on the pitcher's right side (i.e., standing somewhere in `-x` looking towards `+x`), the ball is rotating counter-clockwise.
* Right hand rule determines that the spin axis points in the `-x` direction. 

### Cross product

The Magnus term is defined as proportional to the cross product of the spin vector and the velocity vector. The Magnus coefficient $\beta$ controls the magnitude of the force:

$$ \vec{F}_{magnus} = m \cdot \beta \cdot \vec{\omega} \times \vec{v}$$

$$ \vec{a} = \beta \cdot \vec{\omega} \times \vec{v}$$

## A pitch "slowing down"

A sinker typically has a sidespin; much of its $\vec{\omega}$ is in the $\pm z$ direction. The cross product $\vec{\omega}\times\vec{v}$ would have a large component in the $\pm x$ direction, and hence that's where the acceleration would point. But a sinker is not a *slider*, and not just because it's a type of fastball (as opposed to an offspeed pitch). Moreover, many pitchers also have some amount of backspin (i.e, spin axis points parallel to the $x$ axis, pointing to their arm side) in their sinkers. You can actually see on Baseball Savant that many sinkers have a vertical break *towards the sky* when gravity is isolated. Then why does the pitch appear to *sink*?

Let's consider a righty pitcher. The spin axis, in this case would point down to the ground, and the Magnus force would point to the pitcher's right. From their perspective, the ball travels with a arm-side lateral break and falls naturally due to gravity. But this means that, as the ball nears the plate, there are more $v_x$ and $v_z$ components than there were at the release point, their directions pointing to the arm side and downward, respectively. Interestingly, this means that the cross product $\vec{\omega}\times\vec{v}$ would have a larger $y$ component than it had in the beginning, effectively slowing down and speeding up the ball in that direction depending on the situation. 

## Gyro spin

If a pitched ball has "gyro spin," it usually means that the ball's spin axis is roughly parallel to the $y$ axis of the coordinate system. In other words, the ball is spinning almost purely clockwise or counter-clockwise when viewed from the perspectives of either mound or home plate. In this case, assuming that the ball is heading from mound towards the home plate, most of its $\vec{v}$ being its $v_y$ component, the cross product described above should be zero, or very close to zero. Hence, at first glance, it appears that gyro spin does not matter much for simulating the trajectory of the baseball.

However, the direction of the velocity will change throughout the flight of the baseball, either due to gravity, any $\omega_x$ or $\omega_z$ components, any $v_x$ or $v_z$ components, or any combination thereof. This means that the $\omega_y$ component, if present, could eventually yield a meaningfully large enough cross product with $\vec{v}$.
