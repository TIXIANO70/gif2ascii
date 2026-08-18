#!/usr/bin/env python3
"""
tests/test_core.py - Core unit tests for gif2ascii.
Covers:
- Color math and ANSI escape sequences (TrueColor, 256 colors, luminance).
- ASCII / Unicode half-block rendering and transparency (frame_to_ascii).
- Binary .asciigif packaging and gzip serialization (save_asciigif, load_asciigif).
- PresetManager persistence, defaults, and custom CRUD operations.
- LibraryManager favorites, alias resolution, and history rotation.
"""

import os
import sys
import tempfile
import unittest
from PIL import Image

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils import (
    rgb_to_luminance,
    rgb_to_ansi_truecolor,
    rgb_to_ansi_256,
    frame_to_ascii,
    save_asciigif,
    load_asciigif,
    RESET_ANSI,
    RESET_BG,
    CLEAR_TO_EOL,
)
from presets import PresetManager, BUILTIN_PRESETS
from library import LibraryManager


class TestUtilsColorAndLuminance(unittest.TestCase):
    """Tests for color conversions and ANSI code generation in utils.py."""

    def test_rgb_to_luminance_standard_weights(self):
        """Verify ITU-R BT.601 luminance weights (0.299 R + 0.587 G + 0.114 B)."""
        # Black
        self.assertAlmostEqual(rgb_to_luminance(0, 0, 0), 0.0)
        # Pure Red
        self.assertAlmostEqual(rgb_to_luminance(255, 0, 0), 0.299 * 255)
        # Pure Green
        self.assertAlmostEqual(rgb_to_luminance(0, 255, 0), 0.587 * 255)
        # Pure Blue
        self.assertAlmostEqual(rgb_to_luminance(0, 0, 255), 0.114 * 255)
        # Pure White
        self.assertAlmostEqual(rgb_to_luminance(255, 255, 255), 255.0)

    def test_rgb_to_ansi_truecolor_foreground_and_background(self):
        """Verify 24-bit TrueColor ANSI escape sequences."""
        fg_code = rgb_to_ansi_truecolor(255, 128, 64, is_bg=False)
        self.assertEqual(fg_code, "\033[38;2;255;128;64m")

        bg_code = rgb_to_ansi_truecolor(10, 20, 30, is_bg=True)
        self.assertEqual(bg_code, "\033[48;2;10;20;30m")

    def test_rgb_to_ansi_256_grayscale(self):
        """Verify 256-color mapping for grayscale values (r == g == b)."""
        # Darkest range (< 8) -> index 16 (black)
        self.assertEqual(rgb_to_ansi_256(5, 5, 5, is_bg=False), "\033[38;5;16m")
        # Brightest range (> 248) -> index 231 (white)
        self.assertEqual(rgb_to_ansi_256(250, 250, 250, is_bg=False), "\033[38;5;231m")
        # Middle grayscale (e.g. 128) -> 232 + ((128-8)/247)*24 ~= 232 + 11 = 243
        bg_gray = rgb_to_ansi_256(128, 128, 128, is_bg=True)
        self.assertTrue(bg_gray.startswith("\033[48;5;"))

    def test_rgb_to_ansi_256_colors(self):
        """Verify 256-color cube mapping (6x6x6)."""
        # Pure red (255, 0, 0) -> r_idx=5, g_idx=0, b_idx=0 -> 16 + 36*5 = 196
        self.assertEqual(rgb_to_ansi_256(255, 0, 0, is_bg=False), "\033[38;5;196m")
        # Pure green (0, 255, 0) -> r_idx=0, g_idx=5, b_idx=0 -> 16 + 6*5 = 46
        self.assertEqual(rgb_to_ansi_256(0, 255, 0, is_bg=False), "\033[38;5;46m")
        # Pure blue (0, 0, 255) -> r_idx=0, g_idx=0, b_idx=5 -> 16 + 5 = 21
        self.assertEqual(rgb_to_ansi_256(0, 0, 255, is_bg=False), "\033[38;5;21m")


