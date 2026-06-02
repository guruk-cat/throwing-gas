# Case Study: Yoshinobu Yamamoto to Ramón Laureano, three-pitch strikeout

## About

On May 18, 2026, during the Dodgers-Padres game, Yamamoto (with Will Smith catching) threw a nasty three-pitch sequence to strike out the batter. The sequence was: Four-seamer -> Curveball -> Splitter (pitch numbers 31-33).

## Resources

`configs/` contain the yaml files used as simulation configurations.
`figures/` contain the animated html figures. The "adjusted" figure is compensated for the inaccurate estimates made due to certain Statcast datapoints not being publicly available.

## Pitch tunnel

A pitch tunnel refers to a hypothetical tunnel through which a ball travels during the first 150ms or so. Good pitchers will have a narrower tunnel, meaning that different types of pitches appear relatively similar in the beginning. I suggest that you play with the config files to see for yourself how the tunnel affects the perceived amount of "break" of the pitches.

## Reaction time

I also want to point out the reaction time required for the batter. You can see that until `t = 0.167s` in the recreation, it is difficult to tell which direction each ball is going to break. At `t = 2.000s` you can tell that the curveball begins to drop. Only at `t = 2.333s` you can definitely tell that the curveball is breaking and can see that the splitter is not a 4-seam fastball low in the zone. Of course, these are not precise observations, but they cohere with the common understanding of batter reaction time (150~200 ms to track the pitch and make a decision).
