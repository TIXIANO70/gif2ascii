"""
test_tui.py - Unit tests for TUI lifecycle and curses suspension context manager.
"""

import unittest
from unittest.mock import MagicMock, patch
import curses
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tui import suspend_curses


class TestTUISuspendCurses(unittest.TestCase):
    """Tests for the suspend_curses context manager in tui.py."""

    @patch("curses.curs_set")
    @patch("curses.reset_prog_mode")
    @patch("curses.endwin")
    @patch("curses.def_prog_mode")
    def test_suspend_curses_normal_execution(
        self,
        mock_def_prog_mode,
        mock_endwin,
        mock_reset_prog_mode,
        mock_curs_set
    ):
        """Verify that curses program mode is suspended and safely restored on normal execution."""
        mock_stdscr = MagicMock()
        executed_inside = False

        with suspend_curses(mock_stdscr):
            executed_inside = True
            mock_def_prog_mode.assert_called_once()
            mock_endwin.assert_called_once()
            mock_reset_prog_mode.assert_not_called()
            mock_stdscr.clear.assert_not_called()

        self.assertTrue(executed_inside)
        mock_reset_prog_mode.assert_called_once()
        mock_stdscr.clear.assert_called_once()
        mock_curs_set.assert_called_once_with(0)

    @patch("curses.curs_set")
    @patch("curses.reset_prog_mode")
    @patch("curses.endwin")
    @patch("curses.def_prog_mode")
    def test_suspend_curses_restores_on_exception(
        self,
        mock_def_prog_mode,
        mock_endwin,
        mock_reset_prog_mode,
        mock_curs_set
    ):
        """Verify that curses program mode is restored even if an exception occurs inside the block."""
        mock_stdscr = MagicMock()

        with self.assertRaises(RuntimeError):
            with suspend_curses(mock_stdscr):
                raise RuntimeError("Simulated crash during animation or conversion")

        mock_def_prog_mode.assert_called_once()
        mock_endwin.assert_called_once()
        mock_reset_prog_mode.assert_called_once()
        mock_stdscr.clear.assert_called_once()
        mock_curs_set.assert_called_once_with(0)

    @patch("curses.curs_set")
    @patch("curses.reset_prog_mode")
    @patch("curses.endwin")
    @patch("curses.def_prog_mode")
    def test_suspend_curses_without_stdscr(
        self,
        mock_def_prog_mode,
        mock_endwin,
        mock_reset_prog_mode,
        mock_curs_set
    ):
        """Verify that suspend_curses operates correctly when stdscr is None."""
        with suspend_curses(None):
            pass

        mock_def_prog_mode.assert_called_once()
        mock_endwin.assert_called_once()
        mock_reset_prog_mode.assert_called_once()
        mock_curs_set.assert_not_called()

    @patch("curses.reset_prog_mode", side_effect=curses.error("Curses terminal reset failure"))
    @patch("curses.endwin")
    @patch("curses.def_prog_mode")
    def test_suspend_curses_handles_curses_error_gracefully(
        self,
        mock_def_prog_mode,
        mock_endwin,
        mock_reset_prog_mode
    ):
        """Verify that curses.error during teardown/restore is caught without crashing finally block."""
        mock_stdscr = MagicMock()
        # Should not raise curses.error
        with suspend_curses(mock_stdscr):
            pass

        mock_def_prog_mode.assert_called_once()
        mock_endwin.assert_called_once()
        mock_reset_prog_mode.assert_called_once()

    @patch("curses.curs_set")
    @patch("curses.reset_prog_mode")
    @patch("curses.endwin")
    @patch("curses.def_prog_mode")
    def test_suspend_curses_restores_on_system_exit(
        self,
        mock_def_prog_mode,
        mock_endwin,
        mock_reset_prog_mode,
        mock_curs_set
    ):
        """Verify that curses program mode is restored even if SystemExit is raised."""
        mock_stdscr = MagicMock()

        with self.assertRaises(SystemExit):
            with suspend_curses(mock_stdscr):
                sys.exit(1)

        mock_def_prog_mode.assert_called_once()
        mock_endwin.assert_called_once()
        mock_reset_prog_mode.assert_called_once()
        mock_stdscr.clear.assert_called_once()
        mock_curs_set.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
