"""Couche média : résolution et exécution annulable de ffmpeg/ffprobe."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .config import (
    OPENROUTER_AUDIO_BITRATE,
    OPENROUTER_SILENCE_DURATION,
    OPENROUTER_SILENCE_NOISE,
    VIDEO_EXTENSIONS,
)
from .errors import CancelledError, MediaToolMissingError, TranscribeError
from .models import CancelToken

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_POLL_INTERVAL = 0.1
_TERMINATE_GRACE_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class MediaProcessResult:
    returncode: int
    stdout: str
    stderr: str


def creation_flags() -> int:
    """Empêche l'ouverture d'une console Windows pour les sous-processus."""
    return CREATE_NO_WINDOW if sys.platform == "win32" else 0


def resolve_tool(name: str) -> str | None:
    """Résout ffmpeg/ffprobe : override, bundle, puis PATH."""
    filename = (
        name + ".exe"
        if sys.platform == "win32" and not name.endswith(".exe")
        else name
    )
    candidates: list[Path] = []
    env_dir = os.environ.get("ECOTRANSCRIBE_FFMPEG_DIR")
    if env_dir:
        candidates.append(Path(env_dir) / filename)

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "bin" / filename)

    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        candidates.append(
            Path(sys.executable).resolve().parents[1]
            / "Resources"
            / "bin"
            / filename
        )

    for candidate in candidates:
        if candidate.is_file() and (
            sys.platform == "win32" or os.access(candidate, os.X_OK)
        ):
            return str(candidate)

    return shutil.which(filename)


def _require_tool(name: str) -> str:
    path = resolve_tool(name)
    if not path:
        raise MediaToolMissingError(name)
    return path


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()


def run_media(
    args: list[str] | tuple[str, ...],
    *,
    cancel: CancelToken | None = None,
    timeout: float | None = None,
) -> MediaProcessResult:
    """Exécute un outil média avec polling d'annulation toutes les 100 ms."""
    cancel = cancel or CancelToken()
    command = [str(argument) for argument in args]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags(),
            shell=False,
        )
    except FileNotFoundError as exc:
        raise TranscribeError(
            "Impossible de lancer l'outil média.",
            detail=str(exc),
        ) from exc

    deadline = time.monotonic() + timeout if timeout is not None else None
    try:
        while True:
            cancel.raise_if_cancelled()
            if deadline is not None and time.monotonic() >= deadline:
                _stop_process(process)
                raise TranscribeError(
                    "Le traitement du média a pris trop de temps.",
                    detail=" ".join(command),
                )
            wait = _POLL_INTERVAL
            if deadline is not None:
                wait = min(wait, max(0.01, deadline - time.monotonic()))
            try:
                stdout, stderr = process.communicate(timeout=wait)
            except subprocess.TimeoutExpired:
                continue
            return MediaProcessResult(
                process.returncode or 0, stdout or "", stderr or ""
            )
    except CancelledError:
        _stop_process(process)
        raise
    except BaseException:
        _stop_process(process)
        raise


def get_media_duration(
    path: Path, *, cancel: CancelToken | None = None
) -> float | None:
    """Durée du média via ffprobe, ou None si illisible."""
    ffprobe = _require_tool("ffprobe")
    result = run_media(
        [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(path),
        ],
        cancel=cancel,
        timeout=30,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
        duration = payload.get("format", {}).get("duration")
        return float(duration) if duration is not None else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def is_video_file(path: Path, *, cancel: CancelToken | None = None) -> bool:
    """Détecte une vidéo par extension, puis par ffprobe si ambigu."""
    if Path(path).suffix.lower() in VIDEO_EXTENSIONS:
        return True

    ffprobe = _require_tool("ffprobe")
    result = run_media(
        [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(path),
        ],
        cancel=cancel,
        timeout=30,
    )
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return any(
        stream.get("codec_type") == "video"
        for stream in payload.get("streams", [])
    )


def extract_audio(
    video_path: Path,
    output_path: Path,
    *,
    cancel: CancelToken | None = None,
) -> None:
    """Extrait l'audio en WAV 16 kHz mono."""
    ffmpeg = _require_tool("ffmpeg")
    result = run_media(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ],
        cancel=cancel,
    )
    if result.returncode != 0:
        raise TranscribeError(
            "Impossible de traiter ce fichier audio ou vidéo.",
            detail=result.stderr.strip(),
        )


def detect_silences(
    audio_path: Path, *, cancel: CancelToken | None = None
) -> list[tuple[float, float]]:
    """Détecte les silences via `ffmpeg silencedetect`."""
    ffmpeg = _require_tool("ffmpeg")
    result = run_media(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(audio_path),
            "-af",
            (
                f"silencedetect=noise={OPENROUTER_SILENCE_NOISE}"
                f":d={OPENROUTER_SILENCE_DURATION}"
            ),
            "-f",
            "null",
            "-",
        ],
        cancel=cancel,
    )
    if result.returncode != 0:
        return []

    starts = [
        float(value)
        for value in re.findall(
            r"silence_start:\s*([0-9.]+)", result.stderr
        )
    ]
    ends = [
        float(value)
        for value in re.findall(
            r"silence_end:\s*([0-9.]+)", result.stderr
        )
    ]
    return list(zip(starts, ends))


def extract_chunk_mp3(
    audio_path: Path,
    chunk_path: Path,
    start: float,
    duration: float,
    *,
    cancel: CancelToken | None = None,
) -> None:
    """Extrait une tranche MP3 mono 16 kHz."""
    ffmpeg = _require_tool("ffmpeg")
    result = run_media(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(audio_path),
            "-t",
            f"{duration:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "libmp3lame",
            "-b:a",
            OPENROUTER_AUDIO_BITRATE,
            str(chunk_path),
        ],
        cancel=cancel,
    )
    if result.returncode != 0:
        raise TranscribeError(
            "Impossible de découper l'audio.",
            detail=result.stderr.strip(),
        )


def tool_version(tool: str) -> str | None:
    """Première ligne de `tool -version`, ou None si indisponible."""
    try:
        result = run_media([tool, "-version"], timeout=10)
    except TranscribeError:
        return None
    output = result.stdout or result.stderr
    line = output.strip().splitlines()
    return line[0] if line else None
