# Better and Quicker Optimization for Constant *K*

## 1. Background

The physics implemented in `Simulator` calculates the net force acting on the baseball as follows:

$$ \vec{F}_{net} = \vec{F}_{gravity} + \vec{F}_{drag} + \vec{F}_{spin}$$

where the three force terms express gravity, air drag, and Magnus force caused by the spin of the ball. Each term is defined as follows:

$$ \vec{F}_{net} = m\vec{g}  - \alpha \cdot |v|^2 \cdot \hat{v} + \beta \cdot \vec{\omega} \times \vec{v}$$

Air drag is proportional to the magnitude of velocity squared, and is in the opposite direction of the velocity. The mangus force is proportional to the cross product of the spin vector (whose direction is defined as the spin axis accoording to the right-hand rule) and the velocity vector. $\alpha$ and $\beta$ denote unknown constants that must be empirically determined. Since $\vec{F} = m\vec{a}$, we can express the acceleration of the ball as:

$$ \vec{a} = -g + \alpha \frac{|v|^2\hat{v}}{m} + \beta \frac{\vec{\omega} \times \vec{v}}{m} $$

The `optimize.py` script exists for determining the unknown constants in this context. In the code, the letter `k` is used to denote an unknown constant. In this document, we will assume that $\beta$ is unknown, and will refer to it as the "Magnus term coefficient" or "constant $K$. 

## 2. Concept

The optimizer performs a **gradient descent** on an error function $E$ of state vector $S$ and constant $K$. Its operation in simple terms is as follows.

We must have a **sample** that includes initial state vector $s_0$ and final state vector $s_1$. In the context of the baseball simulator, these are the vectors that contains the ball's position, velocity, and spin at time $t$. So, we would need a set of datapoints from a ball that is actually thrown and tracked (e.g., Statcast) in order to have the $s_0$ and $s_1$ pairing. Let's say $s_0$ is measured at the release point (ball leaves pitcher's hand) and $s_1$ is measured when it crosses the home plate.

We then perform a simulation with $s_0$ and see what the final outcome is. Let's call this $s_2$, the state vector of the ball when it crosses the home plate in the simulation. So far, then, we have three state vectors:

* $s_0$: the intial state
* $s_1$: the "correct" answer for the final state
* $s_2$: the simulator's answer for the final state, calculated from $s_1$.

If the simulation is accurate, $s_1 - s_2$ should be nearly zero. The goal of the optimizer is to bring this difference as close as possible to zero.

If we make small changes to constant $K$, there would also be small changes to $s_2$. Hence, if we run the same simulation with $K$ and with $dK$, we should be able to compute a grandient of an error function $E$ in respect to $K$, like this:

$$  \frac{dE}{dK}  \approx \frac{E(K) - E(K + \delta)}{\delta} $$

We can then mutliply a "learning rate" to this result, and adjust $K$ by that amount; and repeat until error converges to near-zero.

## 3. Implementation

The gradient descent approach as described above remains the same. What changes in the code, however, is the vector that is used as the "correct answer" to compare the simulation against. Statcast tracks `ax`, `ay`, `az`: instantaneous acceleration (ft/s^2) at the `y` = 50ft tracking start position. This position also happens to be where the "initial" velocity vector is tracked, although actual release positions typically have a `y` value that ranges 52-55 ft.

We can thus acquire a set of $s_0$, $s_1$, and $s_2$ without running the simulator for the entire trajectory of the baseball. The simulator simply needs to calculate the acceleration $\vec{a}$ from a velocity $\vec{v}$ at time $t$, which it already does internally at every time step. The initial velocity vector tracked at `y` = 50 feet in Statcast becomes the velocity in $s_0$, the rest of the state vector being configured accordingly to the Statcast sample; the intial acceleration vector as explained above is the "correct" reference point; and the time derivative of velocity at $s_0$, as computed in the simulator, become the "prediction" that is compared for error calculation.

The `Simulator` class in the `phys` module gains a new `def point_run()` for this purpose. It uses the same computing method as `run()`, but iterates over only one time step (or two half-steps) and returns $dv/dt$ for the state vector that is passed onto it

The yaml files (used to set up a `Configuration` instance) have an optional block `training` for this purpose. It can be written either by `statcast_to_config.py --training` or the `command.py` CLI tool when the appropriate option is selected. The block, when used, includes the `ax/ay/az` values. It is not read by `Simulation` and is ignored outside the optimizer. 

See `optimize.py` for the code.
