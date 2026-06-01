# Optimizing for a Constant *K*

## 1. Background

The physics implemented in `Simulator` calculates the net force acting on the baseball as follows:

$$ F_{net} = F_{gravity} + F_{drag} + F_{spin}$$

where the three force terms express gravity, air drag, and Magnus force caused by the spin of the ball. Because mass can be canceled out in each term, we can express the accleration of the ball as follows:

$$ \vec{a} = -g + \alpha |v|^2\hat{v} + \beta \vec{\omega} \times \vec{v} $$

Air drag is proportional to the magnitude of velocity squared, and is in the opposite direction of the velocity. The mangus force is proportional to the cross product of the spin vector (whose direction is defined as the spin axis accoording to the right-hand rule) and the velocity vector.

The two constants in the equation, $\alpha$ and $\beta$, have to be empirically determined. The `optimize.py` code exists for this purpose. In the code, the letter *k* is used to denote an unknown constant. In this document, we will assume that $\beta$ is unknown, and will refer to it as the "Magnus term coefficient" or "constant *K*. 

## 2. Methods

### 2.1. Overview

The optimizer performs a **gradient descent** on a function $f$ of state vector $s$ and constant $k$. Its operation in simple terms is as follows.

We must have a **sample** that includes initial state vector $s_1$ and final state vector $s_2$. In the context of the baseball simulator, these are the vectors that contains the ball's position, velocity, and spin at time $t$. So, we would need a set of datapoints from a ball that is actually thrown and tracked (e.g., Statcast) in order to have the $s_1$ and $s_2$ pairing. Let's say $s_1$ is measured at the release point (ball leaves pitcher's hand) and $s_2$ is measured when it crosses the home plate.

We then perform a simulation with $s_1$ and see what the final outcome is. Let's call this $s_3$, the state vector of the ball when it crosses the home plate in the simulation. So far, then, we have three state vectors:

* $s_1$: the intial state
* $s_2$: the "correct" answer for the final state
* $s_3$: the simulator's answer for the final state, calculated from $s_1$.

If the simulation is accurate, $s_2 - s_3$ should be nearly zero. The goal of the optimizer is to bring this difference as close as possible to zero.
