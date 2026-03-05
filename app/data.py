"""Cobra LANs – data loading and file-system utilities."""

import subprocess
import sys
import zlib
from pathlib import Path
from tkinter import messagebox

import yaml

from .config import BASE_DIR, FILTER_PATH, MANIFEST_PATH, YAML_PATH


def load_games() -> list[dict]:
    """Load and return the games list from games.yaml.

    If ``config/filter.yaml`` exists its ``games`` list is treated as an
    allow-list of game names; only matching entries are returned.
    Exits on failure to read games.yaml.
    """
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
    games = data.get("games", [])

    # Apply optional allow-list filter
    if FILTER_PATH is not None:
        with open(FILTER_PATH, "r", encoding="utf-8") as fh:
            filter_data = yaml.safe_load(fh) or {}
        if filter_data.get("enabled", True):
            allowed = {str(n) for n in (filter_data.get("games") or [])}
            if allowed:
                games = [g for g in games if g.get("name") in allowed]

    return games


def load_manifest() -> dict[str, list[dict]]:
    """Load ``config/manifest.yaml`` and return a dict mapping game name to
    its list of ``{"path": ..., "crc32": ...}`` file records.

    Returns an empty dict if the manifest does not exist.
    """
    if not MANIFEST_PATH.exists():
        return {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    raw = data.get("games", {})
    # Each value is {"files": [...]}
    return {name: entry.get("files", []) for name, entry in raw.items()}


def _base_path(game: dict) -> Path:
    """Return the absolute base installer directory for *game*."""
    bp = game.get("base_path", "")
    return BASE_DIR / bp if bp else BASE_DIR


def get_installer_folder(game: dict) -> Path:
    """Return the absolute path to the installer directory for *game*.

    ``base_path`` already points to the full installer subdirectory
    (e.g. ``Installers/Call Of Duty 4/Game``), so this simply resolves it.
    """
    return _base_path(game)


def _primary_installer_path(game: dict) -> Path | None:
    """Return the absolute path to the primary installer for *game*, or ``None``."""
    base = _base_path(game)
    rel  = game.get("install_exe") or game.get("install_msi") or ""
    return base / rel if rel else None


def _crc32_file(path: Path) -> str:
    """Return the CRC32 of *path* as an 8-char uppercase hex string (1 MB chunks)."""
    crc = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def _read_installer_version(installer: Path, installer_type: str) -> str:
    """Read the version string from the primary installer file.

    Uses PowerShell to query ``ProductVersion`` from the EXE version resource
    (Inno Setup) or the MSI Property table.  Returns an empty string on failure.
    """
    if installer_type == "inno_setup":
        ps = (
            "$ErrorActionPreference='Stop';"
            f"$v=(Get-Item '{installer}').VersionInfo.ProductVersion;"
            "if($v){Write-Output $v}"
        )
    else:
        ps = (
            "$ErrorActionPreference='Stop';"
            "$i=New-Object -ComObject WindowsInstaller.Installer;"
            f"$d=$i.OpenDatabase([string]'{installer}',0);"
            "$q=$d.OpenView(\"SELECT Value FROM Property WHERE Property='ProductVersion'\");"
            "$q.Execute();"
            "$rec=$q.Fetch();"
            "if($rec -ne $null){Write-Output $rec.StringData(1)}"
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
    except Exception:  # noqa: BLE001
        pass
    return ""


# ── Game file checks (used by right-click "Check Game Files") ──────────────────

class FileCheckResult:
    """Holds pass/fail detail for a single check category."""

    def __init__(self, name: str):
        self.name    = name
        self.passed  = True
        self.details: list[str] = []

    def fail(self, msg: str) -> None:
        self.passed = False
        self.details.append(msg)

    def info(self, msg: str) -> None:
        self.details.append(msg)


def check_game_files(
    game: dict,
    manifest: dict[str, list[dict]],
    progress_cb=None,
) -> tuple[str, str, str]:
    """Run all three game-file checks and return ``(report, colour_key, short_label)``.

    Checks performed:
    1. All files listed in manifest.yaml exist on disk.
    2. CRC32 of every file matches the manifest.
    3. The primary installer's version matches ``games.yaml``.

    *progress_cb*, if provided, is called with a short string at each step so
    the UI can display what is currently being checked.
    *colour_key* is one of ``"green"`` or ``"red"``.
    *short_label* is a concise pass/fail string for the row status column.
    """
    def _progress(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    name      = game.get("name", "")
    base      = _base_path(game)
    file_list = manifest.get(name, [])

    exist_check   = FileCheckResult("Files Present")
    crc_check     = FileCheckResult("CRC32 Integrity")
    version_check = FileCheckResult("Version Match")

    # ── Check 1 & 2: existence and CRC ────────────────────────────────────────
    if not file_list:
        exist_check.fail("No manifest entry found – run update_manifest.py first.")
        crc_check.fail("Skipped (no manifest).")
    else:
        _progress("Checking files\u2026")
        for rec in file_list:
            rel_path   = rec.get("path", "")
            expected   = (rec.get("crc32") or "").strip().upper()
            full_path  = base / rel_path

            if not full_path.exists():
                exist_check.fail(f"Missing: {rel_path}")
                crc_check.fail(f"Cannot check (missing): {rel_path}")
            else:
                exist_check.info(f"OK: {rel_path}")
                if expected:
                    _progress(f"CRC: {Path(rel_path).name}")
                    actual = _crc32_file(full_path)
                    if actual == expected:
                        crc_check.info(f"OK: {rel_path}")
                    else:
                        crc_check.fail(f"Mismatch: {rel_path}  (expected {expected}, got {actual})")
                else:
                    crc_check.info(f"No CRC recorded: {rel_path}")

    # ── Check 3: version ──────────────────────────────────────────────────────
    _progress("Checking version\u2026")
    expected_version = str(game.get("version", "")).strip()
    installer_path   = _primary_installer_path(game)
    installer_type   = game.get("installer_type", "inno_setup")

    if not expected_version:
        version_check.info("No version recorded in games.yaml – skipped.")
    elif installer_path is None:
        version_check.fail("No installer path configured.")
    elif not installer_path.exists():
        version_check.fail(f"Installer not found: {installer_path.name}")
    else:
        actual_version = _read_installer_version(installer_path, installer_type)
        if not actual_version:
            version_check.fail("Could not read version from installer file.")
        elif actual_version.strip() == expected_version:
            version_check.info(f"Version matches: {actual_version}")
        else:
            version_check.fail(
                f"Version mismatch – expected {expected_version!r}, "
                f"got {actual_version!r}"
            )

    # ── Build report ──────────────────────────────────────────────────────────
    all_checks = [exist_check, crc_check, version_check]
    lines: list[str] = []
    overall_ok = True
    for chk in all_checks:
        icon = "\u2713" if chk.passed else "\u2717"
        lines.append(f"{icon} {chk.name}")
        if not chk.passed:
            overall_ok = False
            for d in chk.details:
                if not d.startswith("OK:"):
                    lines.append(f"    {d}")
        else:
            for d in chk.details:
                if d.startswith("No "):
                    lines.append(f"    {d}")

    report = "\n".join(lines)
    colour_key = "green" if overall_ok else "red"

    # ── Build short label for the row status column ───────────────────────────
    failures = [c for c in all_checks if not c.passed]
    if not failures:
        short_label = "\u2713 OK"
    elif len(failures) == 1:
        _short_map = {
            "Files Present":   "\u2717 Missing",
            "CRC32 Integrity": "\u2717 CRC",
            "Version Match":   "\u2717 Version",
        }
        short_label = _short_map.get(failures[0].name, "\u2717 Failed")
    else:
        short_label = "\u2717 Issues"

    return report, colour_key, short_label


def folder_size_str(path: Path) -> str:
    """Return a human-readable size string for *path*, or '—' if absent/empty."""
    if not path.exists():
        return "\u2014"
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    if total == 0:
        return "\u2014"
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024.0:
            return f"{total:.1f} {unit}"
        total /= 1024.0
    return f"{total:.1f} TB"
