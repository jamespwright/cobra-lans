# Scrollable game-list panel.
#
# Displays all games that match the current install mode (game / server)
# as selectable rows with a checkbox, name, status, and disk-size column.
# Owns no business logic – just presentation and selection state.

import threading
import tkinter as tk

from .theme import C, FONT, FONT_BOLD
from .widgets import neon_line
from core.data import folder_size_str, get_installer_folder


class GameList(tk.Frame):
    """Scrollable, selectable game list with column headers."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=C["border_hi"], padx=1, pady=1)

        self.check_vars: list[tk.BooleanVar] = []
        self.status_vars: list[tk.StringVar] = []
        self.size_vars: list[tk.StringVar] = []
        self.visible_games: list[dict] = []
        self._stripe_widgets: list[tk.Frame] = []
        self._check_all_var = tk.BooleanVar(value=False)

        container = tk.Frame(self, bg=C["surface"])
        container.pack(fill="both", expand=True)

        # Section header
        hdr_bar = tk.Frame(container, bg=C["surface2"])
        hdr_bar.pack(fill="x")
        tk.Label(hdr_bar, text="  \u25b8 SELECT GAMES", font=FONT_BOLD,
                 bg=C["surface2"], fg=C["cyan"], pady=8).pack(side="left")
        neon_line(container, C["cyan"])

        # Column sub-header
        col_row = tk.Frame(container, bg=C["surface"], pady=4)
        col_row.pack(fill="x")
        tk.Frame(col_row, bg=C["surface"], width=4).pack(side="left", fill="y")
        tk.Checkbutton(
            col_row, variable=self._check_all_var, command=self._toggle_all,
            font=FONT_BOLD, bg=C["surface"], fg=C["magenta"],
            selectcolor=C["cb_select"], activebackground=C["surface"],
            activeforeground=C["magenta"], bd=0, relief="flat",
        ).pack(side="left", padx=(6, 0))
        tk.Label(col_row, text="", font=FONT, bg=C["surface"], width=3).pack(side="left")
        tk.Label(col_row, text="GAME TITLE", font=FONT_BOLD,
                 bg=C["surface"], fg=C["text_dim"]).pack(side="left")
        tk.Label(col_row, text="DISK SIZE", font=FONT_BOLD,
                 bg=C["surface"], fg=C["text_dim"], width=10, anchor="e"
                 ).pack(side="right", padx=(0, 12))
        tk.Label(col_row, text="STATUS", font=FONT_BOLD,
                 bg=C["surface"], fg=C["text_dim"], width=30, anchor="w"
                 ).pack(side="right", padx=(0, 16))
        neon_line(container, C["border_hi"])

        # Scrollable canvas
        scroll_host = tk.Frame(container, bg=C["surface"])
        scroll_host.pack(fill="both", expand=True)
        canvas = tk.Canvas(scroll_host, bg=C["surface"], highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._row_container = tk.Frame(canvas, bg=C["surface"])
        win_id = canvas.create_window((0, 0), window=self._row_container, anchor="nw")
        self._row_container.bind(
            "<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-(e.delta // 120), "units"))

    # ── Public API ────────────────────────────────────────────────────────────

    def populate(self, games: list[dict], mode: str) -> None:
        """Rebuild the game rows for the given install mode."""
        for child in self._row_container.winfo_children():
            child.destroy()
        self.check_vars.clear()
        self._stripe_widgets.clear()
        self.status_vars.clear()
        self.size_vars.clear()
        self._check_all_var.set(False)

        self.visible_games = [g for g in games if g.get("type", "game") == mode]
        for idx, game in enumerate(self.visible_games):
            self._add_row(idx, game)

    def selected_games(self) -> list[dict]:
        """Return the list of currently checked games."""
        return [self.visible_games[i] for i, v in enumerate(self.check_vars) if v.get()]

    def update_status(self, game_name: str, msg: str) -> None:
        """Set the status text for the row matching *game_name*."""
        for i, game in enumerate(self.visible_games):
            if game["name"] == game_name and i < len(self.status_vars):
                self.status_vars[i].set(msg)
                break

    def refresh_size(self, game_name: str) -> None:
        """Recalculate the disk-size label for *game_name*."""
        for i, game in enumerate(self.visible_games):
            if game["name"] == game_name and i < len(self.size_vars):
                self.size_vars[i].set(folder_size_str(get_installer_folder(game)))
                break

    # ── Private ───────────────────────────────────────────────────────────────

    def _toggle_all(self) -> None:
        state = self._check_all_var.get()
        for v, s in zip(self.check_vars, self._stripe_widgets):
            v.set(state)
            s.configure(bg=C["cyan"] if state else C["border"])

    def _sync_select_all(self) -> None:
        self._check_all_var.set(
            all(v.get() for v in self.check_vars) if self.check_vars else False)

    def _add_row(self, idx: int, game: dict) -> None:
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
        self.size_vars.append(size_var)
        size_lbl = tk.Label(frame, textvariable=size_var, font=FONT,
                            fg=C["accent_dim"], bg=row_bg, width=10, anchor="e")
        size_lbl.pack(side="right", padx=(0, 12))

        status_var = tk.StringVar(value="")
        self.status_vars.append(status_var)
        status_lbl = tk.Label(frame, textvariable=status_var, font=FONT,
                              fg=C["accent_dim"], bg=row_bg, width=30, anchor="w")
        status_lbl.pack(side="right")

        # Fetch folder size in background
        threading.Thread(
            target=lambda v=size_var, g=game: v.set(
                folder_size_str(get_installer_folder(g))),
            daemon=True,
        ).start()

        # Row interaction helpers
        def _set_bg(widget: tk.Widget, bg: str):
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
            _set_bg(r, C["row_hover"])
            s.configure(bg=C["cyan"] if v.get() else C["magenta"])

        def _leave(_e, r=frame, s=stripe, v=var, bg=row_bg):
            _set_bg(r, bg)
            s.configure(bg=C["cyan"] if v.get() else C["border"])

        for w in (frame, name_lbl, size_lbl, status_lbl):
            w.bind("<Button-1>", _toggle)
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
