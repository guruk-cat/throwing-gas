# Research, Testing, and Implementation Logs for Modeling Unknown Coefficients

## 1. Background

The physics implemented in the `phys` module calculates three force terms at every time interval: gravity, air drag, and deflection due to spin; the last of which is known as the Magnus force. Typically, it is expressed as a function of several variables, and understood to be proportional to the velocity squared:

$$ \vec{F}_{magnus} = C_L \cdot \vec{v}^2 $$

where $C_L$ is the "lift coefficient," which is itself a function of the object's spin, its radius, surface area, spin, air density, and velocity. 

But the original `phys` module assumed that, because baseballs are all we're interested in, things like air density and object's profile can be absorbed into one constant. Moreover, $C_L$ depends on a spin parameter $S$, which has a $1/v$ factor inside it. For baseballs traveling at the speed at which they do, $C_L$ comes out to be roughly proportional to $1/v$. For this reason, it was assumed that the squared velocity term can be canceled out. Thus, the equation implemented in `phys` expressed the Magnus term as follows:

$$ \vec{F}_{magnus} = \beta \cdot \vec{\omega} \times \vec{v} $$

where $\beta$ is an empirically determined constant, $\omega$ is spin, and $v$ is velocity.

However, I could not get the average error in acceleration down below ~2.35 $m/s^2$ over a batch of ten Statcast-tracked games. This is a pretty significant error, as the final displacement error at home plate can be as large as 8 inches. Hence, a refinement of the physics model is warranted. 

The first suspect of the large error is, of course, air density. It would presumably vary by ballpark and by weather. The Rockies' Coors field, for example, is known as a homerun-friendly park. A part of the reason is due to its altitude and consequent low air drag on the balls. We can imagine that it causes less breaks on pitches, as well. 

Another suspect is the ball's surface, which would be more difficult to model. The air around the ball (and equally importantly the air *behind* the ball) acts differently depending on how rough or smooth the surface of the baseball is. The trouble is that a baseball has seams. A even further trouble is that these seams are rotating at different axes depending on the pitch.

The same questions should be asked also for the air drag term, which can be similarly expressed as:

$$ \vec{F}_{drag}  = C_d \cdot \vec{v}^2 $$

where $C_d$ is the drag coefficient, again a function of surface area, air density, and so on.

## 2. Issues
### 2.1. Coefficients are not easily predictable

Adair (1995) noted that a baseball, given its typical range, lives within the transition from (a) leaving classical vortices behind it (due to the Prandtl boundary being intact), to (b) leaving turbulent air behind it (due to the boundary being blown away at higher speed). In this regard, he observed that a rougher ball may have less air drag than a smoother ball, countrary to intuition. He wrote:

> Baseball velocities are typically between 60 and 120 miles per hour, where the transition to turbulent flow — or "drag crisis" — causes $C_d$ to vary rapidly with velocity. A rotating baseball is neither uniformly smooth nor rough, since it presents both its smooth cover and raised stitching to the air. This smooths the transition somewhat.

The figure he presents with this explanation is interesting (see below). The big dip happens to be around the 80-100 mph range, where most pitches live. This means that, if we were to take Adair's comments seriously, we must express both the Magnus coefficient and the drag coefficient as functions of velocity. (But what kind of functions? I don't know!)

![drag coefficient and magnus coefficients, plotted against ball velocity](../docs/imgs/Adair-fig-3a.png)

Figure 3(a) from Adair (1995).

One thing we could do, in order to avoid the complicated physics of turbulence, is to estimate. We can do this by setting up an arbitrary polynomial like this:

$$ C = a \cdot v^0 + b \cdot v^1 + c \cdot v^2 + d \cdot v^3 + ...$$

and minimize an error function in respect to each of those $a$, $b$, $c$, ... coefficients. I'm not sure how fruitful this would be. Frankly, it feels like a brute force solution. But we can try it, nonetheless.

### 2.2. Air density

This one is pretty simple in comparison. The Statcast-fetched YAML files have already been configured to accept an optional `scene` block, wherein weather information is included. From this, it's comparatively straight-forward to calculate the air density.

