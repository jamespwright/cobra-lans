# Core business logic for LAN Game Installer (no UI dependencies).
#
# Provides the base directory constant and config-file locator used by
# every other core module (data, downloader, installer, settings).

import sys
from pathlib import Path

# Base path – works for both a .py script and a PyInstaller --onefile bundle.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent


def locate_yaml(file_name: str) -> Path | None:
    """Search standard config directories for *file_name*; return the first match."""
    candidates = [
        Path.cwd() / "config" / file_name,
        Path(sys.executable).resolve().parent / "config" / file_name,
        Path(__file__).parent.parent / "config" / file_name,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None
