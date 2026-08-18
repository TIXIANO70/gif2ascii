"""
tui.py - Zero-dependency interactive arrow-key TUI menu for gif2ascii.
Uses standard Python curses for terminal navigation.
"""

import sys
import os
import curses
import tempfile
from contextlib import contextmanager
from typing import List, Dict, Any, Tuple, Optional
from presets import PresetManager, BUILTIN_PRESETS
from library import LibraryManager
from gif2ascii import convert_gif, convert_with_preset
from ascii_player import play_animation
from utils import get_logger

logger = get_logger()

@contextmanager
def suspend_curses(stdscr=None):
    """
    Safely suspend curses mode to execute external terminal actions
    (such as animation playback or CLI export), guaranteeing that curses program mode
    and screen/cursor state are reliably restored in all cases (including exceptions).
    """
    curses.def_prog_mode()
    curses.endwin()
    try:
        yield
    finally:
        try:
            curses.reset_prog_mode()
            if stdscr is not None:
                stdscr.clear()
                curses.curs_set(0)
        except curses.error as e:
            logger.debug(f"Error resetting curses program mode: {e}")

def get_gif_files() -> List[str]:
    """Scan current directory for .gif files."""
    try:
        files = [f for f in os.listdir(".") if f.lower().endswith(".gif")]
        files.sort()
        return files
    except OSError as e:
        logger.warning(f"Failed to scan directory for GIF files: {e}")
        return []

