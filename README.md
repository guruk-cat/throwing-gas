# Throwing-Gas

- [1. About](#1-about)
  - [1.1. Overview](#11-overview)
  - [1.2. Authors and History](#12-authors-and-history)
  - [1.3. Database Credits](#13-database-credits)
- [2. Usage](#2-usage)
  - [2.1. Configurating](#21-configurating)
  - [2.2. Simulating](#22-simulating)
  - [2.3. Example](#23-example)
  - [2.4. Required Packages](#24-required-packages)
- [3. Studies](#3-studies)
  - [3.1. Augmenting Statcast](#31-augmenting-statcast)
  - [3.2. The Magnus Constant](#32-the-magnus-constant)
  - [3.3. Others](#33-others)

## 1. About
### 1.1. Overview

This is a baseball pitch simulator. The repo contains a physics simulator, configuration tools, and plotting tools, with which you can do the following:

* Tweak around arm slots, spin rate, etc. to explore differences in pitch trajectories.
* Import data from Statcast to compare, modify, and play with pitches actually thrown in the MLB.
* Create imaginary pitcher profiles or test "what if" scenarios.

Studies are being conducted to improve the accuracy of the simulations. Other studies focus on better understanding pitch types. A simple CLI tool has been built for utilizing Statcast, and more work is to come. For the latest ongoing work, see [new coefficient modeling](studies/spin_and_drag/coeff_logs.md).

Here are some works that were completed earlier:

* [Back-computing initial velocity from Statcast](studies/init-v/back-computing-v.md)
* [What makes a fastball fast? (Other than yanking it as hard as one can.)](studies/fastballs/fastballs.md)
* [Results from optimizer and analytic solution for constant $K$](legacy/docs/k-results.md)

### 1.2. Authors and History

The original physics implementation was written in 2018/2019 by two undergraduate students, **June Jung** and **Richard Whitehill**. The code was then rewritten to provide a cleaner API by **C.D. Clark III**, who also worked on some machine-learning models to simulate the batter's response. This can be found at [CD3/BaseballSimulator](https://github.com/CD3/BaseballSimulator).

The present repository is authored and maintained by June Jung. Some of the old code has been forked from `BaseballSimulator`, but majority of the stuff here has been rebuilt from scratch. This repository focuses strictly on **accuracy, usability, and interpretability**.

### 1.3. Database Credits

Some scripts in this repository rely on the [pybaseball](https://github.com/jldbc/pybaseball) package to retrieve raw values from the [MLB Statcast](https://baseballsavant.mlb.com/statcast_search) database. 

Weather conditions are fetched from the [Open-Meteo](https://open-meteo.com/) historical archive.

## 2. Usage
### 2.1. Configurating

A simulation is run with an instance of `phys.Simulation`, which takes as its argument an instance of `phys.Configuration`. A pitch configuration file written in `.yaml` is required to initialize a `Configuration` instance. 

There are primarily two ways to generate such a file. One is to manually create it; you can consult [configuration help](docs/config-help.md) for doing so. The other way is to import data from Statcast. Running `main/command.py` in the terminal will provide you with a simple CLI tool that will fetch data from Statcast and generate the configuration files for you. You can consult [CLI help](docs/cli-help.md) for using the tool.

### 2.2. Simulating

While you can read the Python scripts and DIY a process of your own, the easiest way to run a simulation (or many of them) is by using `main/launch.py`. It takes as its first argument the path to your configuration files. You can run one pitch at a time, like:

```bash
python main/launch.py configs/clean-inning/2-FS.yaml --plot
```

or you can run a whole bunch of them, like:

```bash
python main/launch.py "configs/clean-inning/*" --plot
```

Use a `--plot` flag to generate a 3D plot. By default, the plot will be generated in `animated` mode, which is pretty fancy. It supports 60fps live-time animation, a mock baseball field, a time slider, Magnus force direction indicator, strike zone crossings, and so on. Below is an example.

### 2.3. Example

This is a knuckle curveball thrown by Gerrit Cole (NYY). The configuration can be found in `configs/examples/Cole-KC.yaml`. The animation has been slowed down to 0.5 speed in order to accommodate for the GIF frame rate.

![animation from simulation](docs/imgs/cole-sim.gif)

And here's the actual pitch, from the broadcast camera:

![broadcast recording](docs/imgs/cole-broadcast.gif)

You can see that the recreation was off by a couple of inches. It's been very difficult to consistently and accurately recreate pitches from Statcast data. Remember, we're not just plotting position vectors; we're simulating the baseball's flight with a physics engine. We have to work with data that is unavoidably incomplete. Work has been done to improve things in this regard, and is still being undertaken.

### 2.4. Required Packages

The following packages are required for all the scripts to function fully:

- numpy
- pandas
- pint
- plotly
- pyyaml
- pybaseball

## 3. Studies
### 3.1. Augmenting Statcast

Why even bother to simulate a pitch in the first place? While Statcast and Baseball Savant provide precise trackings of pitches and body mechanics, they lack a proper physics engine that's made available to the public. Therefore, they lack the ability to test imagined scenarios or break down force vectors mid-pitch. Some examples of questions you might ask are:

* Clayton Kershaw and Hyun-Jin Ryu, who played together for the Dodgers, reportedly shared tips on their respective signature pitches: Kershaw's curveball and Ryu's changeup. But apparently, Kershaw's arm angle was simply incompatible with Ryu's changeup grip. If everything else stayed constant, what might it look like if Kershaw threw with Ryu's spin axis?
* Trey Yesavage's extremely high release point really confuses batters. Interestingly, his sliders break towards the *arm side* instead of the glove side. At what point does a slider act weirdly like his?

You can attempt to answer such questions with simulations. After you generate the baseline configurations from Statcast using the scripts mentioned above, you can manually tweak the configuration files to see what changes. 

The pitch config format was specifically designed to **accommodate intuition** rather than rely exclusively on raw vectors. The [pitch frame](docs/pitch-frame.md) is a coordinate system that is used for the sole purpose of easily creating configurations; it is not used by `phys.Simulation`, nor is it used in plotting. It allows you to specify a spin profile independent of the pitcher's arm slot, release point, or the initial velocity direction. And when you pass it to an instance of `phys.Configuration`, it'll do the math for you.

### 3.2. The Magnus Constant

The deflection from the baseball's spin is characterized by the Magnus force, which is proportional to the cross product of the spin vector $\vec{\omega}$ and velocity $\vec{v}$. We can express it as thus:

$$ \vec{F}_{magnus} = \beta \cdot \vec{\omega} \times \vec{v} $$

where $\beta$ represents a constant that has to be empirically determined. Back in the day, we used data recorded by some older literature to determine $\beta$. The current value, in contrast, has been computed from Statcast trackings by optimizing the simulator's acceleration prediction against them. There are additional studies being done to make the model more accurate. You can find more on this topic in `coefficients/` and `legacy/`.

### 3.3. Others

Other studies are included in `studies/`, separated into subdirectories by topic. Some of them are concerned with improving the precision and accuracy of the simulations and Statcast-based configurations. Others have more to do with understanding different pitch types and why they appear the way they do.
