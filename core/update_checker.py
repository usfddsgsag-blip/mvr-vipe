from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from core.app_paths import macos_app_bundle, resource_path
from core.version import APP_BUNDLE_ID, APP_VERSION, GITHUB_REPO

CURRENT_VERSION = APP_VERSION
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=50"
USER_AGENT = "MVR-PSP-Check-AutoUpdater"


def _version_parts(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)+)", value or "")
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def normalized_version(value: str) -> str:
    parts = _version_parts(value)
    return ".".join(str(part) for part in parts)


def is_version_newer(current: str, latest: str) -> bool:
    current_parts = list(_version_parts(current))
    latest_parts = list(_version_parts(latest))
    if not current_parts or not latest_parts:
        return latest != current

    width = max(len(current_parts), len(latest_parts))
    current_parts.extend([0] * (width - len(current_parts)))
    latest_parts.extend([0] * (width - len(latest_parts)))
    return latest_parts > current_parts


def _normalized_arch(machine: str | None = None) -> str:
    value = (machine or platform.machine()).lower()
    if value in {"arm64", "aarch64"}:
        return "arm64"
    if value in {"x86_64", "amd64", "x64"}:
        return "x86_64"
    return value


def _asset_score(name: str, system_name: str, machine: str) -> int:
    lowered = name.lower()
    if not lowered.endswith(".zip"):
        return -1

    is_macos = any(token in lowered for token in ("macos", "mac-os", "darwin", "osx"))
    is_windows = any(token in lowered for token in ("windows", "win32", "win64"))
    is_linux = "linux" in lowered
    is_universal = any(token in lowered for token in ("universal", "universal2"))
    is_arm = any(token in lowered for token in ("arm64", "aarch64", "apple-silicon", "apple_silicon"))
    is_intel = any(token in lowered for token in ("x86_64", "x64", "intel", "amd64"))

    if system_name == "darwin":
        if not is_macos or is_windows or is_linux:
            return -1
        if machine == "arm64" and is_intel and not is_universal:
            return -1
        if machine == "x86_64" and is_arm and not is_universal:
            return -1
        if (machine == "arm64" and is_arm) or (machine == "x86_64" and is_intel):
            return 30
        if is_universal:
            return 20
        return 10

    if system_name == "windows":
        if is_macos or is_linux:
            return -1
        return 20 if is_windows else 1

    return -1


