from __future__ import annotations

import argparse
import asyncio
import base64
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from aiohttp import ClientSession, ClientTimeout
from tqdm import tqdm
from yarl import URL

API_ENTRYPOINT = URL("https://api.onedrive.com/v1.0/drives/")
PERSONAL_API_ENTRYPOINT = URL("https://my.microsoftpersonalcontent.com/_api/v2.0/shares/")
SHARE_LINK_HOST = "1drv.ms"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"}
TIMEOUTS = ClientTimeout(total=60, connect=30)
DOWNLOAD_FOLDER = Path("OneDrive_Downloads")
BADGER_URL = URL("https://api-badgerp.svc.ms/v1.0/token")

# Default app details used in browsers by unautenticated sessions
APP_ID = "1141147648"
APP_UUID = "5cbed6ac-a083-4e14-b191-b4ba07653de2"

# Precomputed QuickXorHash schedule tables (computed once at import time)
_QXH_CYCLE = 160
_QXH_SHIFT = 11
_qxh_bit_pos = np.arange(_QXH_CYCLE, dtype=np.int32) * _QXH_SHIFT % _QXH_CYCLE
_qxh_byte_idx = (_qxh_bit_pos // 8).astype(np.intp)
_qxh_bit_off = (_qxh_bit_pos % 8).astype(np.uint16)
_qxh_low_shift = _qxh_bit_off
_qxh_high_shift = (8 - _qxh_bit_off) % 8
_qxh_has_high = _qxh_bit_off > 0
_QXH_BLOCK_SIZE = (64 * 1024 * 1024 // _QXH_CYCLE) * _QXH_CYCLE  # 67,108,800 bytes


@dataclass(frozen=True, slots=True)
class AccessDetails:
    container_id: str
    resid: str
    auth_key: str
    redeem: str

    @classmethod
    def from_url(cls, direct_url: URL) -> AccessDetails:
        resid = direct_url.query.get("resid") or ""
        redeem = direct_url.query.get("redeem") or ""
        auth_key = direct_url.query.get("authkey") or ""
        id_ = direct_url.query.get("id") or ""
        container_id = direct_url.query.get("cid")
        if not resid and "!" in id_:
            resid = id_
        if not container_id:
            container_id = resid.split("!")[0]

        return AccessDetails(container_id, resid, auth_key, redeem)


async def process_url(url: URL) -> None:
    try:
        async with ClientSession(
            headers=DEFAULT_HEADERS,
            raise_for_status=False,
            timeout=TIMEOUTS,
        ) as client_session:
            # ex: https://1drv.ms/t/s!ABCJKL-ABCJKL?e=ABC123 or  https://1drv.ms/t/c/a12345678/aTOKEN?e=ABC123
            if is_share_link(url):
                async with client_session.get(url, allow_redirects=True) as response:
                    url = response.url

            # ex: https://onedrive.live.com/?id=ABCXYZ!12345&cid=ABC0123BVC
            await download(client_session, url)

    except Exception as e:
        msg = f"Download Failed: {e}"
        print(msg)


async def download(client_session: ClientSession, url: URL) -> None:
    access_details = AccessDetails.from_url(url)
    if access_details.redeem:
        await get_badger_token(client_session)

    api_url = create_api_url(access_details)
    async with client_session.get(api_url, raise_for_status=True) as response:
        json_resp: dict = await response.json()

    # print(json_resp)

    name: str = json_resp["name"]
    if "folder" in json_resp:
        await download_folder(client_session, api_url, DOWNLOAD_FOLDER / name)
    else:
        download_url = URL(json_resp["@content.downloadUrl"])
        expected_size: int | None = json_resp.get("size")
        expected_hash: str | None = json_resp.get("file", {}).get("hashes", {}).get("quickXorHash")
        await download_file(client_session, download_url, DOWNLOAD_FOLDER / name, expected_size, expected_hash)


async def download_folder(client_session: ClientSession, api_url: URL, folder_path: Path) -> None:
    #print(f"Downloading folder to: {folder_path}")
    if "microsoftpersonalcontent" in (api_url.host or ""):
        drive_base = URL(f"{api_url.scheme}://{api_url.host}/_api/v2.0/drives/")
    else:
        drive_base = URL(f"{api_url.scheme}://{api_url.host}/v1.0/drives/")

    next_url: URL | None = api_url / "children"
    while next_url:
        async with client_session.get(next_url, raise_for_status=True) as response:
            json_resp: dict = await response.json()
        for item in json_resp.get("value", []):
            item_path = folder_path / item["name"]
            if "folder" in item:
                drive_id = item["parentReference"]["driveId"]
                child_api_url = drive_base / drive_id / "items" / item["id"]
                await download_folder(client_session, child_api_url, item_path)
            else:
                download_url = URL(item["@content.downloadUrl"])
                expected_size: int | None = item.get("size")
                expected_hash: str | None = item.get("file", {}).get("hashes", {}).get("quickXorHash")
                await download_file(client_session, download_url, item_path, expected_size, expected_hash)
        next_link = json_resp.get("@odata.nextLink")
        next_url = URL(next_link) if next_link else None


async def get_badger_token(client_session: ClientSession) -> None:
    new_headers = dict(client_session.headers) | {"AppId": APP_ID}
    data = {"appId": APP_UUID}

    async with client_session.post(BADGER_URL, headers=new_headers, raise_for_status=True, json=data) as response:
        json_resp: dict = await response.json()

    #print(f"\n Badger token response: \n{json.dumps(json_resp, indent=4)}")
    token: str = json_resp["token"]
    auth_headers = {"Prefer": "autoredeem", "Authorization": f"Badger {token}"}
    client_session.headers.update(auth_headers)


async def download_file(
    client_session: ClientSession,
    url: URL,
    output: Path,
    expected_size: int | None = None,
    expected_hash: str | None = None,
) -> None:
    if output.exists() and expected_size is not None and expected_hash is not None:
        if output.stat().st_size != expected_size:
            print(f"  Size mismatch ({output.stat().st_size} != {expected_size}), re-downloading: {output.name}")
        else:
            loop = asyncio.get_running_loop()
            local_hash = await loop.run_in_executor(None, quickxorhash_file, output)
            print(f"  Local hash: {local_hash}")
            print(f"  Expected hash: {expected_hash}")
            if local_hash == expected_hash:
                print(f"  Skipping (up to date): {output}")
                return
            print(f"  Hash mismatch, re-downloading: {output.name}")

    print(f"Downloading: {output}")
    async with client_session.get(url, raise_for_status=True) as response:
        total_size = int(response.headers.get("Content-Length", 0))
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as f, tqdm(
            total=total_size or None,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            dynamic_ncols=True,
            bar_format="{n_fmt}/{total_fmt} [{elapsed}{remaining}, {rate_fmt}]",
        ) as progress:
            async for chunk in response.content.iter_chunked(65536):
                f.write(chunk)
                progress.update(len(chunk))
    #print(f"Downloaded: {output.resolve()}")


def create_api_url(access_details: AccessDetails) -> URL:
    if access_details.redeem:
        return PERSONAL_API_ENTRYPOINT / f"u!{access_details.redeem}" / "driveitem"
    api_url = API_ENTRYPOINT / access_details.container_id / "items" / access_details.resid
    if access_details.auth_key:
        return api_url.with_query(authkey=access_details.auth_key)
    return api_url

def is_share_link(url: URL) -> bool:
    return url.host == SHARE_LINK_HOST and any(p in url.parts for p in ("f", "t", "u"))

def quickxorhash_file(path: Path) -> str:
    xor_accum = np.zeros(_QXH_CYCLE, dtype=np.uint8)
    total_length = 0

    with open(path, "rb") as fh:
        while chunk := fh.read(_QXH_BLOCK_SIZE):
            data = np.frombuffer(chunk, dtype=np.uint8)
            total_length += len(data)
            remainder = len(data) % _QXH_CYCLE
            if remainder:
                padded = np.zeros(len(data) + (_QXH_CYCLE - remainder), dtype=np.uint8)
                padded[: len(data)] = data
                data = padded
            xor_accum ^= np.bitwise_xor.reduce(data.reshape(-1, _QXH_CYCLE), axis=0)

    # Apply the rotation schedule to produce the 20-byte state
    state = np.zeros(20, dtype=np.uint8)
    low_vals = ((xor_accum.astype(np.uint16) << _qxh_low_shift) & 0xFF).astype(np.uint8)
    np.bitwise_xor.at(state, _qxh_byte_idx, low_vals)

    mask = _qxh_has_high
    high_vals = ((xor_accum[mask].astype(np.uint16) >> _qxh_high_shift[mask]) & 0xFF).astype(np.uint8)
    np.bitwise_xor.at(state, (_qxh_byte_idx[mask] + 1) % 20, high_vals)

    # XOR in the file length into the last 8 bytes of the state
    state[12:] ^= np.frombuffer(total_length.to_bytes(8, "little"), dtype=np.uint8)

    return base64.b64encode(bytes(state)).decode()


def main() -> None:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("url", type=str, help="URL to download")
        args = parser.parse_args()
        url = URL(args.url)
        asyncio.run(process_url(url))
    except KeyboardInterrupt:
        pass
    except Exception:
        print("Download Failed")


if __name__ == "__main__":
    main()