class TestFrameToAsciiRendering(unittest.TestCase):
    """Tests for frame_to_ascii image conversion and terminal character encoding."""

    def test_frame_to_ascii_blocks_truecolor(self):
        """Test half-block rendering with TrueColor colors."""
        # 10x10 image: Top half red, bottom half blue
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        for x in range(10):
            for y in range(5):
                img.putpixel((x, y), (255, 0, 0, 255))
            for y in range(5, 10):
                img.putpixel((x, y), (0, 0, 255, 255))

        content, width, height = frame_to_ascii(
            img,
            target_width=10,
            mode="blocks",
            color_mode="truecolor",
            font_aspect_ratio=0.5
        )

        self.assertEqual(width, 10)
        self.assertEqual(height, 5)
        self.assertIn("▀", content)
        # Should contain TrueColor escape codes for red fg (38;2;255;0;0) and blue bg (48;2;0;0;255)
        self.assertIn("\033[38;2;", content)
        self.assertIn(RESET_ANSI, content)
        self.assertIn(CLEAR_TO_EOL, content)

    def test_frame_to_ascii_blocks_transparency(self):
        """Test that fully transparent cells render as spaces with background reset."""
        img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        content, width, height = frame_to_ascii(
            img,
            target_width=8,
            mode="blocks",
            color_mode="truecolor",
            font_aspect_ratio=0.5
        )

        self.assertEqual(width, 8)
        self.assertEqual(height, 4)
        self.assertIn(" ", content)
        self.assertIn(RESET_BG, content)

    def test_frame_to_ascii_blocks_half_transparency(self):
        """Test top-only and bottom-only half block characters with transparency."""
        # Top pixel visible, bottom transparent -> '▀'
        img_top = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        for x in range(4):
            img_top.putpixel((x, 0), (255, 0, 0, 255))
            # y=1 remains alpha=0

        content_top, _, _ = frame_to_ascii(
            img_top,
            target_width=4,
            mode="blocks",
            color_mode="truecolor",
            font_aspect_ratio=0.5
        )
        self.assertIn("▀", content_top)

        # Top pixel transparent, bottom visible -> '▄'
        img_bot = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        for x in range(4):
            # y=0 remains alpha=0
            img_bot.putpixel((x, 1), (0, 255, 0, 255))

        content_bot, _, _ = frame_to_ascii(
            img_bot,
            target_width=4,
            mode="blocks",
            color_mode="truecolor",
            font_aspect_ratio=0.5
        )
        self.assertIn("▄", content_bot)

    def test_frame_to_ascii_blocks_with_custom_bg_color(self):
        """Test that bg_color fills transparent pixels."""
        img = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
        content, width, height = frame_to_ascii(
            img,
            target_width=6,
            mode="blocks",
            color_mode="truecolor",
            font_aspect_ratio=0.5,
            bg_color=(50, 50, 50)
        )
        self.assertEqual(width, 6)
        self.assertIn("\033[38;2;50;50;50m", content)
        self.assertIn("\033[48;2;50;50;50m", content)

    def test_frame_to_ascii_standard_ascii_mode(self):
        """Test standard ASCII density ramp mode."""
        # Gradient from black to white
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 255))
        for x in range(10):
            lum = int((x / 9.0) * 255)
            for y in range(10):
                img.putpixel((x, y), (lum, lum, lum, 255))

        content, width, height = frame_to_ascii(
            img,
            target_width=10,
            mode="ascii",
            color_mode="mono",
            font_aspect_ratio=0.5
        )
        self.assertEqual(width, 10)
        self.assertEqual(height, 5)
        # Mono mode should not have ANSI truecolor codes
        self.assertNotIn("\033[38;2;", content)

    def test_frame_to_ascii_256_color_mode(self):
        """Test frame conversion in 256-color palette mode."""
        img = Image.new("RGBA", (10, 10), (255, 128, 0, 255))
        content, _, _ = frame_to_ascii(
            img,
            target_width=10,
            mode="blocks",
            color_mode="256",
            font_aspect_ratio=0.5
        )
        self.assertIn("\033[38;5;", content)


