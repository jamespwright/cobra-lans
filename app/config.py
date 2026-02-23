"""Cobra LANs – shared constants: paths, colour palette, fonts."""

import sys
from pathlib import Path

# ── Base path (works for both .py script and PyInstaller --onefile bundle) ─────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent   # project root (one level above app/)

YAML_PATH = BASE_DIR / "config" / "games.yaml"

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
