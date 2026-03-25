# Game details panel – displays information for the currently selected game.
#
# Shows a banner image, game title, description, and metadata
# fields.  Content is updated via show_game() when the user clicks
# a row in the adjacent game list.

import os
import tkinter as tk

import numpy as np
from PIL import Image, ImageTk

from .theme import C, FONT, FONT_BOLD, FONT_HEAD, FONT_SM

_IMAGES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "config", "images")
)
_BANNER_H = 400
_BANNER_CROP_BOTTOM = 0    # pixels to crop from the bottom of the banner image (0 = no crop)
_BANNER_SCALE_X = 1.3     # horizontal width multiplier (1.0 = natural, >1.0 = wider)
_FADE_RATIO = 0.15  # fraction of banner height that fades to bg


class GameDetails(tk.Frame):
    """Right-side panel showing details for the selected game."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=C["surface"])

        # Banner canvas – edge-to-edge, no padding, no border
        self._banner_canvas = tk.Canvas(
            self, height=_BANNER_H, bg=C["surface"],
            highlightthickness=0, bd=0,
        )
        self._banner_canvas.pack(fill="x")
        self._banner_canvas.bind("<Configure>", self._on_banner_resize)

        self._current_game_name: str | None = None
        self._photo: ImageTk.PhotoImage | None = None  # prevent GC

        # Description header + text
        tk.Label(
            self, text="// DESCRIPTION", font=FONT_BOLD,
            bg=C["surface"], fg=C["cyan"], anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))

        self._desc_var = tk.StringVar(value="No game selected.")
        self._desc_label = tk.Label(
            self, textvariable=self._desc_var, font=FONT_SM,
            bg=C["surface"], fg=C["text"], anchor="nw",
            wraplength=300, justify="left", width=1,
        )
        self._desc_label.pack(fill="x", padx=14, pady=(0, 14))
        self.bind("<Configure>", self._on_frame_resize)

        # Metadata fields
        meta_frame = tk.Frame(self, bg=C["surface"])
        meta_frame.pack(fill="x", padx=14, pady=(0, 14))

        self._meta_vars: dict[str, tk.StringVar] = {}
        for label in ("Released On", "Genre", "Developers", "Publishers", "Players", "Disk Size"):
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

    # ── Resize helpers ────────────────────────────────────────────────────────

    def _on_frame_resize(self, event: tk.Event) -> None:
        wrap = max(event.width - 28, 100)  # account for padx=14 on each side
        self._desc_label.configure(wraplength=wrap)

    def _on_banner_resize(self, event: tk.Event) -> None:
        if self._current_game_name:
            self._render_banner(self._current_game_name, event.width)

    def _render_banner(self, name: str, width: int | None = None) -> None:
        if width is None or width <= 1:
            width = self._banner_canvas.winfo_width()
        if width <= 1:
            width = 500  # pre-map fallback

        img_path = os.path.join(_IMAGES_DIR, f"{name}.png")
        if not os.path.isfile(img_path):
            self._banner_canvas.delete("all")
            self._photo = None
            return

        img = Image.open(img_path).convert("RGBA")
        iw, ih = img.size

        # Scale uniformly (preserving aspect ratio) so the full target height
        # (_BANNER_H + _BANNER_CROP_BOTTOM) fits inside the scaled image, then
        # _BANNER_SCALE_X zooms both axes equally → wider image, no stretch.
        # The excess vertical pixels (crop + zoom overshoot) are trimmed off the bottom.
        target_h = int((_BANNER_H + _BANNER_CROP_BOTTOM) * _BANNER_SCALE_X)
        scale = target_h / ih
        scaled_w = int(iw * scale)  # aspect ratio preserved
        img = img.resize((scaled_w, target_h), Image.LANCZOS)
        img = img.crop((0, 0, scaled_w, _BANNER_H))
        h = _BANNER_H

        # Place image centred horizontally on a transparent canvas
        canvas_img = Image.new("RGBA", (width, h), (0, 0, 0, 0))
        x_offset = (width - scaled_w) // 2
        canvas_img.paste(img, (x_offset, 0))

        arr = np.array(canvas_img, dtype=np.float32)
        bg_hex = C["surface"].lstrip("#")
        bg_r, bg_g, bg_b = (int(bg_hex[i:i + 2], 16) for i in (0, 2, 4))

        # Bottom fade
        fade_start = int(h * (1.0 - _FADE_RATIO))
        fade_rows = max(h - fade_start - 1, 1)
        for y in range(fade_start, h):
            t = (y - fade_start) / fade_rows
            arr[y, :, 3] *= (1.0 - t)

        # Left fade
        fade_w = max(int(scaled_w * _FADE_RATIO), 1)
        left_end = x_offset + fade_w
        for x in range(min(left_end, width)):
            t = 1.0 - max(x - x_offset, 0) / fade_w
            arr[:, x, 3] *= (1.0 - t)

        # Right fade (mirror)
        right_start = x_offset + scaled_w - fade_w
        for x in range(max(right_start, 0), width):
            t = max(x - right_start, 0) / fade_w
            arr[:, x, 3] *= (1.0 - t)

        faded = Image.fromarray(arr.astype(np.uint8), "RGBA")
        bg_layer = Image.new("RGBA", (width, h), (bg_r, bg_g, bg_b, 255))
        bg_layer.paste(faded, (0, 0), faded)

        self._photo = ImageTk.PhotoImage(bg_layer.convert("RGB"))
        self._banner_canvas.delete("all")
        self._banner_canvas.create_image(0, 0, anchor="nw", image=self._photo)

    # ── Public API ────────────────────────────────────────────────────────────

    def show_game(self, game: dict, size_str: str = "---") -> None:
        """Update the panel with details for *game*."""
        name = game.get("name", "Unknown")
        self._desc_var.set(game.get("description", "No description available."))
        self._meta_vars["Released On"].set(f" {game.get('release_date', '--')}")
        self._meta_vars["Genre"].set(f" {game.get('genre', '--')}")
        self._meta_vars["Developers"].set(f" {game.get('developer', '--')}")
        self._meta_vars["Publishers"].set(f" {game.get('publisher', '--')}")
        self._meta_vars["Players"].set(f" {game.get('player_count', '--')}")
        self._meta_vars["Disk Size"].set(f" {size_str}")

        self._current_game_name = name
        self._render_banner(name)

    def update_size(self, size_str: str) -> None:
        """Update just the disk size field."""
        self._meta_vars["Disk Size"].set(f" {size_str}")