class TestSerialization(unittest.TestCase):
    """Tests for .asciigif package compression, serialization and loading."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_asciigif_roundtrip(self):
        """Test full roundtrip compression/decompression of .asciigif payload."""
        sample_data = {
            "version": "1.0",
            "source": "sample_animation.gif",
            "width": 80,
            "height": 40,
            "frame_count": 2,
            "render_mode": "blocks",
            "color_mode": "truecolor",
            "frames": [
                {"index": 0, "delay_ms": 100, "content": "Frame 1 \033[38;2;255;0;0m▀\033[0m"},
                {"index": 1, "delay_ms": 120, "content": "Frame 2 \033[38;2;0;255;0m▀\033[0m"}
            ]
        }
        out_file = os.path.join(self.temp_dir.name, "test_output.asciigif")

        save_asciigif(sample_data, out_file)
        self.assertTrue(os.path.exists(out_file))

        loaded_data = load_asciigif(out_file)
        self.assertEqual(loaded_data, sample_data)
        self.assertEqual(loaded_data["frame_count"], 2)
        self.assertEqual(len(loaded_data["frames"]), 2)

    def test_save_asciigif_creates_parent_directories(self):
        """Test that save_asciigif creates parent directory structure if missing."""
        nested_path = os.path.join(self.temp_dir.name, "sub1", "sub2", "nested.asciigif")
        save_asciigif({"test": "data"}, nested_path)
        self.assertTrue(os.path.exists(nested_path))
        loaded = load_asciigif(nested_path)
        self.assertEqual(loaded, {"test": "data"})


class TestPresetManagerCore(unittest.TestCase):
    """Tests for PresetManager persistence and defaults."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "presets.json")
        self.pm = PresetManager(config_file=self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_builtin_presets_present(self):
        """Verify standard built-in presets exist."""
        all_presets = self.pm.get_all_presets()
        for expected in ["pixel-art", "hd", "retro-matrix", "mono"]:
            self.assertIn(expected, all_presets)
            self.assertTrue(all_presets[expected].get("is_builtin"))

    def test_get_preset_fallback(self):
        """Verify requesting unknown preset falls back to pixel-art."""
        p = self.pm.get_preset("non-existent-preset-key")
        self.assertEqual(p["mode"], "blocks")
        self.assertEqual(p["width"], 50)

    def test_add_and_get_custom_preset(self):
        """Verify adding a user custom preset persists and is loaded."""
        success = self.pm.add_preset(
            key="custom-gaming",
            name="Custom Gaming",
            description="High contrast test preset",
            mode="blocks",
            width=70,
            color="truecolor",
            black_bg=True,
            speed=1.2
        )
        self.assertTrue(success)

        # Verify in get_preset
        preset = self.pm.get_preset("custom-gaming")
        self.assertEqual(preset["name"], "Custom Gaming")
        self.assertEqual(preset["width"], 70)
        self.assertEqual(preset["black_bg"], True)
        self.assertFalse(preset["is_builtin"])

        # Verify persistent re-read
        new_pm = PresetManager(config_file=self.config_path)
        reloaded = new_pm.get_preset("custom-gaming")
        self.assertEqual(reloaded["name"], "Custom Gaming")

    def test_delete_custom_preset(self):
        """Verify deleting custom preset removes it from storage."""
        self.pm.add_preset("temp-preset", "Temp", "To delete")
        self.assertIn("temp-preset", self.pm.get_all_presets())

        deleted = self.pm.delete_preset("temp-preset")
        self.assertTrue(deleted)
        self.assertNotIn("temp-preset", self.pm.get_all_presets())

    def test_delete_builtin_preset_returns_false(self):
        """Verify built-in presets cannot be deleted."""
        result = self.pm.delete_preset("pixel-art")
        self.assertFalse(result)
        self.assertIn("pixel-art", self.pm.get_all_presets())


class TestLibraryManagerCore(unittest.TestCase):
    """Tests for LibraryManager favorites, alias resolution, and history rotation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "presets.json")
        self.pm = PresetManager(config_file=self.config_path)
        self.lm = LibraryManager(data_dir=self.temp_dir.name, preset_manager=self.pm)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_resolve_favorite_asciigif(self):
        """Verify adding an .asciigif file to library and resolving alias."""
        # Create dummy asciigif file
        dummy_src = os.path.join(self.temp_dir.name, "source.asciigif")
        save_asciigif({"version": "1.0", "frames": []}, dummy_src)

        added = self.lm.add_favorite(
            alias="isaac-test",
            gif_or_asciigif_path=dummy_src,
            preset_name="pixel-art",
            title="Isaac Sprite"
        )
        self.assertTrue(added)

        resolved_path = self.lm.resolve_alias("isaac-test")
        self.assertIsNotNone(resolved_path)
        self.assertTrue(os.path.exists(resolved_path))

    def test_resolve_alias_not_found(self):
        """Verify non-existent alias resolves to None."""
        self.assertIsNone(self.lm.resolve_alias("unknown_alias_123"))

    def test_remove_favorite(self):
        """Verify favorite removal cleans both index and disk."""
        dummy_src = os.path.join(self.temp_dir.name, "source2.asciigif")
        save_asciigif({"version": "1.0"}, dummy_src)

        self.lm.add_favorite("to-remove", dummy_src)
        resolved = self.lm.resolve_alias("to-remove")
        self.assertTrue(os.path.exists(resolved))

        removed = self.lm.remove_favorite("to-remove")
        self.assertTrue(removed)
        self.assertIsNone(self.lm.resolve_alias("to-remove"))
        self.assertFalse(os.path.exists(resolved))

    def test_add_to_history_prunes_to_max_10(self):
        """Verify history tracks recent animations and rotates to max 10 entries."""
        dummy_asciigif = os.path.join(self.temp_dir.name, "anim.asciigif")
        save_asciigif({"version": "1.0"}, dummy_asciigif)

        # Add 15 history entries
        for i in range(15):
            self.lm.add_to_history(
                gif_path=f"/fake/path/anim_{i}.gif",
                asciigif_path=dummy_asciigif,
                preset_name="pixel-art"
            )

        index = self.lm.load_index()
        history = index.get("history", [])
        self.assertEqual(len(history), 10)
        # Most recent should be anim_14
        self.assertEqual(history[0]["title"], "anim_14.asciigif")


if __name__ == "__main__":
    unittest.main()
