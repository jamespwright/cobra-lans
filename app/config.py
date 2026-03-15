"""Cobra LANs – shared constants: paths, colour palette, fonts."""

import sys
import time
import urllib.request
from pathlib import Path

# ── Base path (works for both .py script and PyInstaller --onefile bundle) ─────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent   # project root (one level above app/)


def _locate_yaml(file_name: str) -> Path | None:
    """Return the path to a YAML file (e.g., `config/filter.yaml` or `config/games.yaml`).

    Checks the local YAML file for a ``sync_from_github`` flag (default
    ``True``). When enabled, downloads the latest version from GitHub,
    overwriting the local copy. If the download fails (network error,
    etc.) or sync is disabled, falls back to the first existing local
    candidate.

    Applies the same search order as the original `_locate_games_yaml`.
    """
    candidates = [
        Path.cwd() / "config" / file_name,
        Path(sys.executable).resolve().parent / "config" / file_name,
        Path(__file__).parent.parent / "config" / file_name,
    ]

    # Check whether GitHub sync is enabled in user settings
    from . import usersettings as _us  # local import avoids circular dependency at module level
    if not _us.disable_game_sync:
        save_to = candidates[0]  # Default to the first candidate for saving
        urls = [
            "https://raw.githubusercontent.com/jamespwright/cobra-lans/refs/heads/main/config/filter.yaml",
            "https://raw.githubusercontent.com/jamespwright/cobra-lans/refs/heads/main/config/games.yaml",
        ]
        if _download_yaml_files(save_to, urls):
            return save_to

    # Sync disabled or download failed – fall back to any existing local copy
    for p in candidates:
        if p.exists():
            return p
    return None

def _download_yaml_files(dest: Path, urls: list[str]) -> bool:
    """Download multiple YAML files from GitHub into *dest*.

    Returns True if all downloads succeed, False otherwise.
    """
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        for url in urls:
            bust = int(time.time())
            full_url = f"{url}?_={bust}"
            req = urllib.request.Request(
                full_url,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req) as response:
                file_name = url.split('/')[-1]  # Extract file name from URL
                (dest.parent / file_name).write_bytes(response.read())
        return True
    except Exception:
        return False


FILTER_PATH: Path | None = _locate_yaml("filter.yaml")
GAMES_PATH: Path | None = _locate_yaml("games.yaml")


# ── Colour palette ─────────────────────────────────────────────────────────────
C: dict[str, str] = {
    "bg":         "#04040a",
    "surface":    "#07070f",
    "surface2":   "#0a0a16",
    "border":     "#0d2e28",
    "row_even":   "#07070f",
    "row_odd":    "#050510",
    "row_hover":  "#001c14",
    "header":     "#02020a",
    "cyan":       "#00ffe0",
    "magenta":    "#ff2d78",
    "green":      "#00ff88",
    "yellow":     "#ffcc00",
    "red":        "#ff4455",
    "text":       "#c8ffe8",
    "text_dim":   "#3a7060",
    "btn_bg":     "#cc1f5e",
    "btn_fg":     "#ffffff",
    "btn_hov":    "#ff2d78",
    "accent_dim": "#005544",
    "border_hi":  "#00ffe0",
    "cb_select":  "#002220",
    "entry_bg":   "#030308",
}

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT      = ("Courier New", 20)
FONT_BOLD = ("Courier New", 20, "bold")
FONT_HEAD = ("Courier New", 30, "bold")
