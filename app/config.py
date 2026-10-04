"""Persistent application configuration stored as JSON."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

APP_NAME = "LocalChessAI"

DEFAULTS: Dict[str, Any] = {
    # Engine
    "stockfish_path": "",
    "threads": 2,
    "hash_mb": 128,
    # Appearance
    "board_theme": "Green",
    "piece_set": "Glyphs",
    # Sound
    "sound_enabled": True,
    "sound_volume": 0.6,
    # Play page
    "player_color": "White",
    "difficulty": "Medium",
    "thinking_time": "Unlimited",
    "engine_depth": 15,
    # Analysis
    "analysis_depth": 14,
    "analysis_multipv": 1,
    # Window
    "window_width": 1440,
    "window_height": 900,
}


def _config_dir() -> Path:
    """Return the per-user configuration directory on Windows."""
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home()
    directory = root / APP_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def config_dir() -> Path:
    """Public alias for the per-user configuration directory."""
    return _config_dir()


def sounds_dir() -> Path:
    """Location where synthesised sound files are cached."""
    directory = _config_dir() / "sounds"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class Config:
    """Small JSON-backed key/value store with sane defaults."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else _config_dir() / "config.json"
        self._data: Dict[str, Any] = dict(DEFAULTS)
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key, value in raw.items():
                    self._data[key] = value
        except (OSError, json.JSONDecodeError):
            self._data = dict(DEFAULTS)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            return self._data[key]
        if default is not None:
            return default
        return DEFAULTS.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, values: Dict[str, Any]) -> None:
        self._data.update(values)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self.save()