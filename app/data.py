"""Cobra LANs – data loading and file-system utilities."""

import sys
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
            allowed = {str(n) for n in (filter_data.get("games") or [])}
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


def load_download_url() -> str | None:
    """Return the ``download_url`` value from games.yaml, or *None* if unset."""
    if not YAML_PATH.exists():
        return None
    with open(YAML_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    url = data.get("download_url", "")
    return url if url else None


def save_download_url(url: str) -> None:
    """Persist *url* as ``download_url`` in games.yaml."""
    with open(YAML_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data["download_url"] = url
    with open(YAML_PATH, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, allow_unicode=True, sort_keys=False)


def missing_installer_files(games: list[dict]) -> list[str]:
    """Return the names of games whose installer file does not exist locally."""
    missing: list[str] = []
    for game in games:
        bp = _base_path(game)
        installer_type = game.get("installer_type", "msi")
        if installer_type == "inno_setup":
            rel = game.get("install_exe", "")
        else:
            rel = game.get("install_msi", "")
        if rel and not (bp / rel).exists():
            missing.append(game["name"])
    return missing
