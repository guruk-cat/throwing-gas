# To-Do: Ballpark and Weather Info for Magnus Constant

# 1. Background

Currently, the deflection force from spin, or the Magnus force, is simply expressed as the following:

$$ \vec{F}_{magnus} = \beta \cdot \vec{\omega} \times \vec{v},$$

where the empirically determined constant $\beta$ absorbs all information traditionally expressed separately, such as air density and surface area. For the information pertaining to the object in question, this is not a problem, since we're only interested in baseballs flying at a fairly consistent range of 75-105 mph. But other factors such as air density -- which is affected by temperature and altitude at the ballpark, for example -- may be the reason why the optimizer and the closed solution can't get the RMS error down below $~2.35$ $m/s^2$. 

# 2. Approach

We can keep $\beta$ as a constant within the force equation used in the simulator. But during configuration, we can make $\beta$ a function of temperature and altitude.
