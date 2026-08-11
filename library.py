"""
library.py - Persistent Animation Library and Recent History Manager.
Stores pre-converted .asciigif files and metadata index in ~/.local/share/gif2ascii/.
"""

import os
import json
import shutil
import time
from typing import Dict, Any, List, Optional
from gif2ascii import convert_gif
from presets import PresetManager

DATA_DIR = os.path.expanduser("~/.local/share/gif2ascii")
LIBRARY_DIR = os.path.join(DATA_DIR, "library")
INDEX_FILE = os.path.join(DATA_DIR, "library.json")

class LibraryManager:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.library_dir = os.path.join(data_dir, "library")
        self.index_file = os.path.join(data_dir, "library.json")
        self.ensure_dirs()

    def ensure_dirs(self):
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.library_dir, exist_ok=True)
        if not os.path.exists(self.index_file):
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump({"favorites": {}, "history": []}, f, indent=2)

    def load_index(self) -> Dict[str, Any]:
        try:
            if not os.path.exists(self.index_file):
                return {"favorites": {}, "history": []}
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "favorites" not in data:
                    data["favorites"] = {}
                if "history" not in data:
                    data["history"] = []
                return data
        except Exception:
            return {"favorites": {}, "history": []}

    def save_index(self, index_data: Dict[str, Any]):
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.library_dir, exist_ok=True)
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

    def resolve_alias(self, alias_or_path: str) -> Optional[str]:
        """
        Check if alias_or_path matches a saved favorite key.
        Returns the absolute filepath to the cached .asciigif file if found, else None.
        """
        index = self.load_index()
        alias_key = alias_or_path.lower().strip()
        favs = index.get("favorites", {})

        if alias_key in favs:
            file_name = favs[alias_key].get("filename")
            if file_name:
                target_path = os.path.join(self.library_dir, file_name)
                if os.path.exists(target_path):
                    return target_path
        return None

    def add_favorite(
        self,
        alias: str,
        gif_or_asciigif_path: str,
        preset_name: str = "pixel-art",
        title: Optional[str] = None
    ) -> bool:
        """Add or overwrite a favorite animation in the library."""
        if not os.path.exists(gif_or_asciigif_path):
            return False

        alias_key = alias.lower().strip().replace(" ", "-")
        target_filename = f"{alias_key}.asciigif"
        target_filepath = os.path.join(self.library_dir, target_filename)

        pm = PresetManager()
        preset_cfg = pm.get_preset(preset_name)

        # If source is already an .asciigif file, copy it directly
        if gif_or_asciigif_path.lower().endswith(".asciigif"):
            shutil.copy2(gif_or_asciigif_path, target_filepath)
        else:
            # Convert GIF directly to library storage
            width_setting = preset_cfg.get("width", 50)
            if str(width_setting).lower() == "auto":
                try:
                    term_cols = os.get_terminal_size().columns
                except Exception:
                    term_cols = 80
                width_val = max(20, term_cols)
            else:
                width_val = int(width_setting)

            convert_gif(
                input_path=gif_or_asciigif_path,
                output_path=target_filepath,
                width=width_val,
                mode=preset_cfg.get("mode", "blocks"),
                color_mode=preset_cfg.get("color", "truecolor"),
                speed=preset_cfg.get("speed", 1.0),
                font_aspect_ratio=0.5,
                black_bg=preset_cfg.get("black_bg", False)
            )

        index = self.load_index()
        display_title = title if title else alias.title()
        index["favorites"][alias_key] = {
            "alias": alias_key,
            "title": display_title,
            "filename": target_filename,
            "source_path": os.path.abspath(gif_or_asciigif_path),
            "preset": preset_name,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        self.save_index(index)
        return True

    def remove_favorite(self, alias: str) -> bool:
        """Remove a favorite animation from library and disk."""
        alias_key = alias.lower().strip()
        index = self.load_index()
        favs = index.get("favorites", {})

        if alias_key in favs:
            filename = favs[alias_key].get("filename")
            if filename:
                target_path = os.path.join(self.library_dir, filename)
                if os.path.exists(target_path):
                    try:
                        os.remove(target_path)
                    except Exception:
                        pass
            del favs[alias_key]
            index["favorites"] = favs
            self.save_index(index)
            return True
        return False

    def add_to_history(self, gif_path: str, asciigif_path: str, preset_name: str = "custom"):
        """Record a recently played animation in history (max 10 items)."""
        index = self.load_index()
        history = index.get("history", [])

        # Create history cached filename
        history_id = int(time.time())
        hist_filename = f"hist_{history_id}.asciigif"
        hist_filepath = os.path.join(self.library_dir, hist_filename)

        if os.path.exists(asciigif_path):
            try:
                shutil.copy2(asciigif_path, hist_filepath)
            except Exception:
                hist_filepath = asciigif_path

        base_title = os.path.splitext(os.path.basename(gif_path))[0]
        entry = {
            "title": f"{base_title}.asciigif",
            "source_path": os.path.abspath(gif_path),
            "filename": hist_filename,
            "preset": preset_name,
            "played_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Prepend to history list and trim to 10
        history.insert(0, entry)
        if len(history) > 10:
            old_item = history.pop()
            old_file = os.path.join(self.library_dir, old_item.get("filename", ""))
            if os.path.exists(old_file):
                try:
                    os.remove(old_file)
                except Exception:
                    pass

        index["history"] = history
        self.save_index(index)
