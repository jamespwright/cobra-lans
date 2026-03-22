# Game data loading and file-system utilities.
#
# Reads games.yaml and filter.yaml to produce the game list shown in the UI.
# Also provides helpers for resolving installer paths and computing folder sizes.

from pathlib import Path

import yaml

from . import BASE_DIR, locate_yaml
from . import settings


def load_games() -> list[dict]:
    """Load and optionally filter the game list from games.yaml."""
    games_path = locate_yaml("games.yaml")
    if games_path is None:
        return []
    with open(games_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    games = data.get("games", [])

    filter_path = locate_yaml("filter.yaml")
    if filter_path and settings.games_filter:
        with open(filter_path, "r", encoding="utf-8") as fh:
            filter_data = yaml.safe_load(fh) or {}
        filters = filter_data.get("filters") or []
        active = next((f for f in filters if f.get("name") == settings.games_filter), None)
        if active:
            allowed = {str(n) for n in (active.get("games") or [])}
            if allowed:
                games = [g for g in games if g.get("name") in allowed]

    return games


def load_filter_names() -> list[str]:
    """Return the list of filter names from filter.yaml."""
    filter_path = locate_yaml("filter.yaml")
    if filter_path is None:
        return []
    try:
        with open(filter_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return [f["name"] for f in (data.get("filters") or []) if "name" in f]
    except Exception:
        return []


def get_installer_folder(game: dict) -> Path:
    """Return the absolute path to the installer directory for *game*."""
    bp = game.get("base_path", "")
    return (BASE_DIR / bp) if bp else BASE_DIR


def folder_size_str(path: Path) -> str:
    """Return a human-readable size string for *path*, or '\u2014' if absent/empty."""
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


def missing_installer_files(games: list[dict]) -> list[str]:
    """Return names of games whose installer file doesn't exist locally."""
    missing: list[str] = []
    for game in games:
        bp = game.get("base_path", "")
        base = (BASE_DIR / bp) if bp else BASE_DIR
        installer_type = game.get("installer_type", "msi")
        rel = game.get("install_exe" if installer_type == "inno_setup" else "install_msi", "")
        if rel and not (base / rel).exists():
            missing.append(game["name"])
    return missing
