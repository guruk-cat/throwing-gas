# Using the CLI Tool

This doc pertains to the `command.py` script, which is a CLI wrapper around `statcast_to_config.py`. The latter script uses `pybaseball` to fetch Statcast data, makes API calls to MLBAM for pitcher information, and makes API calls to Open-Meteo for weather information.

## Option A: Search and Select

This is the easiest to use if you're unsure as to what you want to try out. It'll ask for a pitcher name and a game date. Then, it'll have you select the pitches thrown by that pitcher on that day. You get to see a list of the details (pitch count, pitch type, S-B count, etc.) before making your selection. This will generate a folder within `configs/` named after the pitcher and the date. Inside it, you'll see individual YAML files for each pitch that was fetched and selected.

## Option B: Generate from a YAML list

This is useful if you are fetching from multiple different games. The only time I use this (and the reason why I made it) is for producing sample batches for the coefficient optimizers. (See `legacy/` for the older ones and `coefficients/` for the newer one.) You point to a YAML file that hosts a list of pitcher/date entries, which would look something like this:

```yaml
- pitcher: Gerrit Cole
  date: 2024-04-01
- pitcher: Blake Snell
  date: 2024-05-02
```
