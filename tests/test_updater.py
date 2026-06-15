from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from updater.updater import safe_extract


class SafeExtractTests(unittest.TestCase):
    def test_extracts_regular_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "update.zip"
            destination = Path(temp_dir) / "output"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("MVR PSP Check.app/Contents/test.txt", "ok")

            with zipfile.ZipFile(archive_path, "r") as archive:
                safe_extract(archive, str(destination))

            self.assertEqual(
                (destination / "MVR PSP Check.app/Contents/test.txt").read_text(),
                "ok",
            )

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "update.zip"
            destination = Path(temp_dir) / "output"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "bad")

            with zipfile.ZipFile(archive_path, "r") as archive:
                with self.assertRaises(ValueError):
                    safe_extract(archive, str(destination))


if __name__ == "__main__":
    unittest.main()
