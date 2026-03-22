# Reusable Tkinter widgets and layout helpers.
#
# Provides themed building blocks (buttons, toggles, decorative lines)
# used throughout the UI.  No business logic lives here.

import tkinter as tk

from .theme import C, FONT_BOLD


def neon_line(parent: tk.Widget, color: str = C["border_hi"], thick: int = 1) -> tk.Frame:
    """Horizontal coloured rule."""
    f = tk.Frame(parent, bg=color, height=thick)
    f.pack(fill="x")
    return f


def neon_box(parent: tk.Widget, label: str, color: str = C["cyan"]) -> tk.Frame:
    """Neon-bordered labelled panel; returns the inner content frame."""
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


class ToggleSwitch(tk.Canvas):
    """Animated rounded toggle switch."""

    _W, _H   = 58, 28
    _OFF_X   = 14.0
    _ON_X    = 44.0
    _KR      = 11

    def __init__(self, parent: tk.Widget, variable: tk.BooleanVar, **kw):
        bg = kw.pop("bg", C["surface2"])
        super().__init__(
            parent, width=self._W, height=self._H,
            bg=bg, highlightthickness=0, bd=0, cursor="hand2",
        )
        self._var      = variable
        self._knob_x   = self._ON_X if variable.get() else self._OFF_X
        self._target_x = self._knob_x
        self._draw()
        self.bind("<Button-1>", self._on_click)

    def snap(self, val: bool) -> None:
        """Move knob to the correct end immediately, no animation."""
        self._knob_x = self._target_x = self._ON_X if val else self._OFF_X
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        on = self._var.get()
        self._draw_pill(3, 8, 55, 20, fill=C["cyan"] if on else C["border"])
        kx, ky = int(self._knob_x), self._H // 2
        self.create_oval(
            kx - self._KR, ky - self._KR,
            kx + self._KR, ky + self._KR,
            fill=C["text"] if on else C["text_dim"], outline="",
        )

    def _draw_pill(self, x1: int, y1: int, x2: int, y2: int,
                   fill: str, outline: str = "") -> None:
        r = (y2 - y1) // 2
        self.create_arc(x1, y1, x1 + 2*r, y2, start=90, extent=180,
                        fill=fill, outline=outline)
        self.create_arc(x2 - 2*r, y1, x2, y2, start=270, extent=180,
                        fill=fill, outline=outline)
        self.create_rectangle(x1 + r, y1, x2 - r, y2,
                              fill=fill, outline=outline)

    def _on_click(self, _) -> None:
        self._var.set(not self._var.get())
        self._target_x = self._ON_X if self._var.get() else self._OFF_X
        self._animate()

    def _animate(self) -> None:
        diff = self._target_x - self._knob_x
        if abs(diff) < 1.5:
            self._knob_x = self._target_x
            self._draw()
            return
        self._knob_x += diff * 0.35
        self._draw()
        self.after(16, self._animate)
