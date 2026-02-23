"""Cobra LANs – data loading and file-system utilities."""

import json
import sys
from pathlib import Path
from tkinter import messagebox

import yaml

from .config import BASE_DIR, YAML_PATH


# Status constants returned by verify_game_files
STATUS_OK        = "ok"
STATUS_MISSING   = "missing"
STATUS_MISMATCH  = "mismatch"   # MSI ProductVersion differs from YAML version


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


def _read_msi_version(msi_path: Path) -> str:
    """
    Return the ProductVersion string from *msi_path* using the standard-library
    ``msilib`` module (Windows only).  Returns an empty string on failure.
    """
    try:
        import msilib  # noqa: PLC0415 – Windows-only stdlib module
        db = msilib.OpenDatabase(str(msi_path), msilib.MSIDBOPEN_READONLY)
        view = db.OpenView("SELECT Value FROM Property WHERE Property='ProductVersion'")
        view.Execute(None)
        record = view.Fetch()
        if record:
            return record.GetString(1)
    except Exception:  # noqa: BLE001
        pass
    return ""


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
    Check every file listed in ``game['files']`` (game mode) or
    ``game['server_files']`` (server mode) for existence on disk.
    For the primary MSI, also verify that its ProductVersion matches
    the ``version`` recorded in the YAML.

    Paths in the file entries are relative to the game's ``base_path``.

    Returns a dict mapping each relative path to one of:
        ``STATUS_OK``       – file exists (and MSI version matches, if applicable)
        ``STATUS_MISSING``  – file does not exist on disk
        ``STATUS_MISMATCH`` – MSI exists but its ProductVersion differs from game['version']

    Returns an empty dict when the game has no file entries for the mode.
    """
    file_key         = "server_files" if mode == "server" else "files"
    msi_key          = "server_msi"   if mode == "server" else "install_msi"
    base             = _base_path(game)
    msi_rel          = game.get(msi_key, "")
    expected_version = game.get("version", "").strip()

    entries = [e["path"] for e in game.get(file_key, []) if e.get("path")]
    if not entries:
        return {}

    results: dict[str, str] = {}
    for rel in entries:
        full_path = base / rel
        if not full_path.exists():
            results[rel] = STATUS_MISSING
        elif msi_rel and Path(rel).as_posix() == Path(msi_rel).as_posix() and expected_version:
            # Primary MSI – validate ProductVersion against the YAML version field
            actual_version = _read_msi_version(full_path)
            results[rel] = STATUS_OK if actual_version == expected_version else STATUS_MISMATCH
        else:
            results[rel] = STATUS_OK
    return results


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
