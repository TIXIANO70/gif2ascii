# gif2ascii

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Terminal Support](https://img.shields.io/badge/terminal-TrueColor%2024bit-magenta.svg)](#features)

A high-performance, unified Python CLI application and interactive TUI studio designed to convert animated GIF images into compressed ANSI ASCII art packages (`.asciigif`) and play them smoothly inside terminal emulators with zero flicker, inspired by terminal classics like `asciiaquarium`.

---

## Key Features

- **Streamlined TUI Studio (`gif2ascii`)**:
  - Zero-dependency arrow-key terminal user interface.
  - Unified `Select GIF File` menu incorporating manual path entry, local directory GIFs, saved favorites, and recent history into a single screen.
- **1-Step Direct Playback**:
  - Simply run `gif2ascii sample.gif` or `gif2ascii isaac` to play instantly in one command.
- **Animation Library & Favorites**:
  - Store favorite animations in `~/.local/share/gif2ascii/library/` with custom alias shortcuts for **0ms instant playback**.
- **Persistent Custom Presets Manager**:
  - Saved in `~/.config/gif2ascii/presets.json`.
  - Built-in presets: `pixel-art`, `hd`, `retro-matrix`, `mono`.
  - Easily add, edit, or delete custom presets via TUI or CLI.
- **High-Fidelity Rendering Modes**:
  - **Unicode Half-Block Mode (`▀`, `▄`)**: Combines top and bottom pixel RGB values into single character cells to double vertical resolution.
  - **ASCII Density Ramp Mode**: Maps pixel luminance to character density gradients (`@%#*+=-:. `).
- **Pre-Packaged Isaac Gallery (`examples/TBOI/`)**:
  - Includes full 14-character sprite animations from *The Binding of Isaac* ready to play out of the box!

---

## Requirements & System Dependencies

`gif2ascii` requires **Python 3.8+** and the **Pillow** image processing library.

### 1. Install System Packages by OS

#### Arch Linux / Manjaro
```bash
sudo pacman -S python python-pillow python-pip git
```

#### Debian / Ubuntu / Pop!_OS / Linux Mint
```bash
sudo apt update
sudo apt install python3 python3-pip python3-pil git
```

#### Fedora / RHEL
```bash
sudo dnf install python3 python3-pip python3-pillow git
```

#### macOS (via Homebrew)
```bash
brew install python pillow git
```

---

### 2. Install `gif2ascii`

Clone the repository and install globally into your user environment:

```bash
git clone https://github.com/TIXIANO70/gif2ascii.git
cd gif2ascii
pip install --user --break-system-packages -e .
```

---

## Quickstart Guide

### 1. Interactive TUI Studio Menu

Run `gif2ascii` with no arguments to open the main TUI menu:

```bash
gif2ascii
```

Main Menu Options:
- `Select GIF File` `[sample.gif]` *(Unified selector: Custom path/alias, local GIFs, Favorites, & History)*
- `Select Preset` `[Pixel Art]`
- `PLAY ANIMATION NOW`
- `Export .asciigif Package`
- `Manage Custom Presets`
- `Exit`

---

### 2. 1-Step Direct Playback

```bash
# Play using default Pixel Art preset
gif2ascii sample.gif

# Play directly from library alias (0ms instant launch!)
gif2ascii isaac

# Play using a specific preset
gif2ascii play sample.gif --preset hd
```

---

### 3. Pre-Packaged Isaac Character Collection (`examples/TBOI/`)

`gif2ascii` comes with 14 pre-converted character animations from *The Binding of Isaac*:

```bash
# Play Isaac directly
gif2ascii play examples/TBOI/q1xhhsof1pe81.asciigif

# Play Azazel
gif2ascii play examples/TBOI/azazel.asciigif

# Play The Lost
gif2ascii play examples/TBOI/Lost.asciigif
```

---

### 4. Library & Preset Management CLI

```bash
# List all saved favorites and recent history
gif2ascii library list

# Save a GIF to library as alias
gif2ascii library add sample.gif --alias isaac --preset pixel-art

# List presets
gif2ascii preset list
```

---

## Interactive Player Keyboard Controls

While an animation is playing in your terminal:

- <kbd>Space</kbd> : **Pause / Play** toggle
- <kbd>+</kbd> / <kbd>=</kbd> : **Increase speed** (+0.2x)
- <kbd>-</kbd> / <kbd>_</kbd> : **Decrease speed** (-0.2x)
- <kbd>R</kbd> : **Restart** animation from frame 0
- <kbd>Q</kbd> / <kbd>ESC</kbd> / <kbd>Ctrl+C</kbd> : **Quit** cleanly (restores terminal cursor and settings)

---

## Contributing

Contributions are welcome! Please check [CONTRIBUTING.md](CONTRIBUTING.md) for details on submitting issues and pull requests.

---

## License

Distributed under the **GNU General Public License v3.0 (GPLv3)**. See [LICENSE](LICENSE) for more information.
