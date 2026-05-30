# About

## Purpose

This is a baseball pitch simulator. The repo contains physics simulations, configuration tools, and plotting tools, with which you can do the follwing:

* Tweak around arm slots, spin rate, etc. to explore visual differences in pitch trajectories.
* Run multiple instances of the simulation with different configurations and compare results.
* Create imaginary pitcher profiles or test "what if" scenarios based on real pitchers.

While Statcast and Baseball Savant provide precise trackings of pitches and body mechanics, they lack a proper physics engine and therefore the ability to test imagined scenarios and/or perspectives. Such limitations are meant to be overcome with the use of `the-bump`.

## Authors, History, and Plans

The original physics implementation was written in 2018/2019 by two undergraduate students, **June Jung** and **Richard Whitehill**. The code was then rewritten to provide a cleaner API by **C.D. Clark III**. In 2020, we were working on learning-based models to simulate a batter's response to differnt types of pitchers. The repository can be found at [CD3/BaseballSimulator](https://github.com/CD3/BaseballSimulator). 

The present repository is maintained by June Jung. This repository focuses strictly on **accuracy and usability**. Most of the code related to machine learning in `BaseballSimulator` has been stripped away. The following are planned for the future:

* Import data from Statcast or Baseball Savant to comapre, modify, and play with pitches actually thrown in the MLB.
* Test and improve the physics engine based on Statcast trackings.
* Factor in wind and spin-drag (as opposed to velocity-based air drag and Magnus force from spin)

# Try

The below setup will give you a 4-seam fastball and a sinker to compare, thrown by an imaginary pitcher who's 6'2" with a 38-degree arm slot (which is almost sidearm but still three-quarters). You can see what they mean by "tunneling" that confuses batters.

```bash
python src/launch.py "example-configs/*" --plot
```

**Expected output** (the GIF had to resample the frame rate, so the animation is slowed down here):

![example-run-gif](docs/example-run.gif)
