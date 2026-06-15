from __future__ import annotations

import os
import unittest
from pathlib import Path

from core.app_paths import macos_app_bundle


class MacosAppBundleTests(unittest.TestCase):
    def test_finds_bundle_from_frozen_executable(self) -> None:
        if os.name == "nt":
            bundle = Path("C:/Applications/MVR PSP Check.app")
        else:
            bundle = Path("/Applications/MVR PSP Check.app")

        executable = bundle / "Contents" / "MacOS" / "MVR_PSP_Check"

        self.assertEqual(macos_app_bundle(executable), bundle)

    def test_returns_none_outside_bundle(self) -> None:
        self.assertIsNone(macos_app_bundle("/usr/local/bin/python3"))


if __name__ == "__main__":
    unittest.main()
