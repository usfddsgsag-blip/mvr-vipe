from __future__ import annotations

import webview

from core.app_paths import resource_path, user_data_dir
from core.pipeline import Engine
from core.version import APP_NAME, APP_VERSION
from ui.webview_api import Api


def run_ui(engine: Engine, startup_pdf_path: str | None = None) -> None:
    api = Api(engine, startup_pdf_path=startup_pdf_path)
    html_path = resource_path("ui", "web", "index.html")

    window = webview.create_window(
        f"{APP_NAME} - v{APP_VERSION}",
        url=str(html_path),
        js_api=api,
        width=1420,
        height=840,
        min_size=(1100, 650),
        background_color='#0D0D14'
    )

    api.set_window(window)
    window.events.closed += api.cleanup
    webview.start(
        private_mode=False,
        storage_path=str(user_data_dir()),
    )
