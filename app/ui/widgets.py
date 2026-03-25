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


class CyberScrollbar(tk.Canvas):
    """Custom canvas-based scrollbar with a capped thumb height."""

    def __init__(self, parent: tk.Widget, orient: str = "vertical",
                 command=None, width: int = 24, thumb_min: int = 40,
                 thumb_max: int = 120, bg: str = C["surface"],
                 thumb_color: str = C["border"],
                 thumb_hover: str = C["accent_dim"],
                 thumb_press: str = C["cyan"], **kw):
        super().__init__(parent, width=width, bg=bg,
                         highlightthickness=0, bd=0, **kw)
        self._command = command
        self._thumb_min = thumb_min
        self._thumb_max = thumb_max
        self._thumb_color = thumb_color
        self._thumb_hover = thumb_hover
        self._thumb_press = thumb_press
        self._current_color = thumb_color
        self._lo = 0.0
        self._hi = 1.0
        self._drag_start_y: int | None = None
        self._drag_start_lo = 0.0
        self._thumb_id: int | None = None

        self.bind("<Configure>", lambda _: self._redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def set(self, lo: str, hi: str) -> None:
        """Called by the associated widget to update thumb position."""
        self._lo, self._hi = float(lo), float(hi)
        self._redraw()

    def _thumb_coords(self) -> tuple[int, int, int, int]:
        h = self.winfo_height()
        w = self.winfo_width()
        if h < 1:
            return 0, 0, w, 0
        visible = self._hi - self._lo
        raw_h = int(h * visible)
        thumb_h = max(self._thumb_min, min(self._thumb_max, raw_h))
        track = h - thumb_h
        if (1.0 - visible) > 0:
            top = int(track * self._lo / (1.0 - visible))
        else:
            top = 0
        pad = max(1, (w - max(w - 8, 6)) // 2)
        return pad, top, w - pad, top + thumb_h

    def _redraw(self) -> None:
        self.delete("all")
        if self._hi - self._lo >= 1.0:
            return
        x1, y1, x2, y2 = self._thumb_coords()
        r = min(4, (x2 - x1) // 2)
        self._thumb_id = self._round_rect(
            x1, y1, x2, y2, r, fill=self._current_color, outline="")

    def _round_rect(self, x1: int, y1: int, x2: int, y2: int,
                    r: int, **kw) -> int:
        points = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kw)

    def _on_press(self, event: tk.Event) -> None:
        x1, y1, x2, y2 = self._thumb_coords()
        if y1 <= event.y <= y2:
            self._drag_start_y = event.y
            self._drag_start_lo = self._lo
            self._current_color = self._thumb_press
            self._redraw()
        else:
            h = self.winfo_height()
            frac = event.y / h
            visible = self._hi - self._lo
            new_lo = max(0.0, min(1.0 - visible, frac - visible / 2))
            if self._command:
                self._command("moveto", str(new_lo))

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_start_y is None:
            return
        h = self.winfo_height()
        visible = self._hi - self._lo
        _, y1, _, y2 = self._thumb_coords()
        thumb_h = y2 - y1
        track = h - thumb_h
        if track <= 0:
            return
        dy = event.y - self._drag_start_y
        delta = dy / track * (1.0 - visible)
        new_lo = max(0.0, min(1.0 - visible, self._drag_start_lo + delta))
        if self._command:
            self._command("moveto", str(new_lo))

    def _on_release(self, _event: tk.Event) -> None:
        self._drag_start_y = None
        self._current_color = self._thumb_hover
        self._redraw()

    def _on_enter(self, _event: tk.Event) -> None:
        if self._drag_start_y is None:
            self._current_color = self._thumb_hover
            self._redraw()
        self.configure(cursor="hand2")

    def _on_leave(self, _event: tk.Event) -> None:
        if self._drag_start_y is None:
            self._current_color = self._thumb_color
            self._redraw()
        self.configure(cursor="")


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
