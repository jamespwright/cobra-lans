"""Cobra LANs – data loading and file-system utilities."""

import sys
import zlib
from pathlib import Path
from tkinter import messagebox

import yaml

from .config import BASE_DIR, FILTER_PATH, YAML_PATH


def load_games() -> list[dict]:
    """Load and return the games list from games.yaml.

    If ``config/filter.yaml`` exists its ``games`` list is treated as an
    allow-list of game names; only matching entries are returned.
    Exits on failure to read games.yaml.
    """
    if not YAML_PATH.exists():
        messagebox.showerror(
            "Error",
            (
                f"games.yaml not found:\n{YAML_PATH}\n\n"
                "Place a `config/games.yaml` next to the executable or in the current working directory."
            ),
        )
        sys.exit(1)
    with open(YAML_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    games = data.get("games", [])

    # Apply optional allow-list filter
    if FILTER_PATH is not None:
        with open(FILTER_PATH, "r", encoding="utf-8") as fh:
            filter_data = yaml.safe_load(fh) or {}
        if filter_data.get("enabled", True):
            allowed = {str(n) for n in filter_data.get("games", [])}
            if allowed:
                games = [g for g in games if g.get("name") in allowed]

    return games


def _base_path(game: dict) -> Path:
    """Return the absolute base installer directory for *game*."""
    bp = game.get("base_path", "")
    return BASE_DIR / bp if bp else BASE_DIR


def get_installer_folder(game: dict) -> Path:
    """Return the absolute path to the installer directory for *game*.

    ``base_path`` already points to the full installer subdirectory
    (e.g. ``Installers/Call Of Duty 4/Game``), so this simply resolves it.
    """
    return _base_path(game)


def _primary_installer_path(game: dict) -> Path | None:
    """Return the absolute path to the primary installer for *game*, or ``None``."""
    base = _base_path(game)
    rel  = game.get("install_exe") or game.get("install_msi") or ""
    return base / rel if rel else None


def _crc32_file(path: Path) -> str:
    """Return the CRC32 of *path* as an 8-char uppercase hex string (1 MB chunks)."""
    crc = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def verify_installer_crc(game: dict) -> tuple[str, str]:
    """
    Check the primary installer file using a CRC32 hash.

    Returns a ``(label, colour_key)`` pair for display in the UI where
    ``colour_key`` is one of ``"green"``, ``"red"``, ``"yellow"``, ``"text_dim"``.
    """
    installer    = _primary_installer_path(game)
    expected_crc = game.get("crc32", "").strip().upper()

    if installer is None:
        return "\u2014 no installer", "text_dim"

    if not installer.exists():
        return "\u2717 missing", "red"

    if not expected_crc:
        return "? no CRC", "text_dim"

    actual_crc = _crc32_file(installer)
    if actual_crc == expected_crc:
        return "\u2713 OK", "green"
    return "\u2717 mismatch", "yellow"


def folder_size_str(path: Path) -> str:
    """Return a human-readable size string for *path*, or '—' if absent/empty."""
    if not path.exists():
        return "\u2014"
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    if total == 0:
        return "\u2014"
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024.0:
            return f"{total:.1f} {unit}"
        total /= 1024.0
    return f"{total:.1f} TB"
