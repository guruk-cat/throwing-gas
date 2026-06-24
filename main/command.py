import json
import pathlib
import sys
import yaml
import requests

# Repo root
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
DEFAULT_OUT = pathlib.Path(__file__).parent.parent / "configs"

from statcast_to_config import fetch_pitcher_height, fetch_pitches, pitch_to_config, print_pitch_list
from config_io import clear_cli, exit_cli, user_input, delete_lines, simple_question, yes_or_no



# Run with options
include_training_data = False
SETTINGS_PATH = pathlib.Path(__file__).parent / "command_settings.json"

def load_settings():
    global include_training_data
    if SETTINGS_PATH.exists():
        s = json.loads(SETTINGS_PATH.read_text())
        include_training_data = s.get("include_training_data", False)

def save_settings():
    SETTINGS_PATH.write_text(json.dumps({"include_training_data": include_training_data}))


# CLI menu
class Menu:
    def __init__(self, title, items, suppress_back_key=False):
        # title : STR
        # items : LIST of tuples of (STR, FUNCTION)
        self.title = title
        self.items = items
        self.suppress_back_key = suppress_back_key
        self.rendered_lines = 0
    
    def run_menu(self, inject=None, new_page=True):
        if new_page:
            clear_cli()
        
        lines = 0
        def p(s=''):
            nonlocal lines
            print(s)
            lines += s.count('\n') + 1   # +1 for the newline print() always appends

        if inject is not None:
            p(inject)
            p((f"{self.title.upper()}\n"))
        else:
            p(f"\n{self.title.upper()}\n")

        for i, (label, _) in enumerate(self.items, 1):
            p(f"  {i}. {label() if callable(label) else label}")
        if not self.suppress_back_key:
            p(f"\n  0. Back")
        
        choice = user_input()
        lines = lines + 4
        self.rendered_lines = lines
        if not new_page:
            delete_lines(self.rendered_lines)

        if choice == "0" and not self.suppress_back_key:
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(self.items):
            _, action = self.items[int(choice) - 1]
            if isinstance(action, Menu):
                action.run_menu()   # recurse
            else:
                action()
                return
        else:
            self.run_menu(inject="Not a valid option...", new_page=new_page)



# Statcast-related

def parse_selection(s):
    nums = []
    for part in s.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            nums.extend(range(int(a), int(b) + 1))
        else:
            nums.append(int(part))
    return sorted(set(nums))

def select_pitches():
    print("\nSelecting...\n")
    print("  Enter the numbers of all the pitches you want to select.")
    print("  Ex: 1-6, 33, 34 , 35, 42-53")
    pitch_nums = user_input()
    pitches = parse_selection(pitch_nums)

    delete_lines(9) 
    print("\nThe following pitches have been selected:\n")
    print("  " + ", ".join(str(p) for p in pitches))
    user_continue = yes_or_no("  Continue?")

    if user_continue:
        return pitches
    else:
        delete_lines(8)
        return None

def after_pitch_list(df):
    def select_and_build():
        pitches = select_pitches()
        if pitches is None:
            after_pitch_list(df)
            return
        clear_cli()
        pitches = [i - 1 for i in pitches]
        in_range = all(0 <= i < len(df) for i in pitches)
        if in_range:
            build_chain(df, pitches)
        else:
            pass  # TO-DO: handle out-of-range

    menu = Menu("Options:", [
        ("Select pitches from here", select_and_build),
        ("Different search", search_statcast)
    ])
    menu.run_menu(new_page=False)

def resolve_height(df):
    try:
        height = fetch_pitcher_height(int(df.iloc[0]['pitcher']))
    except requests.RequestException:
        print("\nCould not fetch pitcher's height from the web...")
        height = simple_question("Please enter manually: ")
        clear_cli()
    return height

def out_dir_for(df, config_parent):
    raw_name = str(df.iloc[0]['player_name'])
    pitcher_slug = raw_name.split(',')[0].strip().replace(' ', '-')
    date_slug = str(df.iloc[0]['game_date'])[:10]
    out_dir = config_parent / f"{pitcher_slug}-{date_slug}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

def file_name_for(row, i, include_slug=False):
    pitch_type = str(row.get('pitch_type', 'UNK'))
    name = f"{i + 1}-{pitch_type}.yaml"
    if include_slug:
        pitcher_slug = str(row['player_name']).split(',')[0].strip().replace(' ', '-')
        date_slug = str(row['game_date'])[:10]
        name = f"{pitcher_slug}-{date_slug}-{name}"
    return name

