# Throwing-Gas

## 1. About

### 1.1. Overview

This is a baseball pitch simulator. The repo contains a physics simulator, configuration tools, and plotting tools, with which you can do the following:

* Tweak around arm slots, spin rate, etc. to explore differences in pitch trajectories.
* Import data from Statcast to compare, modify, and play with pitches actually thrown in the MLB.
* Create imaginary pitcher profiles or test "what if" scenarios.

Studies are being conducted to improve the accuracy of the simulations. Other studies focus on better understanding pitch types. A simple CLI tool has been built for utilizing Statcast, and more work is to come. For the latest work undertaken, see the following:

* [Back-computing initial velocity from Statcast](studies/init-v/back-computing-v.md)
* [What makes a fastball fast? (Other than yanking it as hard as one can.)](studies/fastballs/fastballs.md)
* [Discrepancy Between Optimizer and Closed Solution](optimizing/discrepancy.md)

### 1.2. Authors and History

The original physics implementation was written in 2018/2019 by two undergraduate students, **June Jung** and **Richard Whitehill**. The code was then rewritten to provide a cleaner API by **C.D. Clark III**, who also worked on some machine-learning models to simulate the batter's response. This can be found at [CD3/BaseballSimulator](https://github.com/CD3/BaseballSimulator).

The present repository is maintained by June Jung. Some of the old code has been forked from `BaseballSimulator`, but much of the stuff here has been rebuilt from scratch. This repository focuses strictly on **accuracy, usability, and interpretability**.

## 2. Usage

### 2.1. The Simulation & Configurations

A simulation is run with an instance of `phys.Simulation`, which takes as its argument an instance of `phys.Configuration`. A configuration file written in `.yaml` is required to initialize a `Configuration`. There are primarily two ways to generate such a file. One is to manually create it; you can consult [config-help](docs/config-help.md) for doing so. The other way is to import data from Statcast. Running `main/command.py` in the terminal will provide you with a simple CLI tool that will fetch data from Statcast and generate the configuration files for you. Alternatively, you can run `main/statcast-to-config.py` directly with line arguments. The CLI tool is basically a wrapper around this latter script. Both scripts rely on the [pybaseball](https://github.com/jldbc/pybaseball) package to retrieve raw values from the Statcast database. 


In the CLI tool, you must specify a pitcher by their name, the date of the game, (optionally) the specific pitch count numbers from that game, and the pitcher's height. Unfortunately, the pitcher's height is not included in a standard Statcast tracking. You can easily look it up online. The tool will then generate a sub-directory in `configs/` named after the pitcher and the game date. Inside that folder, you'll find individual `.yaml` files for each pitch that you selected.

While you can read the Python scripts and DIY a process of your own, the easiest way to run a simulation (or many of them) is by using `main/launch.py`. It takes as its first argument the path to your configuration files. You can run one pitch at a time, like:

```bash
python main/launch.py configs/Scott-2026-05-23/5-SL.yaml
```

or you can run a whole bunch of them, like:

```bash
python main/launch.py configs/Scott-2026-05-23/*
```

Additionally, use a `--plot` flag to generate a 3D plot. By default, the plot will be generated in `animated` mode, which is pretty fancy. It supports 60fps live-time animation, a mock baseball field, a time slider, Magnus force direction indicator, strike zone crossings, and so on. Below is an example.

### 2.2. Example

This is a knuckle curveball thrown by Gerrit Cole (NYY). The configuration can be found in `configs/examples/Cole-KC.yaml`. The animation has been slowed down to 0.5 speed in order to accommodate for the GIF frame rate.

![example sim](docs/imgs/cole-sim.gif)

And here's the actual pitch, from the broadcast camera:

![live feed](docs/imgs/cole-broadcast.gif)

You can see that the recreation was off by a couple of inches. It's been very difficult to consistently and accurately recreate pitches from Statcast data. Remember, we're not just plotting position vectors; we're simulating the baseball's flight with a physics engine. We have to work with data that is unavoidably incomplete. For one thing, the baseball's initial state is, to an extent, estimated from data. For another, the physics engine considers three force terms (gravity, air drag, and deflection from spin), while there are other factors in real life such as ambient wind.

### 2.3. Augmenting Statcast

So, then, why even bother to simulate a pitch in the first place? While Statcast and Baseball Savant provide precise trackings of pitches and body mechanics, they lack a proper physics engine that's made available to the public. Therefore, they lack the ability to test imagined scenarios or break down force vectors mid-pitch. Some examples of questions you might ask are:

* Clayton Kershaw and Hyun-Jin Ryu, who played together for the Dodgers, reportedly shared with each other tips on their respective signature pitches: Kershaw's curveball and Ryu's changeup. But apparently, Kershaw's arm angle was simply not compatible with Ryu's changeup grip. If everything else stayed constant, what might it look like if Kershaw threw with Ryu's spin axis?
* Trey Yesavage's extremely high release point really confuses batters. Interestingly, his sliders break towards the *arm side* instead of the glove side. At what point does a slider act weirdly like his?

You can attempt to answer such questions with simulations. After you generate the baseline configurations from Statcast using the scripts mentioned above, you can manually tweak the configuration files to see what changes. The format for the configuration `.yaml` files was designed specifically to **accommodate intuition** rather than to rely exclusively on raw vectors. The [pitch frame](docs/pitch-frame.md) is a coordinate system that is used for the sole purpose of easily creating configurations. It is not used by `phys.Simulation`, nor is it used in plotting. It allows you to specify a spin profile independent of the pitcher's arm slot, release point, or the initial velocity direction. And when you pass it to an instance of `phys.Configuration`, it'll do the math for you.

### 2.4. Required Packages

The following packages are required for all the scripts to function fully:

- numpy
- pandas
- pint
- plotly
- pyyaml
- pybaseball

## 3. Studies

### 3.1. The Magnus Constant

The deflection from the baseball's spin is characterized by the Magnus force, which is proportional to the cross product of the spin vector $\vec{\omega}$ and velocity $\vec{v}$. We can express it as thus:

$$ \vec{F}_{magnus} = \beta \cdot \vec{\omega} \times \vec{v} $$

where $\beta$ represents a constant that has to be empirically determined. Back in the day, we used data recorded by some older literature to determine $\beta$. The current value, in contrast, has been computed from Statcast trackings by optimizing the simulator's acceleration prediction against them. You can find documentations and source codes relating to this topic in `optimizing/`.

### 3.2. Others

Other studies are included in `studies/`, separated into subdirectories by topic. Some of them are concerned with improving the precision and accuracy of the simulations and Statcast-based configurations. Others have more to do with understanding different pitch types and why they appear the way they do.

## 4. Physics

### 4.1. Force Equation

The physics implemented in `phys.Simulator` essentially computes, at every time interval $t$, the following set of forces acting on the baseball:

$$ \vec{F}_{net} = -mg - \alpha \cdot |\vec{v}|^2 \cdot \hat{v} + \beta \cdot \vec{\omega} \times \vec{v}$$

The three terms express, in respective order: gravity, air drag, and Magnus force. Because we are only working with a single, very specific object (i.e., a baseball) and because we are working within a limited context (i.e., the baseball flying roughly at 80~105 mph for less than half a second), we can afford to have coefficients $\alpha$ and $\beta$ absorb information that is traditionally expressed separately, such as air density and reference area. Again, the downside of this is that we can't account for ballpark-specific or time-specific air conditions, but I don't know how I'd find data on that anyways.

### 4.2. Approximation and Precision

I'll write this later.
