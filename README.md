# About

## Purpose

This is a baseball pitch simulator. The repo plans to eventually contain physics simulations, configuration tools, and plotting tools, with which you can do the follwing:

* Tweak around arm slots, spin rate, etc. to visually explore differences in pitch trajectories.
* Import data from Statcast or Baseball Savant to comapre, modify, and play with pitches actually thrown in the MLB.
* Run parallel instances of the simulator with slightly different configurations and compare results.

## Authors and History

The physics implementation was written by two undergraduate students, **June Jung** and **Richard Whitehill**. The original code was rewritten to provide a cleaner API by **C.D. Clark III**. In 2020, we were working on learning-based models to simulate a batter's response to differnt types of pitchers. The repository can be found at [CD3/BaseballSimulator](https://github.com/CD3/BaseballSimulator). 

The code is now being rewritten again by June Jung. This repository focuses strictly on **accuracy and ease of use**. Most of the code related to machine learning in `BaseballSimulator` has been stripped away. Other parts are currently being written from scratch.