def select_release_asset(
    assets: Iterable[Dict[str, Any]],
    system_name: str | None = None,
    machine: str | None = None,
) -> Optional[Dict[str, Any]]:
    system = (system_name or platform.system()).lower()
    arch = _normalized_arch(machine)
    candidates = []
    for asset in assets:
        name = str(asset.get("name", ""))
        score = _asset_score(name, system, arch)
        if score >= 0 and asset.get("browser_download_url"):
            candidates.append((score, name, asset))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def find_latest_compatible_release(
    releases: Iterable[Dict[str, Any]],
    system_name: str | None = None,
    machine: str | None = None,
) -> Optional[Dict[str, Any]]:
    candidates = []
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue

        version = normalized_version(str(release.get("tag_name", "")))
        asset = select_release_asset(release.get("assets", []), system_name, machine)
        if not version or not asset:
            continue

        asset_name = str(asset.get("name", ""))
        checksum_name = f"{asset_name}.sha256".lower()
        checksum_asset = next(
            (
                item
                for item in release.get("assets", [])
                if str(item.get("name", "")).lower() == checksum_name
            ),
            None,
        )
        info = {
            "version": version,
            "download_url": asset.get("browser_download_url"),
            "checksum_url": checksum_asset.get("browser_download_url") if checksum_asset else None,
            "asset_name": asset_name,
            "release_notes": release.get("body", ""),
        }
        candidates.append((_version_parts(version), info))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def get_latest_release_info() -> Optional[Dict[str, Any]]:
    try:
        request = urllib.request.Request(
            GITHUB_RELEASES_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            releases = json.loads(response.read().decode("utf-8"))

        info = find_latest_compatible_release(releases)
        if info:
            return info

        platform_name = "macOS" if sys.platform == "darwin" else platform.system()
        return {
            "version": CURRENT_VERSION,
            "download_url": None,
            "checksum_url": None,
            "release_notes": "",
            "message": f"No compatible {platform_name} release is published yet.",
        }
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {
                "version": CURRENT_VERSION,
                "download_url": None,
                "checksum_url": None,
                "release_notes": "",
                "message": "No GitHub releases are published yet.",
            }
        print(f"[UpdateChecker] GitHub returned HTTP {exc.code}: {exc}")
    except Exception as exc:
        print(f"[UpdateChecker] Failed to check for updates: {exc}")
    return None


def _validate_release_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    expected_prefix = f"/{GITHUB_REPO}/releases/download/"
    if parsed.scheme != "https" or parsed.hostname != "github.com" or not parsed.path.startswith(expected_prefix):
        raise ValueError("The update URL is not a trusted GitHub release asset.")


def _read_expected_checksum(url: str) -> str:
    _validate_release_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=15) as response:
        value = response.read().decode("ascii", errors="strict").strip().split()[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("The release checksum file is invalid.")
    return value


def download_update(info: Dict[str, Any]) -> str:
    url = str(info.get("download_url") or "")
    if not url:
        raise ValueError("This release has no compatible download asset.")
    _validate_release_url(url)

    version = normalized_version(str(info.get("version", ""))) or "unknown"
    destination = Path(tempfile.gettempdir()) / f"mvr_psp_update_{version}.zip"
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            digest.update(chunk)

    checksum_url = info.get("checksum_url")
    if checksum_url:
        expected = _read_expected_checksum(str(checksum_url))
        actual = digest.hexdigest()
        if actual != expected:
            destination.unlink(missing_ok=True)
            raise ValueError("The downloaded update failed SHA-256 verification.")

    return str(destination)


def _launch_windows_updater_and_exit(zip_path: str) -> None:
    app_dir = Path(sys.executable).resolve().parent
    updater_candidates = [
        app_dir / "updater.exe",
        app_dir.parent / "updater" / "updater.exe",
        app_dir / "updater" / "updater.exe",
    ]
    updater_exe = next((path for path in updater_candidates if path.is_file()), None)
    if not updater_exe:
        raise FileNotFoundError("The Windows updater component was not found.")

    temp_updater = Path(tempfile.gettempdir()) / f"mvr_psp_updater_{os.getpid()}.exe"
    shutil.copy2(updater_exe, temp_updater)
    args = [
        str(temp_updater),
        "--zip",
        zip_path,
        "--target",
        str(app_dir),
        "--launch",
        str(Path(sys.executable).resolve()),
        "--pid",
        str(os.getpid()),
    ]
    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    subprocess.Popen(args, close_fds=True, creationflags=creationflags)
    os._exit(0)


def _launch_macos_updater_and_exit(zip_path: str) -> None:
    app_bundle = macos_app_bundle()
    if not getattr(sys, "frozen", False) or app_bundle is None:
        raise RuntimeError("Automatic updates are available only in the packaged macOS app.")
    if str(app_bundle).startswith("/Volumes/"):
        raise RuntimeError(
            "Move MVR PSP Check.app to Applications before installing updates."
        )

    source_script = resource_path("updater", "macos_update.sh")
    if not source_script.is_file():
        raise FileNotFoundError("The macOS updater helper was not found in the app bundle.")

    helper_dir = Path(tempfile.mkdtemp(prefix="mvr_psp_updater_"))
    helper_script = helper_dir / "macos_update.sh"
    shutil.copy2(source_script, helper_script)
    helper_script.chmod(0o700)

    subprocess.Popen(
        [
            "/bin/zsh",
            str(helper_script),
            zip_path,
            str(app_bundle),
            str(os.getpid()),
            APP_BUNDLE_ID,
        ],
        close_fds=True,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os._exit(0)


def launch_updater_and_exit(zip_path: str) -> None:
    if sys.platform == "darwin":
        _launch_macos_updater_and_exit(zip_path)
    elif os.name == "nt":
        _launch_windows_updater_and_exit(zip_path)
    else:
        raise RuntimeError(f"Automatic updates are not supported on {platform.system()}.")
