# updater/updater.py
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import tempfile
import time
import zipfile
from typing import List


def wait_pid_exit(pid: int, timeout_sec: int = 60) -> None:
    """Wait until the process exits on Windows or POSIX."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not is_pid_running(pid):
            return
        time.sleep(0.3)


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}"],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        ).decode("utf-8", errors="replace")
        return str(pid) in out
    except Exception:
        return False


def safe_extract(archive: zipfile.ZipFile, destination: str) -> None:
    destination_path = os.path.realpath(destination)
    for member in archive.infolist():
        member_path = os.path.realpath(os.path.join(destination, member.filename))
        if os.path.commonpath([destination_path, member_path]) != destination_path:
            raise ValueError(f"Unsafe ZIP entry: {member.filename}")
    archive.extractall(destination)


def safe_rmtree(path: str) -> None:
    for _ in range(5):
        try:
            shutil.rmtree(path, ignore_errors=True)
            return
        except Exception:
            time.sleep(0.2)


def copy_tree_over(src_dir: str, dst_dir: str, exclude_names: List[str]) -> None:
    """
    Copy everything from src_dir into dst_dir, replacing existing files.
    exclude_names: top-level names to skip (e.g. user_config.json)
    """
    os.makedirs(dst_dir, exist_ok=True)

    for name in os.listdir(src_dir):
        if name in exclude_names:
            continue

        s = os.path.join(src_dir, name)
        d = os.path.join(dst_dir, name)

        if os.path.isdir(s):
            # replace folder
            if os.path.isdir(d):
                safe_rmtree(d)
            shutil.copytree(s, d, symlinks=True)
        else:
            os.makedirs(os.path.dirname(d), exist_ok=True)
            # if file exists and locked, retry
            for _ in range(5):
                try:
                    shutil.copy2(s, d)
                    break
                except Exception:
                    time.sleep(0.2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="Path to update zip")
    ap.add_argument("--target", required=True, help="Install dir to replace")
    ap.add_argument("--launch", required=True, help="Exe to launch after update")
    ap.add_argument("--pid", required=False, type=int, default=0, help="App PID to wait for")
    args = ap.parse_args()

    zip_path = os.path.abspath(args.zip)
    target_dir = os.path.abspath(args.target)
    launch_exe = os.path.abspath(args.launch)
    pid = int(args.pid or 0)

    # Wait app close
    if pid > 0:
        wait_pid_exit(pid, timeout_sec=120)

    if not os.path.isfile(zip_path):
        print("ZIP not found:", zip_path)
        return 2

    # Extract to temp
    tmp_root = tempfile.mkdtemp(prefix="mvr_psp_update_")
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            safe_extract(z, tmp_root)

        # Some zips might contain a single top folder; normalize:
        extracted_root = tmp_root
        entries = os.listdir(tmp_root)
        if len(entries) == 1:
            one = os.path.join(tmp_root, entries[0])
            if os.path.isdir(one):
                extracted_root = one

        # Update target
        # Exclusions: add if you later keep user config / local bundles
        exclude = ["user_config.json", "debug_bundles"]
        copy_tree_over(extracted_root, target_dir, exclude_names=exclude)

        # Launch updated app
        try:
            if platform.system() == "Darwin" and launch_exe.endswith(".app"):
                subprocess.Popen(["/usr/bin/open", launch_exe])
            else:
                subprocess.Popen([launch_exe], cwd=target_dir)
        except Exception as e:
            print("Failed to launch:", e)
            return 3

        return 0

    finally:
        safe_rmtree(tmp_root)


if __name__ == "__main__":
    raise SystemExit(main())
