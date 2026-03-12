"""Cobra LANs – download & install logic (no UI dependencies)."""

import os
import subprocess
from typing import Callable

from .config import BASE_DIR
from .downloader import download_game

StatusCallback = Callable[[str, str], None]


def run_installs(
    games: list[dict],
    install_dir: str,
    player: str,
    server_ip_parts: list[str] | None,
    download_url: str | None = None,
    status_callback: StatusCallback | None = None,
) -> list[str]:
    """Download (when *download_url* is set) and install each game.

    Returns a list of error messages (empty = all OK).
    """
    errors: list[str] = []

    for game in games:
        name = game["name"]

        def _notify(msg: str, _name: str = name) -> None:
            if status_callback:
                status_callback(_name, msg)

        try:
            # ── Download phase ─────────────────────────────────────────
            if download_url and game.get("base_path"):
                dl_errors = download_game(download_url, game, _notify)
                if dl_errors:
                    errors.extend(f"{name}: {e}" for e in dl_errors)
                    continue

            # ── Install phase ──────────────────────────────────────────
            _notify("Installing\u2026")

            base_path = BASE_DIR / game["base_path"] if game.get("base_path") else BASE_DIR

            # Prerequisites (paths remain root-relative as they are manual)
            for prereq in game.get("prerequisites", []):
                prereq_path = BASE_DIR / prereq["path"]
                args = prereq.get("args", "")
                subprocess.run(f'"{prereq_path}" {args}'.strip(), shell=True, check=False)

            # Dispatch based on installer type
            installer_type = game.get("installer_type", "msi")
            target_dir = os.path.normpath(os.path.join(install_dir, game["name"]))

            if installer_type == "inno_setup":
                exe_rel = game.get("install_exe", "")
                if not exe_rel:
                    continue

                exe_path = base_path / exe_rel

                # Inno Setup silent install flags
                cmd = [
                    f'"{exe_path}"',
                    "/SILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                    f'/DIR="{target_dir}"',
                ]

                if player and game.get("supports_player_name", False):
                    cmd.append(f'/PLAYERNAME="{player}"')

                subprocess.run(" ".join(cmd), shell=True, check=True)

            else:
                # Build msiexec command
                msi_rel = game.get("install_msi", "")
                if not msi_rel:
                    continue

                msi_path = base_path / msi_rel

                # INSTALLDIR must use backslashes and end with a trailing backslash
                # so msiexec doesn't misinterpret the closing quote as escaped.
                install_dir_msi = target_dir.rstrip("\\") + "\\"
                cmd = ["msiexec", "/i", f'"{msi_path}"', f'INSTALLDIR="{install_dir_msi}"']

                if player and game.get("supports_player_name", False):
                    cmd.append(f'PLAYERNAME="{player}"')

                if server_ip_parts and game.get("requires_server_ip", False):
                    for i, octet in enumerate(server_ip_parts, start=1):
                        cmd.append(f'SERVERADDRESS{i}="{octet}"')

                cmd.append("/qb")
                subprocess.run(" ".join(cmd), shell=True, check=True)

            _notify("Complete")

        except subprocess.CalledProcessError as exc:
            errors.append(f'{name}: installer exited with code {exc.returncode}')
            _notify(f"Error (exit {exc.returncode})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f'{name}: {exc}')
            _notify(f"Error: {exc}")

    return errors
