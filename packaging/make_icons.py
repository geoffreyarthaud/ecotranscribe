#!/usr/bin/env python3
"""Génère les tailles d'icône depuis assets/ecotranscribe-650.png.

Produit les PNG multi-tailles embarqués par l'application
(`src/ecotranscribe/gui/assets/`) ainsi que `icon.png`, `EcoTranscribe.icns`
et `icon.ico` dans `packaging/build/` pour la distribution.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "assets" / "ecotranscribe-650.png"
DEFAULT_OUTPUT = ROOT / "packaging" / "build"
DEFAULT_ASSETS = ROOT / "src" / "ecotranscribe" / "gui" / "assets"

RUNTIME_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICONSET = (
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


def _scaled(image: Image.Image, size: int) -> Image.Image:
    return image.resize((size, size), Image.Resampling.LANCZOS)


def generate(source: Path, output: Path, assets: Path) -> list[Path]:
    """Écrit les icônes dérivées et retourne les chemins produits."""
    with Image.open(source) as raw:
        image = raw.convert("RGBA")
    if image.width != image.height:
        raise SystemExit(f"Logo non carré : {source} ({image.width}×{image.height})")

    produced: list[Path] = []

    assets.mkdir(parents=True, exist_ok=True)
    for size in RUNTIME_SIZES:
        path = assets / f"icon-{size}.png"
        _scaled(image, size).save(path, format="PNG", optimize=True)
        produced.append(path)

    output.mkdir(parents=True, exist_ok=True)
    png = output / "icon.png"
    _scaled(image, 1024).save(png, format="PNG", optimize=True)
    produced.append(png)

    if sys.platform == "darwin" and shutil.which("iconutil"):
        iconset = output / "EcoTranscribe.iconset"
        if iconset.exists():
            shutil.rmtree(iconset)
        iconset.mkdir(parents=True)
        for name, size in ICONSET:
            _scaled(image, size).save(
                iconset / name, format="PNG", optimize=True
            )
        icns = output / "EcoTranscribe.icns"
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
            check=True,
        )
        produced.append(icns)

    ico = output / "icon.ico"
    _scaled(image, 256).save(
        ico,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    produced.append(ico)
    return produced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    args = parser.parse_args(argv)
    if not args.source.is_file():
        raise SystemExit(f"Logo introuvable : {args.source}")
    for path in generate(args.source, args.output_dir, args.assets_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