def curses_menu(stdscr, title: str, options: List[str], descriptions: List[str] = None) -> int:
    """Render a clean arrow-key menu using curses."""
    curses.curs_set(0)
    current_row = 0
    stdscr.clear()

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Title header
        title_str = f" === {title} === "
        stdscr.addstr(1, max(0, (w - len(title_str)) // 2), title_str, curses.A_BOLD | curses.A_UNDERLINE)
        stdscr.addstr(2, max(0, (w - 44) // 2), "Use [Up/Down] Arrows, [ENTER] Select, [q] Back/Quit", curses.A_DIM)

        start_y = 4
        for idx, option in enumerate(options):
            x = 4
            y = start_y + idx
            if y >= h - 4:
                break
            
            if idx == current_row:
                stdscr.attron(curses.A_REVERSE | curses.A_BOLD)
                stdscr.addstr(y, x, f" > {option:<45} ")
                stdscr.attroff(curses.A_REVERSE | curses.A_BOLD)
            else:
                stdscr.addstr(y, x, f"   {option:<45} ")

        # Description footer if available
        if descriptions and current_row < len(descriptions):
            desc = descriptions[current_row]
            stdscr.addstr(h - 2, 4, f"Info: {desc[:w-10]}", curses.A_ITALIC)

        stdscr.refresh()
        key = stdscr.getch()

        if key in [curses.KEY_UP, ord('k'), ord('K')]:
            current_row = (current_row - 1) % len(options)
        elif key in [curses.KEY_DOWN, ord('j'), ord('J')]:
            current_row = (current_row + 1) % len(options)
        elif key in [curses.KEY_ENTER, 10, 13]:
            return current_row
        elif key in [ord('q'), ord('Q'), 27]:  # ESC or q
            return -1

def input_prompt(stdscr, prompt_text: str, default_val: str = "") -> str:
    """Prompt user for text input in curses."""
    curses.curs_set(1)
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    stdscr.addstr(2, 4, prompt_text, curses.A_BOLD)
    stdscr.addstr(3, 4, f"Default: [{default_val}]" if default_val else "")
    stdscr.addstr(5, 4, "> ")
    stdscr.refresh()

    curses.echo()
    input_bytes = stdscr.getstr(5, 6, w - 10)
    curses.noecho()
    curses.curs_set(0)

    val = input_bytes.decode('utf-8').strip()
    return val if val else default_val

def tui_select_gif_unified(stdscr, lm: LibraryManager) -> tuple[str, str]:
    """
    Unified Select GIF Sub-menu:
    1. Type Custom Path or Alias
    2. Local directory .gif files
    3. Saved Favorites & Recent History
    
    Returns (selected_path_or_alias, optional_preset_key)
    """
    local_gifs = get_gif_files()
    index = lm.load_index()
    favs = index.get("favorites", {})
    history = index.get("history", [])

    options = ["⌨️  [ Type Custom File Path or Library Alias ]"]
    descs = ["Type a custom file path or library shortcut alias (e.g. isaac)"]
    targets = [("prompt", None)]

    # Local GIFs
    for g in local_gifs:
        options.append(f"📄  {g}")
        descs.append("Local GIF file in current working directory")
        targets.append((g, None))

    # Saved Favorites
    for fav_key, item in favs.items():
        options.append(f"⭐  {item.get('title', fav_key)} ({fav_key})")
        descs.append(f"Saved Favorite | Preset: {item.get('preset', 'pixel-art')}")
        fav_path = os.path.join(lm.library_dir, item["filename"])
        targets.append((fav_path, item.get("preset")))

    # Recent History
    for hist in history:
        options.append(f"🕒  {hist.get('title')} [{hist.get('played_at', '')}]")
        descs.append(f"Recent History | Source: {hist.get('source_path')}")
        hist_path = os.path.join(lm.library_dir, hist["filename"])
        src = hist_path if os.path.exists(hist_path) else hist.get("source_path")
        targets.append((src, hist.get("preset")))

    options.append("<-  Back to Main Menu")
    descs.append("Return to gif2ascii Main Menu")

    choice = curses_menu(stdscr, "Select GIF Animation", options, descs)
    if choice == -1 or choice == len(targets):
        return None, None

    action_type, preset_key = targets[choice]
    if action_type == "prompt":
        input_str = input_prompt(stdscr, "Enter GIF File Path or Library Alias:")
        if not input_str:
            return None, None
        
        # Check alias
        resolved = lm.resolve_alias(input_str)
        if resolved:
            return resolved, None
        elif os.path.exists(input_str):
            return input_str, None
        else:
            stdscr.erase()
            stdscr.addstr(4, 4, f"Error: File or alias '{input_str}' not found.", curses.A_BOLD)
            stdscr.addstr(6, 4, "Press any key to continue...")
            stdscr.refresh()
            stdscr.getch()
            return None, None
    else:
        return action_type, preset_key

def tui_create_preset(stdscr, pm: PresetManager):
    """Sub-menu to create a custom preset interactively."""
    name = input_prompt(stdscr, "Enter Preset Name:", "My Custom Preset")
    if not name:
        return

    desc = input_prompt(stdscr, "Enter Description:", "Custom user preset")
    
    mode_idx = curses_menu(stdscr, "Select Rendering Mode", ["blocks (Unicode ▀ ▄)", "ascii (Density Ramp)"])
    mode = "blocks" if mode_idx == 0 else "ascii"

    width_str = input_prompt(stdscr, "Enter Target Width (or 'auto' for full terminal width):", "auto")
    if width_str.lower() == "auto":
        width_val = "auto"
    else:
        try:
            width_val = int(width_str)
        except ValueError:
            width_val = 60

    color_idx = curses_menu(stdscr, "Select Color Palette Mode", ["truecolor (24-bit RGB)", "256 (256-color ANSI)", "mono (Monochrome)"])
    colors = ["truecolor", "256", "mono"]
    color_val = colors[max(0, color_idx)]

    bg_idx = curses_menu(stdscr, "Background Transparency", ["Transparent (Terminal default)", "Solid Black Background"])
    black_bg = (bg_idx == 1)

    slug = name.lower().replace(" ", "-")
    pm.add_preset(
        key=slug,
        name=name,
        description=desc,
        mode=mode,
        width=width_val,
        color=color_val,
        black_bg=black_bg
    )
    
    stdscr.erase()
    stdscr.addstr(4, 4, f"Preset '{name}' created successfully!", curses.A_BOLD)
    stdscr.addstr(6, 4, "Press any key to continue...")
    stdscr.refresh()
    stdscr.getch()

def tui_delete_preset(stdscr, pm: PresetManager):
    """Sub-menu to delete a user custom preset."""
    all_p = pm.get_all_presets()
    custom_keys = [k for k, v in all_p.items() if not v.get("is_builtin", False)]

    if not custom_keys:
        stdscr.erase()
        stdscr.addstr(4, 4, "No custom presets found to delete.", curses.A_BOLD)
        stdscr.addstr(6, 4, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()
        return

    options = [f"{all_p[k]['name']} ({k})" for k in custom_keys] + ["<- Cancel"]
    idx = curses_menu(stdscr, "Select Custom Preset to Delete", options)
    
    if idx >= 0 and idx < len(custom_keys):
        target_key = custom_keys[idx]
        pm.delete_preset(target_key)
        stdscr.erase()
        stdscr.addstr(4, 4, f"Deleted preset '{target_key}'!", curses.A_BOLD)
        stdscr.addstr(6, 4, "Press any key to continue...")
        stdscr.refresh()
        stdscr.getch()

def main_tui(stdscr):
    pm = PresetManager()
    lm = LibraryManager()
    selected_gif = None
    selected_preset_key = "pixel-art"

    gifs = get_gif_files()
    if gifs:
        selected_gif = gifs[0]

    while True:
        all_p = pm.get_all_presets()
        preset_info = all_p.get(selected_preset_key, BUILTIN_PRESETS["pixel-art"])

        menu_items = [
            f"📁 Select GIF File        [{os.path.basename(selected_gif) if selected_gif else 'None selected'}]",
            f"🎨 Select Preset          [{preset_info['name']}]",
            f"▶  PLAY ANIMATION NOW",
            f"💾 Export .asciigif Package",
            f"⚙️  Manage Custom Presets",
            f"❌ Exit"
        ]
        
        descs = [
            "Select GIF file, type custom path/alias, or choose from History/Favorites",
            f"Current Preset: {preset_info.get('description', '')}",
            "Convert GIF to temporary cache and launch interactive terminal player",
            "Convert GIF and save compressed .asciigif file to disk",
            "Create new custom presets or delete existing ones",
            "Exit gif2ascii application"
        ]

        choice = curses_menu(stdscr, "gif2ascii Interactive Studio", menu_items, descs)

        if choice == 0:  # Select GIF (Unified Sub-menu)
            sel_gif, assoc_preset = tui_select_gif_unified(stdscr, lm)
            if sel_gif:
                selected_gif = sel_gif
                if assoc_preset and assoc_preset in all_p:
                    selected_preset_key = assoc_preset

        elif choice == 1:  # Select Preset
            keys = list(all_p.keys())
            p_options = [f"{all_p[k]['name']} {'(Built-in)' if all_p[k].get('is_builtin') else '(Custom)'}" for k in keys] + ["<- Back"]
            p_descs = [all_p[k].get('description', '') for k in keys] + ["Back to main menu"]
            p_choice = curses_menu(stdscr, "Select Preset Configuration", p_options, p_descs)
            if p_choice >= 0 and p_choice < len(keys):
                selected_preset_key = keys[p_choice]

        elif choice == 2:  # Play Animation
            if not selected_gif or not os.path.exists(selected_gif):
                stdscr.erase()
                stdscr.addstr(4, 4, "Error: Please select a valid GIF file first!", curses.A_BOLD)
                stdscr.addstr(6, 4, "Press any key to continue...")
                stdscr.refresh()
                stdscr.getch()
                continue

            # If selecting already converted .asciigif (from library/history)
            if selected_gif.lower().endswith(".asciigif"):
                try:
                    with suspend_curses(stdscr):
                        play_animation(selected_gif)
                except (Exception, SystemExit) as e:
                    logger.error(f"Playback error for '{selected_gif}': {e}")
                    stdscr.erase()
                    err_msg = str(e) if str(e) and str(e) != "1" else f"Failed to play '{selected_gif}'"
                    stdscr.addstr(4, 4, f"Playback Error: {err_msg[:60]}", curses.A_BOLD)
                    stdscr.addstr(6, 4, "Press any key to continue...")
                    stdscr.refresh()
                    stdscr.getch()
                continue

            try:
                with suspend_curses(stdscr):
                    temp_dir = os.path.join(tempfile.gettempdir(), "gif2ascii_cache")
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_asciigif = os.path.join(temp_dir, "current.asciigif")

                    print(f"\033[36mConverting '{selected_gif}' with preset '{preset_info['name']}'...\033[0m")
                    convert_with_preset(
                        input_path=selected_gif,
                        output_path=temp_asciigif,
                        preset_cfg=preset_info
                    )

                    # Record in recent history
                    lm.add_to_history(selected_gif, temp_asciigif, preset_name=selected_preset_key)

                    # Play animation
                    play_animation(temp_asciigif)
            except (Exception, SystemExit) as e:
                logger.error(f"Conversion/playback error: {e}")
                stdscr.erase()
                err_msg = str(e) if str(e) and str(e) != "1" else "Failed to process GIF file."
                stdscr.addstr(4, 4, f"Error: {err_msg[:60]}", curses.A_BOLD)
                stdscr.addstr(5, 4, "Check that the file exists and is a valid GIF animation.", curses.A_DIM)
                stdscr.addstr(7, 4, "Press any key to continue...")
                stdscr.refresh()
                stdscr.getch()

        elif choice == 3:  # Export .asciigif
            if not selected_gif or not os.path.exists(selected_gif):
                stdscr.erase()
                stdscr.addstr(4, 4, "Error: Please select a valid GIF file first!", curses.A_BOLD)
                stdscr.addstr(6, 4, "Press any key to continue...")
                stdscr.refresh()
                stdscr.getch()
                continue

            default_out = f"{os.path.splitext(selected_gif)[0]}.asciigif"
            out_path = input_prompt(stdscr, "Enter Output .asciigif File Path:", default_out)

            try:
                with suspend_curses(stdscr):
                    print(f"\033[36mExporting '{selected_gif}' -> '{out_path}'...\033[0m")
                    convert_with_preset(
                        input_path=selected_gif,
                        output_path=out_path,
                        preset_cfg=preset_info
                    )
                    print("\033[32mExport complete! Press ENTER to return to menu...\033[0m")
                    input()
            except (Exception, SystemExit) as e:
                logger.error(f"Export error: {e}")
                stdscr.erase()
                err_msg = str(e) if str(e) and str(e) != "1" else f"Failed to export to '{out_path}'."
                stdscr.addstr(4, 4, f"Export Error: {err_msg[:60]}", curses.A_BOLD)
                stdscr.addstr(6, 4, "Press any key to continue...")
                stdscr.refresh()
                stdscr.getch()

        elif choice == 4:  # Manage Presets
            m_options = ["➕ Create New Custom Preset", "🗑️ Delete Custom Preset", "<- Back"]
            m_choice = curses_menu(stdscr, "Manage Presets", m_options)
            if m_choice == 0:
                tui_create_preset(stdscr, pm)
            elif m_choice == 1:
                tui_delete_preset(stdscr, pm)

        elif choice == 5 or choice == -1:  # Exit
            break

def run_tui_app():
    curses.wrapper(main_tui)
