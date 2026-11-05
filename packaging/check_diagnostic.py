#!/usr/bin/env python3
"""Vérifie le JSON --diagnose d'un artefact lite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {
    "app_version",
    "flavor",
    "commit",
    "build_date",
    "python",
    "qt",
    "platform",
    "arch",
    "frozen",
    "ffmpeg_path",
    "ffprobe_path",
    "ffmpeg_version",
    "ffprobe_version",
    "whisper_available",
    "whisper_reason",
    "openrouter_model",
    "config_dir",
    "log_file",
}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: check_diagnostic.py DIAGNOSTIC.json", file=sys.stderr)
        return 2
    path = Path(args[0])
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED - data.keys()
    if missing:
        raise SystemExit(f"Champs manquants : {sorted(missing)}")
    if data["flavor"] != "lite":
        raise SystemExit("flavor différent de lite")
    if data["frozen"] is not True:
        raise SystemExit("l'artefact n'est pas gelé")
    if data["whisper_available"] is not False:
        raise SystemExit("Whisper ne doit pas être disponible")
    for key in ("ffmpeg_path", "ffprobe_path", "ffmpeg_version", "ffprobe_version"):
        if not data.get(key):
            raise SystemExit(f"Champ vide : {key}")
    print(
        f"{data['app_version']} {data['flavor']} {data['arch']} "
        f"{data['ffmpeg_version']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
