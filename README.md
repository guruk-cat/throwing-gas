# About

## Purpose

This is a baseball pitch simulator. The repo contains physics simulations, configuration tools, and plotting tools, with which you can do the follwing:

* Tweak around arm slots, spin rate, etc. to explore visual differences in pitch trajectories.
* Import data from Statcast to comapre, modify, and play with pitches actually thrown in the MLB.
* Create imaginary pitcher profiles or test "what if" scenarios.

While Statcast and Baseball Savant provide precise trackings of pitches and body mechanics, they lack a proper physics engine and therefore the ability to test imagined scenarios. Some examples include:

* Clayton Kershaw and Hyun-Jin Ryu, who played together for the Dodgers, reportedly shared with each other tips on their respective signature pitches: Kershaw's curveball and Ryu's changeup. But apparently, Kershaw's arm angle was simply not compatible with Ryu's changeup grip. If everything else stayed constant, what might it look like if Kershaw threw with Ryu's spin axis?
* Trey Yesavage's extremely high release point really confuses batters. Interestingly, his sliders break towards the *arm side* instead of the glove side. At what point does a slider act weirdly like his?

The repository contains tools that can help you answer such questions, and more.

## Authors, History, and Plans

The original physics implementation was written in 2018/2019 by two undergraduate students, **June Jung** and **Richard Whitehill**. The code was then rewritten to provide a cleaner API by **C.D. Clark III**. In 2020, we were working on learning-based models to simulate a batter's response to differnt types of pitchers. The repository can be found at [CD3/BaseballSimulator](https://github.com/CD3/BaseballSimulator). 

The present repository is maintained by June Jung. This repository focuses strictly on **accuracy and usability**. Currently being undertaken are the following: 
* Test physics engine based on Statcast trackings.
* Rebuild constant optimizer and re-define the Magnus term coefficient for a regulation baseball. Current value was calculated from data recorded by older literature. New model will use more recent literature + Statcast trackings. See [optimizing.md](docs/optimizing.md) for latest work.
* CLI for accessing the entire simulation suite.

The following are planned for the future:
* Factor in wind 
* Research on possible changes in spin axis and/or spin rate during ball's fly.

# Try

## Simple two-way comparison

The below setup will give you a 4-seam fastball and a sinker to compare, thrown by an imaginary pitcher who's 6'2" with a 38-degree arm slot (which is nearly sidearm but still three-quarters). You can see what they mean by "tunneling" that confuses batters.

```bash
python src/launch.py "configs/examples/*" --plot
```

**Expected output** (the GIF had to resample the frame rate, so the animation is slowed down here):

![example-run-gif](docs/example-run.gif)

## MLB pitchers

You can use `statcast-to-config.py` to create a configuration file from Statcast data. The file has a comment block that explains how to use the script. The script relies on the [pybaseball](https://github.com/jldbc/pybaseball) package to retrieve raw values. 

A CLI script is being built for making everything easier to use.

## Resources

See `docs/config-help.md` for making your own configs.
See `configs/` for configs that are already prepared.
See `studies/` for case studies made using the simulator & plotter.
