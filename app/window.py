"""Cobra LANs – main application window."""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .config import BASE_DIR, C, FONT, FONT_BOLD, FONT_HEAD
from .data import (
    folder_size_str,
    get_installer_folder,
    load_filter_names,
    load_games,
    missing_installer_files,
)
from . import usersettings
from .installer import run_installs
from .downloader import download_game
from .widgets import CyberButton, ToggleSwitch, neon_box, neon_line

_PANEL_W = 380   # width of the slide-in settings panel


class CobraLANs(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Cobra LANs")
        self.configure(bg=C["bg"])
        self.geometry("1500x1080")
        self.minsize(1280, 580)
        #self.state("zoomed")

        self.games: list[dict]                   = load_games()
        self._visible_games: list[dict]          = []
        self.check_vars: list[tk.BooleanVar]     = []
        self._stripe_widgets: list[tk.Frame]     = []
        self._status_vars: list[tk.StringVar]    = []
        self._size_vars: list[tk.StringVar]      = []
        self.install_type                        = tk.StringVar(value="game")
        self.player_name                         = tk.StringVar()
        self._check_all_var                      = tk.BooleanVar(value=False)
        self._install_btn: CyberButton | None    = None
        self._row_container: tk.Frame | None     = None
        self._installing                         = False
        self._config_reload_pending              = False

        self._build_ui()

        # Rebuild the game list whenever the install mode radio changes
        self.install_type.trace_add("write", lambda *_: self._populate_game_rows())

        # Bind the resize event to ensure the settings panel stays snapped
        self.bind("<Configure>", self._on_resize)

        self._sync_config()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_game_list()
        self._build_bottom_bar()
        self._build_status_bar()
        self._build_settings_panel()   # overlay – must be last so it stacks on top

    def _build_header(self):
        hdr = tk.Frame(self, bg=C["header"], padx=20, pady=10)
        hdr.pack(fill="x")

        neon_line(hdr, C["cyan"])
        tk.Frame(hdr, bg=C["header"], height=1).pack(fill="x")
        neon_line(hdr, C["magenta"])

        inner = tk.Frame(hdr, bg=C["header"], pady=10)
        inner.pack(fill="x")

        # Hamburger button – pack RIGHT first so it anchors to the far right
        ham = tk.Label(
            inner, text="\u2630", font=("Courier New", 26, "bold"),
            bg=C["header"], fg=C["cyan"], cursor="hand2", padx=4,
        )
        ham.pack(side="right", padx=(0, 14))
        ham.bind("<Button-1>", lambda _: self._toggle_settings_panel())
        ham.bind("<Enter>",    lambda _: ham.configure(fg=C["magenta"]))
        ham.bind("<Leave>",    lambda _: ham.configure(fg=C["cyan"]))

        tk.Label(inner, text="//",              font=FONT_HEAD, bg=C["header"], fg=C["magenta"]).pack(side="left", padx=(0, 8))
        tk.Label(inner, text="COBRA",           font=FONT_HEAD, bg=C["header"], fg=C["cyan"]   ).pack(side="left")
        tk.Label(inner, text=" LANs",           font=FONT_HEAD, bg=C["header"], fg=C["magenta"]).pack(side="left")
        tk.Label(inner, text=" :: GAME INSTALLER",
                 font=("Courier New", 25), bg=C["header"], fg=C["text_dim"],
                 ).pack(side="left", padx=(10, 0), anchor="s", pady=(0, 6))

        neon_line(hdr, C["magenta"])
        tk.Frame(hdr, bg=C["header"], height=2).pack(fill="x")
        neon_line(hdr, C["cyan"])

    def _build_game_list(self):
        outer = tk.Frame(self, bg=C["border_hi"], padx=1, pady=1)
        outer.pack(fill="both", expand=True, padx=22, pady=(14, 0))

        container = tk.Frame(outer, bg=C["surface"])
        container.pack(fill="both", expand=True)

        # Header bar
        hdr_bar = tk.Frame(container, bg=C["surface2"])
        hdr_bar.pack(fill="x")
        tk.Label(hdr_bar, text="  \u25b8 SELECT GAMES", font=FONT_BOLD,
                 bg=C["surface2"], fg=C["cyan"], pady=8).pack(side="left")

        neon_line(container, C["cyan"])

        # Column sub-header – mirrors _add_game_row's left section exactly so
        # every column header lines up with the corresponding row cell.
        col_row = tk.Frame(container, bg=C["surface"], pady=4)
        col_row.pack(fill="x")
        # ── left placeholders (must match row: stripe → checkbox → index) ──
        tk.Frame(col_row, bg=C["surface"], width=4).pack(side="left", fill="y")   # stripe
        tk.Checkbutton(
            col_row, variable=self._check_all_var, command=self._toggle_all,
            font=FONT_BOLD, bg=C["surface"], fg=C["magenta"],
            selectcolor=C["cb_select"], activebackground=C["surface"],
            activeforeground=C["magenta"], bd=0, relief="flat",
        ).pack(side="left", padx=(6, 0))
        tk.Label(col_row, text="", font=FONT, bg=C["surface"], width=3).pack(side="left")   # index
        # ── expandable title ──
        tk.Label(col_row, text="GAME TITLE", font=FONT_BOLD,
                 bg=C["surface"], fg=C["text_dim"]).pack(side="left", padx=(0, 0))
        # ── right columns ──
        tk.Label(col_row, text="DISK SIZE", font=FONT_BOLD,
             bg=C["surface"], fg=C["text_dim"], width=10, anchor="e").pack(side="right", padx=(0, 12))
        tk.Label(col_row, text="STATUS", font=FONT_BOLD,
             bg=C["surface"], fg=C["text_dim"], width=30, anchor="w").pack(side="right", padx=(0, 16))

        neon_line(container, C["border_hi"])

        # Scrollable canvas
        scroll_host = tk.Frame(container, bg=C["surface"])
        scroll_host.pack(fill="both", expand=True)

        canvas    = tk.Canvas(scroll_host, bg=C["surface"], highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._row_container = tk.Frame(canvas, bg=C["surface"])
        win_id = canvas.create_window((0, 0), window=self._row_container, anchor="nw")

        self._row_container.bind("<Configure>",
                                 lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-(e.delta // 120), "units"))

        self._populate_game_rows()

    def _populate_game_rows(self):
        """Clear and rebuild the scrollable game rows for the current install mode."""
        if self._row_container is None:
            return
        # Destroy existing rows and reset state
        for child in self._row_container.winfo_children():
            child.destroy()
        self.check_vars.clear()
        self._stripe_widgets.clear()
        self._status_vars.clear()
        self._size_vars.clear()
        self._check_all_var.set(False)

        mode = self.install_type.get()
        # Show only entries whose type matches the selected install mode
        visible = [g for g in self.games if g.get("type", "game") == mode]

        self._visible_games = visible
        for idx, game in enumerate(visible):
            self._add_game_row(idx, game)

    def _add_game_row(self, idx: int, game: dict):
        row_bg = C["row_even"] if idx % 2 == 0 else C["row_odd"]

        frame = tk.Frame(self._row_container, bg=row_bg, pady=6, cursor="hand2")
        frame.pack(fill="x")

        stripe = tk.Frame(frame, bg=C["border"], width=4)
        stripe.pack(side="left", fill="y")

        var = tk.BooleanVar(value=False)
        self.check_vars.append(var)
        self._stripe_widgets.append(stripe)

        def _update_stripe(v=var, s=stripe):
            s.configure(bg=C["cyan"] if v.get() else C["border"])
            self._sync_select_all()

        tk.Checkbutton(
            frame, variable=var, command=_update_stripe,
            bg=row_bg, fg=C["cyan"],
            selectcolor=C["cb_select"], activebackground=row_bg,
            activeforeground=C["cyan"], bd=0, relief="flat",
        ).pack(side="left", padx=(6, 0))

        tk.Label(frame, text=f"{idx + 1:02d}", font=FONT,
                 bg=row_bg, fg=C["text_dim"], width=3, anchor="e").pack(side="left")

        name_lbl = tk.Label(frame, text=game["name"], font=FONT,
                             fg=C["text"], bg=row_bg, anchor="w")
        name_lbl.pack(side="left", padx=(8, 0), fill="x", expand=True)

        size_var = tk.StringVar(value="---")
        self._size_vars.append(size_var)
        size_lbl = tk.Label(frame, textvariable=size_var, font=FONT,
                     fg=C["accent_dim"], bg=row_bg, width=10, anchor="e")
        size_lbl.pack(side="right", padx=(0, 12))

        status_var = tk.StringVar(value="")
        self._status_vars.append(status_var)
        status_lbl = tk.Label(frame, textvariable=status_var, font=FONT,
                     fg=C["accent_dim"], bg=row_bg, width=30, anchor="w")
        status_lbl.pack(side="right", padx=(0, 0))

        threading.Thread(
            target=lambda v=size_var, g=game: v.set(
                folder_size_str(get_installer_folder(g))
            ),
            daemon=True,
        ).start()

        # ── Row interaction helpers ────────────────────────────────────────────

        def _set_row_bg(widget: tk.Widget, bg: str):
            widget.configure(bg=bg)
            for child in widget.winfo_children():
                try:
                    child.configure(bg=bg)
                except tk.TclError:
                    pass

        def _toggle(_e, v=var, s=stripe):
            v.set(not v.get())
            s.configure(bg=C["cyan"] if v.get() else C["border"])
            self._sync_select_all()

        def _enter(_e, r=frame, s=stripe, v=var):
            _set_row_bg(r, C["row_hover"])
            s.configure(bg=C["cyan"] if v.get() else C["magenta"])

        def _leave(_e, r=frame, s=stripe, v=var, bg=row_bg):
            _set_row_bg(r, bg)
            s.configure(bg=C["cyan"] if v.get() else C["border"])

        for w in (frame, name_lbl, size_lbl, status_lbl):
            w.bind("<Button-1>", _toggle)
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)

    # ── Bottom bar ─────────────────────────────────────────────────────────────

    # ── Status bar ────────────────────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        """Thin status bar at the very bottom; shows OneDrive sync state."""
        self._status_base_text: str = ""
        self._status_dot_count: int = 0
        self._status_animating: bool = False
        self._status_after_id = None

        bar = tk.Frame(self, bg=C["surface2"])
        bar.pack(fill="x")
        neon_line(bar, C["cyan"])

        self._status_label = tk.Label(
            bar, text="",
            font=("Courier New", 13),
            bg=C["surface2"], fg=C["text_dim"],
            anchor="w", padx=14, pady=5,
        )
        self._status_label.pack(side="left", fill="x")

    def _set_status(self, text: str, animated: bool = False) -> None:
        """Update the status bar text. Pass animated=True to start dot animation."""
        self._stop_dot_animation()
        self._status_base_text = text
        if animated:
            self._status_dot_count = 0
            self._status_animating = True
            self._tick_dot_animation()
        else:
            self._status_label.configure(text=text)

    def _tick_dot_animation(self) -> None:
        if not self._status_animating:
            return
        dots = "." * (self._status_dot_count % 4)
        self._status_label.configure(text=f"{self._status_base_text}{dots}")
        self._status_dot_count += 1
        self._status_after_id = self.after(500, self._tick_dot_animation)

    def _stop_dot_animation(self) -> None:
        self._status_animating = False
        if self._status_after_id is not None:
            self.after_cancel(self._status_after_id)
            self._status_after_id = None

    # ── Settings panel ──────────────────────────────────────────────────────────

    def _build_settings_panel(self) -> None:
        """Build the slide-in settings overlay (hidden off-screen initially)."""
        self._panel_open       = False
        self._panel_animating  = False
        self._settings_refreshing = False
        self._toggle_switches: dict  = {}
        self._settings_vars:   dict  = {}
        self._settings_original: dict = {}

        panel = tk.Frame(self, bg=C["surface2"], bd=0)
        # Start completely off-screen to the right
        panel.place(x=9999, y=0, width=_PANEL_W, relheight=1.0)
        self._settings_panel = panel

        # Left neon border stripe
        tk.Frame(panel, bg=C["cyan"], width=2).pack(side="left", fill="y")

        content = tk.Frame(panel, bg=C["surface2"], padx=18, pady=14)
        content.pack(side="left", fill="both", expand=True)

        # ── Panel header ──────────────────────────────────────────────────────
        hdr_row = tk.Frame(content, bg=C["surface2"])
        hdr_row.pack(fill="x", pady=(0, 6))
        tk.Label(
            hdr_row, text="\u25b8 SETTINGS",
            font=("Courier New", 18, "bold"), bg=C["surface2"], fg=C["cyan"],
        ).pack(side="left")
        close_lbl = tk.Label(
            hdr_row, text="\u2715",
            font=("Courier New", 18, "bold"), bg=C["surface2"], fg=C["magenta"],
            cursor="hand2",
        )
        close_lbl.pack(side="right")
        close_lbl.bind("<Button-1>", lambda _: self._toggle_settings_panel())
        close_lbl.bind("<Enter>",    lambda _: close_lbl.configure(fg=C["text"]))
        close_lbl.bind("<Leave>",    lambda _: close_lbl.configure(fg=C["magenta"]))

        neon_line(content, C["cyan"])

        # ── Toggle rows ───────────────────────────────────────────────────────
        sync_var = tk.BooleanVar(value=usersettings.disable_game_sync)
        self._settings_vars["disable_game_sync"] = sync_var
        self._add_toggle_row(
            content, "disable_game_sync",
            "DISABLE GAME SYNC",
            "Stop syncing game list",
            sync_var,
        )

        dl_var = tk.BooleanVar(value=usersettings.disable_downloads)
        self._settings_vars["disable_downloads"] = dl_var
        self._add_toggle_row(
            content, "disable_downloads",
            "DISABLE DOWNLOADS",
            "Disable downloading files",
            dl_var,
        )

        dl_only_var = tk.BooleanVar(value=usersettings.download_only)
        self._settings_vars["download_only"] = dl_only_var
        self._add_toggle_row(
            content, "download_only",
            "DOWNLOAD ONLY",
            "Download no installation",
            dl_only_var,
        )

        neon_line(content, C["border_hi"])

        # ── Entry rows ────────────────────────────────────────────────────────
        filter_var = tk.StringVar(value=usersettings.games_filter or "")
        self._settings_vars["games_filter"] = filter_var
        self._filter_combobox = self._add_combobox_row(
            content, "GAMES FILTER",
            "Filter the list of games",
            filter_var,
            load_filter_names(),
        )

        url_var = tk.StringVar(value=usersettings.download_url or "")
        self._settings_vars["download_url"] = url_var
        self._add_entry_row(
            content, "DOWNLOAD URL",
            "URL for downloading files",
            url_var,
        )

        neon_line(content, C["border_hi"])

        # ── Save button ───────────────────────────────────────────────────────
        save_wrap = tk.Frame(content, bg=C["surface"], padx=1, pady=1)
        save_wrap.pack(fill="x", pady=(14, 0))
        self._save_btn = CyberButton(
            save_wrap, text="\u25b6  SAVE SETTINGS", command=self._save_settings,
            pady=10,
        )
        self._save_btn.pack(fill="both")
        # Start greyed-out
        self._save_btn.configure(
            state="disabled", bg=C["surface"], fg=C["text_dim"],
            activebackground=C["surface"], cursor="arrow",
        )
        self._save_btn._bg  = C["surface"]
        self._save_btn._hov = C["surface"]

        # Snapshot originals and attach dirty-tracking traces
        self._snapshot_settings()
        for var in self._settings_vars.values():
            var.trace_add("write", self._check_settings_dirty)

    def _add_toggle_row(
        self, parent: tk.Frame, key: str,
        label: str, description: str,
        var: tk.BooleanVar,
    ) -> None:
        row = tk.Frame(parent, bg=C["surface2"], pady=10)
        row.pack(fill="x")
        text_col = tk.Frame(row, bg=C["surface2"])
        text_col.pack(side="left", fill="both", expand=True)
        tk.Label(
            text_col, text=label,
            font=("Courier New", 15, "bold"), bg=C["surface2"], fg=C["text"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            text_col, text=description,
            font=("Courier New", 12), bg=C["surface2"], fg=C["text_dim"], anchor="w",
        ).pack(fill="x")
        ts = ToggleSwitch(row, variable=var, bg=C["surface2"])
        ts.pack(side="right", padx=(10, 0), pady=2)
        self._toggle_switches[key] = ts

    def _add_combobox_row(
        self, parent: tk.Frame,
        label: str, description: str,
        var: tk.StringVar,
        values: list[str],
    ) -> ttk.Combobox:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Cobra.TCombobox",
            fieldbackground=C["entry_bg"],
            background=C["surface2"],
            foreground=C["text"],
            arrowcolor=C["cyan"],
            bordercolor=C["border"],
            lightcolor=C["border"],
            darkcolor=C["border"],
            selectbackground=C["cb_select"],
            selectforeground=C["text"],
            padding=(4, 4),
            relief="flat",
        )
        style.map(
            "Cobra.TCombobox",
            fieldbackground=[("readonly", C["entry_bg"]), ("disabled", C["entry_bg"])],
            foreground=[("readonly", C["text"]), ("disabled", C["text_dim"])],
            background=[("readonly", C["surface2"]), ("active", C["surface2"])],
            bordercolor=[("focus", C["cyan"]), ("active", C["cyan"])],
            arrowcolor=[("active", C["magenta"]), ("focus", C["cyan"])],
        )
        # Style the popup listbox to match the app palette
        self.option_add("*TCombobox*Listbox.background",        C["entry_bg"])
        self.option_add("*TCombobox*Listbox.foreground",        C["text"])
        self.option_add("*TCombobox*Listbox.selectBackground",  C["cb_select"])
        self.option_add("*TCombobox*Listbox.selectForeground",  C["cyan"])
        self.option_add("*TCombobox*Listbox.font",              ("Courier New", 14))
        self.option_add("*TCombobox*Listbox.relief",            "flat")
        self.option_add("*TCombobox*Listbox.borderWidth",       1)
        frame = tk.Frame(parent, bg=C["surface2"], pady=10)
        frame.pack(fill="x")
        tk.Label(
            frame, text=label,
            font=("Courier New", 15, "bold"), bg=C["surface2"], fg=C["text"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            frame, text=description,
            font=("Courier New", 12), bg=C["surface2"], fg=C["text_dim"], anchor="w",
        ).pack(fill="x")
        combo = ttk.Combobox(
            frame, textvariable=var,
            font=("Courier New", 14),
            values=[""] + values,
            state="readonly",
            style="Cobra.TCombobox",
        )
        combo.pack(fill="x", pady=(4, 0), ipady=5)
        return combo

    def _add_entry_row(
        self, parent: tk.Frame,
        label: str, description: str,
        var: tk.StringVar,
    ) -> None:
        frame = tk.Frame(parent, bg=C["surface2"], pady=10)
        frame.pack(fill="x")
        tk.Label(
            frame, text=label,
            font=("Courier New", 15, "bold"), bg=C["surface2"], fg=C["text"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            frame, text=description,
            font=("Courier New", 12), bg=C["surface2"], fg=C["text_dim"], anchor="w",
        ).pack(fill="x")
        tk.Entry(
            frame, textvariable=var,
            font=("Courier New", 14), width=24,
            bg=C["entry_bg"], fg=C["text"], insertbackground=C["cyan"],
            relief="flat", bd=0, highlightthickness=1,
            highlightcolor=C["cyan"], highlightbackground=C["border_hi"],
        ).pack(fill="x", pady=(4, 0), ipady=5)

    # ── Panel open / close ────────────────────────────────────────────────────

    def _toggle_settings_panel(self) -> None:
        if self._panel_animating:
            return
        if not self._panel_open:
            # Refresh displayed values from current in-memory settings
            self._settings_refreshing = True
            for key, val in [
                ("disable_game_sync", usersettings.disable_game_sync),
                ("disable_downloads", usersettings.disable_downloads),
                ("download_only",     usersettings.download_only),
                ("games_filter",      usersettings.games_filter or ""),
                ("download_url",      usersettings.download_url or ""),
            ]:
                self._settings_vars[key].set(val)
                if key in self._toggle_switches:
                    self._toggle_switches[key].snap(bool(val))
            self._settings_refreshing = False
            self._snapshot_settings()
            self._check_settings_dirty()
            # Refresh filter dropdown values in case filter.yaml was re-synced
            self._filter_combobox["values"] = [""] + load_filter_names()
            # Snap panel to start position (just off the right edge)
            w = self.winfo_width()
            self._settings_panel.place(x=w, y=0, width=_PANEL_W, relheight=1.0)
            self._settings_panel.lift()
        self._panel_animating = True
        self._panel_open = not self._panel_open
        self._animate_panel()

    def _animate_panel(self) -> None:
        """Step the panel one frame toward its target x position."""
        w = self.winfo_width()
        info        = self._settings_panel.place_info()
        current_x   = int(float(info.get("x", w)))
        target_x    = (w - _PANEL_W) if self._panel_open else w

        diff = target_x - current_x
        if abs(diff) < 3:
            self._settings_panel.place(x=target_x, y=0, width=_PANEL_W, relheight=1.0)
            self._panel_animating = False
            return

        step = max(3, int(abs(diff) * 0.28))
        new_x = current_x + (step if diff > 0 else -step)
        self._settings_panel.place(x=new_x, y=0, width=_PANEL_W, relheight=1.0)
        self.after(12, self._animate_panel)

    def _on_resize(self, event):
        """Ensure the settings panel stays snapped to the right edge when the window is resized."""
        if self._panel_open:
            w = self.winfo_width()
            self._settings_panel.place(x=(w - _PANEL_W), y=0, width=_PANEL_W, relheight=1.0)

    # ── Dirty tracking & save ────────────────────────────────────────────────

    def _snapshot_settings(self) -> None:
        """Record current var values as the baseline for dirty detection."""
        for key, var in self._settings_vars.items():
            self._settings_original[key] = var.get()

    def _check_settings_dirty(self, *_) -> None:
        """Enable or disable the save button depending on whether values changed."""
        if self._settings_refreshing:
            return
        dirty = any(
            var.get() != self._settings_original.get(key)
            for key, var in self._settings_vars.items()
        )
        if dirty:
            self._save_btn.configure(
                state="normal", bg=C["btn_bg"], fg=C["btn_fg"],
                activebackground=C["btn_hov"], cursor="hand2",
            )
            self._save_btn._bg  = C["btn_bg"]
            self._save_btn._hov = C["btn_hov"]
        else:
            self._save_btn.configure(
                state="disabled", bg=C["surface"], fg=C["text_dim"],
                activebackground=C["surface"], cursor="arrow",
            )
            self._save_btn._bg  = C["surface"]
            self._save_btn._hov = C["surface"]

    def _save_settings(self) -> None:
        """Persist settings to YAML file and reload game data."""
        old_url = usersettings.download_url
        kwargs = {}
        for key, var in self._settings_vars.items():
            raw = var.get()
            if key in ("disable_game_sync", "disable_downloads", "download_only"):
                kwargs[key] = bool(raw)
            elif key == "download_url":
                kwargs[key] = str(raw).strip() or None
            elif key == "games_filter":
                kwargs[key] = "" if str(raw) == "" else str(raw)
            else:
                kwargs[key] = str(raw)
        usersettings.save(**kwargs)
        self._snapshot_settings()
        self._check_settings_dirty()
        self._refresh_install_btn_label()
        self.games = load_games()
        self._populate_game_rows()
        if usersettings.download_url != old_url and usersettings.download_url and not usersettings.disable_game_sync:
            self._sync_config()

    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=C["bg"], padx=22, pady=14)
        bar.pack(fill="x")

        # Centered container for all bottom-bar controls
        center = tk.Frame(bar, bg=C["bg"])
        center.pack(expand=True)

        # Install mode
        mode_box = neon_box(center, "INSTALL MODE", color=C["magenta"])
        mode_row = tk.Frame(mode_box, bg=C["surface2"], pady=8)
        mode_row.pack(fill="x", padx=90)
        radio_kw = dict(font=FONT_BOLD, bg=C["surface2"], selectcolor=C["cb_select"],
                        bd=0, relief="flat")
        tk.Radiobutton(mode_row, text="GAME",   value="game",   variable=self.install_type,
                       fg=C["cyan"],    activebackground=C["surface2"], activeforeground=C["cyan"],    **radio_kw).pack(side="left", padx=(0, 10))
        tk.Radiobutton(mode_row, text="SERVER", value="server", variable=self.install_type,
                       fg=C["magenta"], activebackground=C["surface2"], activeforeground=C["magenta"], **radio_kw).pack(side="left")

        # Player name
        name_box = neon_box(center, "PLAYER NAME", color=C["cyan"])
        tk.Entry(
            name_box, textvariable=self.player_name, font=FONT, width=22,
            bg=C["entry_bg"], fg=C["text"], insertbackground=C["cyan"],
            relief="flat", bd=0, highlightthickness=1,
            highlightcolor=C["cyan"], highlightbackground=C["border_hi"],
        ).pack(fill="x", padx=10, pady=10, ipady=6)

        # Install button
        btn_outer = tk.Frame(center, bg=C["magenta"], padx=1, pady=1)
        btn_outer.pack(side="left", fill="y")
        self._install_btn = CyberButton(
            btn_outer,
            text="\u25b6  DOWNLOAD GAMES" if usersettings.download_only else "\u25b6  INSTALL GAMES",
            pady=12, command=self._on_install,
        )
        self._install_btn.pack(fill="both", expand=True)

    # ── Checkbox helpers ───────────────────────────────────────────────────────

    def _toggle_all(self):
        state = self._check_all_var.get()
        for v, stripe in zip(self.check_vars, self._stripe_widgets):
            v.set(state)
            stripe.configure(bg=C["cyan"] if state else C["border"])

    def _sync_select_all(self):
        self._check_all_var.set(all(v.get() for v in self.check_vars))

    # ── Install logic ──────────────────────────────────────────────────────────

    def _on_install(self):
        selected = [self._visible_games[i] for i, v in enumerate(self.check_vars) if v.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Select at least one game to install.")
            return

        download_only = usersettings.download_only
        download_url = None if usersettings.disable_downloads else usersettings.download_url

        if download_only:
            # Download-only mode: skip player name, install dir, and server IP prompts.
            if not download_url and not usersettings.disable_downloads:
                url = simpledialog.askstring(
                    "Download URL Required",
                    "Enter the OneDrive share URL to download the files:",
                    parent=self,
                )
                if not url or not url.strip():
                    return
                url = url.strip()
                usersettings.save(download_url=url)
                download_url = url
            self._set_busy(True)
            threading.Thread(
                target=self._run_in_thread,
                args=(selected, "", "", None, download_url),
                kwargs={"download_only": True},
                daemon=True,
            ).start()
            return

        player = self.player_name.get().strip()
        if not player:
            messagebox.showwarning(
                "Player Name Required",
                "Please enter your player name before installing.",
            )
            return

        install_dir = filedialog.askdirectory(title="Select Install Directory", initialdir=r"C:\Games")
        if not install_dir:
            return

        server_ip_parts: list[str] | None = None
        if any(g.get("requires_server_ip", False) for g in selected):
            ip = simpledialog.askstring(
                "Server IP",
                "Enter the IP address of the Bad Company 2 server\n(format: 192.168.1.1):",
                parent=self,
            )
            if not ip:
                return
            parts = ip.strip().split(".")
            if len(parts) != 4 or not all(p.isdigit() for p in parts):
                messagebox.showerror("Invalid IP", "Please enter a valid IPv4 address.")
                return
            server_ip_parts = parts

        download_url = None if usersettings.disable_downloads else usersettings.download_url

        # ── Pre-flight: ensure installer files exist or a download URL is set ──
        missing = missing_installer_files(selected)
        if missing and not download_url and not usersettings.disable_downloads:
            url = simpledialog.askstring(
                "Download URL Required",
                "The following game installer(s) were not found locally:\n"
                + "\n".join(f"  • {n}" for n in missing)
                + "\n\nEnter the OneDrive share URL to download them:",
                parent=self,
            )
            if not url or not url.strip():
                messagebox.showwarning(
                    "Download URL Required",
                    "Installation cancelled. A download URL is needed to fetch the missing files.",
                )
                return
            url = url.strip()
            usersettings.save(download_url=url)
            download_url = url

        self._set_busy(True)
        threading.Thread(
            target=self._run_in_thread,
            args=(selected, install_dir, player, server_ip_parts, download_url),
            daemon=True,
        ).start()

    def _run_in_thread(
        self,
        selected:          list[dict],
        install_dir:       str,
        player:            str,
        server_ip_parts:   list[str] | None,
        download_url:      str | None = None,
        download_only:     bool = False,
    ):
        def _status_cb(game_name: str, msg: str) -> None:
            self.after(0, self._update_game_status, game_name, msg)

        def _recalculate_game_size(game_name: str):
            for i, game in enumerate(self._visible_games):
                if game["name"] == game_name and i < len(self._size_vars):
                    self._size_vars[i].set(folder_size_str(get_installer_folder(game)))
                    break

        errors = run_installs(
            selected, install_dir, player, server_ip_parts,
            download_url=download_url, status_callback=_status_cb,
            download_only=download_only,
        )

        for game in selected:
            self.after(0, _recalculate_game_size, game["name"])

        self.after(0, self._set_busy, False)
        if errors:
            self.after(0, lambda: messagebox.showerror(
                "Install Errors",
                "One or more games failed to install:\n\n" + "\n".join(errors),
            ))
        else:
            self.after(0, lambda: messagebox.showinfo("Done", "All selected games downloaded successfully." if download_only else "All selected games installed successfully."))

    def _update_game_status(self, game_name: str, msg: str) -> None:
        """Set the status text for the row matching *game_name*."""
        for i, game in enumerate(self._visible_games):
            if game["name"] == game_name and i < len(self._status_vars):
                self._status_vars[i].set(msg)
                break

    def _refresh_install_btn_label(self) -> None:
        """Update the install button label to reflect the current download_only setting."""
        if self._install_btn:
            label = "\u25b6  DOWNLOAD GAMES" if usersettings.download_only else "\u25b6  INSTALL GAMES"
            self._install_btn.configure(text=label)

    def _sync_config(self) -> None:
        if usersettings.disable_game_sync or not usersettings.download_url:
            return
        self._set_status("\u25b6 Syncing games list", animated=True)
        threading.Thread(target=self._run_config_sync, daemon=True).start()

    def _run_config_sync(self) -> None:
        games_yaml = BASE_DIR / "config" / "games.yaml"
        mtime_before = games_yaml.stat().st_mtime if games_yaml.exists() else None

        errors = download_game(usersettings.download_url, {"base_path": "config"}, None)

        if errors:
            self.after(0, self._set_status, "\u25b6 Failed to connect to OneDrive")
        else:
            mtime_after = games_yaml.stat().st_mtime if games_yaml.exists() else None
            if mtime_after != mtime_before:
                # games.yaml was actually written – reload the list
                self.after(0, self._on_config_synced)
            else:
                self.after(0, self._set_status, "\u25b6 Connected to OneDrive")

    def _on_config_synced(self) -> None:
        self._set_status("\u25b6 Games list updated")
        if self._installing:
            self._config_reload_pending = True
        else:
            self.games = load_games()
            self._populate_game_rows()

    def _set_busy(self, busy: bool):
        self._installing = busy
        if self._install_btn:
            self._install_btn.configure(state="disabled" if busy else "normal")
        if not busy and self._config_reload_pending:
            self._config_reload_pending = False
            self.games = load_games()
            self._populate_game_rows()
