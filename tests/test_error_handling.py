"""
tests/test_error_handling.py - Unit tests for specific exception handling and logging.
"""

import os
import sys
import json
import logging
import tempfile
import unittest
from unittest.mock import patch

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils import get_logger, setup_logging
from presets import PresetManager, BUILTIN_PRESETS
from library import LibraryManager
from tui import get_gif_files

class TestErrorHandling(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.logger = get_logger()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_setup_logging_levels(self):
        """Test that setup_logging properly sets WARNING or DEBUG levels."""
        setup_logging(verbose=False)
        self.assertEqual(self.logger.level, logging.WARNING)

        setup_logging(verbose=True)
        self.assertEqual(self.logger.level, logging.DEBUG)

    def test_presets_load_corrupt_json(self):
        """Test that PresetManager handles corrupt JSON without crashing, logs a warning and returns {}."""
        corrupt_config = os.path.join(self.test_dir.name, "corrupt_presets.json")
        with open(corrupt_config, "w", encoding="utf-8") as f:
            f.write("{ invalid json content: 123, ")

        pm = PresetManager(config_file=corrupt_config)
        with self.assertLogs("gif2ascii", level="WARNING") as cm:
            user_presets = pm.load_user_presets()

        self.assertEqual(user_presets, {})
        self.assertTrue(any("Failed to load user presets" in msg for msg in cm.output))

        # Ensure built-ins are still available even if user presets file is corrupt
        all_presets = pm.get_all_presets()
        self.assertIn("pixel-art", all_presets)

    def test_presets_load_valid_json(self):
        """Test that PresetManager correctly loads valid user presets."""
        valid_config = os.path.join(self.test_dir.name, "presets.json")
        custom_data = {
            "custom-test": {
                "name": "Custom Test",
                "description": "Test preset",
                "mode": "blocks",
                "width": 60,
                "color": "truecolor",
                "black_bg": False,
                "speed": 1.0
            }
        }
        with open(valid_config, "w", encoding="utf-8") as f:
            json.dump(custom_data, f)

        pm = PresetManager(config_file=valid_config)
        user_presets = pm.load_user_presets()
        self.assertIn("custom-test", user_presets)
        self.assertEqual(user_presets["custom-test"]["name"], "Custom Test")

    def test_library_load_corrupt_json(self):
        """Test that LibraryManager handles corrupt library.json, logs a warning and returns default dict."""
        lib_data_dir = os.path.join(self.test_dir.name, "lib_data")
        os.makedirs(lib_data_dir, exist_ok=True)
        corrupt_index = os.path.join(lib_data_dir, "library.json")

        with open(corrupt_index, "w", encoding="utf-8") as f:
            f.write("MALFORMED JSON [[[")

        lm = LibraryManager(data_dir=lib_data_dir)
        with self.assertLogs("gif2ascii", level="WARNING") as cm:
            index = lm.load_index()

        self.assertEqual(index, {"favorites": {}, "history": []})
        self.assertTrue(any("Failed to load library index" in msg for msg in cm.output))

    def test_library_remove_favorite_missing_file(self):
        """Test removing a favorite whose target file was already deleted from disk."""
        lib_data_dir = os.path.join(self.test_dir.name, "lib_data")
        lm = LibraryManager(data_dir=lib_data_dir)

        # Manually write an index entry pointing to a non-existent file
        index = {
            "favorites": {
                "ghost": {
                    "alias": "ghost",
                    "title": "Ghost Animation",
                    "filename": "ghost_not_on_disk.asciigif",
                    "preset": "pixel-art"
                }
            },
            "history": []
        }
        lm.save_index(index)

        # Removing should cleanly succeed and remove from index
        result = lm.remove_favorite("ghost")
        self.assertTrue(result)
        updated_index = lm.load_index()
        self.assertNotIn("ghost", updated_index["favorites"])

    def test_tui_get_gif_files_oserror(self):
        """Test that get_gif_files() catches OSError and logs a warning."""
        with patch("os.listdir", side_effect=PermissionError("Permission denied")):
            with self.assertLogs("gif2ascii", level="WARNING") as cm:
                files = get_gif_files()
            self.assertEqual(files, [])
            self.assertTrue(any("Failed to scan directory" in msg for msg in cm.output))

    def test_play_animation_clean_quit(self):
        """Test that play_animation cleanly returns when 'q' is pressed without raising SystemExit."""
        import gzip
        asciigif_path = os.path.join(self.test_dir.name, "test.asciigif")
        package = {
            "version": "1.0",
            "source": "test.gif",
            "width": 10,
            "height": 5,
            "frame_count": 1,
            "render_mode": "blocks",
            "color_mode": "truecolor",
            "frames": [{"index": 0, "delay_ms": 100, "content": "test frame"}]
        }
        with open(asciigif_path, "wb") as f:
            f.write(gzip.compress(json.dumps(package).encode("utf-8")))

        from ascii_player import play_animation
        with patch("ascii_player.TerminalController.get_key", return_value="q"):
            # This should complete normally and not raise SystemExit or _curses.error
            play_animation(asciigif_path)

if __name__ == "__main__":
    unittest.main()