The density of [humid air](https://en.wikipedia.org/wiki/Density_of_air#Humid_air) can be calculated by treating it as a mixture of ideal gases; we calculate the density of dry air, the water vapor pressue, and their sum. 

$$ \rho = \frac{P_d}{R_d T} + \frac{P_v}{R_v T}$$

where:

- $P$ is partial pressures, for dry air and vapor
- $R$ is specific gas constants, and
- $T$ is temperature in Kelvins

$P_v$ can be calculated entirely from humidity and temperature, while the specific gas constants can be calculated from the molar mass of dry air and water vapor. So, the three entries in the `scene` block of the pitch config files (temperature, pressure, and hudity) are enough to compute the air density at a given game.

And we modify our force terms to include this new value. For example, the Magnus term becomes:

$$ \vec{F}_{magnus} = \beta \cdot \rho \cdot \vec{\omega} \times \vec{v} $$

where $\beta$ still absorbs everything else. And the drag term also gets a similar update:

$$ \vec{F}_{drag} = \alpha \cdot \rho \cdot \lvert \vec{v} \rvert^2 \cdot \hat{v} $$

### 2.3. Dropping the assumptions

We also drop the earlier assumption that, for a baseball traveling at its typical speed, $C_L$ comes out to be roughly proportional to $1/v$. Hence, the Magnus term is finally expressed as:

$$ \vec{F}_{magnus} = \beta \cdot \rho \cdot \lvert \vec{v} \rvert^2 \cdot \vec{\omega} \times \hat{v} $$

It's important to remember that, if we are considering the problems in §2.1., $\alpha$ and $\beta$ are no longer empirically determined *constants*, but are rather empirically determined *functions* of velocity. The coefficients for higher powers of $v$ in the arbitrary polynomial (so, $d$ and onwards), will probably be computed to be near-zero. In other words, the drag and magnus coefficients will probably not turn out to be functions of $v^3$ or higher powers of $v$. But because we're estimating the effects of vortex flows and turbulences left behind the ball, I don't think it is unreasonable to include those higher-power terms for now.

## 3. Scalar coefficients
### 3.1. Methods

For the scalar version of the coefficieints $\alpha$ and $\beta$, we simply minimize an error function $E$. `Simulation.point_run()` takes a state vector and interates the force equation over *one time step*, returning the instantaneous accleeration vector at that point. We use this to compute $dv/dt$ at the 50-feet Statcast tracking location, since that is where the `ax`, `ay`, and `az` vectors are recorded in Statcast. We take the residual from those tracked vectors to the predicted vectors, and try to minimize the residual.

The net force acting on the ball has three terms:

$$ \vec{F}_{net} = \vec{F}_{gravity} + \vec{F}_{drag} + \vec{F}_{magnus} $$

Both $\alpha$ and $\beta$ enter the equation linearly. Moreover, we can assume mass stays constant (baseball mass) and just work with acceleration, since that's the reference unit from Statcast. For *each* unknown coefficient (which we'll call $k$ when referring to either one or the other) the acceleration predicted by the simulator can be expressed as follows:

$$ \vec{a} = \vec{A} \cdot k + \vec{C} $$

where $A$ is the force term $F_k$ divided by $k$, thus leaving some function of velocity, spin, air density, and so forth; and $C$ is simply the $k$-independent remainders of the equation, including gravity. We can subtract the Statcast reference vector to obtain the residual:

$$ \vec{a}_{pred} - \vec{a}_{ref} = \vec{A} \cdot k + \vec{C}- \vec{a}_{ref} $$

and let $\vec{B} = \vec{C}- \vec{a}_{ref} $, thus obtaining:

$$ E(k) = \vec{A} \cdot k + \vec{B} $$

Intuitively, we can understand $\vec{A}$ as how much $k$ affects the prediction, and $\vec{B}$ as $k$-independent errors. Both $\vec{A}$ and $\vec{B}$ can be empricially determined from the simulation given a config sample. For each sample $i$, we run two simulations, one with $k=0$ and one with $k=1$. Then, we get:

$$ E_i(0) = \vec{B}_i $$
$$ E_i(1) = \vec{A}_i + \vec{B}_i $$
$$ \vec{A}_i = E_i(1) - E_i(0) $$

The goal is to get $E$ as close to zero as possible. For individual samples, we can simply set $E = 0$, which gives us:

$$ k_i = - \frac{B_i}{A_i} $$

What becomes tricky over a whole batch of samples, however, is that different samples have different $\vec{A}_i$, and thus the prediction's *sensitivity* to $k$ is different. To address this, instead of taking a simple mean, we take a *weighted average*, each sample weighted by $A_i^2$ so that noisy samples are not as much trusted. (This is, in the end result, identical to making $E$ a squared error function.) Hence, we finally have:

$$ k_{pred} = -\frac{\sum_{i=1}^n A_i B_i}{\sum_{i=1}^n A_i^2} $$

See `coefficients/coefficient.py` for the implementation.

### 3.2. Results and Suggestions

The two scalar coefficients were computed back-to-back, each starting at the same intial arbitrary value. Because the $k$ value that yields the minimum error can be entirely isolated from the $k$-independent terms of the physics equation (unlike in gradient descent), this one-time compute suffices, and iterating the alternation does not reduce the error.

Terminal output:

```
samples: 147 pitches loaded.

computing k for drag...
computing RMS error...
FINAL:
  K         = 6.30816026e-04 (meter ** 2)
  RMS       = 2.70451054e+01 (meter ** 2)

computing k for magnus...
computing RMS error...
FINAL:
  K         = 1.37800775e-06 (meter ** 2 * second)
  RMS       = 2.03637249e+00 (meter ** 2 * second)

Computing displacement error...
Avg. Δx (all samples)    : 5.7741e+00 (inch)
  Δx avg. for fastballs  : 4.9095e+00 (inch)
  Δx avg. for offspeeds  : 5.3649e+00 (inch)
  Δx avg. for curveballs : 4.9923e+00 (inch)
  Δx avg. for sliders    : 8.8195e+00 (inch)
```

First, these errors are the best I've seen so far during this project. The lowest one I had gotten previously was 2.3538 (m/s²), before air density was factored out of the unknown coefficient (see [old optimizer results](../../legacy/docs/k-results.md))

The error is noticeably larger for offspeeds, and *significantly* larger for sliders. This may have to do with gyro spin, since both of those pitches have gyro spin that affects the trajectory of the ball as it nears the plate (i.e., as its velocity vector gains more components in the $x$ and $z$ directions).

Putting aside that, however, the fastballs and curveballs (which have more straight-forward spin axes) still present average errors that are too large to be satisfactory. Running the script with the `--details` flag shows that some of those pitches are only off by an inch or so, but stuff like sinkers (which again has some degree of gyro spin) skew the average. I do wonder if the "effective spin" variable in Statcast trackings could be used, in conjunction with the regular spin rate, to back-compute the complete, three-dimensional spin vector.

## 4. Testing for Gyro Spin
