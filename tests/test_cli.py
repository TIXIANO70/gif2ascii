#!/usr/bin/env python3
"""
tests/test_cli.py - Unit tests for CLI argument parsing and main command dispatcher.
"""

import os
import sys
import io
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cli import build_parser, main, __version__
from presets import PresetManager
from library import LibraryManager


class TestCLIParsing(unittest.TestCase):
    """Tests for CLI ArgumentParser definitions and option extraction."""

    def setUp(self):
        self.parser = build_parser()

    def test_version_argument(self):
        """Verify -V/--version flag raises SystemExit and shows version."""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            with self.assertRaises(SystemExit) as exit_ctx:
                self.parser.parse_args(["--version"])
            self.assertEqual(exit_ctx.exception.code, 0)
            self.assertIn(__version__, mock_out.getvalue())

    def test_parse_play_arguments(self):
        """Verify 'play' subcommand argument parsing."""
        args = self.parser.parse_args(["play", "isaac", "-p", "hd", "-w", "100", "-l", "3", "--fps", "24.0", "--max-pixels", "5000000"])
        self.assertEqual(args.subcommand, "play")
        self.assertEqual(args.input, "isaac")
        self.assertEqual(args.preset, "hd")
        self.assertEqual(args.width, "100")
        self.assertEqual(args.loop, 3)
        self.assertEqual(args.fps, 24.0)
        self.assertEqual(args.max_pixels, 5000000)

    def test_parse_convert_arguments(self):
        """Verify 'convert' subcommand argument parsing."""
        args = self.parser.parse_args(["convert", "input.gif", "-o", "out.asciigif", "-p", "retro-matrix", "-w", "80", "-m", "ascii", "-c", "mono", "--max-pixels", "0"])
        self.assertEqual(args.subcommand, "convert")
        self.assertEqual(args.input, "input.gif")
        self.assertEqual(args.output, "out.asciigif")
        self.assertEqual(args.preset, "retro-matrix")
        self.assertEqual(args.width, "80")
        self.assertEqual(args.mode, "ascii")
        self.assertEqual(args.color, "mono")
        self.assertEqual(args.max_pixels, 0)

    def test_parse_preset_subcommands(self):
        """Verify 'preset' actions: list, add, delete."""
        args_list = self.parser.parse_args(["preset", "list"])
        self.assertEqual(args_list.subcommand, "preset")
        self.assertEqual(args_list.preset_action, "list")

        args_add = self.parser.parse_args([
            "preset", "add", "my-preset",
            "--display-name", "My Cool Preset",
            "--desc", "Test custom preset",
            "--mode", "blocks",
            "--width", "64",
            "--color", "truecolor",
            "--black-bg"
        ])
        self.assertEqual(args_add.subcommand, "preset")
        self.assertEqual(args_add.preset_action, "add")
        self.assertEqual(args_add.name, "my-preset")
        self.assertEqual(args_add.display_name, "My Cool Preset")
        self.assertEqual(args_add.desc, "Test custom preset")
        self.assertEqual(args_add.mode, "blocks")
        self.assertEqual(args_add.width, "64")
        self.assertEqual(args_add.color, "truecolor")
        self.assertTrue(args_add.black_bg)

        args_del = self.parser.parse_args(["preset", "delete", "my-preset"])
        self.assertEqual(args_del.subcommand, "preset")
        self.assertEqual(args_del.preset_action, "delete")
        self.assertEqual(args_del.name, "my-preset")

    def test_parse_library_subcommands(self):
        """Verify 'library' actions: list, add, remove."""
        args_list = self.parser.parse_args(["library", "list"])
        self.assertEqual(args_list.subcommand, "library")
        self.assertEqual(args_list.lib_action, "list")

        args_add = self.parser.parse_args([
            "library", "add", "anim.gif",
            "-a", "isaac-boss",
            "-t", "Boss Animation",
            "-p", "pixel-art"
        ])
        self.assertEqual(args_add.subcommand, "library")
        self.assertEqual(args_add.lib_action, "add")
        self.assertEqual(args_add.input, "anim.gif")
        self.assertEqual(args_add.alias, "isaac-boss")
        self.assertEqual(args_add.title, "Boss Animation")
        self.assertEqual(args_add.preset, "pixel-art")

        args_rem = self.parser.parse_args(["library", "remove", "isaac-boss"])
        self.assertEqual(args_rem.subcommand, "library")
        self.assertEqual(args_rem.lib_action, "remove")
        self.assertEqual(args_rem.alias, "isaac-boss")

    def test_parse_uninstall_and_tui(self):
        """Verify 'uninstall' and 'tui' subcommands."""
        args_uninst = self.parser.parse_args(["uninstall", "--purge", "-y"])
        self.assertEqual(args_uninst.subcommand, "uninstall")
        self.assertTrue(args_uninst.purge)
        self.assertTrue(args_uninst.yes)

        args_tui = self.parser.parse_args(["tui"])
        self.assertEqual(args_tui.subcommand, "tui")


