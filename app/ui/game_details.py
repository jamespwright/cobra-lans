# Game details panel – displays information for the currently selected game.
#
# Shows a banner placeholder, game title, description, and metadata
# fields.  Content is updated via show_game() when the user clicks
# a row in the adjacent game list.

import tkinter as tk

from .theme import C, FONT, FONT_BOLD, FONT_HEAD, FONT_SM
from .widgets import neon_line


class GameDetails(tk.Frame):
    """Right-side panel showing details for the selected game."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=C["surface"])

        # Banner placeholder
        self._banner = tk.Frame(
            self, bg=C["surface2"], height=200,
            highlightbackground=C["cyan"], highlightthickness=1,
        )
        self._banner.pack(fill="x", padx=14, pady=(10, 10))
        self._banner.pack_propagate(False)

        neon_line(self, C["border_hi"])

        # Game title
        self._title_var = tk.StringVar(value="// GAME TITLE")
        tk.Label(
            self, textvariable=self._title_var, font=FONT_HEAD,
            bg=C["surface"], fg=C["magenta"], anchor="w",
        ).pack(fill="x", padx=14, pady=(14, 4))

        # Description header + text
        tk.Label(
            self, text="// GAME DESCRIPTION", font=FONT_BOLD,
            bg=C["surface"], fg=C["cyan"], anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))

        self._desc_var = tk.StringVar(value="No game selected.")
        tk.Label(
            self, textvariable=self._desc_var, font=FONT_SM,
            bg=C["surface"], fg=C["text"], anchor="nw",
            wraplength=500, justify="left",
        ).pack(fill="x", padx=14, pady=(0, 14))

        # Metadata fields
        meta_frame = tk.Frame(self, bg=C["surface"])
        meta_frame.pack(fill="x", padx=14, pady=(0, 14))

        self._meta_vars: dict[str, tk.StringVar] = {}
        for label in ("Released On", "Developers", "Publishers", "Disk Size"):
            row = tk.Frame(meta_frame, bg=C["surface"])
            row.pack(fill="x", pady=2)
            tk.Label(
                row, text=f"// {label}:", font=FONT_BOLD,
                bg=C["surface"], fg=C["cyan"], anchor="w",
            ).pack(side="left")
            var = tk.StringVar(value=" --")
            self._meta_vars[label] = var
            tk.Label(
                row, textvariable=var, font=FONT,
                bg=C["surface"], fg=C["text"], anchor="w",
            ).pack(side="left", padx=(4, 0))

    # ── Public API ────────────────────────────────────────────────────────────

    def show_game(self, game: dict, size_str: str = "---") -> None:
        """Update the panel with details for *game*."""
        name = game.get("name", "Unknown")
        self._title_var.set(f"// {name.upper()}")
        self._desc_var.set(
            f"Installer type: {game.get('installer_type', 'unknown').upper()}\n"
            f"Type: {game.get('type', 'game')}"
        )
        self._meta_vars["Released On"].set(" --")
        self._meta_vars["Developers"].set(" --")
        self._meta_vars["Publishers"].set(" --")
        self._meta_vars["Disk Size"].set(f" {size_str}")

    def update_size(self, size_str: str) -> None:
        """Update just the disk size field."""
        self._meta_vars["Disk Size"].set(f" {size_str}")
