"""
Utility module for gif2ascii core engine: image processing, ASCII/Unicode rendering,
color encoding, transparency handling, and .asciigif file serialization.
"""

import gzip
import json
import logging
import math
import os
import sys
from typing import Dict, List, Tuple, Any
from PIL import Image

_LOGGER_NAME = "gif2ascii"

def get_logger() -> logging.Logger:
    """Returns the package-level logger for gif2ascii."""
    return logging.getLogger(_LOGGER_NAME)

def setup_logging(verbose: bool = False):
    """Configures root stream handler for gif2ascii directing to sys.stderr."""
    logger = get_logger()
    level = logging.DEBUG if verbose else logging.WARNING
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter("[gif2ascii %(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)


# ASCII Density Ramp (from darkest to brightest for dark terminal backgrounds)
RAMP_STANDARD = " .:-=+*#%@"
RAMP_EXTENDED = " .'`^\",:;Il!i>~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

def rgb_to_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance using standard perceptual weights."""
    return 0.299 * r + 0.587 * g + 0.114 * b

def rgb_to_ansi_truecolor(r: int, g: int, b: int, is_bg: bool = False) -> str:
    """Generate 24-bit ANSI TrueColor escape sequence."""
    code = 48 if is_bg else 38
    return f"\033[{code};2;{r};{g};{b}m"

def rgb_to_ansi_256(r: int, g: int, b: int, is_bg: bool = False) -> str:
    """Map RGB tuple to 256-color ANSI code."""
    code = 48 if is_bg else 38
    if r == g == b:
        if r < 8:
            color_idx = 16
        elif r > 248:
            color_idx = 231
        else:
            color_idx = 232 + int(((r - 8) / 247) * 24)
    else:
        r_idx = int(r / 255 * 5 + 0.5)
        g_idx = int(g / 255 * 5 + 0.5)
        b_idx = int(b / 255 * 5 + 0.5)
        color_idx = 16 + 36 * r_idx + 6 * g_idx + b_idx
    return f"\033[{code};5;{color_idx}m"

RESET_ANSI = "\033[0m"
RESET_BG = "\033[49m"
CLEAR_TO_EOL = "\033[K"

def frame_to_ascii(
    frame: Image.Image,
    target_width: int,
    mode: str = "ascii",
    color_mode: str = "truecolor",
    font_aspect_ratio: float = 0.5,
    bg_color: Tuple[int, int, int] = None
) -> Tuple[str, int, int]:
    """
    Convert a single PIL Image frame (RGBA) into an ANSI ASCII/Unicode string buffer.
    
    Supports alpha channel transparency: if bg_color is None, transparent pixels
    let terminal background show through.
    """
    orig_w, orig_h = frame.size
    
    if mode == "blocks":
        # Each character cell renders 2 vertical pixels via half blocks ('▀', '▄', ' ')
        target_height = int(orig_h * (target_width / orig_w) * font_aspect_ratio * 2)
        if target_height % 2 != 0:
            target_height += 1
    else:
        target_height = int(orig_h * (target_width / orig_w) * font_aspect_ratio)
    
    target_width = max(1, target_width)
    target_height = max(1, target_height)
    
    resized = frame.resize((target_width, target_height), Image.Resampling.LANCZOS)
    rgba_im = resized.convert("RGBA")
    pixels = rgba_im.load()
    
    lines = []
    
    if mode == "blocks":
        for y in range(0, target_height, 2):
            line_buf = []
            prev_fg = None
            prev_bg = None
            for x in range(target_width):
                r1, g1, b1, a1 = pixels[x, y]
                r2, g2, b2, a2 = pixels[x, y + 1] if (y + 1 < target_height) else (0, 0, 0, 0)
                
                # Check transparency (alpha < 128)
                top_visible = (a1 >= 128)
                bot_visible = (a2 >= 128)
                
                if bg_color is not None:
                    # Fill background color for transparent pixels
                    if not top_visible:
                        r1, g1, b1 = bg_color
                        top_visible = True
                    if not bot_visible:
                        r2, g2, b2 = bg_color
                        bot_visible = True

                char_seq = ""
                
                if not top_visible and not bot_visible:
                    # Fully transparent cell -> space with reset bg
                    if prev_bg != "reset":
                        char_seq += RESET_BG
                        prev_bg = "reset"
                    prev_fg = None
                    char_seq += " "
                elif top_visible and not bot_visible:
                    # Top pixel only -> '▀' with fg=top, no bg
                    if color_mode == "truecolor":
                        fg_ansi = rgb_to_ansi_truecolor(r1, g1, b1, is_bg=False)
                    elif color_mode == "256":
                        fg_ansi = rgb_to_ansi_256(r1, g1, b1, is_bg=False)
                    else:
                        fg_ansi = ""
                    
                    if fg_ansi != prev_fg:
                        char_seq += fg_ansi
                        prev_fg = fg_ansi
                    if prev_bg != "reset":
                        char_seq += RESET_BG
                        prev_bg = "reset"
                    char_seq += "▀"
                elif not top_visible and bot_visible:
                    # Bottom pixel only -> '▄' with fg=bottom, no bg
                    if color_mode == "truecolor":
                        fg_ansi = rgb_to_ansi_truecolor(r2, g2, b2, is_bg=False)
                    elif color_mode == "256":
                        fg_ansi = rgb_to_ansi_256(r2, g2, b2, is_bg=False)
                    else:
                        fg_ansi = ""
                    
                    if fg_ansi != prev_fg:
                        char_seq += fg_ansi
                        prev_fg = fg_ansi
                    if prev_bg != "reset":
                        char_seq += RESET_BG
                        prev_bg = "reset"
                    char_seq += "▄"
                else:
                    # Both top and bottom pixels visible -> '▀' with fg=top, bg=bottom
                    if color_mode == "truecolor":
                        fg_ansi = rgb_to_ansi_truecolor(r1, g1, b1, is_bg=False)
                        bg_ansi = rgb_to_ansi_truecolor(r2, g2, b2, is_bg=True)
                    elif color_mode == "256":
                        fg_ansi = rgb_to_ansi_256(r1, g1, b1, is_bg=False)
                        bg_ansi = rgb_to_ansi_256(r2, g2, b2, is_bg=True)
                    else:
                        fg_ansi = ""
                        bg_ansi = ""
                    
                    if fg_ansi != prev_fg:
                        char_seq += fg_ansi
                        prev_fg = fg_ansi
                    if bg_ansi != prev_bg:
                        char_seq += bg_ansi
                        prev_bg = bg_ansi
                    char_seq += "▀"
                
                line_buf.append(char_seq)
            
            line_str = "".join(line_buf)
            if color_mode != "mono":
                line_str += RESET_ANSI
            line_str += CLEAR_TO_EOL
            lines.append(line_str)
            
        final_height = target_height // 2
    else:
        # Standard ASCII density ramp mode
        ramp = RAMP_EXTENDED
        ramp_len = len(ramp)
        
        for y in range(target_height):
            line_buf = []
            prev_fg = None
            for x in range(target_width):
                r, g, b, a = pixels[x, y]
                
                if a < 128 and bg_color is None:
                    # Transparent pixel
                    if prev_fg is not None:
                        line_buf.append(RESET_ANSI)
                        prev_fg = None
                    line_buf.append(" ")
                    continue
                elif a < 128 and bg_color is not None:
                    r, g, b = bg_color
                    
                lum = rgb_to_luminance(r, g, b)
                char_idx = int((lum / 255.0) * (ramp_len - 1))
                char = ramp[char_idx]
                
                if color_mode == "truecolor":
                    fg_ansi = rgb_to_ansi_truecolor(r, g, b, is_bg=False)
                elif color_mode == "256":
                    fg_ansi = rgb_to_ansi_256(r, g, b, is_bg=False)
                else:
                    fg_ansi = ""
                
                char_seq = ""
                if fg_ansi != prev_fg:
                    char_seq += fg_ansi
                    prev_fg = fg_ansi
                char_seq += char
                line_buf.append(char_seq)
            
            line_str = "".join(line_buf)
            if color_mode != "mono":
                line_str += RESET_ANSI
            line_str += CLEAR_TO_EOL
            lines.append(line_str)
            
        final_height = target_height
        
    return "\r\n".join(lines), target_width, final_height

def save_asciigif(data: Dict[str, Any], output_path: str) -> None:
    """Serialize dictionary payload to gzipped JSON format (.asciigif)."""
    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    json_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
    compressed = gzip.compress(json_bytes)
    with open(output_path, "wb") as f:
        f.write(compressed)

def load_asciigif(input_path: str) -> Dict[str, Any]:
    """Decompress and parse a .asciigif file."""
    with open(input_path, "rb") as f:
        compressed = f.read()
    decompressed = gzip.decompress(compressed)
    return json.loads(decompressed.decode('utf-8'))
