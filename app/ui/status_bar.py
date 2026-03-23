# Status bar with animated dot indicator.
#
# Thin bar at the bottom of the window that shows sync state
# and other transient messages, with an optional dot animation.

import tkinter as tk

from .theme import C, FONT_STATUS
from .widgets import neon_line


class StatusBar(tk.Frame):
    """Thin status bar at the bottom of the window."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=C["surface2"])
        neon_line(self, C["cyan"])
        self._label = tk.Label(
            self, text="", font=FONT_STATUS,
            bg=C["surface2"], fg=C["text_dim"],
            anchor="w", padx=14, pady=8,
        )
        self._label.pack(side="left", fill="x")
        self._base_text = ""
        self._dot_count = 0
        self._animating = False
        self._after_id = None

    def set(self, text: str, animated: bool = False) -> None:
        """Update the status text.  Pass *animated=True* for a dot animation."""
        self._stop()
        self._base_text = text
        if animated:
            self._dot_count = 0
            self._animating = True
            self._tick()
        else:
            self._label.configure(text=text)

    def _tick(self) -> None:
        if not self._animating:
            return
        dots = "." * (self._dot_count % 4)
        self._label.configure(text=f"{self._base_text}{dots}")
        self._dot_count += 1
        self._after_id = self.after(500, self._tick)

    def _stop(self) -> None:
        self._animating = False
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
