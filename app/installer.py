"""Cobra LANs – MSI installation logic (no UI dependencies)."""

import os
import subprocess

from .config import BASE_DIR


def run_installs(
    games: list[dict],
    install_dir: str,
    player: str,
    server_ip_parts: list[str] | None,
) -> list[str]:
    """Run MSI installers for each game; returns a list of error messages (empty = all OK)."""
    errors: list[str] = []

    for game in games:
        try:
            # Resolve the game's base installer directory.
            # New format:  base_path + relative msi_rel
            # Legacy fallback: base_path absent, msi_rel is already root-relative
            base_path = BASE_DIR / game["base_path"] if game.get("base_path") else BASE_DIR

            # 1. Prerequisites (paths remain root-relative as they are manual)
            for prereq in game.get("prerequisites", []):
                prereq_path = BASE_DIR / prereq["path"]
                args = prereq.get("args", "")
                subprocess.run(f'"{prereq_path}" {args}'.strip(), shell=True, check=False)

            # 2. Choose MSI from the entry's install_msi field
            msi_rel = game.get("install_msi", "")
            if not msi_rel:
                continue

            msi_path   = base_path / msi_rel
            target_dir = os.path.normpath(os.path.join(install_dir, game["name"]))

            # 3. Build msiexec command
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

        except subprocess.CalledProcessError as exc:
            errors.append(f'{game["name"]}: installer exited with code {exc.returncode}')
        except Exception as exc:  # noqa: BLE001
            errors.append(f'{game["name"]}: {exc}')

    return errors
