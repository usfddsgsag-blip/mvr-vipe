from __future__ import annotations

import unittest

from core.update_checker import (
    find_latest_compatible_release,
    is_version_newer,
    normalized_version,
    select_release_asset,
)


def asset(name: str) -> dict:
    return {
        "name": name,
        "browser_download_url": (
            f"https://github.com/xuiila337/mvr-vipe/releases/download/test/{name}"
        ),
    }


class UpdateSelectionTests(unittest.TestCase):
    def test_selects_native_apple_silicon_asset(self) -> None:
        selected = select_release_asset(
            [
                asset("update_v2.0.0.zip"),
                asset("MVR_PSP_Check-macOS-x86_64.zip"),
                asset("MVR_PSP_Check-macOS-arm64.zip"),
                asset("MVR_PSP_Check-Windows-x64.zip"),
            ],
            system_name="darwin",
            machine="arm64",
        )
        self.assertEqual(selected["name"], "MVR_PSP_Check-macOS-arm64.zip")

    def test_selects_intel_asset(self) -> None:
        selected = select_release_asset(
            [
                asset("MVR_PSP_Check-macOS-arm64.zip"),
                asset("MVR_PSP_Check-macOS-x86_64.zip"),
            ],
            system_name="darwin",
            machine="x86_64",
        )
        self.assertEqual(selected["name"], "MVR_PSP_Check-macOS-x86_64.zip")

    def test_rejects_generic_windows_archive_on_macos(self) -> None:
        selected = select_release_asset(
            [asset("update_v1.2.2.zip")],
            system_name="darwin",
            machine="arm64",
        )
        self.assertIsNone(selected)

    def test_uses_universal_asset_as_fallback(self) -> None:
        selected = select_release_asset(
            [asset("MVR_PSP_Check-macOS-universal2.zip")],
            system_name="darwin",
            machine="arm64",
        )
        self.assertEqual(selected["name"], "MVR_PSP_Check-macOS-universal2.zip")

    def test_picks_highest_compatible_release_and_checksum(self) -> None:
        releases = [
            {
                "tag_name": "macos-v1.4.0",
                "assets": [asset("MVR_PSP_Check-macOS-arm64.zip")],
                "body": "older",
            },
            {
                "tag_name": "macos-v1.5.0",
                "assets": [
                    asset("MVR_PSP_Check-macOS-arm64.zip"),
                    asset("MVR_PSP_Check-macOS-arm64.zip.sha256"),
                ],
                "body": "newer",
            },
        ]
        selected = find_latest_compatible_release(
            releases,
            system_name="darwin",
            machine="arm64",
        )
        self.assertEqual(selected["version"], "1.5.0")
        self.assertTrue(selected["checksum_url"].endswith(".sha256"))
        self.assertEqual(selected["release_notes"], "newer")


class VersionTests(unittest.TestCase):
    def test_normalizes_macos_tag(self) -> None:
        self.assertEqual(normalized_version("macos-v2.3.4"), "2.3.4")

    def test_compares_padded_versions(self) -> None:
        self.assertTrue(is_version_newer("1.2", "1.2.1"))
        self.assertFalse(is_version_newer("1.2.0", "1.2"))


if __name__ == "__main__":
    unittest.main()