class TestCLIMainDispatcher(unittest.TestCase):
    """Tests for main() entry point execution and routing."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.preset_config = os.path.join(self.temp_dir.name, "presets.json")
        self.real_pm = PresetManager(config_file=self.preset_config)
        self.real_lm = LibraryManager(data_dir=self.temp_dir.name, preset_manager=self.real_pm)
        self.preset_patch = patch("cli.PresetManager", return_value=self.real_pm)
        self.lib_patch = patch("cli.LibraryManager", return_value=self.real_lm)
        self.preset_patch.start()
        self.lib_patch.start()

    def tearDown(self):
        self.preset_patch.stop()
        self.lib_patch.stop()
        self.temp_dir.cleanup()

    @patch("cli.run_tui_app")
    def test_main_no_arguments_launches_tui(self, mock_tui):
        """Test executing gif2ascii with no arguments launches interactive TUI."""
        with patch.object(sys, "argv", ["gif2ascii"]):
            main()
            mock_tui.assert_called_once()

    @patch("cli.play_animation")
    def test_main_play_alias_resolution(self, mock_play):
        """Test playing a library alias directly."""
        dummy_file = os.path.join(self.temp_dir.name, "source.asciigif")
        with open(dummy_file, "w") as f:
            f.write("dummy")
        self.real_lm.add_favorite(alias="isaac", gif_or_asciigif_path=dummy_file)

        with patch.object(sys, "argv", ["gif2ascii", "play", "isaac", "-l", "2"]):
            main()
            mock_play.assert_called_once()
            args, kwargs = mock_play.call_args
            self.assertTrue(args[0].endswith("isaac.asciigif"))
            self.assertEqual(kwargs["loop_count"], 2)

    @patch("cli.play_animation")
    def test_main_implicit_play_subcommand(self, mock_play):
        """Test that passing a filename directly without 'play' subcmd routes to play."""
        fake_asciigif = os.path.join(self.temp_dir.name, "direct.asciigif")
        with open(fake_asciigif, "w") as f:
            f.write("dummy")

        with patch.object(sys, "argv", ["gif2ascii", fake_asciigif]):
            main()
            mock_play.assert_called_once_with(fake_asciigif, loop_count=-1, override_fps=None)

    @patch("cli.convert_with_preset")
    def test_main_convert_file(self, mock_convert):
        """Test converting a GIF file via convert subcommand."""
        fake_gif = os.path.join(self.temp_dir.name, "source.gif")
        with open(fake_gif, "w") as f:
            f.write("dummy")
        target_asciigif = os.path.join(self.temp_dir.name, "target.asciigif")

        with patch.object(sys, "argv", ["gif2ascii", "convert", fake_gif, "-o", target_asciigif, "-p", "pixel-art"]):
            main()
            mock_convert.assert_called_once()
            _, kwargs = mock_convert.call_args
            self.assertEqual(kwargs["input_path"], fake_gif)
            self.assertEqual(kwargs["output_path"], target_asciigif)

    def test_main_preset_list_runs_without_error(self):
        """Test running 'preset list' outputs formatted preset catalog."""
        with patch.object(sys, "argv", ["gif2ascii", "preset", "list"]), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            main()
            output = mock_out.getvalue()
            self.assertIn("=== gif2ascii Presets ===", output)
            self.assertIn("pixel-art", output)
            self.assertIn("hd", output)


if __name__ == "__main__":
    unittest.main()