def write_configs(df, pitches, height, include_scene, out_dir, include_slug=False):
    saved_pitches = 0
    for i in pitches:
        row = df.iloc[i]
        try:
            config = pitch_to_config(row, height, include_training=include_training_data, include_scene=include_scene)
        except ValueError as e:
            print(f"  Skipping pitch #{i + 1}: {e}")
            continue
        filename = file_name_for(row, i, include_slug=include_slug)
        yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
        (out_dir / filename).write_text(yaml_str)
        saved_pitches += 1
    return saved_pitches

def build_chain(df, pitches):
    clear_cli()
    height = resolve_height(df)
    include_scene = yes_or_no("Fetch and include weather info?")
    out_dir = out_dir_for(df, DEFAULT_OUT)
    saved = write_configs(df, pitches, height, include_scene, out_dir)

    clear_cli()
    print(f"\nSaved {saved} config(s) to {out_dir}")
    print("Press ENTER to return to the main menu")
    user_input()

def search_statcast(inject=None):
    title = "Fetch from the Statcast database"
    clear_cli()
    if inject is None:
        print(f"\n{title.upper()}")
    else:
        print(inject)
        print(f"{title.upper()}")

    pitcher = simple_question("  Enter the name (first + last) of the pitcher...")
    date = simple_question("  Enter the date of the game (YYYY-MM-DD)...")
    clear_cli()

    try:
        df = fetch_pitches(pitcher, date)
    except ValueError as e:
        search_statcast(inject=str(e))
        return
    
    print_pitch_list(df, pitcher)
    after_pitch_list(df)



# FETCH FROM A LIST CONFIG

def fetch_only(inject=None):
    title = "Fetch from a list"
    description =   "  A YAML-style list of pitcher/date combos are supported.\n" \
                    "  See cli-help.md in docs."

    clear_cli()
    if inject is None:
        print(f"\n{title.upper()}")
    else:
        print(inject)
        print(f"{title.upper()}")
    print(description)

    config_path = simple_question(f"  Root path is set to: {sys.path[0]}\n  Enter relative path to file...")
    config_path = pathlib.Path(sys.path[0]) / config_path.strip()
    config_parent = config_path.parent
    clear_cli()

    try:
        batches = yaml.safe_load(config_path.read_text())
    except (OSError, yaml.YAMLError) as e:
        fetch_only(inject=f"Could not read config file: {e}")
        return

    if not isinstance(batches, list) or not batches:
        fetch_only(inject="Config file must be a non-empty list of pitcher names and dates.")
        return

    # Run once for the entire request
    include_scene = yes_or_no("Fetch and include weather info?")
    consolidate_output = yes_or_no("Consolidate output into one folder?")
    if consolidate_output:
        out_dir_name = simple_question(f"Output folder name? It will be {config_parent}/<your-folder-name>")

    results_saved = []
    for i, batch in enumerate(batches, 1):
        clear_cli()
        print(f"Fetching {i}/{len(batches)}")
        try:
            pitcher, date = batch['pitcher'], batch['date']
        except (TypeError, KeyError):
            print(f"  Skipping malformed batch (need 'pitcher' and 'date'): {batch!r}")
            continue
        try:
            df = fetch_pitches(pitcher, str(date))
        except ValueError as e:
            print(f"  Skipping {pitcher} on {date}: {e}")
            continue
        height = resolve_height(df)

        if consolidate_output:
            out_dir = config_parent / out_dir_name.strip()
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = out_dir_for(df, config_parent)

        # Narrow down by range
        pitch_range = batch.get('range')
        if pitch_range is not None:
            pitches = [i - 1 for i in parse_selection(str(pitch_range))]
            pitches = [i for i in pitches if 0 <= i < len(df)]
        else:
            pitches = range(len(df))

        saved_pitches = write_configs(df, pitches, height, include_scene, out_dir, include_slug=consolidate_output)
        results_saved.append((saved_pitches, pitcher))

    clear_cli()
    print(f"\nProcessed {len(results_saved)} batches:")
    for saved, pitcher in results_saved:
        print(f"  {saved} config(s) for {pitcher}")
    print("\nPress ENTER to return to the main menu")
    user_input()



# TRAINING DATA TOGGLE

def toggle_training_data():
    global include_training_data
    include_training_data = not include_training_data
    save_settings()
    options.run_menu()

options = Menu("Options",[
    (lambda: f"Include training data in output  [{'ON' if include_training_data else 'OFF'}]", toggle_training_data)
])



# MAIN MENU

main_menu = Menu("Start with data from Statcast", [
    ("Search and select", search_statcast),
    ("Fetch from a configurated list", fetch_only),
    (options.title, options),
    ("Exit", exit_cli)
], suppress_back_key=True)

def main():
    load_settings()
    while True:
        main_menu.run_menu()

if __name__ == '__main__':
    main()