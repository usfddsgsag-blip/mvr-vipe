from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base_dir = Path(__file__).resolve().parent.parent
    return base_dir.joinpath(*parts)


def user_data_dir() -> Path:
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base_dir = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    path = base_dir / "MVR PSP Check"
    path.mkdir(parents=True, exist_ok=True)
    return path


def macos_app_bundle(executable: str | Path | None = None) -> Path | None:
    executable_path = Path(executable or sys.executable).resolve()
    for parent in (executable_path, *executable_path.parents):
        if parent.suffix.lower() == ".app":
            return parent
    return None
