# What makes a fastball fast? (Other than yanking it as hard as one can)

## 1. Background
### 1.1. About fastballs
Below, we consider the fastball and its variations: four-seam, sinker, and cutter. They are all characterized by *backspin*, meaning that the top of the ball rolls towards the pitcher and the bottom towards the plate. Traditionally, fastballs and especially the four-seam fastball is understood to have a "ride," meaning that the ball seems to float in air longer than what one would expect from gravity alone. This causes batters to swing underneath the incoming ball and miss. But is this, along with the high speed of the ball enabled by the biomechanics of the fastball grip, the only reasons why fastballs appear "fast"?

### 1.2. Coordinate system
Before discussing anything further, we must agree on a coordinate system. This document assumes the world frame used in the simulator, which is also identical to the Statcast tracking conventions. It is as follows:

* Origin at home plate (the back point).
* `+x` points to the right side of the catcher/ump (= left side of the pitcher).
* `+y` towards pitcher (i.e., pitcher throws towards `-y`).
* `+z` points to the sky.

## 2. Preliminary work
### 2.1. What we know from the math
If the ball travels with backspin, this means that the spin axis is pointing roughly to the side. Formally speaking, the spin vector $\vec{\omega}$ has a large $x$ component in our coordinate system. If the pitcher is right-handed, the vector would point in the $-x$ direction, and if the pitcher is left-handed, the vector would point $+x$, following the right-hand rule.

The Magnus force caused by the spin of the baseball can be expressed as:

$$ \vec{F}_{magnus} = m \cdot \beta \cdot \vec{\omega} \times \vec{v} $$

where $m$ is the ball's mass, $\beta$ a constant; the force is proportional to the cross product of the spin and velocity vectors. In our coordinate system, the ball travels from mound to plate in the $-y$ direction. This means that, for a righty pitcher, the cross product yields a vector that points roughly in $+z$, or towards the sky. This is what produces the "ride" as we discussed above.

### 2.2. What we know from trackings

A fastball still tends to fall. It may appear to float in almost a straight line because the batter's eyes (or for that matter, anyone's eyes) expect a certain amount of effect of gravity, and there is therefore a *relative* lack of vertical displacement. In other words, the upward acceleration from the Magnus force tends to be smaller than the downward gravitational acceleration.

But if this is true (which we will test below), it would mean that as the ball nears the plate, the velocity vector would gain magnitude in the $-z$ direction. In turn, the cross product $\vec{\omega} \times \vec{v}$ would gain in the $-y$ direction, effectively *speeding up the ball* as it nears the plate. 

If our math is correct, a fastball isn't fast only because the pitcher throws it hard; it actually crosses the plate faster than what one would expect from release speed alone! Below, we'll test two things: (1) whether this actually happens, and (2) if it does, whether the effect is significant enough to make the ball more difficult to hit.

## 3. Testing

### 3.1. Simulating a four-seamer
Two simulations have been run with a configuration produced from a four-seam fastball thrown by Freddy Peralta on 2026-05-12. The pitch had a release speed of 95.3 mph and spin rate of 2434.0 rpm. Peralta threw with an arm slot of 37.2 degrees, and is right-handed. 

Moreover, one simulation was ran with air drag as equal to zero. This way, we know that any change in velocity in the $x$ or $y$ directions are due to spin. The second simulation was ran with air drag *and* Magnus force as zero, such that any change in velocity in any direction is due to gravity (which should only be in the $-z$ direction).

### 3.2. Simulating a sinker
Again, two simulations are run, one with Magnus force and gravity, and another with gravity only. Both simulations have air drag set to zero. I've selected Logan Webb as our test subject. He throws righty, and is known for a pretty nasty sinker. The particular pitch being recreated was thrown with a 23.3-degree arm slot, 92.1 mph release speed, and 1752.0 rpm spin rate.

### 3.3. Simulating a cutter

TBD

## 4. Results and interpretations
### 4.1 Four-seam

Peralta's 37.2-degree arm slot, combined with the additional clock rotation from his grip, produced a spin vector whose unit vector was the following:

```
spin = ( -0.82, 0.01, -0.57 )
```

So, the spin axis is pointing to the armside, and then a good amount downward.  There is very little gyro spin. This is expected. If you are having a hard time visualizing this, think of a wheel. Assume that we are standing on the mound looking towards the plate. A wheel in the air, moving towards the plate, but spinning such that if it were on the ground, it'd be rolling towards us (=backspin). This wheel is also tilted such that its top and bottom reach from 2 o'clock to 8 o'clock.

