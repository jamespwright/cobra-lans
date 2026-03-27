# Scrollable game-list panel.
#
# Displays all games that match the current install mode (game / server)
# as selectable rows with a checkbox, name, and selection highlight.
# Owns no business logic – just presentation and selection state.

import tkinter as tk

from .theme import C, FONT, FONT_BOLD
from .widgets import CyberScrollbar, neon_line


class GameList(tk.Frame):
    """Scrollable, selectable game list with column headers."""

    def __init__(self, parent: tk.Widget, on_select=None):
        super().__init__(parent, bg=C["surface"])

        self.check_vars: list[tk.BooleanVar] = []
        self.visible_games: list[dict] = []
        self._stripe_widgets: list[tk.Frame] = []
        self._row_frames: list[tuple[tk.Frame, str]] = []
        self._check_all_var = tk.BooleanVar(value=False)
        self._on_select = on_select
        self._selected_idx = -1

        container = tk.Frame(self, bg=C["surface"])
        container.pack(fill="both", expand=True)

        # Scrollable canvas with retro-styled scrollbar
        scroll_host = tk.Frame(container, bg=C["surface"])
        scroll_host.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(scroll_host, bg=C["surface"], highlightthickness=0, bd=0)
        canvas = self._canvas
        scrollbar = CyberScrollbar(
            scroll_host, command=canvas.yview, width=24,
            thumb_min=40, thumb_max=520,
            bg=C["surface"], thumb_color=C["border"],
            thumb_hover=C["accent_dim"], thumb_press=C["cyan"],
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._row_container = tk.Frame(canvas, bg=C["surface"])
        win_id = canvas.create_window((0, 0), window=self._row_container, anchor="nw")
        self._row_container.bind("<Configure>", lambda _: self._sync_scrollregion())
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width) or self._sync_scrollregion())
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-(e.delta // 120), "units"))

    # ── Public API ────────────────────────────────────────────────────────────

    def populate(self, games: list[dict], mode: str) -> None:
        """Rebuild the game rows for the given install mode."""
        for child in self._row_container.winfo_children():
            child.destroy()
        self.check_vars.clear()
        self._stripe_widgets.clear()
        self._row_frames.clear()
        self._check_all_var.set(False)
        self._selected_idx = -1

        self.visible_games = [g for g in games if g.get("type", "game") == mode]
        for idx, game in enumerate(self.visible_games):
            self._add_row(idx, game)
        if self.visible_games:
            self.select_game(0)

        self._row_container.update_idletasks()
        self._sync_scrollregion()
        self._canvas.yview_moveto(0)

    def selected_games(self) -> list[dict]:
        """Return the list of currently checked games."""
        return [self.visible_games[i] for i, v in enumerate(self.check_vars) if v.get()]

    def selected_game(self) -> dict | None:
        """Return the currently highlighted game, or None."""
        if 0 <= self._selected_idx < len(self.visible_games):
            return self.visible_games[self._selected_idx]
        return None

    def select_game(self, idx: int) -> None:
        """Highlight row *idx* and fire the on_select callback."""
        if idx == self._selected_idx:
            return
        if 0 <= self._selected_idx < len(self._row_frames):
            old_frame, old_bg = self._row_frames[self._selected_idx]
            self._set_row_bg(old_frame, old_bg)
        self._selected_idx = idx
        if 0 <= idx < len(self._row_frames):
            new_frame, _ = self._row_frames[idx]
            self._set_row_bg(new_frame, C["row_hover"])
        if self._on_select and 0 <= idx < len(self.visible_games):
            self._on_select(self.visible_games[idx])

    # ── Private ───────────────────────────────────────────────────────────────

    def _sync_scrollregion(self) -> None:
        bb = self._canvas.bbox("all") or (0, 0, 0, 0)
        h = max(bb[3], self._canvas.winfo_height())
        self._canvas.configure(scrollregion=(bb[0], bb[1], bb[2], h))

    def _toggle_all(self) -> None:
        state = self._check_all_var.get()
        for v, s in zip(self.check_vars, self._stripe_widgets):
            v.set(state)
            s.configure(bg=C["cyan"] if state else C["border"])

    def _sync_select_all(self) -> None:
        self._check_all_var.set(
            all(v.get() for v in self.check_vars) if self.check_vars else False)

    @staticmethod
    def _set_row_bg(frame: tk.Frame, bg: str) -> None:
        frame.configure(bg=bg)
        for child in frame.winfo_children():
            try:
                child.configure(bg=bg)
            except tk.TclError:
                pass

    def _add_row(self, idx: int, game: dict) -> None:
        row_bg = C["row_even"] if idx % 2 == 0 else C["row_odd"]

        frame = tk.Frame(self._row_container, bg=row_bg, pady=6, cursor="hand2")
        frame.pack(fill="x")

        stripe = tk.Frame(frame, bg=C["border"], width=4)
        stripe.pack(side="left", fill="y")

        var = tk.BooleanVar(value=False)
        self.check_vars.append(var)
        self._stripe_widgets.append(stripe)
        self._row_frames.append((frame, row_bg))

        def _update_stripe(v=var, s=stripe):
            s.configure(bg=C["cyan"] if v.get() else C["border"])
            self._sync_select_all()

        cb = tk.Checkbutton(
            frame, variable=var, command=_update_stripe,
            bg=row_bg, fg=C["cyan"],
            selectcolor=C["cb_select"], activebackground=row_bg,
            activeforeground=C["cyan"], bd=0, relief="flat",
        )
        cb.pack(side="left", padx=(6, 0))

        tk.Label(frame, text=f"{idx + 1:02d}", font=FONT,
                 bg=row_bg, fg=C["text_dim"], width=3, anchor="e").pack(side="left")

        name_lbl = tk.Label(frame, text=game["name"], font=FONT,
                            fg=C["text"], bg=row_bg, anchor="w")
        name_lbl.pack(side="left", padx=(8, 0), fill="x", expand=True)

        # Row interaction helpers
        def _select(_e, i=idx):
            self.select_game(i)

        def _enter(_e, r=frame, s=stripe, v=var, i=idx):
            if self._selected_idx != i:
                self._set_row_bg(r, C["row_hover"])
            s.configure(bg=C["cyan"] if v.get() else C["magenta"])

        def _leave(_e, r=frame, s=stripe, v=var, bg=row_bg, i=idx):
            sel_bg = C["row_hover"] if self._selected_idx == i else bg
            self._set_row_bg(r, sel_bg)
            s.configure(bg=C["cyan"] if v.get() else C["border"])

        for w in (frame, name_lbl):
            w.bind("<Button-1>", _select)
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
        cb.bind("<Enter>", _enter)
        cb.bind("<Leave>", _leave)
