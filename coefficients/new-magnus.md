# New Assumptions for, and Subsequent Computing of, the Magnus Force and its Coefficient

## 1. Background

The physics implemented in the `phys` module calculates three force terms at every time interval: gravity, air drag, and deflection due to spin; the last of which is known as the Magnus force. Typically, it is expressed as a function of several variables, and understood to be proportional to the velocity squared:

$$ \vec{F}_{magnus} = C_L \cdot \vec{v}^2 $$

where $C_L$ is the "lift coefficient," which is itself a function of the object's spin, its radius, surface area, spin, air density, and velocity. 

But the original `phys` module assumed that, because baseballs are all we're interested in, things like air density and object's profile can be absorbed into one constant. Moreover, $C_L$ depends on a spin parameter $S$, which has a $1/v$ factor inside it. For baseballs traveling at the speed at which they do, $C_L$ comes out to be roughly proportional to $1/v$. For this reason, it was assumed that the squared velocity term can be canceled out. Thus, the equation implemented in `phys` expressed the Magnus term as follows:

$$ \vec{F}_{magnus} = \beta \cdot \vec{\omega} \times \vec{v} $$

where $\beta$ is an empirically determined constant, $\omega$ is spin, and $v$ is velocity.

However, as you can see in [the optimization results](docs/k-results.md), I could not get the average error in acceleration down below ~2.35 $m/s^2$ over a batch of ten Statcast-tracked games. This is a pretty significant error, as the final displacement error at home plate can be as large as 8 inches. Hence, a refinement of the physics model is warranted. 

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

and perform gradient descents on partial derivatives of an error function in respect to each of those $a$, $b$, $c$, ... coefficients. I'm not sure how fruitful this would be. Frankly, it feels like a brute force solution. But we can try it, nonetheless.

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

## 3. Methods

To be written after code implementation
