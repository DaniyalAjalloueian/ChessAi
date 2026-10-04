"""Generic helpers shared across the application."""
from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    """Directory that contains the application (works when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(relative: str = "") -> Path:
    """Resolve a bundled resource, honouring PyInstaller's _MEIPASS."""
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base / relative if relative else base


def human_int(value: int | float | None) -> str:
    """Format a large integer compactly: 1234567 -> '1.23M'."""
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(number) >= limit:
            return f"{number / limit:.2f}{suffix}"
    return str(int(number))


def format_eval(cp: int | None, mate: int | None) -> str:
    """Format an evaluation for display (always White's point of view)."""
    if mate is not None:
        if mate == 0:
            return "#"
        return f"M{abs(mate)}" if mate > 0 else f"-M{abs(mate)}"
    if cp is None:
        return "0.00"
    return f"{cp / 100.0:+.2f}"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))