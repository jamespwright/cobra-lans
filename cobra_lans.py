#!/usr/bin/env python3
"""Cobra LANs – LAN Party Game Installer (entry point)."""

import ctypes
import sys


def _is_admin() -> bool:
    """Return True if the current process already has admin rights."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _elevate() -> None:
    """Re-launch this process elevated via ShellExecute 'runas', then exit."""
    if getattr(sys, "frozen", False):
        # PyInstaller one-file bundle: the exe IS the entry point.
        executable = sys.executable
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        # Running as a plain Python script – use pythonw.exe to suppress the console.
        executable = sys.executable.replace("python.exe", "pythonw.exe")
        params = " ".join(f'"{a}"' for a in sys.argv)

    ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    sys.exit(0)


from app.window import CobraLANs

if __name__ == "__main__":
    if not _is_admin():
        _elevate()

    app = CobraLANs()
    app.mainloop()
