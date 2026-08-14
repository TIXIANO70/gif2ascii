#!/usr/bin/env python3
"""
ascii_player.py - High-performance interactive terminal player for .asciigif animation packages
"""

import sys
import os
import time
import argparse
import signal
import atexit
import gzip
import json
from utils import load_asciigif, get_logger

logger = get_logger()

# Unix non-blocking input setup
HAS_TERMIOS = False
try:
    import termios
    import tty
    import select
    HAS_TERMIOS = True
except ImportError:
    pass

class TerminalController:
    """Manages terminal raw mode, cursor visibility, and clean restoration."""
    def __init__(self):
        self.old_settings = None
        self.is_raw = False

    def setup_raw(self):
        if HAS_TERMIOS and sys.stdin.isatty():
            try:
                self.old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
                self.is_raw = True
            except (termios.error, OSError) as e:
                logger.debug(f"Could not setup raw terminal mode: {e}")
        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def restore(self):
        # Show cursor and reset terminal colors
        sys.stdout.write("\033[0m\033[?25h\n")
        sys.stdout.flush()
        if self.is_raw and self.old_settings and HAS_TERMIOS:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                self.is_raw = False
            except (termios.error, OSError) as e:
                logger.debug(f"Could not restore terminal settings: {e}")

    def get_key(self, timeout: float = 0.0) -> str:
        """Poll for a single key press within timeout seconds."""
        if not self.is_raw or not HAS_TERMIOS:
            time.sleep(timeout)
            return ""

        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            key = sys.stdin.read(1)
            # Handle escape sequences
            if key == '\x1b':
                r2, _, _ = select.select([sys.stdin], [], [], 0.001)
                if r2:
                    seq = sys.stdin.read(2)
                    return '\x1b' + seq
                return '\x1b'
            return key
        return ""

def get_term_size():
    try:
        size = os.get_terminal_size()
        return size.columns, size.lines
    except OSError:
        return 80, 24

def play_animation(asciigif_path: str, loop_count: int = -1, override_fps: float = None):
    if not os.path.exists(asciigif_path):
        print(f"Error: Animation file '{asciigif_path}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        package = load_asciigif(asciigif_path)
    except (gzip.BadGzipFile, json.JSONDecodeError, OSError, UnicodeDecodeError, KeyError) as e:
        logger.error(f"Error loading '.asciigif' package '{asciigif_path}': {e}")
        print(f"Error loading '.asciigif' package: {e}", file=sys.stderr)
        sys.exit(1)

    frames = package.get("frames", [])
    if not frames:
        print("Error: Package contains no animation frames.", file=sys.stderr)
        sys.exit(1)

    pkg_w = package.get("width", 80)
    pkg_h = package.get("height", 24)
    term_cols, term_rows = get_term_size()

    if pkg_w > term_cols:
        print(f"\033[33mWarning: Animation width ({pkg_w} chars) exceeds terminal width ({term_cols} cols).")
        print(f"To avoid broken line wrapping, consider converting with '-w {term_cols}' or enlarging your terminal.\033[0m")
        time.sleep(1.5)

    term = TerminalController()

    old_sigint = signal.getsignal(signal.SIGINT)
    old_sigterm = signal.getsignal(signal.SIGTERM)

    def sig_handler(sig=None, frame=None):
        term.restore()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
    except (ValueError, OSError):
        pass

    atexit.register(term.restore)
    term.setup_raw()

    # Clear screen initially
    sys.stdout.write("\033[2J")
    sys.stdout.flush()

    current_frame_idx = 0
    paused = False
    speed_multiplier = 1.0
    loops_completed = 0

    try:
        while True:
            if loop_count > 0 and loops_completed >= loop_count:
                break

            frame_data = frames[current_frame_idx]
            base_delay_ms = frame_data.get("delay_ms", 100)

            if override_fps and override_fps > 0:
                target_delay_sec = (1.0 / override_fps) / speed_multiplier
            else:
                target_delay_sec = (base_delay_ms / 1000.0) / speed_multiplier

            # Prepare frame content
            content = frame_data["content"]

            # Status overlay line
            status = (
                f"\033[0m\r[Frame {current_frame_idx + 1}/{len(frames)}] "
                f"[{'PAUSED' if paused else 'PLAYING'}] "
                f"Speed: {speed_multiplier:.1f}x | "
                f"[Space] Pause | [+/-] Speed | [R] Reset | [Q] Quit\033[K"
            )

            # Render frame at home position (\033[H)
            # \033[J clears screen from cursor to end, eliminating ghosting from taller/wider previous frames
            buffer = "\033[H" + content + "\r\n" + status + "\033[J"
            sys.stdout.write(buffer)
            sys.stdout.flush()

            # Handle timing and keyboard events during frame delay
            frame_start = time.perf_counter()
            quit_playback = False

            while True:
                elapsed = time.perf_counter() - frame_start
                remaining = target_delay_sec - elapsed
                if remaining <= 0 and not paused:
                    break

                poll_time = max(0.01, remaining) if not paused else 0.1
                key = term.get_key(timeout=poll_time)

                if key in ['q', 'Q', '\x1b', '\x03']:  # 'q', ESC, or Ctrl+C
                    quit_playback = True
                    break
                elif key == ' ':
                    paused = not paused
                elif key in ['+', '=']:
                    speed_multiplier = min(5.0, round(speed_multiplier + 0.2, 1))
                elif key in ['-', '_']:
                    speed_multiplier = max(0.2, round(speed_multiplier - 0.2, 1))
                elif key in ['r', 'R']:
                    current_frame_idx = 0
                    sys.stdout.write("\033[2J")  # Clear screen on reset
                    break

            if quit_playback:
                break

            if not paused:
                current_frame_idx += 1
                if current_frame_idx >= len(frames):
                    current_frame_idx = 0
                    loops_completed += 1
    finally:
        term.restore()
        try:
            signal.signal(signal.SIGINT, old_sigint)
            signal.signal(signal.SIGTERM, old_sigterm)
        except (ValueError, OSError):
            pass

def main():
    parser = argparse.ArgumentParser(
        description="Interactive terminal player for .asciigif animation packages."
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to .asciigif animation file"
    )
    parser.add_argument(
        "-l", "--loop",
        type=int,
        default=-1,
        help="Number of loop iterations (-1 for infinite loop) (default: -1)"
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Override playback FPS rate"
    )
    args = parser.parse_args()
    play_animation(args.input, loop_count=args.loop, override_fps=args.fps)

if __name__ == "__main__":
    main()
