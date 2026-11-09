#!/usr/bin/env python3
"""Vérifie les capacités ffmpeg/ffprobe utilisées par EcoTranscribe."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"

REQUIRED_FILTERS = ("silencedetect", "aresample", "aformat", "anull")
REQUIRED_ENCODERS = ("pcm_s16le", "libmp3lame")
REQUIRED_MUXERS = ("wav", "mp3", "null")
REQUIRED_PROTOCOLS = ("file", "pipe")
REQUIRED_DEMUXERS = (
    "aac",
    "aiff",
    "asf",
    "avi",
    "flac",
    "flv",
    "matroska",
    "mov",
    "mp3",
    "mpegts",
    "mxf",
    "ogg",
    "wav",
)
REQUIRED_DECODERS = (
    "aac",
    "aac_latm",
    "ac3",
    "eac3",
    "dca",
    "truehd",
    "mlp",
    "flac",
    "alac",
    "opus",
    "vorbis",
    "mp1",
    "mp2",
    "mp3",
    "wmav1",
    "wmav2",
    "wmapro",
    "wmavoice",
    "amrnb",
    "amrwb",
    "gsm",
    "gsm_ms",
    "speex",
    "nellymoser",
    "pcm_s16le",
    "pcm_s16be",
    "pcm_u8",
    "pcm_s24le",
    "pcm_s24be",
    "pcm_s32le",
    "pcm_s32be",
    "pcm_f32le",
    "pcm_f32be",
    "pcm_f64le",
    "pcm_f64be",
    "pcm_alaw",
    "pcm_mulaw",
    "adpcm_ima_wav",
    "adpcm_ms",
    "adpcm_yamaha",
    "adpcm_ima_qt",
)


class CheckError(RuntimeError):
    """Capacité ffmpeg manquante ou smoke test en échec."""


def _run(command: list[str], *, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _require_names(output: str, names: tuple[str, ...], label: str) -> None:
    missing = [
        name
        for name in names
        if not re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
            output,
        )
    ]
    if missing:
        raise CheckError(f"{label} manquants : {', '.join(missing)}")


def _write_test_wav(path: Path) -> None:
    """WAV 1 s : 0,5 s de silence puis 0,5 s de sinusoïde 440 Hz."""
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        frames = bytearray()
        for index in range(16_000):
            value = (
                0
                if index < 8_000
                else int(12_000 * math.sin(2 * math.pi * 440 * index / 16_000))
            )
            frames += struct.pack("<h", value)
        handle.writeframes(frames)


def _smoke_test(ffmpeg: str, ffprobe: str, workdir: Path) -> None:
    source = workdir / "source.wav"
    _write_test_wav(source)

    for option in ("-show_format", "-show_streams"):
        result = _run(
            [ffprobe, "-v", "quiet", "-print_format", "json", option, str(source)]
        )
        if result.returncode != 0:
            raise CheckError(f"ffprobe {option} a échoué : {result.stderr.strip()}")
        json.loads(result.stdout)

    extracted = workdir / "extracted.wav"
    result = _run(
        [
            ffmpeg,
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(extracted),
        ]
    )
    if result.returncode != 0 or not extracted.is_file():
        raise CheckError(f"extraction WAV impossible : {result.stderr.strip()}")

    result = _run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-i",
            str(extracted),
            "-af",
            "silencedetect=noise=-35dB:d=0.4",
            "-f",
            "null",
            "-",
        ]
    )
    if result.returncode != 0 or "silence_start" not in result.stderr:
        raise CheckError(f"silencedetect indisponible : {result.stderr.strip()}")

    chunk = workdir / "chunk.mp3"
    result = _run(
        [
            ffmpeg,
            "-nostdin",
            "-y",
            "-ss",
            "0",
            "-i",
            str(extracted),
            "-t",
            "0.5",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            str(chunk),
        ]
    )
    if result.returncode != 0 or not chunk.is_file() or chunk.stat().st_size == 0:
        raise CheckError(f"encodage MP3 impossible : {result.stderr.strip()}")

    result = _run(
        [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", str(chunk)]
    )
    if result.returncode != 0:
        raise CheckError(f"ffprobe MP3 impossible : {result.stderr.strip()}")
    duration = json.loads(result.stdout).get("format", {}).get("duration")
    if duration is None or float(duration) <= 0:
        raise CheckError("durée MP3 absente ou nulle")


def check_tools(
    ffmpeg: str | Path,
    ffprobe: str | Path,
    *,
    require_lgpl: bool = True,
    smoke: bool = True,
) -> dict[str, str]:
    """Vérifie licence, composants et parcours réel sur un WAV de test."""
    ffmpeg = str(ffmpeg)
    ffprobe = str(ffprobe)
    for path in (ffmpeg, ffprobe):
        if not Path(path).is_file():
            raise CheckError(f"binaire introuvable : {path}")

    version = _run([ffmpeg, "-hide_banner", "-version"])
    if version.returncode != 0:
        raise CheckError(f"ffmpeg -version a échoué : {version.stderr.strip()}")
    if not version.stdout.startswith("ffmpeg version 9."):
        raise CheckError(
            "version ffmpeg inattendue : "
            + (version.stdout.splitlines()[0] if version.stdout else "vide")
        )

    license_result = _run([ffmpeg, "-hide_banner", "-L"])
    license_text = license_result.stdout + license_result.stderr
    if require_lgpl and "Lesser General Public License" not in license_text:
        raise CheckError("ffmpeg n'est pas sous LGPL")

    for option, names, label in (
        ("-filters", REQUIRED_FILTERS, "filtres"),
        ("-encoders", REQUIRED_ENCODERS, "encodeurs"),
        ("-muxers", REQUIRED_MUXERS, "muxers"),
        ("-protocols", REQUIRED_PROTOCOLS, "protocoles"),
        ("-demuxers", REQUIRED_DEMUXERS, "démuxeurs"),
        ("-decoders", REQUIRED_DECODERS, "décodeurs"),
    ):
        result = _run([ffmpeg, "-hide_banner", option])
        if result.returncode != 0:
            raise CheckError(f"ffmpeg {option} a échoué : {result.stderr.strip()}")
        _require_names(result.stdout, names, label)

    if smoke:
        with tempfile.TemporaryDirectory(prefix="ecotranscribe-ffmpeg-") as tmp:
            _smoke_test(ffmpeg, ffprobe, Path(tmp))

    return {
        "version": version.stdout.splitlines()[0],
        "license": "LGPLv2.1+" if require_lgpl else "non vérifiée",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vérifie les capacités ffmpeg/ffprobe d'EcoTranscribe."
    )
    parser.add_argument("--target", default=None)
    parser.add_argument("--ffmpeg", type=Path, default=None)
    parser.add_argument("--ffprobe", type=Path, default=None)
    parser.add_argument("--skip-smoke", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if bool(args.ffmpeg) != bool(args.ffprobe):
        print("Erreur : fournissez --ffmpeg et --ffprobe ensemble.", file=sys.stderr)
        return 2

    if args.ffmpeg and args.ffprobe:
        ffmpeg, ffprobe = args.ffmpeg, args.ffprobe
        target = args.target or "explicit"
    else:
        from fetch_ffmpeg import detect_target

        target = args.target or detect_target()
        base = VENDOR / "ffmpeg" / target
        suffix = ".exe" if sys.platform == "win32" else ""
        ffmpeg = base / f"ffmpeg{suffix}"
        ffprobe = base / f"ffprobe{suffix}"

    try:
        summary = check_tools(ffmpeg, ffprobe, smoke=not args.skip_smoke)
    except (CheckError, OSError, subprocess.SubprocessError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    print(f"{target} : {summary['version']} ({summary['license']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
