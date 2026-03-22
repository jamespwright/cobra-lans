# Main application window – coordinates UI panels and core logic.
#
# This is the top-level Tk window.  It wires together the header,
# game list, bottom bar, status bar, and settings panel, and drives
# the install / download workflow on background threads.  It owns no
# business logic itself — that lives in core/.

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from .theme import C, FONT, FONT_BOLD, FONT_HEAD
from .widgets import CyberButton, neon_box, neon_line
from .game_list import GameList
from .settings_panel import SettingsPanel
from .status_bar import StatusBar
from core import BASE_DIR, settings
from core.data import load_games, missing_installer_files
from core.installer import run_installs
from core.downloader import download_game


class CobraLANs(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Cobra LANs")
        self.configure(bg=C["bg"])
        self.state('zoomed')

        self.games = load_games()
        self.install_type = tk.StringVar(value="game")
        self.player_name = tk.StringVar()
        self._install_btn: CyberButton | None = None
        self._installing = False
        self._config_reload_pending = False

        self._build_ui()
        self.install_type.trace_add(
            "write", lambda *_: self._game_list.populate(
                self.games, self.install_type.get()))
        self.bind("<Configure>", self._on_resize)
        self._sync_config()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_header()

        self._game_list = GameList(self)
        self._game_list.pack(fill="both", expand=True, padx=22, pady=(14, 0))
        self._game_list.populate(self.games, self.install_type.get())

        self._build_bottom_bar()

        self._status_bar = StatusBar(self)
        self._status_bar.pack(fill="x")

        # Settings overlay – must be last so it stacks on top
        self._settings_panel = SettingsPanel(self, on_save=self._on_settings_saved)

    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg=C["header"], padx=20, pady=10)
        hdr.pack(fill="x")

        neon_line(hdr, C["cyan"])
        tk.Frame(hdr, bg=C["header"], height=1).pack(fill="x")
        neon_line(hdr, C["magenta"])

        inner = tk.Frame(hdr, bg=C["header"], pady=10)
        inner.pack(fill="x")

        # Hamburger menu – anchored right
        ham = tk.Label(
            inner, text="\u2630", font=("Courier New", 26, "bold"),
            bg=C["header"], fg=C["cyan"], cursor="hand2", padx=4,
        )
        ham.pack(side="right", padx=(0, 14))
        ham.bind("<Button-1>", lambda _: self._settings_panel.toggle())
        ham.bind("<Enter>", lambda _: ham.configure(fg=C["magenta"]))
        ham.bind("<Leave>", lambda _: ham.configure(fg=C["cyan"]))

        tk.Label(inner, text="//", font=FONT_HEAD,
                 bg=C["header"], fg=C["magenta"]).pack(side="left", padx=(0, 8))
        tk.Label(inner, text="COBRA", font=FONT_HEAD,
                 bg=C["header"], fg=C["cyan"]).pack(side="left")
        tk.Label(inner, text=" LANs", font=FONT_HEAD,
                 bg=C["header"], fg=C["magenta"]).pack(side="left")
        tk.Label(inner, text=" :: GAME INSTALLER",
                 font=("Courier New", 25), bg=C["header"], fg=C["text_dim"],
                 ).pack(side="left", padx=(10, 0), anchor="s", pady=(0, 6))

        neon_line(hdr, C["magenta"])
        tk.Frame(hdr, bg=C["header"], height=2).pack(fill="x")
        neon_line(hdr, C["cyan"])

    def _build_bottom_bar(self) -> None:
        bar = tk.Frame(self, bg=C["bg"], padx=22, pady=14)
        bar.pack(fill="x")

        center = tk.Frame(bar, bg=C["bg"])
        center.pack(expand=True)

        # Install mode
        mode_box = neon_box(center, "INSTALL MODE", color=C["magenta"])
        mode_row = tk.Frame(mode_box, bg=C["surface2"], pady=8)
        mode_row.pack(fill="x", padx=90)
        radio_kw = dict(font=FONT_BOLD, bg=C["surface2"],
                        selectcolor=C["cb_select"], bd=0, relief="flat")
        tk.Radiobutton(mode_row, text="GAME", value="game",
                       variable=self.install_type,
                       fg=C["cyan"], activebackground=C["surface2"],
                       activeforeground=C["cyan"], **radio_kw
                       ).pack(side="left", padx=(0, 10))
        tk.Radiobutton(mode_row, text="SERVER", value="server",
                       variable=self.install_type,
                       fg=C["magenta"], activebackground=C["surface2"],
                       activeforeground=C["magenta"], **radio_kw
                       ).pack(side="left")

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
            text="\u25b6  DOWNLOAD GAMES" if settings.download_only else "\u25b6  INSTALL GAMES",
            pady=12, command=self._on_install,
        )
        self._install_btn.pack(fill="both", expand=True)

    # ── Resize ─────────────────────────────────────────────────────────────────

    def _on_resize(self, _event) -> None:
        self._settings_panel.snap_to_edge()

    # ── Settings save callback ─────────────────────────────────────────────────

    def _on_settings_saved(self, url_changed: bool) -> None:
        """Called by the settings panel after a successful save."""
        self._refresh_install_btn_label()
        self.games = load_games()
        self._game_list.populate(self.games, self.install_type.get())
        if url_changed and settings.download_url and not settings.disable_game_sync:
            self._sync_config()

    def _refresh_install_btn_label(self) -> None:
        if self._install_btn:
            label = ("\u25b6  DOWNLOAD GAMES" if settings.download_only
                     else "\u25b6  INSTALL GAMES")
            self._install_btn.configure(text=label)

    # ── Install flow ───────────────────────────────────────────────────────────

    def _on_install(self) -> None:
        selected = self._game_list.selected_games()
        if not selected:
            messagebox.showwarning("No Selection",
                                   "Select at least one game to install.")
            return

        dl_only = settings.download_only
        dl_url = None if settings.disable_downloads else settings.download_url

        if dl_only:
            if not dl_url and not settings.disable_downloads:
                url = simpledialog.askstring(
                    "Download URL Required",
                    "Enter the OneDrive share URL to download the files:",
                    parent=self)
                if not url or not url.strip():
                    return
                url = url.strip()
                settings.save(download_url=url)
                dl_url = url
            self._set_busy(True)
            threading.Thread(
                target=self._run_in_thread,
                args=(selected, "", "", None, dl_url),
                kwargs={"download_only": True},
                daemon=True,
            ).start()
            return

        player = self.player_name.get().strip()
        if not player:
            messagebox.showwarning("Player Name Required",
                                   "Please enter your player name before installing.")
            return

        install_dir = filedialog.askdirectory(
            title="Select Install Directory", initialdir=r"C:\Games")
        if not install_dir:
            return

        server_ip_parts: list[str] | None = None
        if any(g.get("requires_server_ip", False) for g in selected):
            ip = simpledialog.askstring(
                "Server IP",
                "Enter the IP address of the Bad Company 2 server\n"
                "(format: 192.168.1.1):",
                parent=self)
            if not ip:
                return
            parts = ip.strip().split(".")
            if len(parts) != 4 or not all(p.isdigit() for p in parts):
                messagebox.showerror("Invalid IP",
                                     "Please enter a valid IPv4 address.")
                return
            server_ip_parts = parts

        missing = missing_installer_files(selected)
        if missing and not dl_url and not settings.disable_downloads:
            url = simpledialog.askstring(
                "Download URL Required",
                "The following game installer(s) were not found locally:\n"
                + "\n".join(f"  \u2022 {n}" for n in missing)
                + "\n\nEnter the OneDrive share URL to download them:",
                parent=self)
            if not url or not url.strip():
                messagebox.showwarning(
                    "Download URL Required",
                    "Installation cancelled. A download URL is needed "
                    "to fetch the missing files.")
                return
            url = url.strip()
            settings.save(download_url=url)
            dl_url = url

        self._set_busy(True)
        threading.Thread(
            target=self._run_in_thread,
            args=(selected, install_dir, player, server_ip_parts, dl_url),
            daemon=True,
        ).start()

    def _run_in_thread(self, selected, install_dir, player, server_ip_parts,
                       download_url=None, download_only=False) -> None:
        def _status_cb(game_name: str, msg: str) -> None:
            self.after(0, self._game_list.update_status, game_name, msg)

        errors = run_installs(
            selected, install_dir, player, server_ip_parts,
            download_url=download_url, status_callback=_status_cb,
            download_only=download_only,
        )

        for game in selected:
            self.after(0, self._game_list.refresh_size, game["name"])

        self.after(0, self._set_busy, False)

        if errors:
            self.after(0, lambda: messagebox.showerror(
                "Install Errors",
                "One or more games failed:\n\n" + "\n".join(errors)))
        else:
            msg = ("All selected games downloaded successfully." if download_only
                   else "All selected games installed successfully.")
            self.after(0, lambda: messagebox.showinfo("Done", msg))

    # ── Config sync ────────────────────────────────────────────────────────────

    def _sync_config(self) -> None:
        if settings.disable_game_sync or not settings.download_url:
            return
        self._status_bar.set("\u25b6 Syncing games list", animated=True)
        threading.Thread(target=self._run_config_sync, daemon=True).start()

    def _run_config_sync(self) -> None:
        games_yaml = BASE_DIR / "config" / "games.yaml"
        mtime_before = games_yaml.stat().st_mtime if games_yaml.exists() else None

        errors = download_game(
            settings.download_url, {"base_path": "config"}, None)

        if errors:
            self.after(0, self._status_bar.set,
                       "\u25b6 Failed to connect to OneDrive")
        else:
            mtime_after = (games_yaml.stat().st_mtime
                           if games_yaml.exists() else None)
            if mtime_after != mtime_before:
                self.after(0, self._on_config_synced)
            else:
                self.after(0, self._status_bar.set,
                           "\u25b6 Connected to OneDrive")

    def _on_config_synced(self) -> None:
        self._status_bar.set("\u25b6 Games list updated")
        if self._installing:
            self._config_reload_pending = True
        else:
            self.games = load_games()
            self._game_list.populate(self.games, self.install_type.get())

    def _set_busy(self, busy: bool) -> None:
        self._installing = busy
        if self._install_btn:
            self._install_btn.configure(state="disabled" if busy else "normal")
        if not busy and self._config_reload_pending:
            self._config_reload_pending = False
            self.games = load_games()
            self._game_list.populate(self.games, self.install_type.get())
