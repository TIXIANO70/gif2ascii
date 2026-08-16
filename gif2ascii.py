#!/usr/bin/env python3
"""
gif2ascii.py - Convert animated GIFs into compressed ANSI ASCII animation packages (.asciigif)
"""

import sys
import os
import argparse
import time
from typing import List, Tuple
from PIL import Image, ImageSequence
from utils import frame_to_ascii, save_asciigif, get_logger

logger = get_logger()

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert animated GIF files into compressed ASCII art animation files (.asciigif)."
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to the input animated GIF file"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output .asciigif path (default: <input_name>.asciigif)"
    )
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=80,
        help="Target rendering width in terminal characters (default: 80)"
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["ascii", "blocks"],
        default="ascii",
        help="Rendering mode: 'ascii' (character density ramp) or 'blocks' (Unicode half-blocks ▀ ▄) (default: ascii)"
    )
    parser.add_argument(
        "-c", "--color",
        choices=["truecolor", "256", "mono"],
        default="truecolor",
        help="Color mode: 'truecolor' (24-bit RGB), '256' (256-color ANSI), or 'mono' (no color) (default: truecolor)"
    )
    parser.add_argument(
        "-s", "--speed",
        type=float,
        default=1.0,
        help="Speed multiplier for playback frame delay (e.g. 2.0 = 2x speed) (default: 1.0)"
    )
    parser.add_argument(
        "--aspect-ratio",
        type=float,
        default=0.5,
        help="Terminal font aspect ratio (height/width per character cell) (default: 0.5)"
    )
    parser.add_argument(
        "--black-bg",
        action="store_true",
        help="Fill transparent background pixels with solid black instead of terminal default background"
    )
    parser.add_argument(
        "--allow-upscale",
        action="store_true",
        help="Allow upscaling GIFs smaller than target width/preset instead of using native GIF resolution"
    )
    return parser.parse_args()

def extract_composited_frames(gif: Image.Image) -> List[Tuple[Image.Image, int]]:
    """
    Extract fully composited RGBA frames from GIF, respecting tile bounding boxes,
    alpha transparency, and frame disposal modes.
    """
    frames = []
    gif_w, gif_h = gif.size
    
    canvas = Image.new("RGBA", (gif_w, gif_h), (0, 0, 0, 0))
    prev_canvas = None
    prev_disposal = 0
    prev_tile_box = None

    for frame in ImageSequence.Iterator(gif):
        duration = frame.info.get("duration", 100)
        if duration <= 0:
            duration = 100
            
        disposal = getattr(frame, "disposal_method", frame.info.get("disposal", 0)) or 0

        # Handle disposal of the previous frame
        if prev_disposal == 2:
            # Restore to background (transparent)
            if prev_tile_box:
                clear_box = Image.new("RGBA", (prev_tile_box[2] - prev_tile_box[0], prev_tile_box[3] - prev_tile_box[1]), (0, 0, 0, 0))
                canvas.paste(clear_box, (prev_tile_box[0], prev_tile_box[1]))
            else:
                canvas = Image.new("RGBA", (gif_w, gif_h), (0, 0, 0, 0))
        elif prev_disposal == 3 and prev_canvas is not None:
            # Restore to previous canvas state
            canvas = prev_canvas.copy()

        prev_canvas = canvas.copy()
        prev_disposal = disposal

        frame_rgba = frame.convert("RGBA")
        
        tile_box = None
        if hasattr(frame, "tile") and frame.tile:
            try:
                tile = frame.tile[0]
                extents = tile[1]  # (left, top, right, bottom)
                tile_box = extents
            except (IndexError, ValueError, OSError, AttributeError) as e:
                logger.debug(f"Tile compositing fallback: {e}")
        
        prev_tile_box = tile_box

        # Paste current frame over canvas using its alpha channel as mask
        canvas.paste(frame_rgba, (0, 0), frame_rgba)

        frames.append((canvas.copy(), duration))

    return frames

def convert_gif(
    input_path: str,
    output_path: str,
    width: int,
    mode: str,
    color_mode: str,
    speed: float,
    font_aspect_ratio: float,
    black_bg: bool = False,
    allow_upscale: bool = False
):
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        gif = Image.open(input_path)
    except (Image.UnidentifiedImageError, OSError) as e:
        logger.error(f"Error opening GIF '{input_path}': {e}")
        print(f"Error opening GIF '{input_path}': {e}", file=sys.stderr)
        sys.exit(1)

    orig_w, orig_h = gif.size
    effective_width = width
    if not allow_upscale and width > orig_w:
        effective_width = orig_w
        print(f"Info: Input GIF width ({orig_w}px) is smaller than target width ({width}). Using native GIF width ({orig_w}).")

    print(f"Converting '{input_path}'...")
    print(f"Options: width={effective_width}, mode={mode}, color={color_mode}, speed={speed}x, black_bg={black_bg}")

    start_time = time.time()
    composited_frames = extract_composited_frames(gif)
    total_frames = len(composited_frames)

    bg_color = (0, 0, 0) if black_bg else None
    frames_data = []

    for idx, (frame_img, raw_delay) in enumerate(composited_frames):
        adjusted_delay = int(raw_delay / speed)
        
        ascii_content, calc_w, calc_h = frame_to_ascii(
            frame_img,
            target_width=effective_width,
            mode=mode,
            color_mode=color_mode,
            font_aspect_ratio=font_aspect_ratio,
            bg_color=bg_color
        )

        frames_data.append({
            "index": idx,
            "delay_ms": adjusted_delay,
            "content": ascii_content
        })

        sys.stdout.write(f"\rProcessing frame {idx + 1}/{total_frames}...")
        sys.stdout.flush()

    print()
    elapsed = time.time() - start_time

    package = {
        "version": "1.0",
        "source": os.path.basename(input_path),
        "width": calc_w,
        "height": calc_h,
        "frame_count": len(frames_data),
        "render_mode": mode,
        "color_mode": color_mode,
        "frames": frames_data
    }

    save_asciigif(package, output_path)
    file_size_kb = os.path.getsize(output_path) / 1024.0
    print(f"Successfully converted {len(frames_data)} frames in {elapsed:.2f}s!")
    print(f"Saved package to '{output_path}' ({file_size_kb:.1f} KB)")

def main():
    args = parse_args()
    if args.output is None:
        base, _ = os.path.splitext(args.input)
        args.output = f"{base}.asciigif"

    convert_gif(
        input_path=args.input,
        output_path=args.output,
        width=args.width,
        mode=args.mode,
        color_mode=args.color,
        speed=args.speed,
        font_aspect_ratio=args.aspect_ratio,
        black_bg=args.black_bg,
        allow_upscale=args.allow_upscale
    )

if __name__ == "__main__":
    main()
