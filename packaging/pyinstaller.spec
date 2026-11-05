# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT / "packaging"))
from fetch_ffmpeg import detect_target  # noqa: E402

TARGET = os.environ.get("ECOTRANSCRIBE_TARGET") or detect_target()
VERSION = "0.2.0"
APP_NAME = "EcoTranscribe Desktop"
BIN_DIR = ROOT / "vendor" / "ffmpeg" / TARGET
WIN = sys.platform == "win32"
FFMPEG = "ffmpeg.exe" if WIN else "ffmpeg"
FFPROBE = "ffprobe.exe" if WIN else "ffprobe"

for binary in (FFMPEG, FFPROBE):
    if not (BIN_DIR / binary).is_file():
        raise SystemExit(
            f"Binaire manquant : {BIN_DIR / binary}. "
            f"Lancez python packaging/fetch_ffmpeg.py --target {TARGET}."
        )

build_generated = ROOT / "build" / "generated"
build_generated.mkdir(parents=True, exist_ok=True)
commit = os.environ.get("ECOTRANSCRIBE_COMMIT", "dev")
build_date = os.environ.get(
    "ECOTRANSCRIBE_BUILD_DATE",
    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
)
(build_generated / "ecotranscribe_build_info.py").write_text(
    '"""Généré par packaging/pyinstaller.spec."""\n'
    f'COMMIT = "{commit}"\n'
    f'BUILD_DATE = "{build_date}"\n',
    encoding="utf-8",
)

icon_build = ROOT / "packaging" / "build"
if sys.platform == "darwin":
    icon = str(icon_build / "EcoTranscribe.icns")
elif WIN:
    icon = str(icon_build / "icon.ico")
else:
    icon = None

datas = [
    (str(BIN_DIR / FFMPEG), "bin"),
    (str(BIN_DIR / FFPROBE), "bin"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(ROOT / "README.md"), "."),
]
notices_dir = ROOT / "packaging" / "notices"
if notices_dir.is_dir():
    datas.append((str(notices_dir), "notices"))

hiddenimports = collect_submodules("keyring.backends", on_error="ignore")
hiddenimports.append("ecotranscribe_build_info")

a = Analysis(
    [str(ROOT / "src" / "ecotranscribe" / "gui" / "app.py")],
    pathex=[str(ROOT / "src"), str(build_generated)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "whisper",
        "torch",
        "torchaudio",
        "torchvision",
        "numba",
        "tiktoken",
        "triton",
        "tensorboard",
        "pytest",
        "tkinter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier="app.ecotranscribe.desktop",
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.productivity",
        },
    )
