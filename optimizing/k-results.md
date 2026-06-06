# Results from Optimizer and Analytic Solution

## 1. Background

The optimizer finds the value for constant $K$ in the dynamics equation that minimizes the mean squared error. Because *K* enters the dynamics equation linearly, the squared error function $E(K)$ is a parabola with one global minimum. Therefore, we can also solve for $K$ at this minimum point, setting $dE/dK = 0$. We expect that the $K$ values from the optimizer and the analytic solution will be very similar, if not practically identical leaving aside floating errors.

For more information, see the following two documentations: 
- [Better and Quicker Optimization for Constant K](optimizing.md)
- [Closed-Form Solution for Constant K](solving.md)

## 2. Issues Found and Addressed

During the first implementation of the closed solution, something important was neglected. It was the fact that, in `phys.Simulator.point_run()`, the constant $K$ absorbs everything in the Magnus term that is not the cross product $\vec{\omega} \times \vec{v}$, and therefore also absorbs the ball mass $m$. Subsequent to this finding, the following was added to the `solve-for-k.py` script:

```
k = m * r_dot_c_sum / c_squared_sum
```

On a similar note, the original physics implementation in `phys.Simulator` assumes a force equation where *everything* except for gravitational acceleration, velocity vector, and spin vector, are absorbed into the two empirical constants, the drag coefficient and the Magnus coefficient (respectively referred to as $\alpha$ and $\beta$ when both are unknown). This should be kept in mind as we move forward.

## 3. Setup and Results

We assume a "linear velocity" Magnus model for its documented consistency with empirical findings specific to baseballs. A total of ten sample batches were used, each batch containing roughly one hundred pitches thrown by the same pitcher on a particular day.

First, the optimizer was run with the following configuration:

- initial $K$ = $1.0 \times 10^{-3} $ (kg * s / m)
- $\Delta K  = 0.0001 \cdot K$
- internally calibrated learning rate $l$ at the first epoch
- each epoch iterates over 10 batches, each batch containing roughly 100 pitches from the same pitcher on the same day.

The optimizer declared convergence as follows:

```
--- Epoch 18/50 ---

  K after epoch     : 6.7496e-05 (kg*s/m)
  Mean RMS error    : 2.3538 (m/s²)

  Error is not getting any smaller... declaring convergence
  Final K                             = 6.749586978411e-05 (kg*s/m)
  Final RMS error across all bacthes  = 2.353751210787 (m/s²)
  Est. ceiling of displacement error  = 7.4 ~ 9.4 (inches)
```

Meanwhile, the solution script, run over the same batches of samples, yielded the following:

```bash
Final K                             = 6.742481583924e-05 (kg*s/m)
Final RMS error across all bacthes  = 2.353764288161 m/s²
Est. ceiling of displacement error  = 7.4 ~ 9.4 (inch)
```

One thing is worth noting regarding the ceiling of displacement error. It should be considered to be the *maximum* amount of error that can happen when the ball is crossing the plate. Usually, the error comes out to be lower than that on individual sample runs. In fact, over the ten sample batches used above, the mean displacement error at home plate computed by `optimizing/goferr.py` comes out to be: 6.15 inches. Well, I suppose that's not much better.

## 4. Remaining Questions

Theoretically, the closed solution should yield a more accurate answer; it's an analytic, not computational, solution. But the optimizer yielded a slightly lower error overall. Why? This could be due to many things, such as floating point errors that stacked up during iterations, different points in the code where I'm summing and/or averaging the erorrs, etc. Who knows. Either way, moving forward, we will use the $K$ value from the optimizer as our new Magnus coefficient.

More importantly, why is the error so large? I need to check if most of the errors are roughly in the same direction in respect to the cross product $\omega \times v$. If so, that would indicate something is wrong with the error function, or the way I implemented it. Perhaps, letting the state vector estimations compound over the whole trajectory would yield more accurate results than using instantaneous acceleration at $y=50$ ft. Otherwise, it would mean that making a single constant $K$ abosrb everything is not sufficient.
