"""Cobra LANs – reusable Tkinter widgets and layout helpers."""

import tkinter as tk

from .config import C, FONT_BOLD


def neon_line(parent: tk.Widget, color: str = C["border_hi"], thick: int = 1) -> tk.Frame:
    """Pack a single-pixel coloured horizontal rule into *parent*."""
    f = tk.Frame(parent, bg=color, height=thick)
    f.pack(fill="x")
    return f


def neon_box(parent: tk.Widget, label: str, color: str = C["cyan"]) -> tk.Frame:
    """Pack a neon-bordered, labelled panel into *parent*; returns the inner content frame."""
    outer = tk.Frame(parent, bg=color, padx=1, pady=1)
    outer.pack(side="left", fill="y", padx=(0, 14))
    inner = tk.Frame(outer, bg=C["surface2"])
    inner.pack(fill="both", expand=True)
    tk.Label(inner, text=f"  \u25b8 {label}", font=FONT_BOLD,
             bg=C["surface2"], fg=color, pady=6).pack(fill="x")
    neon_line(inner, color)
    return inner


class CyberButton(tk.Button):
    """Styled button that brightens on hover."""

    def __init__(self, parent: tk.Widget, **kw):
        defaults = dict(
            bg=C["btn_bg"], fg=C["btn_fg"],
            activebackground=C["btn_hov"], activeforeground=C["btn_fg"],
            font=FONT_BOLD, relief="flat", cursor="hand2",
            padx=16, pady=12, bd=0,
        )
        defaults.update(kw)
        super().__init__(parent, **defaults)
        self._bg  = defaults["bg"]
        self._hov = defaults["activebackground"]
        self.bind("<Enter>", lambda _: self.config(bg=self._hov))
        self.bind("<Leave>", lambda _: self.config(bg=self._bg))
