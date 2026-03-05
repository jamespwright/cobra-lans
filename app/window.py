"""Cobra LANs – main application window."""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from .config import C, FONT, FONT_BOLD, FONT_HEAD
from .data import (
    check_game_files,
    folder_size_str,
    get_installer_folder,
    load_games,
    load_manifest,
)
from .installer import run_installs
from .widgets import CyberButton, neon_box, neon_line


class CobraLANs(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Cobra LANs")
        self.configure(bg=C["bg"])
        self.geometry("1500x1080")
        self.minsize(1060, 580)
        #self.state("zoomed")

        self.games: list[dict]                   = load_games()
        self._manifest: dict[str, list[dict]]    = load_manifest()
        self._visible_games: list[dict]          = []
        self.check_vars: list[tk.BooleanVar]     = []
        self._stripe_widgets: list[tk.Frame]     = []
        self.install_type                        = tk.StringVar(value="game")
        self.player_name                         = tk.StringVar()
        self._check_all_var                      = tk.BooleanVar(value=False)
        self._install_btn: CyberButton | None    = None
        self._row_container: tk.Frame | None     = None

        self._build_ui()

        # Rebuild the game list whenever the install mode radio changes
        self.install_type.trace_add("write", lambda *_: self._populate_game_rows())

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_game_list()
        self._build_bottom_bar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=C["header"], padx=20, pady=10)
        hdr.pack(fill="x")

        neon_line(hdr, C["cyan"])
        tk.Frame(hdr, bg=C["header"], height=1).pack(fill="x")
        neon_line(hdr, C["magenta"])

        inner = tk.Frame(hdr, bg=C["header"], pady=10)
        inner.pack(fill="x")

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
                 bg=C["surface"], fg=C["text_dim"]).pack(side="left", padx=(8, 0))
        # ── right columns – pack STATUS first so it sits at the far right ──
        tk.Label(col_row, text="STATUS",    font=FONT_BOLD,
             bg=C["surface"], fg=C["text_dim"], width=32, anchor="e").pack(side="right", padx=(0, 4))
        tk.Label(col_row, text="DISK SIZE", font=FONT_BOLD,
             bg=C["surface"], fg=C["text_dim"], width=10, anchor="e").pack(side="right", padx=(0, 12))
        tk.Label(col_row, text="VERSION",   font=FONT_BOLD,
             bg=C["surface"], fg=C["text_dim"], width=9,  anchor="e").pack(side="right", padx=(0, 4))

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
        size_lbl = tk.Label(frame, textvariable=size_var, font=FONT,
                     fg=C["accent_dim"], bg=row_bg, width=10, anchor="e")

        status_lbl = tk.Label(frame, text="—", font=FONT,
                       fg=C["text_dim"], bg=row_bg, width=32, anchor="e")

        version_lbl = tk.Label(frame, text=game.get("version", "—"), font=FONT,
                    fg=C["text_dim"], bg=row_bg, width=9, anchor="e")

        # Pack right-side columns: STATUS first (far right), then DISK SIZE, then VERSION
        status_lbl.pack(side="right", padx=(0, 4))
        size_lbl.pack(side="right", padx=(0, 12))
        version_lbl.pack(side="right", padx=(0, 4))

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

        for w in (frame, name_lbl, version_lbl, status_lbl, size_lbl):
            w.bind("<Button-1>", _toggle)
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)
            w.bind("<Button-3>", lambda e, g=game, lb=status_lbl: self._show_context_menu(e, g, lb))

    # ── Right-click context menu ───────────────────────────────────────────────

    def _show_context_menu(self, event: tk.Event, game: dict, status_lbl: tk.Label):
        """Display the right-click context menu for a game row."""
        menu = tk.Menu(self, tearoff=0,
                       bg=C["surface2"], fg=C["text"], activebackground=C["row_hover"],
                       activeforeground=C["cyan"], relief="flat", bd=0,
                       font=FONT)
        menu.add_command(
            label="\u25b8  Check Game Files",
            command=lambda g=game, lb=status_lbl: self._trigger_game_file_check(g, lb),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _trigger_game_file_check(self, game: dict, status_lbl: tk.Label):
        """Start the game-file check: launch a spinner then run checks in a background thread."""
        _FRAMES = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c", "\u2834",
                   "\u2826", "\u2827", "\u2807", "\u280f"]
        state = {"done": False, "msg": "checking\u2026", "fi": 0}

        def _spin():
            if state["done"]:
                return
            status_lbl.configure(
                text=f"{_FRAMES[state['fi']]} {state['msg']}",
                fg=C["text_dim"],
            )
            state["fi"] = (state["fi"] + 1) % len(_FRAMES)
            self.after(120, _spin)

        def _progress(msg: str) -> None:
            state["msg"] = msg

        _spin()
        threading.Thread(
            target=self._run_game_file_check,
            args=(game, status_lbl, state, _progress),
            daemon=True,
        ).start()

    def _run_game_file_check(self, game: dict, status_lbl: tk.Label, state: dict, progress_cb):
        """Background thread: run all file checks, stop spinner, show result popup."""
        report, colour_key, short = check_game_files(game, self._manifest, progress_cb)
        state["done"] = True
        self.after(0, lambda: status_lbl.configure(text=short, fg=C[colour_key]))
        title = f"Check Game Files \u2013 {game.get('name', '')}"
        self.after(0, lambda r=report, c=colour_key, t=title: self._show_check_popup(t, r, c))

    def _show_check_popup(self, title: str, report: str, colour_key: str):
        """Show a styled popup window with the check report."""
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.configure(bg=C["bg"])
        popup.resizable(False, False)
        popup.grab_set()

        hdr_color = C["green"] if colour_key == "green" else C["red"]

        tk.Label(popup, text=title, font=FONT_BOLD,
                 bg=C["bg"], fg=hdr_color, pady=10).pack(fill="x", padx=20)

        sep = tk.Frame(popup, bg=hdr_color, height=1)
        sep.pack(fill="x", padx=20)

        txt_frame = tk.Frame(popup, bg=C["surface"], padx=16, pady=12)
        txt_frame.pack(fill="both", expand=True, padx=20, pady=10)

        txt = tk.Text(
            txt_frame, font=FONT, bg=C["surface"], fg=C["text"],
            relief="flat", bd=0, state="normal",
            width=60, height=min(30, report.count("\n") + 3),
            wrap="word",
        )
        txt.insert("1.0", report)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)

        close_btn = tk.Button(
            popup, text="Close", font=FONT_BOLD,
            bg=C["btn_bg"], fg=C["btn_fg"], activebackground=C["btn_hov"],
            relief="flat", bd=0, padx=20, pady=8, cursor="hand2",
            command=popup.destroy,
        )
        close_btn.pack(pady=(0, 14))

    # ── Bottom bar ─────────────────────────────────────────────────────────────

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
            btn_outer, text="\u25b6  INSTALL GAMES", pady=12, command=self._on_install,
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

        self._set_busy(True)
        threading.Thread(
            target=self._run_in_thread,
            args=(selected, install_dir, player, server_ip_parts),
            daemon=True,
        ).start()

    def _run_in_thread(
        self,
        selected:          list[dict],
        install_dir:       str,
        player:            str,
        server_ip_parts:   list[str] | None,
    ):
        errors = run_installs(selected, install_dir, player, server_ip_parts)
        self.after(0, self._set_busy, False)
        if errors:
            self.after(0, lambda: messagebox.showerror(
                "Install Errors",
                "One or more games failed to install:\n\n" + "\n".join(errors),
            ))
        else:
            self.after(0, lambda: messagebox.showinfo("Done", "All selected games installed successfully."))

    def _set_busy(self, busy: bool):
        """Disable/enable the install button to prevent double-clicks."""
        if self._install_btn:
            self._install_btn.configure(state="disabled" if busy else "normal")
