"""
presets.py - Persistent preset manager for gif2ascii.
Stores built-in defaults and user-created custom presets in ~/.config/gif2ascii/presets.json.
"""

import os
import json
from typing import Dict, Any, List
from utils import get_logger

logger = get_logger()

CONFIG_DIR = os.path.expanduser("~/.config/gif2ascii")
PRESETS_FILE = os.path.join(CONFIG_DIR, "presets.json")

BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "pixel-art": {
        "name": "Pixel Art",
        "description": "Optimal for retro games and sprites (Isaac, Mario). Half-blocks, width 50, TrueColor, transparent BG.",
        "mode": "blocks",
        "width": 50,
        "color": "truecolor",
        "black_bg": False,
        "speed": 1.0,
        "is_builtin": True
    },
    "hd": {
        "name": "HD / High Detail",
        "description": "Full terminal width rendering with half-blocks for complex animations and movies.",
        "mode": "blocks",
        "width": "auto",
        "color": "truecolor",
        "black_bg": False,
        "speed": 1.0,
        "is_builtin": True
    },
    "retro-matrix": {
        "name": "Retro Matrix",
        "description": "Classic terminal ASCII density ramp with monochromatic style.",
        "mode": "ascii",
        "width": 80,
        "color": "mono",
        "black_bg": False,
        "speed": 1.0,
        "is_builtin": True
    },
    "mono": {
        "name": "Mono Standard",
        "description": "Simple 60-character ASCII density ramp without colors.",
        "mode": "ascii",
        "width": 60,
        "color": "mono",
        "black_bg": False,
        "speed": 1.0,
        "is_builtin": True
    }
}

class PresetManager:
    def __init__(self, config_file: str = PRESETS_FILE):
        self.config_file = config_file
        self.config_dir = os.path.dirname(config_file)
        self.ensure_config_dir()

    def ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)

    def load_user_presets(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(self.config_file):
            return {}
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load user presets from '{self.config_file}': {e}")
            return {}

    def save_user_presets(self, presets: Dict[str, Dict[str, Any]]):
        self.ensure_config_dir()
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.warning(f"Failed to save user presets to '{self.config_file}': {e}")

    def get_all_presets(self) -> Dict[str, Dict[str, Any]]:
        """Return combined dict of built-in and user custom presets."""
        presets = {}
        # Load built-ins
        for key, val in BUILTIN_PRESETS.items():
            presets[key] = val.copy()
            
        # Merge user custom presets (overriding or extending)
        user_presets = self.load_user_presets()
        for key, val in user_presets.items():
            val["is_builtin"] = False
            presets[key] = val
            
        return presets

    def get_preset(self, key: str) -> Dict[str, Any]:
        all_p = self.get_all_presets()
        if key in all_p:
            return all_p[key]
        return BUILTIN_PRESETS["pixel-art"].copy()

    def add_preset(
        self,
        key: str,
        name: str,
        description: str,
        mode: str = "blocks",
        width: Any = "auto",
        color: str = "truecolor",
        black_bg: bool = False,
        speed: float = 1.0
    ) -> bool:
        """Add or update a custom user preset."""
        user_presets = self.load_user_presets()
        key_slug = key.lower().replace(" ", "-")
        user_presets[key_slug] = {
            "name": name,
            "description": description,
            "mode": mode,
            "width": width,
            "color": color,
            "black_bg": black_bg,
            "speed": speed,
            "is_builtin": False
        }
        self.save_user_presets(user_presets)
        return True

    def delete_preset(self, key: str) -> bool:
        """Delete a user custom preset (built-ins cannot be deleted)."""
        user_presets = self.load_user_presets()
        if key in user_presets:
            del user_presets[key]
            self.save_user_presets(user_presets)
            return True
        return False
