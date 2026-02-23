#!/usr/bin/env python3
"""
Cobra LANs – Manifest updater
==============================
Scans the ``Installers/`` tree for MSI and CAB files, reads MSI metadata
(ProductName, ProductVersion) via the Windows Installer COM object, then
**fully regenerates** ``config/games.yaml``.

Manual fields already present in the YAML
(supports_player_name, requires_server_ip, server_msi, prerequisites)
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

# ── Paths (project root is one level above this script) ───────────────────────
ROOT_DIR  = Path(__file__).resolve().parent.parent
INST_DIR  = ROOT_DIR / "Installers"
YAML_PATH = ROOT_DIR / "config" / "games.yaml"

# Fields that must be kept exactly as the user configured them in YAML.
# NOTE: server_msi is now auto-detected from the Server/ subfolder.
MANUAL_KEYS = (
    "supports_player_name",
    "requires_server_ip",
    "prerequisites",
)


# ── MSI metadata reader ────────────────────────────────────────────────────────

def read_msi_properties(msi_path: Path) -> dict[str, str]:
    """
    Return ``{"ProductName": ..., "ProductVersion": ...}`` by querying the MSI
    database through the Windows Installer COM object via PowerShell.
    Returns an empty dict if reading fails (e.g. file not yet present).
    """
    # PowerShell command – open database read-only (mode 0), query the
    # Property table, collect rows into a hashtable, serialise to JSON.
    ps = (
        "$ErrorActionPreference='Stop';"
        "$i=New-Object -ComObject WindowsInstaller.Installer;"
        f"$d=$i.OpenDatabase([string]'{msi_path}',0);"
        "$q=$d.OpenView(\"SELECT Property,Value FROM Property "
        "WHERE Property='ProductName' OR Property='ProductVersion'\");"
        "$q.Execute();"
        "$r=[ordered]@{};"
        "do{$rec=$q.Fetch();if($rec -ne $null){$r[$rec.StringData(1)]=$rec.StringData(2)}}while($rec -ne $null);"
        "Write-Output (ConvertTo-Json $r -Compress)"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            text = result.stdout.strip()
            if text:
                return json.loads(text)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] MSI read failed for {msi_path.name}: {exc}", file=sys.stderr)
    return {}


# ── YAML helpers ───────────────────────────────────────────────────────────────

def load_existing_games() -> dict[str, dict]:
    """
    Parse the current YAML and return a dict keyed by game name so that
    manual settings can be carried forward into the regenerated file.
    """
    if not YAML_PATH.exists():
        return {}
    with open(YAML_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {g["name"]: g for g in data.get("games", [])}


# ── Core scanner ───────────────────────────────────────────────────────────────

def _find_subdir(parent: Path, name: str) -> Path | None:
    """Return the first child directory of *parent* whose name matches *name* case-insensitively."""
    for d in parent.iterdir():
        if d.is_dir() and d.name.lower() == name.lower():
            return d
    return None


def _scan_subdir(subdir: Path, base_abs: Path) -> tuple[list[dict], Path | None]:
    """
    Collect all MSI/CAB files inside *subdir* and return
    ``(file_entries, primary_msi)`` where paths in *file_entries* are relative
    to *base_abs* (the game's top-level installer directory).
    """
    inst_files = sorted(
        f for f in subdir.rglob("*")
        if f.is_file() and f.suffix.lower() in (".msi", ".cab")
    )
    if not inst_files:
        return [], None

    print(f"  Found {len(inst_files)} file(s).")
    file_entries: list[dict] = []
    primary_msi: Path | None = None
    for f in inst_files:
        rel = f.relative_to(base_abs).as_posix()  # e.g. "Game/Data1.cab"
        file_entries.append({"path": rel})
        if primary_msi is None and f.suffix.lower() == ".msi":
            primary_msi = f
    return file_entries, primary_msi


def scan_installers() -> list[dict]:
    """
    Walk every subdirectory of ``Installers/`` and build a complete game entry
    for each one.

    Each entry uses a ``base_path`` (e.g. ``Installers/Warcraft III``) and
    stores ``install_msi`` / ``server_msi`` paths *relative* to that base so
    the full path is never duplicated.  A ``Server/`` subfolder (case-insensitive)
    is automatically detected and produces ``server_msi`` + ``server_files``.
    """
    if not INST_DIR.exists():
        print(f"[error] Installers directory not found: {INST_DIR}", file=sys.stderr)
        sys.exit(1)

    existing   = load_existing_games()
    games: list[dict] = []

    game_dirs = sorted(d for d in INST_DIR.iterdir() if d.is_dir())
    if not game_dirs:
        print("[warn] No game directories found inside Installers/", file=sys.stderr)
        return []

    for game_dir in game_dirs:
        game_name     = game_dir.name
        base_path_rel = f"Installers/{game_name}"   # always forward-slash, relative to ROOT_DIR
        base_abs      = ROOT_DIR / base_path_rel     # absolute path = game_dir
        print(f"\nProcessing: {game_name}")

        # ── Locate game / server subdirs ───────────────────────────────────────
        game_subdir   = _find_subdir(game_dir, "game")
        server_subdir = _find_subdir(game_dir, "server")

        # Fallback: if there is no game/ subdir, scan game_dir itself
        scan_target = game_subdir if game_subdir else game_dir

        # ── Scan game installer files ──────────────────────────────────────────
        game_file_entries, primary_game_msi = _scan_subdir(scan_target, base_abs)

        # ── Scan server installer files (if present) ───────────────────────────
        server_file_entries: list[dict] = []
        primary_server_msi: Path | None = None
        if server_subdir:
            print(f"  Server dir detected – scanning …")
            server_file_entries, primary_server_msi = _scan_subdir(server_subdir, base_abs)

        # ── Placeholder when no files were found anywhere ──────────────────────
        if not game_file_entries and not server_file_entries:
            print(f"  [skip] No MSI/CAB files found – placeholder entry created.")
            existing_entry = existing.get(game_name, {})
            entry: dict = {
                "name":      game_name,
                "base_path": base_path_rel,
            }
            for k in MANUAL_KEYS:
                if k in existing_entry:
                    entry[k] = existing_entry[k]
                elif k == "prerequisites":
                    entry[k] = []
                elif k == "supports_player_name":
                    entry[k] = False
            entry["files"] = []
            games.append(entry)
            continue

        # ── Read MSI metadata from primary game MSI ────────────────────────────
        msi_version = ""
        if primary_game_msi:
            print(f"  Reading MSI metadata …")
            props = read_msi_properties(primary_game_msi)
            msi_version = props.get("ProductVersion", "").strip()
            if msi_version:
                print(f"  Version   : {msi_version}")
            else:
                print(f"  Version   : (not found in MSI)")

        # ── Merge with existing entry (preserve manual settings) ───────────────
        existing_entry = existing.get(game_name, {})
        entry = {
            "name":      game_name,
            "base_path": base_path_rel,
        }

        if msi_version:
            entry["version"] = msi_version

        if primary_game_msi:
            # Path is relative to base_abs (e.g. "Game/Warcraft III.msi")
            entry["install_msi"] = primary_game_msi.relative_to(base_abs).as_posix()

        if primary_server_msi:
            entry["server_msi"] = primary_server_msi.relative_to(base_abs).as_posix()

        for k in MANUAL_KEYS:
            if k in existing_entry:
                entry[k] = existing_entry[k]
            elif k == "prerequisites":
                entry[k] = []
            elif k == "supports_player_name":
                entry[k] = False

        entry["files"] = game_file_entries

        if server_file_entries:
            entry["server_files"] = server_file_entries

        games.append(entry)

    return games


# ── YAML writer ────────────────────────────────────────────────────────────────

def write_yaml(games: list[dict]) -> None:
    """Serialise *games* back to ``config/games.yaml``."""
    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(YAML_PATH, "w", encoding="utf-8") as fh:
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
        f"to {YAML_PATH.relative_to(ROOT_DIR)}"
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Cobra LANs – Manifest Updater")
    print("=" * 50)
    games = scan_installers()
    if games:
        write_yaml(games)
    else:
        print("[warn] Nothing written – no games found.", file=sys.stderr)
