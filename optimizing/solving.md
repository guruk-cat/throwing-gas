# Closed-Form Solution for Constant *K*

## 1. Closed Form Exists

The predicted acceleration at a measurement point is:

$$\vec{a}_{pred}(K) = \underbrace{-g\hat{z} + \alpha|v|^2\hat{v}}_{\text{K-independent}} + K(\vec{\omega} \times \vec{v})$$

Because K enters the equation **linearly**, the mean squared error over any batch of samples is a convex quadratic in K — a parabola opening upward, with exactly one global minimum. Setting its derivative to zero yields a closed-form solution.

## 2. Derivation

For sample $i$, define:

$$\vec{c}_i = \vec{\omega}_i \times \vec{v}_i$$

$$\vec{r}_i = \vec{a}_{true,i} - \vec{a}_{base,i}$$

where $\vec{a}_{base,i}$ is the gravity + drag contribution (independent of $K$), and $\vec{a}_{true,i}$ is the ground-truth acceleration from Statcast. $\vec{r}_i$ is the residual acceleration not yet explained by gravity and drag — the part that Magnus must account for.

The squared error for sample $i$ is:

$$E_i(K) = |\vec{r}_i - K\vec{c}_i|^2 = |\vec{r}_i|^2 - 2K(\vec{r}_i \cdot \vec{c}_i) + K^2|\vec{c}_i|^2$$

The mean squared error over $N$ samples is:

$$E(K) = \frac{1}{N}\sum_{i=1}^{N} E_i(K)$$

Setting $dE/dK = 0$:

$$\sum_{i=1}^{N} \left[ -2(\vec{r}_i \cdot \vec{c}_i) + 2K|\vec{c}_i|^2 \right] = 0$$

Solving for $K$:

$$\boxed{K^* = \frac{\displaystyle\sum_{i=1}^{N} (\vec{r}_i \cdot \vec{c}_i)}{\displaystyle\sum_{i=1}^{N} |\vec{c}_i|^2}}$$

This is the unique global minimizer of the mean squared error over the batch.

## 3. Interpretation

The formula is a one-dimensional linear regression of the true acceleration residual onto the Magnus direction vector $\vec{c}_i$. The numerator is the total "alignment" between the unexplained acceleration and the Magnus direction; the denominator is the total Magnus signal strength across the batch. The ratio gives exactly how much of $K$ is needed to explain the residual.

## 4. Practical Notes

- **$\vec{a}_{base,i}$ is not directly observable.** You still need to run the simulator once per sample at any trial $K_0$ to separate the drag and gravity contributions from the Magnus contribution. But one pass is sufficient — no iteration required.
- **All samples can be pooled.** Unlike gradient descent, which processes batches sequentially over many epochs, the formula above can take every available sample at once and return the exact answer in a single computation.
- **No hyperparameters.** Learning rate, epoch count, and convergence thresholds are not needed.
