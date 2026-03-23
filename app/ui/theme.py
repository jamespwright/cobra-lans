# Visual constants: colour palette, fonts, and layout measurements.
#
# Single source of truth for every colour, font tuple, and sizing
# constant used across the UI layer.

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

FONT        = ("Courier New", 20)
FONT_BOLD   = ("Courier New", 20, "bold")
FONT_HEAD   = ("Courier New", 30, "bold")
FONT_SM     = ("Courier New", 15, "bold")
FONT_XS     = ("Courier New", 12)
FONT_STATUS = ("Courier New", 20)

SETTINGS_PANEL_W = 380
