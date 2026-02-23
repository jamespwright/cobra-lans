"""Cobra LANs – data loading and file-system utilities."""

import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import messagebox

import yaml

from .config import BASE_DIR, YAML_PATH


# Status constants returned by verify_game_files
STATUS_OK        = "ok"
STATUS_MISSING   = "missing"
STATUS_MISMATCH  = "mismatch"
STATUS_NO_FILES  = "no_files"


def load_games() -> list[dict]:
    """Load and return the games list from games.yaml; exits on failure."""
    if not YAML_PATH.exists():
        messagebox.showerror(
            "Error",
            (
                f"games.yaml not found:\n{YAML_PATH}\n\n"
                "Place a `config/games.yaml` next to the executable or in the current working directory."
            ),
        )
        sys.exit(1)
    with open(YAML_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("games", [])


def _sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _base_path(game: dict) -> Path:
    """Return the absolute base installer directory for *game*."""
    bp = game.get("base_path", "")
    if bp:
        return BASE_DIR / bp
    # Legacy fallback: old format stored full paths in files[].path
    return BASE_DIR


def get_installer_folder(game: dict, mode: str = "game") -> Path:
    """
    Return the absolute path to the game or server installer subdirectory.
    Tries an exact case-insensitive match for ``game/`` or ``server/``
    inside the game's base_path; falls back to base_path itself.
    """
    base = _base_path(game)
    target = "server" if mode == "server" else "game"
    if base.exists():
        for child in base.iterdir():
            if child.is_dir() and child.name.lower() == target:
                return child
    return base


def verify_game_files(game: dict, mode: str = "game") -> dict[str, str]:
    """
    Compare every file listed in ``game['files']`` (game mode) or
    ``game['server_files']`` (server mode) against its expected SHA-256.

    Paths in the file entries are relative to the game's ``base_path``.

    Returns a dict mapping each relative path to one of:
        ``STATUS_OK``       – file exists and hash matches
        ``STATUS_MISSING``  – file does not exist on disk
        ``STATUS_MISMATCH`` – file exists but hash differs

    Returns an empty dict when the game has no file entries for the mode.
    """
    file_key = "server_files" if mode == "server" else "files"
    base     = _base_path(game)

    entries = [
        (e["path"], e["sha256"])
        for e in game.get(file_key, [])
        if e.get("path") and e.get("sha256")
    ]
    if not entries:
        return {}

    def _check(rel_expected: tuple[str, str]) -> tuple[str, str]:
        rel, expected = rel_expected
        full_path = base / rel
        if not full_path.exists():
            return rel, STATUS_MISSING
        return rel, STATUS_OK if _sha256_file(full_path) == expected else STATUS_MISMATCH

    with ThreadPoolExecutor() as executor:
        return dict(executor.map(_check, entries))


def game_integrity_summary(file_results: dict[str, str]) -> tuple[str, str]:
    """
    Collapse per-file results into a concise ``(label, colour_key)`` pair
    suitable for display in the UI.

    ``colour_key`` is one of ``"green"``, ``"red"``, ``"yellow"``, ``"text_dim"``.
    """
    if not file_results:
        return "— no files", "text_dim"

    missing  = sum(1 for s in file_results.values() if s == STATUS_MISSING)
    mismatch = sum(1 for s in file_results.values() if s == STATUS_MISMATCH)

    if missing == 0 and mismatch == 0:
        return "\u2713 OK", "green"
    parts: list[str] = []
    if missing:
        parts.append(f"{missing} missing")
    if mismatch:
        parts.append(f"{mismatch} mismatch")
    colour = "red" if missing else "yellow"
    return f"\u2717 {', '.join(parts)}", colour


def folder_size_str(path: Path) -> str:
    """Return a human-readable size string for *path*, or '—' if absent/empty."""
    if not path.exists():
        return "—"
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    if total == 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024.0:
            return f"{total:.1f} {unit}"
        total /= 1024.0
    return f"{total:.1f} TB"
