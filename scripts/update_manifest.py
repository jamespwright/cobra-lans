#!/usr/bin/env python3
"""
Cobra LANs – Manifest updater
==============================
Scans the ``Installers/`` tree for MSI and CAB files, reads MSI metadata
(ProductName, ProductVersion) via the Windows Installer COM object, then
**fully regenerates** ``config/games.yaml``.

Manual fields already present in the YAML
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

# ── Paths (project root is one level above this script) ───────────────────────
ROOT_DIR  = Path(__file__).resolve().parent.parent
INST_DIR  = ROOT_DIR / "Installers"
YAML_PATH = ROOT_DIR / "config" / "games.yaml"

# Fields that must be kept exactly as the user configured them in YAML.
MANUAL_KEYS = (
    "supports_player_name",
    "requires_server_ip",
    "prerequisites",
)


# ── Installer metadata readers ────────────────────────────────────────────────

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


def read_exe_version(exe_path: Path) -> str:
    """
    Return the ``ProductVersion`` from an EXE's version resource via PowerShell.
    Returns an empty string if reading fails.
    """
    ps = (
        "$ErrorActionPreference='Stop';"
        f"$v=(Get-Item '{exe_path}').VersionInfo.ProductVersion;"
        "if($v){Write-Output $v}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] EXE version read failed for {exe_path.name}: {exc}", file=sys.stderr)
    return ""


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


def _scan_subdir(subdir: Path, base_abs: Path) -> tuple[list[dict], Path | None, str]:
    """
    Collect all installer files inside *subdir* and return
    ``(file_entries, primary_installer, installer_type)`` where paths in
    *file_entries* are relative to *base_abs*.

    ``installer_type`` is ``"inno_setup"`` when ``.bin`` files are detected
    (Inno Setup splits its payload into ``.exe`` + ``.bin`` parts),
    otherwise ``"msi"``.
    """
    _MSI_EXTS  = {".msi", ".cab"}
    _INNO_EXTS = {".exe", ".bin"}

    all_files = sorted(
        f for f in subdir.rglob("*")
        if f.is_file() and f.suffix.lower() in (_MSI_EXTS | _INNO_EXTS)
    )
    if not all_files:
        return [], None, "msi"

    # Presence of .bin files is the signal for Inno Setup
    has_bin        = any(f.suffix.lower() == ".bin" for f in all_files)
    installer_type = "inno_setup" if has_bin else "msi"
    keep_exts      = _INNO_EXTS if installer_type == "inno_setup" else _MSI_EXTS
    inst_files     = [f for f in all_files if f.suffix.lower() in keep_exts]

    print(f"  Found {len(inst_files)} file(s) [{installer_type}].")
    file_entries: list[dict]  = []
    primary:      Path | None = None
    for f in inst_files:
        rel = f.relative_to(base_abs).as_posix()
        file_entries.append({"path": rel})
        if primary is None:
            suffix = f.suffix.lower()
            if (installer_type == "inno_setup" and suffix == ".exe") or \
               (installer_type == "msi"         and suffix == ".msi"):
                primary = f
    return file_entries, primary, installer_type


def scan_installers() -> list[dict]:
    """
    Walk every subdirectory of ``Installers/`` and build complete installer
    entries for each one.

    Each entry has a ``type`` of ``"game"`` or ``"server"`` and uses
    ``base_path`` + relative ``install_msi`` paths so the full path is
    never duplicated.  A ``Server/`` subfolder (case-insensitive) is
    automatically detected and produces a *separate* server entry rather
    than being embedded alongside the game entry.
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
        dir_name      = game_dir.name
        base_path_rel = f"Installers/{dir_name}"   # always forward-slash, relative to ROOT_DIR
        base_abs      = ROOT_DIR / base_path_rel     # absolute path = game_dir
        print(f"\nProcessing: {dir_name}")

        # ── Locate game / server subdirs ───────────────────────────────────────
        game_subdir   = _find_subdir(game_dir, "game")
        server_subdir = _find_subdir(game_dir, "server")

        # ── Scan game installer files ──────────────────────────────────────────
        # If there's a dedicated game/ subdir, scan it; if not and there's no
        # server/ either, fall back to scanning the dir root as a game entry.
        if game_subdir:
            game_scan_target: Path | None = game_subdir
        elif not server_subdir:
            game_scan_target = game_dir   # root-level files treated as game
        else:
            game_scan_target = None       # server-only directory

        game_file_entries:    list[dict] = []
        primary_game_inst:   Path | None = None
        game_installer_type: str = "msi"
        if game_scan_target is not None:
            game_file_entries, primary_game_inst, game_installer_type = _scan_subdir(game_scan_target, base_abs)

        # ── Scan server installer files (if present) ───────────────────────────
        server_file_entries:   list[dict] = []
        primary_server_inst:   Path | None = None
        server_installer_type: str = "msi"
        if server_subdir:
            print("  Server dir detected – scanning …")
            server_file_entries, primary_server_inst, server_installer_type = _scan_subdir(server_subdir, base_abs)

        # ── Placeholder when no files were found anywhere ──────────────────────
        if not game_file_entries and not server_file_entries:
            print("  [skip] No installer files found – placeholder entry created.")
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
            entry["files"] = []
            games.append(entry)
            continue

        # ── Build game entry (if game files exist) ─────────────────────────────
        if game_file_entries:
            version = ""
            if primary_game_inst:
                if game_installer_type == "inno_setup":
                    print("  Reading EXE version …")
                    version = read_exe_version(primary_game_inst)
                else:
                    print("  Reading MSI metadata …")
                    props = read_msi_properties(primary_game_inst)
                    version = props.get("ProductVersion", "").strip()
                print(f"  Version   : {version or '(not found)'}")

            existing_entry = _get_existing_entry(existing, dir_name)
            entry = {
                "name":           dir_name,
                "type":           "game",
                "installer_type": game_installer_type,
                "base_path":      base_path_rel,
            }
            if version:
                entry["version"] = version
            if primary_game_inst:
                inst_key = "install_exe" if game_installer_type == "inno_setup" else "install_msi"
                entry[inst_key] = primary_game_inst.relative_to(base_abs).as_posix()
            for k in MANUAL_KEYS:
                if k in existing_entry:
                    entry[k] = existing_entry[k]
                elif k == "prerequisites":
                    entry[k] = []
                elif k == "supports_player_name":
                    entry[k] = False
            entry["files"] = game_file_entries
            games.append(entry)

        # ── Build server entry (separate entry, never embedded) ────────────────
        if server_file_entries:
            # Name the server entry "<dir> Server" when a game entry also
            # exists, otherwise keep the original directory name.
            server_name    = f"{dir_name} Server" if game_file_entries else dir_name
            existing_entry = _get_existing_entry(existing, server_name)

            version = ""
            if primary_server_inst:
                if server_installer_type == "inno_setup":
                    print("  Reading server EXE version …")
                    version = read_exe_version(primary_server_inst)
                else:
                    print("  Reading server MSI metadata …")
                    props = read_msi_properties(primary_server_inst)
                    version = props.get("ProductVersion", "").strip()
                print(f"  Server version: {version or '(not found)'}")

            server_entry: dict = {
                "name":           server_name,
                "type":           "server",
                "installer_type": server_installer_type,
                "base_path":      base_path_rel,
            }
            if version:
                server_entry["version"] = version
            if primary_server_inst:
                inst_key = "install_exe" if server_installer_type == "inno_setup" else "install_msi"
                server_entry[inst_key] = primary_server_inst.relative_to(base_abs).as_posix()
            for k in MANUAL_KEYS:
                if k in existing_entry:
                    server_entry[k] = existing_entry[k]
                elif k == "prerequisites":
                    server_entry[k] = []
                elif k == "supports_player_name":
                    server_entry[k] = False
            server_entry["files"] = server_file_entries
            games.append(server_entry)

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
