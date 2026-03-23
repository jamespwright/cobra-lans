# Slide-in settings panel.
#
# Overlay that slides from the right edge. Contains toggle switches,
# a filter dropdown, and a download-URL entry.  Calls back to the
# main window when settings are saved so it can reload data.

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .theme import C, FONT_SM, FONT_XS, SETTINGS_PANEL_W
from .widgets import CyberButton, ToggleSwitch, neon_line
from core import settings
from core.data import load_filter_names


class SettingsPanel(tk.Frame):
    """Settings overlay that slides in from the right edge."""

    def __init__(self, parent: tk.Tk, on_save: Callable[[bool], None]):
        super().__init__(parent, bg=C["surface2"], bd=0)
        self._app = parent
        self._on_save_cb = on_save  # called with url_changed flag
        self._open = False
        self._animating = False
        self._refreshing = False
        self._toggle_switches: dict[str, ToggleSwitch] = {}
        self._vars: dict[str, tk.Variable] = {}
        self._originals: dict[str, object] = {}

        # Start off-screen
        self.place(x=9999, y=0, width=SETTINGS_PANEL_W, relheight=1.0)

        # Left neon border
        tk.Frame(self, bg=C["cyan"], width=2).pack(side="left", fill="y")

        content = tk.Frame(self, bg=C["surface2"], padx=18, pady=14)
        content.pack(side="left", fill="both", expand=True)

        # Spacer to align header row with the hamburger icon in the main header
        tk.Frame(content, bg=C["surface2"], height=17).pack(fill="x")

        # Header row
        hdr = tk.Frame(content, bg=C["surface2"])
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="\u25b8 SETTINGS",
                 font=("Courier New", 18, "bold"),
                 bg=C["surface2"], fg=C["cyan"]).pack(side="left")
        close_lbl = tk.Label(
            hdr, text="\u2715", font=("Courier New", 26, "bold"),
            bg=C["surface2"], fg=C["cyan"], cursor="hand2", padx=4,
        )
        close_lbl.pack(side="right")
        close_lbl.bind("<Button-1>", lambda _: self.toggle())
        close_lbl.bind("<Enter>", lambda _: close_lbl.configure(fg=C["text"]))
        close_lbl.bind("<Leave>", lambda _: close_lbl.configure(fg=C["magenta"]))
        neon_line(content, C["cyan"])

        # Toggle rows
        self._add_toggle(content, "disable_game_sync",
                         "DISABLE GAME SYNC", "Stop syncing game list",
                         settings.disable_game_sync)
        self._add_toggle(content, "disable_downloads",
                         "DISABLE DOWNLOADS", "Disable downloading files",
                         settings.disable_downloads)
        self._add_toggle(content, "download_only",
                         "DOWNLOAD ONLY", "Download no installation",
                         settings.download_only)
        neon_line(content, C["border_hi"])

        # Combobox & entry rows
        self._setup_combobox_style()
        self._filter_combo = self._add_combobox(
            content, "games_filter", "GAMES FILTER", "Filter the list of games",
            settings.games_filter or "", load_filter_names())
        self._add_entry(content, "download_url", "DOWNLOAD URL",
                        "URL for downloading files",
                        settings.download_url or "")
        neon_line(content, C["border_hi"])

        # Save button
        wrap = tk.Frame(content, bg=C["surface"], padx=1, pady=1)
        wrap.pack(fill="x", pady=(14, 0))
        self._save_btn = CyberButton(
            wrap, text="\u25b6  SAVE SETTINGS",
            command=self._save, pady=10,
        )
        self._save_btn.pack(fill="both")
        self._set_save_enabled(False)

        # Dirty tracking
        self._snapshot()
        for var in self._vars.values():
            var.trace_add("write", self._check_dirty)

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self._open

    def toggle(self) -> None:
        """Open or close the panel with a slide animation."""
        if self._animating:
            return
        if not self._open:
            self._refresh_from_settings()
            self._filter_combo["values"] = [""] + load_filter_names()
            w = self._app.winfo_width()
            self.place(x=w, y=0, width=SETTINGS_PANEL_W, relheight=1.0)
            self.lift()
            self._app.bind("<Button-1>", self._on_outside_click, add="+")
        else:
            self._app.unbind("<Button-1>")
        self._animating = True
        self._open = not self._open
        self._animate()

    def snap_to_edge(self) -> None:
        """Keep the panel pinned when the window resizes."""
        if self._open:
            w = self._app.winfo_width()
            self.place(x=w - SETTINGS_PANEL_W, y=0,
                       width=SETTINGS_PANEL_W, relheight=1.0)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _refresh_from_settings(self) -> None:
        self._refreshing = True
        for key, val in [
            ("disable_game_sync", settings.disable_game_sync),
            ("disable_downloads", settings.disable_downloads),
            ("download_only",     settings.download_only),
            ("games_filter",      settings.games_filter or ""),
            ("download_url",      settings.download_url or ""),
        ]:
            self._vars[key].set(val)
            if key in self._toggle_switches:
                self._toggle_switches[key].snap(bool(val))
        self._refreshing = False
        self._snapshot()
        self._check_dirty()

    def _snapshot(self) -> None:
        for key, var in self._vars.items():
            self._originals[key] = var.get()

    def _check_dirty(self, *_) -> None:
        if self._refreshing:
            return
        dirty = any(v.get() != self._originals.get(k)
                     for k, v in self._vars.items())
        self._set_save_enabled(dirty)

    def _set_save_enabled(self, enabled: bool) -> None:
        if enabled:
            self._save_btn.configure(
                state="normal", bg=C["btn_bg"], fg=C["btn_fg"],
                activebackground=C["btn_hov"], cursor="hand2")
            self._save_btn._bg, self._save_btn._hov = C["btn_bg"], C["btn_hov"]
        else:
            self._save_btn.configure(
                state="disabled", bg=C["surface"], fg=C["text_dim"],
                activebackground=C["surface"], cursor="arrow")
            self._save_btn._bg = self._save_btn._hov = C["surface"]

    def _save(self) -> None:
        old_url = settings.download_url
        kwargs: dict = {}
        for key, var in self._vars.items():
            raw = var.get()
            if key in ("disable_game_sync", "disable_downloads", "download_only"):
                kwargs[key] = bool(raw)
            elif key == "download_url":
                kwargs[key] = str(raw).strip() or None
            else:
                kwargs[key] = str(raw) if raw else ""
        settings.save(**kwargs)
        self._snapshot()
        self._check_dirty()
        self._on_save_cb(settings.download_url != old_url)
        if self._open:
            self.toggle()

    def _on_outside_click(self, event: tk.Event) -> None:
        """Close the panel when the user clicks outside it."""
        if not self._open or self._animating:
            return
        panel_x = self.winfo_rootx()
        panel_y = self.winfo_rooty()
        panel_w = self.winfo_width()
        panel_h = self.winfo_height()
        if not (panel_x <= event.x_root < panel_x + panel_w
                and panel_y <= event.y_root < panel_y + panel_h):
            self.toggle()

    def _animate(self) -> None:
        w = self._app.winfo_width()
        current_x = int(float(self.place_info().get("x", w)))
        target_x = (w - SETTINGS_PANEL_W) if self._open else w
        diff = target_x - current_x
        if abs(diff) < 3:
            self.place(x=target_x, y=0, width=SETTINGS_PANEL_W, relheight=1.0)
            self._animating = False
            return
        step = max(3, int(abs(diff) * 0.28))
        new_x = current_x + (step if diff > 0 else -step)
        self.place(x=new_x, y=0, width=SETTINGS_PANEL_W, relheight=1.0)
        self._app.after(12, self._animate)

    # ── Row builders ──────────────────────────────────────────────────────────

    def _add_toggle(self, parent: tk.Frame, key: str,
                    label: str, desc: str, initial: bool) -> None:
        var = tk.BooleanVar(value=initial)
        self._vars[key] = var
        row = tk.Frame(parent, bg=C["surface2"], pady=10)
        row.pack(fill="x")
        text_col = tk.Frame(row, bg=C["surface2"])
        text_col.pack(side="left", fill="both", expand=True)
        tk.Label(text_col, text=label, font=FONT_SM,
                 bg=C["surface2"], fg=C["text"], anchor="w").pack(fill="x")
        tk.Label(text_col, text=desc, font=FONT_XS,
                 bg=C["surface2"], fg=C["text_dim"], anchor="w").pack(fill="x")
        ts = ToggleSwitch(row, variable=var, bg=C["surface2"])
        ts.pack(side="right", padx=(10, 0), pady=2)
        self._toggle_switches[key] = ts

    def _setup_combobox_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "langames.TCombobox",
            fieldbackground=C["entry_bg"], background=C["surface2"],
            foreground=C["text"], arrowcolor=C["cyan"],
            bordercolor=C["border"], lightcolor=C["border"],
            darkcolor=C["border"], selectbackground=C["cb_select"],
            selectforeground=C["text"], padding=(4, 4), relief="flat",
        )
        style.map(
            "langames.TCombobox",
            fieldbackground=[("readonly", C["entry_bg"]), ("disabled", C["entry_bg"])],
            foreground=[("readonly", C["text"]), ("disabled", C["text_dim"])],
            background=[("readonly", C["surface2"]), ("active", C["surface2"])],
            bordercolor=[("focus", C["cyan"]), ("active", C["cyan"])],
            arrowcolor=[("active", C["magenta"]), ("focus", C["cyan"])],
        )
        self._app.option_add("*TCombobox*Listbox.background", C["entry_bg"])
        self._app.option_add("*TCombobox*Listbox.foreground", C["text"])
        self._app.option_add("*TCombobox*Listbox.selectBackground", C["cb_select"])
        self._app.option_add("*TCombobox*Listbox.selectForeground", C["cyan"])
        self._app.option_add("*TCombobox*Listbox.font", ("Courier New", 14))
        self._app.option_add("*TCombobox*Listbox.relief", "flat")
        self._app.option_add("*TCombobox*Listbox.borderWidth", 1)

    def _add_combobox(self, parent: tk.Frame, key: str,
                      label: str, desc: str,
                      initial: str, values: list[str]) -> ttk.Combobox:
        var = tk.StringVar(value=initial)
        self._vars[key] = var
        frame = tk.Frame(parent, bg=C["surface2"], pady=10)
        frame.pack(fill="x")
        tk.Label(frame, text=label, font=FONT_SM,
                 bg=C["surface2"], fg=C["text"], anchor="w").pack(fill="x")
        tk.Label(frame, text=desc, font=FONT_XS,
                 bg=C["surface2"], fg=C["text_dim"], anchor="w").pack(fill="x")
        combo = ttk.Combobox(
            frame, textvariable=var, font=("Courier New", 14),
            values=[""] + values, state="readonly", style="langames.TCombobox",
        )
        combo.pack(fill="x", pady=(4, 0), ipady=5)
        return combo

    def _add_entry(self, parent: tk.Frame, key: str,
                   label: str, desc: str, initial: str) -> None:
        var = tk.StringVar(value=initial)
        self._vars[key] = var
        frame = tk.Frame(parent, bg=C["surface2"], pady=10)
        frame.pack(fill="x")
        tk.Label(frame, text=label, font=FONT_SM,
                 bg=C["surface2"], fg=C["text"], anchor="w").pack(fill="x")
        tk.Label(frame, text=desc, font=FONT_XS,
                 bg=C["surface2"], fg=C["text_dim"], anchor="w").pack(fill="x")
        tk.Entry(
            frame, textvariable=var, font=("Courier New", 14), width=24,
            bg=C["entry_bg"], fg=C["text"], insertbackground=C["cyan"],
            relief="flat", bd=0, highlightthickness=1,
            highlightcolor=C["cyan"], highlightbackground=C["border_hi"],
        ).pack(fill="x", pady=(4, 0), ipady=5)
