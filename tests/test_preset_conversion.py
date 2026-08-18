#!/usr/bin/env python3
"""
tests/test_preset_conversion.py - Unit tests for width calculation resolution and preset-based conversion pipeline.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

from gif2ascii import resolve_preset_width, convert_with_preset, DEFAULT_MAX_IMAGE_PIXELS
from utils import load_asciigif

class TestPresetConversion(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        Image.MAX_IMAGE_PIXELS = DEFAULT_MAX_IMAGE_PIXELS

    def tearDown(self):
        self.temp_dir.cleanup()
        Image.MAX_IMAGE_PIXELS = DEFAULT_MAX_IMAGE_PIXELS

    # --- resolve_preset_width tests ---

    def test_resolve_preset_width_int(self):
        self.assertEqual(resolve_preset_width(60), 60)
        self.assertEqual(resolve_preset_width(100, default_width=50), 100)

    def test_resolve_preset_width_str_numeric(self):
        self.assertEqual(resolve_preset_width("75"), 75)
        self.assertEqual(resolve_preset_width("42", default_width=80), 42)

    def test_resolve_preset_width_none_fallback_to_default(self):
        self.assertEqual(resolve_preset_width(None, default_width=64), 64)
        self.assertEqual(resolve_preset_width(None, default_width="55"), 55)

    @patch("os.get_terminal_size")
    def test_resolve_preset_width_auto_terminal(self, mock_term_size):
        mock_term_size.return_value = os.terminal_size((120, 40))
        self.assertEqual(resolve_preset_width("auto"), 120)
        self.assertEqual(resolve_preset_width("AUTO"), 120)
        self.assertEqual(resolve_preset_width(None, default_width="auto"), 120)

    @patch("os.get_terminal_size")
    def test_resolve_preset_width_auto_clamp_minimum(self, mock_term_size):
        mock_term_size.return_value = os.terminal_size((15, 40))
        self.assertEqual(resolve_preset_width("auto", min_cols=20), 20)

    @patch("os.get_terminal_size", side_effect=OSError("Inappropriate ioctl for device"))
    def test_resolve_preset_width_auto_oserror_fallback(self, mock_term_size):
        self.assertEqual(resolve_preset_width("auto"), 80)
        self.assertEqual(resolve_preset_width("auto", min_cols=20), 80)

    def test_resolve_preset_width_invalid_string_fallback(self):
        self.assertEqual(resolve_preset_width("invalid_value", default_width=50), 50)
        self.assertEqual(resolve_preset_width("not_a_number", default_width="65"), 65)

    # --- convert_with_preset tests ---

    @patch("gif2ascii.convert_gif")
    def test_convert_with_preset_delegates_preset_values(self, mock_convert_gif):
        preset_cfg = {
            "name": "Custom Test",
            "width": 65,
            "mode": "ascii",
            "color": "256",
            "speed": 1.5,
            "black_bg": True
        }
        
        convert_with_preset(
            input_path="/fake/input.gif",
            output_path="/fake/output.asciigif",
            preset_cfg=preset_cfg
        )

        mock_convert_gif.assert_called_once_with(
            input_path="/fake/input.gif",
            output_path="/fake/output.asciigif",
            width=65,
            mode="ascii",
            color_mode="256",
            speed=1.5,
            font_aspect_ratio=0.5,
            black_bg=True,
            allow_upscale=False,
            max_pixels=DEFAULT_MAX_IMAGE_PIXELS
        )

    @patch("gif2ascii.convert_gif")
    def test_convert_with_preset_overrides(self, mock_convert_gif):
        preset_cfg = {
            "name": "Base Preset",
            "width": 40,
            "mode": "blocks",
            "color": "truecolor",
            "speed": 1.0,
            "black_bg": False
        }

        convert_with_preset(
            input_path="/fake/input.gif",
            output_path="/fake/output.asciigif",
            preset_cfg=preset_cfg,
            override_width=90,
            override_mode="ascii",
            override_color="mono",
            allow_upscale=True,
            max_pixels=50_000_000
        )

        mock_convert_gif.assert_called_once_with(
            input_path="/fake/input.gif",
            output_path="/fake/output.asciigif",
            width=90,
            mode="ascii",
            color_mode="mono",
            speed=1.0,
            font_aspect_ratio=0.5,
            black_bg=False,
            allow_upscale=True,
            max_pixels=50_000_000
        )

    def test_convert_with_preset_integration_real_gif(self):
        # Create a small multi-frame test GIF
        gif_path = os.path.join(self.temp_dir.name, "test_sample.gif")
        out_path = os.path.join(self.temp_dir.name, "test_sample.asciigif")

        frames = [
            Image.new("RGBA", (30, 30), color=(255, 0, 0, 255)),
            Image.new("RGBA", (30, 30), color=(0, 255, 0, 255)),
            Image.new("RGBA", (30, 30), color=(0, 0, 255, 255))
        ]
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0
        )

        preset_cfg = {
            "name": "Integration Test Preset",
            "width": 25,
            "mode": "blocks",
            "color": "truecolor",
            "speed": 1.0,
            "black_bg": False
        }

        convert_with_preset(
            input_path=gif_path,
            output_path=out_path,
            preset_cfg=preset_cfg
        )

        self.assertTrue(os.path.exists(out_path))
        package = load_asciigif(out_path)
        self.assertEqual(package["frame_count"], 3)
        self.assertEqual(package["render_mode"], "blocks")
        self.assertEqual(package["color_mode"], "truecolor")
        self.assertEqual(package["width"], 25)

if __name__ == "__main__":
    unittest.main()
