# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

project_root = Path.cwd()
sys.path.insert(0, str(project_root))

from core.version import APP_BUNDLE_ID, APP_BUNDLE_NAME, APP_VERSION

target_arch = os.environ.get("PYINSTALLER_TARGET_ARCH") or None
codesign_identity = os.environ.get("MACOS_CODESIGN_IDENTITY") or None

a = Analysis(
    ["app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ("ui/web", "ui/web"),
        ("updater/macos_update.sh", "updater"),
    ],
    hiddenimports=[
        "webview",
        "webview.platforms.cocoa",
        "bottle",
        "AppKit",
        "Foundation",
        "Quartz",
        "Security",
        "WebKit",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "clr_loader",
        "pythonnet",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "matplotlib",
        "scipy",
        "numpy",
        "IPython",
        "pygame",
        "pkg_resources",
        "setuptools",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MVR_PSP_Check",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=target_arch,
    codesign_identity=codesign_identity,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MVR_PSP_Check",
)

app = BUNDLE(
    coll,
    name=APP_BUNDLE_NAME,
    icon=None,
    bundle_identifier=APP_BUNDLE_ID,
    info_plist={
        "CFBundleDisplayName": "MVR / PSP Check",
        "CFBundleName": "MVR PSP Check",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "LSApplicationCategoryType": "public.app-category.business",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "PDF document",
                "CFBundleTypeExtensions": ["pdf"],
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
            }
        ],
    },
)
