# Cobra LANs — User Guide

A quick-start guide for installing LAN party games using Cobra LANs.

---

## What is Cobra LANs?

Cobra LANs is a one-click game installer for LAN parties. It lets you browse a list of available games, select the ones you want, and install them all at once to a directory of your choice. Each game's installer is verified for integrity before it runs, so you can be confident the files haven't been corrupted.

---

## System Requirements

- **Windows 10 or 11**
- **Administrator privileges** — the app will prompt you to allow elevated access when it starts (this is required to run the game installers)
- **Installer files** — the `Installers\` folder containing the game files must be in the same directory as `Cobra LANs.exe` (your LAN organiser will have this set up for you)

---

## Getting Started

1. **Launch** `Cobra LANs.exe`. If Windows asks for administrator permission, click **Yes**.
2. The main window shows all available games with their version, integrity status, and disk size.

---

## Installing Games

1. **Select games** — Click a row (or its checkbox) to select a game. Use the **ALL** checkbox in the header to select every game at once.
2. **Choose install mode** — At the bottom of the window, pick **GAME** (default) or **SERVER** depending on what you need. The game list updates to show only entries of the chosen type.
3. **Enter your player name** — Type your name into the **PLAYER NAME** box. This is required for all installations.
4. **Click ▶ INSTALL SELECTED**.
5. **Pick an install directory** — A folder picker will open. Choose where you want the games installed (e.g. `C:\Games`). Each game will be placed in its own subfolder.
6. **Server IP** *(if prompted)* — Some games (e.g. Battlefield Bad Company 2) may ask for a server IP address. Enter it in `192.168.x.x` format when prompted.
7. **Wait for installation** — The install button is disabled while installers are running. A message will appear when everything is finished, or if any errors occurred.

---

## Understanding the Game List

Each row in the game list shows:

| Column | Meaning |
|---|---|
| **Game Title** | The name of the game |
| **Version** | The installer version |
| **CRC Status** | Integrity check result (see below) |
| **Disk Size** | Total size of the installer files on disk |

### CRC Status Icons

| Icon | Meaning |
|---|---|
| ✓ OK | Installer file matches the expected checksum — good to go |
| ✗ mismatch | Installer file has changed or may be corrupted — notify your LAN organiser |
| ✗ missing | Installer file was not found — the game cannot be installed |
| ? no CRC | No checksum was recorded for this game — integrity could not be verified |
| — no installer | No installer path is configured for this game |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **App doesn't start** | Make sure you are running on Windows 10/11 and that you accept the administrator prompt. |
| **"games.yaml not found" error** | The `config\games.yaml` file must be in a `config\` folder next to the executable. Ask your LAN organiser for the correct files. |
| **All games show "✗ missing"** | The `Installers\` folder is not in the expected location. It should be in the same directory as the executable. |
| **A game shows "✗ mismatch"** | The installer file has been modified since the manifest was generated. Let your LAN organiser know so they can re-verify. |
| **Installer fails with an error code** | An error dialog will show which game failed. Try installing it individually, or check that you have enough disk space. |
| **No games appear in the list** | A game filter may be active. Ask your organiser to check `config\filter.yaml`. |

---

## Tips

- You can install games in batches — select only the ones you want to play, install them, then come back and install more later.
- The **GAME / SERVER** toggle at the bottom switches between game client installers and dedicated server installers. Most players should leave this set to **GAME**.
- If you need to reinstall a game, just select it again and install to the same directory — the installer will overwrite the existing files.

---

## For LAN Organisers

If you are setting up Cobra LANs for an event:

1. Place `Cobra LANs.exe` and the `config\` folder together in one directory.
2. Ensure the `Installers\` folder (containing all game subfolders) is in the same directory, or accessible via a network path configured in `games.yaml`.
3. *(Optional)* Create or copy `config\filter.yaml` to restrict which games are shown to players. Set `enabled: true` and list only the games for your event.
4. Distribute the folder to each machine, or host it on a shared network drive.

For full technical details, see the developer [README](README.md).
