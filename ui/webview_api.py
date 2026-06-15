from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional

from core.bundle import save_debug_bundle
from core.pipeline import Engine
from core.types import ParseResult, PdfText
from core.version import APP_NAME, APP_VERSION


class Api:
    """Methods exposed to JavaScript through window.pywebview.api."""

    def __init__(self, engine: Engine, startup_pdf_path: str | None = None):
        self.engine = engine
        self.pdf_path = ""
        self.original_filename = ""
        self.pdf_text: Optional[PdfText] = None
        self.result: Optional[ParseResult] = None
        self.page_count = 0
        self._window = None
        self._startup_pdf_path = startup_pdf_path
        self._temporary_pdf_paths: set[str] = set()
        self._pending_update: Optional[Dict[str, Any]] = None

    def set_window(self, window) -> None:
        self._window = window

    def get_app_info(self) -> dict:
        return {
            "name": APP_NAME,
            "version": APP_VERSION,
            "platform": "macos" if sys.platform == "darwin" else sys.platform,
        }

    def consume_startup_pdf(self) -> dict:
        path = self._startup_pdf_path
        self._startup_pdf_path = None
        if not path:
            return {"ok": False, "skipped": True}
        return self._process_pdf(path)

    def cleanup(self, *_args) -> None:
        for path in self._temporary_pdf_paths:
            try:
                os.unlink(path)
            except OSError:
                pass
        self._temporary_pdf_paths.clear()

    def choose_pdf(self) -> dict:
        import webview

        paths = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("PDF Files (*.pdf)",),
        )
        if not paths:
            return {"ok": False}
        return self._process_pdf(paths[0])

    def process_dropped_pdf_bytes(self, base64_data: str, filename: str) -> dict:
        try:
            pdf_bytes = base64.b64decode(base64_data)
            fd, temp_path = tempfile.mkstemp(suffix=".pdf", prefix="dropped_")
            with os.fdopen(fd, "wb") as temp_file:
                temp_file.write(pdf_bytes)

            self._temporary_pdf_paths.add(temp_path)
            return self._process_pdf(temp_path, display_filename=filename)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _process_pdf(self, path: str, display_filename: str | None = None) -> dict:
        try:
            pdf_text, result = self.engine.run(path)
            self.pdf_path = path
            self.original_filename = display_filename or os.path.basename(path)
            self.pdf_text = pdf_text
            self.result = result

            from ui.pdf_viewer import get_page_count

            self.page_count = get_page_count(path)
            if self.page_count <= 0:
                self.page_count = len(pdf_text.page_texts)

            return {
                "ok": True,
                "actual_text": result.actual_text or "",
                "doc_type": result.doc_type,
                "page_count": self.page_count,
                "debug_log": json.dumps(
                    result.debug_log or {},
                    ensure_ascii=False,
                    indent=2,
                ),
                "issues": [
                    {"level": issue.level, "message": issue.message}
                    for issue in (result.issues or [])
                ],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def render_page(self, page_index: int, zoom: float) -> dict:
        if not self.pdf_path:
            return {"ok": False}

        from ui.pdf_viewer import render_pdf_page_to_base64

        image, width, height = render_pdf_page_to_base64(
            self.pdf_path,
            page_index,
            zoom,
        )
        if not image:
            return {"ok": False}
        return {
            "ok": True,
            "base64_png": image,
            "width": width,
            "height": height,
        }

    def get_highlights(self, page_index: int, zoom: float) -> dict:
        if not self.result:
            return {"rects": []}

        rects = self.result.highlights.get(page_index, [])
        return {
            "rects": [
                {
                    "x0": rect.x0 * zoom,
                    "top": rect.top * zoom,
                    "x1": rect.x1 * zoom,
                    "bottom": rect.bottom * zoom,
                }
                for rect in rects
            ]
        }

    def save_txt(self, content: str) -> dict:
        import webview

        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=("Text Files (*.txt)",),
        )
        if not path:
            return {"ok": False}

        save_path = path if isinstance(path, str) else path[0]
        with open(save_path, "w", encoding="utf-8") as output:
            output.write(content + "\n")
        return {"ok": True, "path": save_path}

    def copy_clipboard(self, text: str) -> dict:
        try:
            if sys.platform == "darwin":
                subprocess.run(
                    ["/usr/bin/pbcopy"],
                    input=text.encode("utf-8"),
                    check=True,
                )
            elif os.name == "nt":
                subprocess.run(
                    ["clip"],
                    input=text.encode("utf-16-le"),
                    check=True,
                )
            else:
                raise RuntimeError("Clipboard integration is not supported on this platform.")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def save_bundle(self, expected_text: str) -> dict:
        if not self.pdf_path or not self.pdf_text or not self.result:
            return {"ok": False, "error": "Load a PDF first"}

        import webview

        pdf_base = (
            os.path.splitext(self.original_filename)[0]
            if self.original_filename
            else "dropped_file"
        )
        stamp = datetime.now().strftime("%Y-%m-%d__%H%M")
        default_name = f"{self.result.doc_type}__{pdf_base}__{stamp}.zip"
        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=("ZIP Files (*.zip)",),
            save_filename=default_name,
        )
        if not path:
            return {"ok": False}

        save_path = path if isinstance(path, str) else path[0]
        save_debug_bundle(save_path, self.pdf_text, self.result, expected_text)
        return {"ok": True, "path": save_path}

    def check_updates(self) -> dict:
        from core.update_checker import (
            CURRENT_VERSION,
            get_latest_release_info,
            is_version_newer,
        )

        info = get_latest_release_info()
        if not info:
            return {"ok": False, "message": "Failed to check for updates."}

        if info.get("download_url") and is_version_newer(
            CURRENT_VERSION,
            str(info["version"]),
        ):
            self._pending_update = info
            return {
                "ok": True,
                "has_update": True,
                "version": info["version"],
                "notes": info.get("release_notes", ""),
            }

        self._pending_update = None
        return {
            "ok": True,
            "has_update": False,
            "message": info.get("message", "You have the latest version."),
        }

    def download_and_install_update(self, version: str) -> dict:
        try:
            from core.update_checker import download_update, launch_updater_and_exit

            info = self._pending_update
            if not info or info.get("version") != version:
                return {
                    "ok": False,
                    "error": "The selected update is no longer available.",
                }

            archive_path = download_update(info)
            launch_updater_and_exit(archive_path)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
