# User-level settings backed by config/usersettings.yaml.
#
# Settings are loaded once at import time.  Call save() to persist
# one or more changes and keep the in-memory values in sync.

import sys
from pathlib import Path

import yaml

from . import locate_yaml

_DEFAULTS: dict = {
    "disable_game_sync": False,
    "disable_downloads": False,
    "download_only":     False,
    "games_filter":      "",
    "download_url":      None,
}


def _find_or_create_settings_path() -> Path:
    """Return the path to config/usersettings.yaml, creating it if needed."""
    found = locate_yaml("usersettings.yaml")
    if found:
        return found

    candidates = [
        Path.cwd() / "config" / "usersettings.yaml",
        Path(sys.executable).resolve().parent / "config" / "usersettings.yaml",
        Path(__file__).parent.parent / "config" / "usersettings.yaml",
    ]
    for p in candidates:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                yaml.dump(_DEFAULTS, fh, allow_unicode=True, sort_keys=False)
            return p
        except OSError:
            continue
    return candidates[-1]


SETTINGS_PATH: Path = _find_or_create_settings_path()

# ── Load settings ──────────────────────────────────────────────────────────────

_data: dict = dict(_DEFAULTS)
try:
    with open(SETTINGS_PATH, "r", encoding="utf-8") as _fh:
        _loaded = yaml.safe_load(_fh) or {}
    _data.update({k: _loaded[k] for k in _DEFAULTS if k in _loaded})
except Exception:
    pass

disable_game_sync: bool       = bool(_data["disable_game_sync"])
disable_downloads: bool       = bool(_data["disable_downloads"])
download_only:     bool       = bool(_data["download_only"])
games_filter:      str        = str(_data["games_filter"] or "")
download_url:      str | None = _data["download_url"] or None


def save(**kwargs) -> None:
    """Update one or more settings in memory and write to SETTINGS_PATH."""
    global disable_game_sync, disable_downloads, download_only, games_filter, download_url

    current = {
        "disable_game_sync": disable_game_sync,
        "disable_downloads": disable_downloads,
        "download_only":     download_only,
        "games_filter":      games_filter,
        "download_url":      download_url,
    }
    current.update(kwargs)

    disable_game_sync = bool(current["disable_game_sync"])
    disable_downloads = bool(current["disable_downloads"])
    download_only     = bool(current["download_only"])
    games_filter      = str(current["games_filter"] or "")
    download_url      = current["download_url"] or None

    with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
        yaml.dump(current, fh, allow_unicode=True, sort_keys=False)
