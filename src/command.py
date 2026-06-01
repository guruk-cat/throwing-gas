import argparse
import glob
import pathlib
import sys
import os
import yaml
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from statcast_to_config import fetch_pitches, pitch_to_config, print_pitch_list


# Run with options
include_training_data = False


# CLI helpers

def clear_cli():
    os.system('cls' if os.name == 'nt' else 'clear')

def exit_cli():
    clear_cli()
    print("Goodbye!")
    sys.exit()

def user_input():
    u = input("\n\n\n> ").strip()
    return u

def delete_lines(n):
    for _ in range(n):
        # \033[F moves cursor up one line; \033[K clears that line
        sys.stdout.write("\033[F\033[K")

def simple_question(question):
    lines = 0
    def p(s=''):
        nonlocal lines
        print(s)
        lines += s.count('\n') + 1   # +1 for the newline print() always appends

    p(f"\n{question}")
    u = user_input()
    lines += 4
    delete_lines(lines)
    return u

def yes_or_no(question):
    lines = 0
    def p(s=''):
        nonlocal lines
        print(s)
        lines += s.count('\n') + 1
    
    p(f"{question} [y/n]")
    u = user_input()
    lines += 4

    if u == "y" or u == "Y":
        return True
    elif u == "n" or u == "N":
        return False
    else:
        delete_lines(lines)
        yes_or_no("Dammit, the question was simple. "+question)

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
            p(f"  {i}. {label}")
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
                action()            # call function
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

def menu_after_pitch_print(df):
    def select_and_build():
        pitches = select_pitches()
        if pitches is None:
            menu_after_pitch_print(df)
            return
        pitches = [i - 1 for i in pitches]
        in_range = all(0 <= i < len(df) for i in pitches)
        if in_range:
            menu_build_config(df, pitches)
        else:
            pass  # TO-DO: handle out-of-range

    menu = Menu("Options:", [
        ("Different search", search_statcast),
        ("Select pitches from here", select_and_build)
    ])
    menu.run_menu(new_page=False)

def menu_build_config(df, pitches):
    clear_cli()
    height = simple_question("\nEnter pitcher height (e.g. \"6 ft 2 in\")...")
    clear_cli()
    arm_slot_str = simple_question("\nEnter arm slot override in degrees, or leave blank to use Statcast data...")
    arm_slot = float(arm_slot_str) if arm_slot_str else None

    raw_name = str(df.iloc[0]['player_name'])
    pitcher_slug = raw_name.split(',')[0].strip().replace(' ', '-')
    date_slug = str(df.iloc[0]['game_date'])[:10]
    out_dir = pathlib.Path(__file__).parent.parent / "configs" / f"{pitcher_slug}-{date_slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for i in pitches:
        row = df.iloc[i]
        try:
            config = pitch_to_config(row, height, arm_slot, include_training=include_training_data)
        except ValueError as e:
            print(f"  Skipping pitch #{i + 1}: {e}")
            continue
        pitch_type = str(row.get('pitch_type', 'UNK'))
        filename = f"{i + 1}-{pitch_type}.yaml"
        yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
        (out_dir / filename).write_text(yaml_str)
        saved += 1

    clear_cli()
    print(f"\nSaved {saved} config(s) to {out_dir}")
    print("Press ENTER to return to the main menu")
    user_input()

def search_statcast(inject=None, fetch_only=False):
    title = "Fetch from the Statcast database"
    clear_cli()
    if inject is None:
        print(f"\n{title.upper()}")
    else:
        print(inject)
        print(f"{title.upper()}")

    pitcher = simple_question("  Enter the name of the pitcher...")
    date = simple_question("  Enter the date of the game (YYYY-MM-DD)...")
    clear_cli()

    try:
        df = fetch_pitches(pitcher, date)
    except ValueError as e:
        search_statcast(inject=str(e))
        return
    
    if fetch_only == False:
        print_pitch_list(df, pitcher)
        menu_after_pitch_print(df)
    else:
        pitches = select_pitches()
        if pitches is None:
            return
    
        pitches = [i - 1 for i in pitches]   # start at 0
        in_range = all(0 <= i < len(df) for i in pitches)
        if in_range:
            menu_build_config(df, pitches)
        else:
            pass

def fetch_and_go():
    search_statcast(fetch_only=True)



def confirm_output_training_data():
    global include_training_data
    clear_cli()
    include_training_data = yes_or_no("\nInclude training data in the file output?")

options = Menu("Options",[
    ("Include training data in the file output", confirm_output_training_data)
])

    

statcast_menu = Menu("Start with data from Statcast", [
    ("Search and select", search_statcast),
    ("Fetch only\n     (use this if you already know specific pitch count numbers)", fetch_and_go),
    (options.title, options),
    ("Exit", exit_cli)
], suppress_back_key=True)



def main():
    while True:
        statcast_menu.run_menu()

if __name__ == '__main__':
    main()