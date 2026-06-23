# Using the CLI Tool

This doc pertains to the `command.py` script, which is a CLI wrapper around `statcast_to_config.py`. The latter script uses `pybaseball` to fetch Statcast data, makes API calls to MLBAM for pitcher information, and makes API calls to Open-Meteo for weather information.

## Option A: Search and Select

This is the easier option to use if you're unsure as to what you want to try out. The order of operations goes like this:

1. It'll ask for a pitcher name and a game date. You may want to browse your favorite pitcher's Savant profile to pick a game. 
2. Then, the script will show you a list of the pitches thrown by that pitcher on that day: pitch count, pitch type, S-B count, result, etc. 
3. And you make your selection, by specifying pitch count numbers, by giving a range, or by selecting all.
4. This will generate a folder within `configs/` named after the pitcher and the date. Inside it, you'll see individual YAML files for each pitch that was fetched and selected.

## Option B: Generate from a YAML list config

This is useful if you are fetching from multiple different games. The only time I use this (and the reason why I made it) is for producing sample batches for the coefficient optimizers. (See `legacy/` for the older ones and `coefficients/` for the newer one.) You point to a YAML file that hosts a list of pitcher/date entries, which would look something like this:

```yaml
- pitcher: John Doe
  date: 2026-06-01
- pitcher: Tom Hanks
  date: 2026-05-01
```

For each batch (that is, a pitcher's game on a given date), one or more *pitch configs* are generated. The *list config* as described above is for generating batches of such pitch configs.

Unlike Option A, with this method the output is written to the parent directory of the list config file.
