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


def _locate_games_yaml() -> Path:
    """Return the best candidate path for `config/games.yaml`.

    Search order:
      1. Current working directory /config/games.yaml
      2. Directory next to the executable /config/games.yaml
      3. Project source `config/games.yaml` (fallback when running from source)
      4. Default: directory next to the executable (non-existing path)
    """
    candidates = []
    # 1) Working directory (useful when user runs exe from a folder)
    candidates.append(Path.cwd() / "config" / "games.yaml")
    # 2) Folder next to the executable (install location)
    try:
        exe_dir = Path(sys.executable).resolve().parent
    except Exception:
        exe_dir = BASE_DIR
    candidates.append(exe_dir / "config" / "games.yaml")
    # 3) Project source layout (developer mode)
    candidates.append(Path(__file__).parent.parent / "config" / "games.yaml")

    for p in candidates:
        if p.exists():
            return p
    # Default to exe-dir location if nothing exists (caller will handle missing file)
    return candidates[1]


YAML_PATH = _locate_games_yaml()


_FILTER_YAML_URL = (
    "https://raw.githubusercontent.com/jamespwright/cobra-lans/refs/heads/main/config/filter.yaml"
)


def _download_filter_yaml(dest: Path) -> bool:
    """Download filter.yaml from GitHub into *dest*.

    Returns True on success, False on any error without touching the filesystem.
    """
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        bust = int(time.time())
        url = f"{_FILTER_YAML_URL}?_={bust}"
        req = urllib.request.Request(
            url,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            },
        )
        with urllib.request.urlopen(req) as response:
            dest.write_bytes(response.read())
        return True
    except Exception:
        return False


def _locate_filter_yaml() -> Path | None:
    """Return the path to `config/filter.yaml`.

    Checks the local filter.yaml for a ``sync_from_github`` flag (default
    ``True``).  When enabled, downloads the latest version from GitHub,
    overwriting the local copy.  If the download fails (network error,
    etc.) or sync is disabled, falls back to the first existing local
    candidate.

    Applies the same search order as :func:`_locate_games_yaml`.
    """
    import yaml as _yaml  # local import to avoid circular issues at module level

    candidates = [
        Path.cwd() / "config" / "filter.yaml",
        Path(sys.executable).resolve().parent / "config" / "filter.yaml",
        Path(__file__).parent.parent / "config" / "filter.yaml",
    ]

    # Check whether the local copy opts out of GitHub sync
    sync_enabled = True
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as _fh:
                    _data = _yaml.safe_load(_fh) or {}
                sync_enabled = _data.get("sync_from_github", True)
            except Exception:
                pass
            break

    if sync_enabled:
        save_to = YAML_PATH.parent / "filter.yaml"
        if _download_filter_yaml(save_to):
            return save_to

    # Sync disabled or download failed – fall back to any existing local copy
    for p in candidates:
        if p.exists():
            return p
    return None


FILTER_PATH: Path | None = _locate_filter_yaml()

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
