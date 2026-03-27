# Game details panel – displays information for the currently selected game.
#
# Shows game title, description, and metadata fields.
# Content is updated via show_game() when the user clicks
# a row in the adjacent game list.

import sys
import tkinter as tk
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageTk

from core import BASE_DIR
from .theme import C, FONT, FONT_BOLD, FONT_HEAD, FONT_SM

# ── Banner configuration ──────────────────────────────────────────────────────
BANNER_HEIGHT = 350  # ← Adjust this value to control the banner image height (px)


def _find_game_image(name: str) -> Path | None:
    """Locate the banner image for *name* across config search paths."""
    candidates = [
        Path.cwd() / "config" / "images" / f"{name}.png",
        Path(sys.executable).resolve().parent / "config" / "images" / f"{name}.png",
        BASE_DIR / "config" / "images" / f"{name}.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


class GameBanner(tk.Canvas):
    """Wide banner: crisp centred image with blurred mirrored sides and gradient fades."""

    _BLUR_RADIUS = 10
    _EDGE_FADE_FRAC = 0.10   # fraction of centre-image width for L/R gradient
    _BOTTOM_FADE_PX = 80     # pixels for the bottom-to-background gradient

    def __init__(self, parent: tk.Widget, bg_color: str = C["surface"]):
        super().__init__(parent, bg=bg_color, highlightthickness=0, height=BANNER_HEIGHT)
        self._bg_rgb = self._hex_to_rgb(bg_color)
        self._src_pil: Image.Image | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._last_w = 0
        self._resize_job: str | None = None
        self.bind("<Configure>", self._on_configure)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    # ── Public API ─────────────────────────────────────────────────────────

    def set_image(self, path: str | Path) -> None:
        """Load and display the image at *path*."""
        try:
            self._src_pil = Image.open(path).convert("RGBA")
        except Exception:
            self.clear()
            return
        self._last_w = 0
        self._render()

    def clear(self) -> None:
        self._src_pil = None
        self._photo = None
        self.delete("all")

    # ── Resize handling ────────────────────────────────────────────────────

    def _on_configure(self, _event: tk.Event | None = None) -> None:
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(50, self._render)

    # ── Core render ────────────────────────────────────────────────────────

    def _render(self) -> None:
        self._resize_job = None
        if self._src_pil is None:
            self.delete("all")
            return

        pw = self.winfo_width()
        if pw < 10:
            return
        if pw == self._last_w:
            return
        self._last_w = pw
        h = BANNER_HEIGHT
        src = self._src_pil

        # ── Centre image – fixed pixel size keyed to BANNER_HEIGHT ────────
        aspect = src.width / src.height
        cw = int(h * aspect)
        center = src.resize((cw, h), Image.LANCZOS).convert("RGBA")

        # ── Blurred mirrored background – scales to full panel width ──────
        bg = src.resize((max(pw, 1), h), Image.LANCZOS).convert("RGB")
        bg = bg.transpose(Image.FLIP_LEFT_RIGHT)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=self._BLUR_RADIUS))
        composite = bg.convert("RGBA")

        # ── Gradient alpha on left / right edges of centre image ──────────
        fade_px = max(min(int(cw * self._EDGE_FADE_FRAC), cw // 2), 1)
        c_arr = np.array(center, dtype=np.float32)
        alpha = c_arr[:, :, 3]
        grad = np.linspace(0.0, 1.0, fade_px, dtype=np.float32)
        alpha[:, :fade_px] *= grad[np.newaxis, :]
        alpha[:, -fade_px:] *= grad[np.newaxis, ::-1]
        c_arr[:, :, 3] = alpha
        center_faded = Image.fromarray(c_arr.astype(np.uint8))

        cx = (pw - cw) // 2
        composite.paste(center_faded, (cx, 0), center_faded)

        # ── Bottom gradient fade into surface colour ──────────────────────
        fade_h = min(self._BOTTOM_FADE_PX, h // 2)
        comp_arr = np.array(composite, dtype=np.float32)
        t = np.linspace(0.0, 1.0, fade_h, dtype=np.float32).reshape(-1, 1)
        bg_r, bg_g, bg_b = self._bg_rgb
        sy = h - fade_h
        comp_arr[sy:, :, 0] = comp_arr[sy:, :, 0] * (1 - t) + bg_r * t
        comp_arr[sy:, :, 1] = comp_arr[sy:, :, 1] * (1 - t) + bg_g * t
        comp_arr[sy:, :, 2] = comp_arr[sy:, :, 2] * (1 - t) + bg_b * t

        final = Image.fromarray(comp_arr.astype(np.uint8)).convert("RGB")
        self._photo = ImageTk.PhotoImage(final)
        self.delete("all")
        self.create_image(pw // 2, h // 2, image=self._photo)


class GameDetails(tk.Frame):
    """Right-side panel showing details for the selected game."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=C["surface"])

        # Banner image at top
        self._banner = GameBanner(self)
        self._banner.pack(fill="x")

        # Description header + text (hidden until a game is selected)
        self._desc_frame = tk.Frame(self, bg=C["surface"])
        tk.Label(
            self._desc_frame, text="// DESCRIPTION", font=FONT_BOLD,
            bg=C["surface"], fg=C["cyan"], anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))

        self._desc_var = tk.StringVar()
        self._desc_label = tk.Label(
            self._desc_frame, textvariable=self._desc_var, font=FONT_SM,
            bg=C["surface"], fg=C["text"], anchor="nw",
            wraplength=300, justify="left", width=1,
        )
        self._desc_label.pack(fill="x", padx=14, pady=(0, 14))
        self.bind("<Configure>", self._on_frame_resize)

        # Metadata fields (hidden until a game is selected)
        self._meta_frame = tk.Frame(self, bg=C["surface"])

        self._meta_vars: dict[str, tk.StringVar] = {}
        for label in ("Released On", "Genre", "Developers", "Publishers", "Players", "Disk Size"):
            row = tk.Frame(self._meta_frame, bg=C["surface"])
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

    # ── Public API ────────────────────────────────────────────────────────────

    def show_game(self, game: dict, size_str: str = "---") -> None:
        """Update the panel with details for *game*."""
        name = game.get("name", "Unknown")
        img = _find_game_image(name)
        if img:
            self._banner.set_image(img)
        else:
            self._banner.clear()
        self._desc_var.set(game.get("description", "No description available."))
        self._desc_frame.pack(fill="x")
        self._meta_frame.pack(fill="x", padx=14, pady=(0, 14))
        self._meta_vars["Released On"].set(f" {game.get('release_date', '--')}")
        self._meta_vars["Genre"].set(f" {game.get('genre', '--')}")
        self._meta_vars["Developers"].set(f" {game.get('developer', '--')}")
        self._meta_vars["Publishers"].set(f" {game.get('publisher', '--')}")
        self._meta_vars["Players"].set(f" {game.get('player_count', '--')}")
        self._meta_vars["Disk Size"].set(f" {size_str}")

    def update_size(self, size_str: str) -> None:
        """Update just the disk size field."""
        self._meta_vars["Disk Size"].set(f" {size_str}")
