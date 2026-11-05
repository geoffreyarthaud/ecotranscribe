#!/usr/bin/env python3
"""Génère PNG, .icns et .ico depuis packaging/icon.svg."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SVG = ROOT / "packaging" / "icon.svg"
DEFAULT_OUTPUT = ROOT / "packaging" / "build"

_ICONSET = (
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
)


def _render(renderer: QSvgRenderer, size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


def generate(svg: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        raise SystemExit(f"SVG invalide : {svg}")

    produced: list[Path] = []
    png = output / "icon.png"
    _render(renderer, 1024).save(str(png), "PNG")
    produced.append(png)

    if sys.platform == "darwin" and shutil.which("iconutil"):
        iconset = output / "EcoTranscribe.iconset"
        if iconset.exists():
            shutil.rmtree(iconset)
        iconset.mkdir(parents=True)
        for name, size in _ICONSET:
            _render(renderer, size).save(str(iconset / name), "PNG")
        icns = output / "EcoTranscribe.icns"
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
            check=True,
        )
        produced.append(icns)

    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            "Pillow est requis : uv sync --extra dev"
        ) from exc
    ico = output / "icon.ico"
    with Image.open(png) as image:
        image.save(
            ico,
            format="ICO",
            sizes=[
                (16, 16),
                (24, 24),
                (32, 32),
                (48, 48),
                (64, 64),
                (128, 128),
                (256, 256),
            ],
        )
    produced.append(ico)
    app.processEvents()
    return produced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--svg", type=Path, default=DEFAULT_SVG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    for path in generate(args.svg, args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
