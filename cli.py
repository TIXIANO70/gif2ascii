"""
cli.py - Unified command router for gif2ascii.
Handles alias resolution, direct playback, file conversion, preset management, library management, and TUI menu.
"""

import sys
import os
import argparse
import tempfile
from presets import PresetManager
from library import LibraryManager
from gif2ascii import convert_gif, DEFAULT_MAX_IMAGE_PIXELS
from ascii_player import play_animation
from tui import run_tui_app
from utils import setup_logging, get_logger

__version__ = "1.3.1"

logger = get_logger()

def main():
    # If no arguments provided, launch interactive TUI menu
    if len(sys.argv) == 1:
        setup_logging(verbose=False)
        run_tui_app()
        return

    parser = argparse.ArgumentParser(
        prog="gif2ascii",
        description="Unified GIF to ASCII converter, interactive TUI, preset & library manager, and terminal player."
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")
    subparsers = parser.add_subparsers(dest="subcommand", help="Sub-commands")

    # Command: play
    play_parser = subparsers.add_parser("play", help="Convert and play a GIF directly (or play from library alias / .asciigif)")
    play_parser.add_argument("input", type=str, help="Path to .gif / .asciigif file, or library alias (e.g. isaac)")
    play_parser.add_argument("-p", "--preset", type=str, default="pixel-art", help="Preset configuration name (default: pixel-art)")
    play_parser.add_argument("-w", "--width", type=str, default=None, help="Override width ('auto' or integer)")
    play_parser.add_argument("-l", "--loop", type=int, default=-1, help="Loop iterations (-1 for infinite)")
    play_parser.add_argument("--fps", type=float, default=None, help="Override playback FPS rate")
    play_parser.add_argument(
        "--max-pixels",
        type=int,
        default=DEFAULT_MAX_IMAGE_PIXELS,
        help=f"Maximum allowed image pixels before raising DecompressionBombError (0 to disable) (default: {DEFAULT_MAX_IMAGE_PIXELS})"
    )

    # Command: convert
    convert_parser = subparsers.add_parser("convert", help="Convert a GIF file to a compressed .asciigif package")
    convert_parser.add_argument("input", type=str, help="Path to input .gif file")
    convert_parser.add_argument("-o", "--output", type=str, default=None, help="Output .asciigif path")
    convert_parser.add_argument("-p", "--preset", type=str, default="pixel-art", help="Preset configuration name (default: pixel-art)")
    convert_parser.add_argument("-w", "--width", type=str, default=None, help="Target character width ('auto' or integer)")
    convert_parser.add_argument("-m", "--mode", choices=["ascii", "blocks"], default=None, help="Override render mode")
    convert_parser.add_argument("-c", "--color", choices=["truecolor", "256", "mono"], default=None, help="Override color mode")
    convert_parser.add_argument(
        "--max-pixels",
        type=int,
        default=DEFAULT_MAX_IMAGE_PIXELS,
        help=f"Maximum allowed image pixels before raising DecompressionBombError (0 to disable) (default: {DEFAULT_MAX_IMAGE_PIXELS})"
    )

    # Command: preset
    preset_parser = subparsers.add_parser("preset", help="Manage custom presets (list, add, delete)")
    preset_sub = preset_parser.add_subparsers(dest="preset_action", help="Preset actions")

    # preset list
    preset_sub.add_parser("list", help="List all available presets")

    # preset add
    p_add = preset_sub.add_parser("add", help="Add a new custom preset")
    p_add.add_argument("name", type=str, help="Preset slug key (e.g. my-preset)")
    p_add.add_argument("--display-name", type=str, default=None, help="Display name")
    p_add.add_argument("--desc", type=str, default="Custom user preset", help="Description")
    p_add.add_argument("--mode", choices=["ascii", "blocks"], default="blocks", help="Rendering mode")
    p_add.add_argument("--width", type=str, default="auto", help="Width ('auto' or integer)")
    p_add.add_argument("--color", choices=["truecolor", "256", "mono"], default="truecolor", help="Color mode")
    p_add.add_argument("--black-bg", action="store_true", help="Force solid black background")

    # preset delete
    p_del = preset_sub.add_parser("delete", help="Delete a custom preset")
    p_del.add_argument("name", type=str, help="Preset slug key to delete")

    # Command: library
    lib_parser = subparsers.add_parser("library", help="Manage saved library animations and history")
    lib_sub = lib_parser.add_subparsers(dest="lib_action", help="Library actions")

    # library list
    lib_sub.add_parser("list", help="List saved favorites and recent history")

    # library add
    l_add = lib_sub.add_parser("add", help="Add a GIF animation to library favorites")
    l_add.add_argument("input", type=str, help="Path to .gif file")
    l_add.add_argument("-a", "--alias", type=str, required=True, help="Alias shortcut name (e.g. isaac)")
    l_add.add_argument("-t", "--title", type=str, default=None, help="Display title")
    l_add.add_argument("-p", "--preset", type=str, default="pixel-art", help="Preset configuration name")

    # library remove
    l_rem = lib_sub.add_parser("remove", help="Remove a favorite from library")
    l_rem.add_argument("alias", type=str, help="Alias shortcut name to remove")

    # Command: uninstall
    uninst_parser = subparsers.add_parser("uninstall", help="Uninstall gif2ascii package and remove binaries/user data")
    uninst_parser.add_argument("--purge", action="store_true", help="Also remove user data (~/.config/gif2ascii and ~/.local/share/gif2ascii)")
    uninst_parser.add_argument("-y", "--yes", action="store_true", help="Automatic yes to prompts")

    # If first argument looks like a GIF or file or alias, default to 'play' subcommand!
    first_arg = sys.argv[1]
    if first_arg not in ["play", "convert", "preset", "library", "uninstall", "-h", "--help"] and not first_arg.startswith("-"):
        sys.argv.insert(1, "play")

    args = parser.parse_args()
    setup_logging(verbose=getattr(args, "verbose", False))

    pm = PresetManager()
    lm = LibraryManager()

    if args.subcommand == "play":
        input_target = args.input

        # 1. Try resolving as alias shortcut from Library
        resolved_lib_path = lm.resolve_alias(input_target)
        if resolved_lib_path:
            play_animation(resolved_lib_path, loop_count=args.loop, override_fps=args.fps)
            return

        # 2. Check if filesystem path exists
        if not os.path.exists(input_target):
            print(f"Error: Neither file nor library alias '{input_target}' was found.", file=sys.stderr)
            sys.exit(1)

        # If already a .asciigif, play directly
        if input_target.lower().endswith(".asciigif"):
            play_animation(input_target, loop_count=args.loop, override_fps=args.fps)
            return

        # Convert to temp cache and play
        preset_cfg = pm.get_preset(args.preset)
        width_setting = args.width if args.width is not None else preset_cfg.get("width", 50)
        
        if str(width_setting).lower() == "auto":
            try:
                term_cols = os.get_terminal_size().columns
            except OSError:
                term_cols = 80
            width_val = max(20, term_cols)
        else:
            width_val = int(width_setting)

        temp_dir = os.path.join(tempfile.gettempdir(), "gif2ascii_cache")
        os.makedirs(temp_dir, exist_ok=True)
        temp_asciigif = os.path.join(temp_dir, "play_cache.asciigif")

        print(f"\033[36m[gif2ascii] Converting '{input_target}' using preset '{preset_cfg['name']}'...\033[0m")
        convert_gif(
            input_path=input_target,
            output_path=temp_asciigif,
            width=width_val,
            mode=preset_cfg.get("mode", "blocks"),
            color_mode=preset_cfg.get("color", "truecolor"),
            speed=preset_cfg.get("speed", 1.0),
            font_aspect_ratio=0.5,
            black_bg=preset_cfg.get("black_bg", False),
            max_pixels=args.max_pixels
        )

        # Track in history
        lm.add_to_history(input_target, temp_asciigif, preset_name=args.preset)

        play_animation(temp_asciigif, loop_count=args.loop, override_fps=args.fps)

    elif args.subcommand == "convert":
        input_path = args.input
        if not os.path.exists(input_path):
            print(f"Error: File '{input_path}' not found.", file=sys.stderr)
            sys.exit(1)

        output_path = args.output
        if output_path is None:
            base, _ = os.path.splitext(input_path)
            output_path = f"{base}.asciigif"

        preset_cfg = pm.get_preset(args.preset)
        width_setting = args.width if args.width is not None else preset_cfg.get("width", 50)
        
        if str(width_setting).lower() == "auto":
            try:
                term_cols = os.get_terminal_size().columns
            except OSError:
                term_cols = 80
            width_val = max(20, term_cols)
        else:
            width_val = int(width_setting)

        mode_val = args.mode if args.mode else preset_cfg.get("mode", "blocks")
        color_val = args.color if args.color else preset_cfg.get("color", "truecolor")

        convert_gif(
            input_path=input_path,
            output_path=output_path,
            width=width_val,
            mode=mode_val,
            color_mode=color_val,
            speed=preset_cfg.get("speed", 1.0),
            font_aspect_ratio=0.5,
            black_bg=preset_cfg.get("black_bg", False),
            max_pixels=args.max_pixels
        )

    elif args.subcommand == "preset":
        if args.preset_action == "list":
            all_p = pm.get_all_presets()
            print("\033[1;36m=== gif2ascii Presets ===\033[0m")
            for key, p in all_p.items():
                p_type = "\033[33m[Built-in]\033[0m" if p.get("is_builtin") else "\033[32m[Custom]\033[0m"
                print(f" • \033[1m{key:<15}\033[0m {p_type} - {p['name']} ({p.get('mode')}, w={p.get('width')}, c={p.get('color')})")
                print(f"   \033[90m{p.get('description', '')}\033[0m")
        elif args.preset_action == "add":
            disp_name = args.display_name if args.display_name else args.name.title()
            width_val = args.width
            if width_val != "auto":
                try:
                    width_val = int(width_val)
                except ValueError:
                    width_val = "auto"
                    
            pm.add_preset(
                key=args.name,
                name=disp_name,
                description=args.desc,
                mode=args.mode,
                width=width_val,
                color=args.color,
                black_bg=args.black_bg
            )
            print(f"\033[32mPreset '{args.name}' added successfully!\033[0m")
        elif args.preset_action == "delete":
            success = pm.delete_preset(args.name)
            if success:
                print(f"\033[32mPreset '{args.name}' deleted.\033[0m")
            else:
                print(f"\033[31mError: Custom preset '{args.name}' not found or is built-in.\033[0m")

    elif args.subcommand == "library":
        index = lm.load_index()
        if args.lib_action == "list":
            print("\033[1;36m=== ⭐ Saved Favorites Library ===\033[0m")
            favs = index.get("favorites", {})
            if not favs:
                print(" \033[90m(No favorites saved yet)\033[0m")
            else:
                for alias, item in favs.items():
                    print(f" • \033[1;32m{alias:<15}\033[0m - {item.get('title')} (Preset: {item.get('preset')})")
                    print(f"   \033[90mSource: {item.get('source_path')}\033[0m")

            print("\n\033[1;36m=== 🕒 Recent History ===\033[0m")
            history = index.get("history", [])
            if not history:
                print(" \033[90m(History empty)\033[0m")
            else:
                for idx, h in enumerate(history[:5]):
                    print(f" {idx+1}. {h.get('title')} [{h.get('played_at')}]")

        elif args.lib_action == "add":
            success = lm.add_favorite(
                alias=args.alias,
                gif_or_asciigif_path=args.input,
                preset_name=args.preset,
                title=args.title
            )
            if success:
                print(f"\033[32mSaved animation to Library with alias '\033[1m{args.alias}\033[22m'!\033[0m")
            else:
                print(f"\033[31mError adding GIF to library.\033[0m", file=sys.stderr)

        elif args.lib_action == "remove":
            success = lm.remove_favorite(args.alias)
            if success:
                print(f"\033[32mRemoved '\033[1m{args.alias}\033[22m' from Library.\033[0m")
            else:
                print(f"\033[31mError: Favorite alias '{args.alias}' not found.\033[0m", file=sys.stderr)

    elif args.subcommand == "uninstall":
        import shutil
        import subprocess

        print("\033[1;33m=== 🗑️  gif2ascii Uninstaller ===\033[0m")
        
        do_purge = args.purge
        if not do_purge and not args.yes:
            ans = input("Do you also want to remove user data (~/.config/gif2ascii and ~/.local/share/gif2ascii)? [y/N]: ").strip().lower()
            do_purge = ans in ['y', 'yes']

        if not args.yes:
            confirm = input("Are you sure you want to uninstall gif2ascii? [y/N]: ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("Uninstallation cancelled.")
                return

        if do_purge:
            config_dir = os.path.expanduser("~/.config/gif2ascii")
            share_dir = os.path.expanduser("~/.local/share/gif2ascii")
            for p in [config_dir, share_dir]:
                if os.path.exists(p):
                    shutil.rmtree(p, ignore_errors=True)
                    print(f"\033[32mRemoved user data: {p}\033[0m")

        print("Uninstalling Python package via pip...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "gif2ascii"], check=True)
            print("\033[1;32mSuccessfully uninstalled gif2ascii!\033[0m")
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to run pip uninstall automatically: {e}")
            print(f"\033[31mFailed to run pip uninstall automatically: {e}\033[0m")
            print("You can run manually: pip uninstall -y gif2ascii")

if __name__ == "__main__":
    main()
