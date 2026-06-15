from __future__ import annotations

import sys
from pathlib import Path

from core.pipeline import Engine

from parsers.mvr import MvrParser
from parsers.psp import PspParser

from highlights.mvr import MvrHighlighter
from highlights.psp import PspHighlighter

from ui.main_window import run_ui


def _startup_pdf_path() -> str | None:
    for value in sys.argv[1:]:
        path = Path(value).expanduser()
        if path.suffix.lower() == ".pdf" and path.is_file():
            return str(path.resolve())
    return None


def main() -> None:
    engine = Engine(
        parsers={
            "MVR": MvrParser(),
            "PSP": PspParser(),
        },
        highlighters={
            "MVR": MvrHighlighter(),
            "PSP": PspHighlighter(),
        },
    )
    run_ui(engine, startup_pdf_path=_startup_pdf_path())


if __name__ == "__main__":
    main()
