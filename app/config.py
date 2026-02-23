"""Cobra LANs – shared constants: paths, colour palette, fonts."""

import sys
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
