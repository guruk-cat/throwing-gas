# Discrepancy Between Optimizer and Closed Solution

As of 2026-06-05, issues have been solved. Well, as far as I'm aware.

## Background

The optimizer finds the value for constant $K$ in the dynamics equation that minimizes the mean squared error. Because *K* enters the dynamics equation linearly, the squared error function $E(K)$ is a parabola with one global minimum. We thus solve solve for $K$ at this minimum point, setting $dE/dK = 0$. We expect that the $K$ values from the optimizer and the analytic solution will be very similar, if not practically identical leaving aside floating errors.

For more information, see the following two documentations: 
- [Better and Quicker Optimization for Constant K](optimizing.md)
- [Closed-Form Solution for Constant K](solving.md)

## Setup and Results

We assume a "linear velocity" Magnus model for its documented consistency with empirical findings specific to baseballs. The optimizer was run with the following configuration:

- initial $K$ = $1.0 \times 10^{-3} $ (kg * s / m)
- $\Delta K  = 0.0001 \cdot K$
- internally calibrated learning rate $l$ at the first epoch
- each epoch iterates over 10 batches, each batch containing roughly 100 pitches from the same pitcher on the same day.

The optimizer declared convergence at `epoch = 18/50` as follows:

```
Error is not getting any smaller... declaring convergence
Final K                             = 6.735553241834e-05 (kg*s/m)
Final RMS error across all bacthes  = 2.352487969422 (m/s²)
Est. ceiling of displacement error  = 7.4 ~ 9.4 (inches)
```

The solution script was also run over the same data. However, it yielded very different results:

```
Final K                             = 4.640061747337e-04 (kg*s/m)
Final RMS error across all bacthes  = 4.920826139955 m/s²
Est. ceiling of displacement error  = 15.5 ~ 19.6 (inch)
```

The $K$ value is an order of magnitude larger here than from the optimizer, and the error is also roughly twice as large. Judging by the error alone, intuition tells me that the optimizer is closer to the correct value. 

## Tentative Conclusion (or a Hypothesis, I suppose)

Solution is wrong, or implementaion of the solution is wrong.


## Found Issues

Two bugs were found. First was a typo (wrote "mangus" instead of "magnus"). The other was the fact that, in `Simulator.point_run()`, the constant $K$ absorbs everything in the Magnus term that is not the cross product $\vec{\omega} \times \vec{v}$, and therefore also absorbs the ball mass $m$. Subsequent to this finding, the following was added to the `solve-for-k.py` script:

```
k = m * r_dot_c_sum / c_squared_sum
```

which yielded similar numbers as the optimizer:

```
Final K                             = 6.728089533639e-05 (kg*s/m)
Final RMS error across all bacthes  = 2.352501414866 m/s²
Est. ceiling of displacement error  = 7.4 ~ 9.4 (inch)
```

The original physics implementation in `Simulator` assumes a force equation where *everything* except for gravitational acceleration, velocity vector, and spin vector, are absorbed into the two empirical constants, the drag coefficient and the Magnus coefficient (respectively referred to as $\alpha$ and $\beta$ when both are unknown). Thus, something like this:

$$ \vec{F}_{net} = m\vec{g}  - \alpha \cdot |v|^2 \cdot \hat{v} + \beta \cdot \vec{\omega} \times \vec{v}$$

This was also neglected during the optimization study, but the error in that case was computed by running two simulations with $K$ and $K + \Delta K$, so the math worked out. The optimization doc and the closed solution doc have been updated to reflect this lesson learned.

## Remaining Question

Theoretically, the closed solution should yield a more accurate answer; it's an analytic, not computational, solution. But the optimizer yielded a slightly lower error overall. Why?

This could be due to many things, such as floating point errors that stacked up during iterations, different points wherein I'm summing and/or averaging the erorrs, etc. Who knows. Either way, moving forward, we will use the $K$ value from the optimizer as our new Magnus coefficient.
