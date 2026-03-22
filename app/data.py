"""Cobra LANs – data loading and file-system utilities."""

from pathlib import Path

import yaml

from .config import BASE_DIR, _locate_yaml
from . import usersettings


def load_games() -> list[dict]:
    games_path = _locate_yaml("games.yaml")
    if games_path is None:
        return []
    with open(games_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    games = data.get("games", [])

    filter_path = _locate_yaml("filter.yaml")
    if filter_path is not None and usersettings.games_filter:
        with open(filter_path, "r", encoding="utf-8") as fh:
            filter_data = yaml.safe_load(fh) or {}
        filters = filter_data.get("filters") or []
        active = next((f for f in filters if f.get("name") == usersettings.games_filter), None)
        if active:
            allowed = {str(n) for n in (active.get("games") or [])}
            if allowed:
                games = [g for g in games if g.get("name") in allowed]

    return games


def load_filter_names() -> list[str]:
    filter_path = _locate_yaml("filter.yaml")
    if filter_path is None:
        return []
    try:
        with open(filter_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return [f["name"] for f in (data.get("filters") or []) if "name" in f]
    except Exception:
        return []


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