With that said, below are the velocity vectors recorded every 0.05 seconds. 

| time (seconds) | velo (m/s) without drag (x, y, z) | velo (m/s) with only gravity (x, y, z)|
| --- | --- | --- |
 0.00 | ( 3.45, -42.46, -0.71 ) | ( 3.45, -42.46, -0.71 ) |
 0.05 | ( 3.25, -42.48, -0.91 ) | ( 3.45, -42.46, -1.20 ) |
 0.10 | ( 3.05, -42.50, -1.11 ) | ( 3.45, -42.46, -1.69 ) |
 0.15 | ( 2.85, -42.52, -1.31 ) | ( 3.45, -42.46, -2.18 ) |
 0.20 | ( 2.65, -42.54, -1.51 ) | ( 3.45, -42.46, -2.67 ) |
 0.25 | ( 2.45, -42.57, -1.71 ) | ( 3.45, -42.46, -3.16 ) |
 0.30 | ( 2.25, -42.59, -1.91 ) | ( 3.45, -42.46, -3.65 ) |
 0.35 | ( 2.05, -42.61, -2.11 ) | ( 3.45, -42.46, -4.14 ) |
 0.40 | ( 1.85, -42.64, -2.31 ) | ( 3.45, -42.46, -4.63 ) |


First, we can confirm here that the gravitational force is bigger than the $z$ component of the Magnus force; the $z$ component of the velocity continues to increase in the negative direction despite having backspin. Yet, when spin is present, the ball falls slower than it does when there's only gravity. So, we know that Magnus force is in effeect nonetheless. Secondly, we can confirm that when only gravity is present, there is no change to the $x$ and $y$ components of the velocity vector.

Thirdly, let's focus on the $x$ and $y$ velocity components when spin is present. The most notable thing is the lateral break. The $x$ component starts with 3.45 m/s, and by the time it reaches the plate it is 1.85 m/s. This means that the ball is still moving in the same direction; it doesn't completely "break" into the opposite direction like we might imagine. But the decrease in velocity in that specific direction, we can presume, causes it to appear as if it's breaking the other way. Moreover, given enough flight time, the $x$ velocity would eventually flip signs. What matters, therefore, appears to be the *acceleration* that is perceived but not anticipated.

Our hypothesis from above is also supported. Namely, the velocity does increase in the $y$ direction. However, the difference is only 0.18 m/s, which is roughly 0.40 mph. Is this a substantial difference in the context of reacting to a ball? If the release speed of the above pitch was 95.3 mph as specified earlier, it would mean that when the ball crosses plate it "feels like" 95.7 mph. So, it's probably non-negligible for a professional ball player, but not huge.

### 4.2. Sinker
The pitch had more sidespin than backspin. Its normalized values are printed below:
```
spin = ( -0.36, 0.07, -0.93 )
```

The velocity vectors recorded every 0.05 seconds are as follows:

| time | velo (m/s) without drag (x, y, z) | velo (m/s) with only gravity (x, y, z) |
| --- | --- | --- |
| 0.00 | ( 3.18, -41.05, -0.28 ) | ( 3.18, -41.05, -0.28 ) |
| 0.05 | ( 2.96, -41.07, -0.69 ) | ( 3.18, -41.05, -0.77 ) |
| 0.10 | ( 2.74, -41.08, -1.09 ) | ( 3.18, -41.05, -1.26 ) |
| 0.15 | ( 2.52, -41.10, -1.50 ) | ( 3.18, -41.05, -1.75 ) |
| 0.20 | ( 2.29, -41.12, -1.91 ) | ( 3.18, -41.05, -2.24 ) |
| 0.25 | ( 2.07, -41.13, -2.31 ) | ( 3.18, -41.05, -2.73 ) |
| 0.30 | ( 1.85, -41.15, -2.72 ) | ( 3.18, -41.05, -3.22 ) |
| 0.35 | ( 1.63, -41.16, -3.13 ) | ( 3.18, -41.05, -3.71 ) |
| 0.40 | ( 1.41, -41.18, -3.53 ) | ( 3.18, -41.05, -4.20 ) |

We see a pattern similar to the one we saw with the four-seame: slower fall, lateral arm-side acceleration, and a slight increase of velocity in the $-y$ direction (0.13 m/s = 0.29 mph). The magnitude of change in lateral velocity from $t=0$ to $t=0.4$ is a little larger (46.4% → 55.7%), which may be due to any one or combination of: (1) the "sinker" grip actually coming into play, (2) Webb's lower arm slot, (3) or ballpark-specific factors like wind.

### 4.3. Cutter

TBD