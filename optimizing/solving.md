# Closed-Form Solution for Constant *K*

## 1. Closed Form Exists

The predicted acceleration at a measurement point is:

$$\vec{a}_{pred}(K) = \underbrace{-g\hat{z} + \frac{\alpha|v|^2\hat{v}}{m}}_{\text{K-independent}} + \frac{K}{m}(\vec{\omega} \times \vec{v})$$

where $m$ is the ball mass. Because K enters the equation **linearly**, the mean squared error over any batch of samples is a convex quadratic in K — a parabola opening upward, with exactly one global minimum. Setting its derivative to zero yields a closed-form solution.

## 2. Derivation

For sample $i$, define:

$$\vec{c}_i = \vec{\omega}_i \times \vec{v}_i$$

$$\vec{r}_i = \vec{a}_{true,i} - \vec{a}_{base,i}$$

where $\vec{a}_{base,i}$ is the gravity + drag contribution (independent of $K$), and $\vec{a}_{true,i}$ is the ground-truth acceleration from Statcast. $\vec{r}_i$ is the residual acceleration not yet explained by gravity and drag — the part that Magnus must account for.

The squared error for sample $i$ is:

$$E_i(K) = \left|\vec{r}_i - \frac{K}{m}\vec{c}_i\right|^2 = |\vec{r}_i|^2 - \frac{2K}{m}(\vec{r}_i \cdot \vec{c}_i) + \frac{K^2}{m^2}|\vec{c}_i|^2$$

The mean squared error over $N$ samples is:

$$E(K) = \frac{1}{N}\sum_{i=1}^{N} E_i(K)$$

Setting $dE/dK = 0$:

$$\sum_{i=1}^{N} \left[ -\frac{2}{m}(\vec{r}_i \cdot \vec{c}_i) + \frac{2K}{m^2}|\vec{c}_i|^2 \right] = 0$$

Solving for $K$:

$$\boxed{K = m \cdot \frac{\displaystyle\sum_{i=1}^{N} (\vec{r}_i \cdot \vec{c}_i)}{\displaystyle\sum_{i=1}^{N} |\vec{c}_i|^2}}$$

This is the unique global minimizer of the mean squared error over the batch.

## 3. Interpretation

The formula is a one-dimensional linear regression of the true acceleration residual onto the Magnus direction vector $\vec{c}_i$. The numerator is the total "alignment" between the unexplained acceleration and the Magnus direction; the denominator is the total Magnus signal strength across the batch. The ratio gives exactly how much of $K$ is needed to explain the residual.
