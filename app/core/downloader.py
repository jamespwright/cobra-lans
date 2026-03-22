# OneDrive download logic.
#
# Downloads game files from a OneDrive share link, with integrity checking
# via QuickXorHash and progress reporting through a status callback.
# This module has no UI dependencies.

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from aiohttp import ClientSession, ClientTimeout
from yarl import URL

from . import BASE_DIR

# ── OneDrive API constants ─────────────────────────────────────────────────────
API_ENTRYPOINT = URL("https://api.onedrive.com/v1.0/drives/")
PERSONAL_API_ENTRYPOINT = URL(
    "https://my.microsoftpersonalcontent.com/_api/v2.0/shares/"
)
SHARE_LINK_HOST = "1drv.ms"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) "
        "Gecko/20100101 Firefox/135.0"
    ),
}
TIMEOUTS = ClientTimeout(total=60, connect=30)
BADGER_URL = URL("https://api-badgerp.svc.ms/v1.0/token")
APP_ID = "1141147648"
APP_UUID = "5cbed6ac-a083-4e14-b191-b4ba07653de2"

# ── QuickXorHash precomputed schedule tables ───────────────────────────────────
_QXH_CYCLE = 160
_QXH_SHIFT = 11
_qxh_bit_pos = np.arange(_QXH_CYCLE, dtype=np.int32) * _QXH_SHIFT % _QXH_CYCLE
_qxh_byte_idx = (_qxh_bit_pos // 8).astype(np.intp)
_qxh_bit_off = (_qxh_bit_pos % 8).astype(np.uint16)
_qxh_low_shift = _qxh_bit_off
_qxh_high_shift = (8 - _qxh_bit_off) % 8
_qxh_has_high = _qxh_bit_off > 0
_QXH_BLOCK_SIZE = (64 * 1024 * 1024 // _QXH_CYCLE) * _QXH_CYCLE

StatusCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class _AccessDetails:
    container_id: str
    resid: str
    auth_key: str
    redeem: str

    @classmethod
    def from_url(cls, direct_url: URL) -> _AccessDetails:
        resid = direct_url.query.get("resid") or ""
        redeem = direct_url.query.get("redeem") or ""
        auth_key = direct_url.query.get("authkey") or ""
        id_ = direct_url.query.get("id") or ""
        container_id = direct_url.query.get("cid")
        if not resid and "!" in id_:
            resid = id_
        if not container_id:
            container_id = resid.split("!")[0]
        return cls(container_id, resid, auth_key, redeem)


@dataclass
class _FileEntry:
    """A remote file to download."""
    download_url: URL
    local_path: Path
    size: int
    expected_hash: str | None


# ── OneDrive helpers ───────────────────────────────────────────────────────────


def _is_share_link(url: URL) -> bool:
    return url.host == SHARE_LINK_HOST and any(
        p in url.parts for p in ("f", "t", "u")
    )


def _create_api_url(access: _AccessDetails) -> URL:
    if access.redeem:
        return PERSONAL_API_ENTRYPOINT / f"u!{access.redeem}" / "driveitem"
    api_url = API_ENTRYPOINT / access.container_id / "items" / access.resid
    if access.auth_key:
        return api_url.with_query(authkey=access.auth_key)
    return api_url


def _drive_base(api_url: URL) -> URL:
    host = api_url.host or ""
    if "microsoftpersonalcontent" in host:
        return URL(f"{api_url.scheme}://{host}/_api/v2.0/drives/")
    return URL(f"{api_url.scheme}://{host}/v1.0/drives/")


async def _get_badger_token(session: ClientSession) -> None:
    headers = dict(session.headers) | {"AppId": APP_ID}
    data = {"appId": APP_UUID}
    async with session.post(
        BADGER_URL, headers=headers, raise_for_status=True, json=data,
    ) as resp:
        token: str = (await resp.json())["token"]
    session.headers.update({
        "Prefer": "autoredeem",
        "Authorization": f"Badger {token}",
    })


async def _navigate_to_subfolder(
    session: ClientSession, api_url: URL, parts: list[str],
) -> URL:
    """Walk the OneDrive folder tree to reach the target subfolder."""
    current = api_url
    base = _drive_base(api_url)
    for part in parts:
        found = False
        page: URL | None = current / "children"
        while page:
            async with session.get(page, raise_for_status=True) as resp:
                data = await resp.json()
            for item in data.get("value", []):
                if "folder" in item and item["name"] == part:
                    drive_id = item["parentReference"]["driveId"]
                    current = base / drive_id / "items" / item["id"]
                    found = True
                    break
            if found:
                break
            nxt = data.get("@odata.nextLink")
            page = URL(nxt) if nxt else None
        if not found:
            raise FileNotFoundError(f"Subfolder not found in OneDrive: {part}")
    return current


async def _collect_files(
    session: ClientSession, api_url: URL, local_dir: Path,
) -> list[_FileEntry]:
    """Recursively enumerate every file under *api_url*."""
    files: list[_FileEntry] = []
    base = _drive_base(api_url)
    page: URL | None = api_url / "children"
    while page:
        async with session.get(page, raise_for_status=True) as resp:
            data = await resp.json()
        for item in data.get("value", []):
            path = local_dir / item["name"]
            if "folder" in item:
                drive_id = item["parentReference"]["driveId"]
                child = base / drive_id / "items" / item["id"]
                files.extend(await _collect_files(session, child, path))
            else:
                files.append(_FileEntry(
                    download_url=URL(item["@content.downloadUrl"]),
                    local_path=path,
                    size=item.get("size", 0),
                    expected_hash=(
                        item.get("file", {}).get("hashes", {}).get("quickXorHash")
                    ),
                ))
        nxt = data.get("@odata.nextLink")
        page = URL(nxt) if nxt else None
    return files


async def _download_single(
    session: ClientSession,
    entry: _FileEntry,
    on_chunk: Callable[[int], None] | None = None,
) -> bool:
    """Download one file.  Returns *False* when the local copy is already current."""
    if entry.local_path.exists() and entry.expected_hash is not None:
        if entry.local_path.stat().st_size == entry.size:
            loop = asyncio.get_running_loop()
            local_hash = await loop.run_in_executor(
                None, quickxorhash_file, entry.local_path,
            )
            if local_hash == entry.expected_hash:
                return False
    entry.local_path.parent.mkdir(parents=True, exist_ok=True)
    async with session.get(entry.download_url, raise_for_status=True) as resp:
        with entry.local_path.open("wb") as fh:
            async for chunk in resp.content.iter_chunked(65536):
                fh.write(chunk)
                if on_chunk:
                    on_chunk(len(chunk))
    return True


# ── QuickXorHash ───────────────────────────────────────────────────────────────


def quickxorhash_file(path: Path) -> str:
    xor_accum = np.zeros(_QXH_CYCLE, dtype=np.uint8)
    total_length = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(_QXH_BLOCK_SIZE):
            data = np.frombuffer(chunk, dtype=np.uint8)
            total_length += len(data)
            remainder = len(data) % _QXH_CYCLE
            if remainder:
                padded = np.zeros(
                    len(data) + (_QXH_CYCLE - remainder), dtype=np.uint8,
                )
                padded[: len(data)] = data
                data = padded
            xor_accum ^= np.bitwise_xor.reduce(
                data.reshape(-1, _QXH_CYCLE), axis=0,
            )
    state = np.zeros(20, dtype=np.uint8)
    low_vals = (
        (xor_accum.astype(np.uint16) << _qxh_low_shift) & 0xFF
    ).astype(np.uint8)
    np.bitwise_xor.at(state, _qxh_byte_idx, low_vals)
    mask = _qxh_has_high
    high_vals = (
        (xor_accum[mask].astype(np.uint16) >> _qxh_high_shift[mask]) & 0xFF
    ).astype(np.uint8)
    np.bitwise_xor.at(state, (_qxh_byte_idx[mask] + 1) % 20, high_vals)
    state[12:] ^= np.frombuffer(
        total_length.to_bytes(8, "little"), dtype=np.uint8,
    )
    return base64.b64encode(bytes(state)).decode()


# ── Formatting helpers ─────────────────────────────────────────────────────────


def _fmt_speed(bps: float) -> str:
    if bps < 1024:
        return f"{bps:.0f}B/s"
    if bps < 1024**2:
        return f"{bps / 1024:.1f}KB/s"
    if bps < 1024**3:
        return f"{bps / 1024 ** 2:.1f}MB/s"
    return f"{bps / 1024 ** 3:.1f}GB/s"


def _fmt_eta(seconds: float) -> str:
    if seconds <= 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── Public API ─────────────────────────────────────────────────────────────────


def download_game(
    download_url: str,
    game: dict,
    status_callback: StatusCallback | None = None,
) -> list[str]:
    """Download files for *game* from the OneDrive *download_url*.

    Only the subfolder matching ``game["base_path"]`` is downloaded.
    Returns a list of error messages (empty on success).
    """
    return asyncio.run(_download_game(download_url, game, status_callback))


async def _download_game(
    download_url: str,
    game: dict,
    status_cb: StatusCallback | None,
) -> list[str]:
    errors: list[str] = []
    base_path = game.get("base_path", "")
    target_dir = BASE_DIR / base_path if base_path else BASE_DIR

    def notify(msg: str) -> None:
        if status_cb:
            status_cb(msg)

    try:
        async with ClientSession(
            headers=DEFAULT_HEADERS, raise_for_status=False, timeout=TIMEOUTS,
        ) as session:
            url = URL(download_url)
            if _is_share_link(url):
                notify("Resolving link\u2026")
                async with session.get(url, allow_redirects=True) as resp:
                    url = resp.url

            access = _AccessDetails.from_url(url)
            if access.redeem:
                await _get_badger_token(session)

            api_url = _create_api_url(access)

            # Confirm root is a folder
            async with session.get(api_url, raise_for_status=True) as resp:
                root = await resp.json()
            if "folder" not in root:
                errors.append("Download URL does not point to a folder")
                return errors

            # Navigate to the subfolder matching base_path.
            if base_path:
                parts = [p for p in base_path.replace("\\", "/").split("/") if p]
                root_name = root.get("name", "")
                if parts and parts[0] == root_name:
                    parts = parts[1:]
                if parts:
                    api_url = await _navigate_to_subfolder(session, api_url, parts)

            # Enumerate files
            files = await _collect_files(session, api_url, target_dir)
            if not files:
                notify("Up to date")
                return errors

            total_files = len(files)
            total_bytes = sum(f.size for f in files)
            bytes_done = 0
            bytes_xferred = 0
            files_done = 0
            t0 = time.monotonic()
            last_notify: list[float] = [0.0]

            def _notify_progress(force: bool = False) -> None:
                now = time.monotonic()
                if not force and now - last_notify[0] < 0.1:
                    return
                last_notify[0] = now
                elapsed = now - t0
                speed = bytes_xferred / elapsed if elapsed > 0 else 0
                eta = (total_bytes - bytes_done) / speed if speed > 0 else 0
                pct = int(bytes_done / total_bytes * 100) if total_bytes else 0
                notify(
                    f"{pct}% ({files_done}/{total_files}) "
                    f"{_fmt_speed(speed)} ~{_fmt_eta(eta)}"
                )

            def on_chunk(n: int) -> None:
                nonlocal bytes_done, bytes_xferred
                bytes_done += n
                bytes_xferred += n
                _notify_progress()

            for entry in files:
                downloaded = await _download_single(session, entry, on_chunk=on_chunk)
                files_done += 1
                if not downloaded:
                    bytes_done += entry.size
                _notify_progress(force=True)

            notify("Download complete")

    except Exception as exc:
        errors.append(f"Download failed: {exc}")
        notify(f"Error: {exc}")

    return errors
