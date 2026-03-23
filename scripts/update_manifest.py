#!/usr/bin/env python3
"""
LAN Game Installer – Games updater
===========================
Scans the ``Installers/`` tree, finds the primary installer (.exe or .msi)
for each game, then **fully regenerates**:

* ``config/games.yaml``  – game metadata (name, paths, flags).

Manual fields already present in games.yaml
(supports_player_name, requires_server_ip, prerequisites)
are preserved; everything else is re-derived from the file system.

Usage
-----
    python scripts/update_manifest.py
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

# ── Paths (project root is one level above this script) ─────────────────────
ROOT_DIR      = Path(__file__).resolve().parent.parent
INST_DIR      = ROOT_DIR / "Installers"
GAMES_PATH     = ROOT_DIR / "config" / "games.yaml"

# Fields that must be kept exactly as the user configured them in YAML.
MANUAL_KEYS = (
    "supports_player_name",
    "requires_server_ip",
    "prerequisites",
)

# ── YAML helpers ───────────────────────────────────────────────────────────────

def load_existing_games() -> dict[str, dict]:
    """
    Parse the current YAML and return a dict keyed by game name so that
    manual settings can be carried forward into the regenerated file.
    """
    if not GAMES_PATH.exists():
        raise FileNotFoundError(f"Missing games.yaml at {GAMES_PATH}")

    with open(GAMES_PATH, encoding="utf-8") as fh:
        games_data = yaml.safe_load(fh)
    return {g["name"]: g for g in games_data.get("games", [])}


def _get_existing_entry(existing: dict[str, dict], name: str) -> dict:
    """
    Look up an existing entry by name.  For server entries named ``"X Server"``
    that don't yet exist (first run after migration from combined format),
    fall back to the base name ``"X"`` so manual settings are preserved.
    """
    if name in existing:
        return existing[name]
    if name.endswith(" Server"):
        base = name[: -len(" Server")]
        if base in existing:
            return existing[base]
    return {}


# ── Core scanner ───────────────────────────────────────────────────────────────

def _find_subdir(parent: Path, name: str) -> Path | None:
    """Return the first child directory of *parent* whose name matches *name* case-insensitively."""
    for d in parent.iterdir():
        if d.is_dir() and d.name.lower() == name.lower():
            return d
    return None


def _find_primary_installer(subdir: Path) -> tuple[Path | None, str]:
    """
    Locate the primary installer inside *subdir* and return
    ``(primary_path, installer_type)`` where ``installer_type`` is
    ``"inno_setup"`` when ``.bin`` split-files are present, otherwise ``"msi"``.

    Only ``.exe``/``.bin`` (Inno Setup) or ``.msi``/``.cab`` (MSI) files are
    considered.  The first matching primary file is returned.
    """
    _MSI_EXTS  = {".msi", ".cab"}
    _INNO_EXTS = {".exe", ".bin"}

    all_files = sorted(
        f for f in subdir.rglob("*")
        if f.is_file() and f.suffix.lower() in (_MSI_EXTS | _INNO_EXTS)
    )
    if not all_files:
        return None, "msi"

    has_bin        = any(f.suffix.lower() == ".bin" for f in all_files)
    installer_type = "inno_setup" if has_bin else "msi"
    primary_ext    = ".exe" if installer_type == "inno_setup" else ".msi"

    primary = next(
        (f for f in all_files if f.suffix.lower() == primary_ext),
        None,
    )
    print(f"  Installer type : {installer_type}")
    if primary:
        print(f"  Primary file   : {primary.name}")
    return primary, installer_type


def scan_installers() -> list[dict]:
    """
    Walk every subdirectory of ``Installers/`` and build installer entries.

    Returns a list of game metadata dicts for ``games.yaml``.

    Each game entry has a ``type`` of ``"game"`` or ``"server"``, identifies the
    primary installer via ``install_exe`` or ``install_msi``.

    A ``Server/`` subfolder (case-insensitive) is automatically detected and
    produces a separate server entry.
    """
    if not INST_DIR.exists():
        print(f"[error] Installers directory not found: {INST_DIR}", file=sys.stderr)
        sys.exit(1)

    existing   = load_existing_games()
    games:    list[dict]             = []

    game_dirs = sorted(d for d in INST_DIR.iterdir() if d.is_dir())
    if not game_dirs:
        print("[warn] No game directories found inside Installers/", file=sys.stderr)
        return []

    for game_dir in game_dirs:
        dir_name      = game_dir.name
        base_path_rel = f"Installers/{dir_name}"
        print(f"\nProcessing: {dir_name}")

        game_subdir   = _find_subdir(game_dir, "game")
        server_subdir = _find_subdir(game_dir, "server")

        # Determine scan targets
        if game_subdir:
            game_scan_target: Path | None = game_subdir
        elif not server_subdir:
            game_scan_target = game_dir
        else:
            game_scan_target = None

        # ── Scan game installer ────────────────────────────────────────────────
        primary_game:    Path | None = None
        game_inst_type:  str = "msi"
        if game_scan_target is not None:
            primary_game, game_inst_type = _find_primary_installer(game_scan_target)

        # ── Scan server installer ──────────────────────────────────────────────
        primary_server:    Path | None = None
        server_inst_type:  str = "msi"
        if server_subdir:
            print("  Server dir detected – scanning …")
            primary_server, server_inst_type = _find_primary_installer(server_subdir)

        # ── Placeholder when nothing found ────────────────────────────────────
        if primary_game is None and primary_server is None:
            print("  [skip] No installer found – placeholder entry created.")
            existing_entry = _get_existing_entry(existing, dir_name)
            entry: dict = {
                "name":      dir_name,
                "type":      "game",
                "base_path": base_path_rel,
            }
            for k in MANUAL_KEYS:
                if k in existing_entry:
                    entry[k] = existing_entry[k]
                elif k == "prerequisites":
                    entry[k] = []
                elif k == "supports_player_name":
                    entry[k] = False
            games.append(entry)
            continue

        # ── Build game entry ───────────────────────────────────────────────────
        if primary_game is not None:

            existing_entry = _get_existing_entry(existing, dir_name)
            inst_key = "install_exe" if game_inst_type == "inno_setup" else "install_msi"
            game_base = (
                f"Installers/{dir_name}/{game_scan_target.name}"
                if game_scan_target is not game_dir
                else base_path_rel
            )
            entry = {
                "name":           dir_name,
                "type":           "game",
                "installer_type": game_inst_type,
                "base_path":      game_base,
            }
            entry[inst_key] = primary_game.name
            for k in MANUAL_KEYS:
                if k in existing_entry:
                    entry[k] = existing_entry[k]
                elif k == "prerequisites":
                    entry[k] = []
                elif k == "supports_player_name":
                    entry[k] = False
            games.append(entry)

        # ── Build server entry ─────────────────────────────────────────────────
        if primary_server is not None:
            server_name    = f"{dir_name} Server" if primary_game is not None else dir_name
            existing_entry = _get_existing_entry(existing, server_name)

            inst_key = "install_exe" if server_inst_type == "inno_setup" else "install_msi"
            server_entry: dict = {
                "name":           server_name,
                "type":           "server",
                "installer_type": server_inst_type,
                "base_path":      f"Installers/{dir_name}/{server_subdir.name}",
            }
            server_entry[inst_key] = primary_server.name
            for k in MANUAL_KEYS:
                if k in existing_entry:
                    server_entry[k] = existing_entry[k]
                elif k == "prerequisites":
                    server_entry[k] = []
                elif k == "supports_player_name":
                    server_entry[k] = False
            games.append(server_entry)

    return games


# ── YAML writers ──────────────────────────────────────────────────────────────

def write_yaml(games: list[dict]) -> None:
    """Serialise *games* back to ``config/games.yaml``."""
    GAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GAMES_PATH, "w", encoding="utf-8") as fh:
        yaml.dump(
            {"games": games},
            fh,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )
    print(
        f"\n[done] Wrote {len(games)} game entr{'y' if len(games) == 1 else 'ies'} "
        f"to {GAMES_PATH.relative_to(ROOT_DIR)}"
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("LAN Game Installer – Games Updater")
    print("=" * 50)
    games = scan_installers()
    if games:
        write_yaml(games)
    else:
        print("[warn] Nothing written – no games found.", file=sys.stderr)
