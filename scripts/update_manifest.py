#!/usr/bin/env python3
"""
Cobra LANs – Manifest updater
==============================
Scans the ``Installers/`` tree, finds the primary installer (.exe or .msi)
for each game, reads its version, computes its CRC32 hash, then **fully
regenerates** ``config/games.yaml``.

Only the primary installer is recorded — the per-file ``files`` list is not
used.  The CRC32 is stored as ``crc32`` on each entry so the app can do a
fast single-file integrity check at startup.

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
import zlib
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


# ── CRC32 helper ──────────────────────────────────────────────────────────────

def _crc32_file(path: Path) -> str:
    """Return the CRC32 of *path* as an 8-char uppercase hex string (1 MB chunks)."""
    crc = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


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

    Each entry has a ``type`` of ``"game"`` or ``"server"``, identifies the
    primary installer via ``install_exe`` or ``install_msi``, records the
    version, and stores a ``crc32`` hash of the primary installer file so the
    app can perform a fast single-file integrity check at startup.

    A ``Server/`` subfolder (case-insensitive) is automatically detected and
    produces a separate server entry.
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
            version = ""
            if game_inst_type == "inno_setup":
                print("  Reading EXE version …")
                version = read_exe_version(primary_game)
            else:
                print("  Reading MSI metadata …")
                props   = read_msi_properties(primary_game)
                version = props.get("ProductVersion", "").strip()
            print(f"  Version        : {version or '(not found)'}")

            print("  Computing CRC32 …")
            crc = _crc32_file(primary_game)
            print(f"  CRC32          : {crc}")

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
            if version:
                entry["version"] = version
            entry[inst_key] = primary_game.name
            entry["crc32"]  = crc
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

            version = ""
            if server_inst_type == "inno_setup":
                print("  Reading server EXE version …")
                version = read_exe_version(primary_server)
            else:
                print("  Reading server MSI metadata …")
                props   = read_msi_properties(primary_server)
                version = props.get("ProductVersion", "").strip()
            print(f"  Server version : {version or '(not found)'}")

            print("  Computing server CRC32 …")
            crc = _crc32_file(primary_server)
            print(f"  Server CRC32   : {crc}")

            inst_key = "install_exe" if server_inst_type == "inno_setup" else "install_msi"
            server_entry: dict = {
                "name":           server_name,
                "type":           "server",
                "installer_type": server_inst_type,
                "base_path":      f"Installers/{dir_name}/{server_subdir.name}",
            }
            if version:
                server_entry["version"] = version
            server_entry[inst_key] = primary_server.name
            server_entry["crc32"]  = crc
            for k in MANUAL_KEYS:
                if k in existing_entry:
                    server_entry[k] = existing_entry[k]
                elif k == "prerequisites":
                    server_entry[k] = []
                elif k == "supports_player_name":
                    server_entry[k] = False
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
