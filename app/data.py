"""Cobra LANs – data loading and file-system utilities."""

import sys
from pathlib import Path
from tkinter import messagebox

import yaml

from .config import YAML_PATH


def load_games() -> list[dict]:
    """Load and return the games list from games.yaml; exits on failure."""
    if not YAML_PATH.exists():
        messagebox.showerror("Error", f"games.yaml not found:\n{YAML_PATH}")
        sys.exit(1)
    with open(YAML_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("games", [])


def folder_size_str(path: Path) -> str:
    """Return a human-readable size string for *path*, or '—' if absent/empty."""
    if not path.exists():
        return "—"
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    if total == 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024.0:
            return f"{total:.1f} {unit}"
        total /= 1024.0
    return f"{total:.1f} TB"
