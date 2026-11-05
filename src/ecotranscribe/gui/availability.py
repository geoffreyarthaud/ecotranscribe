"""Disponibilité des moteurs et JSON de diagnostic."""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone

from PySide6.QtCore import qVersion

from .. import __version__
from ..core.config import (
    FLAVOR,
    OPENROUTER_MODEL,
    PROJECT_URL,
    WHISPER_LITE_REASON,
)
from ..core.media import resolve_tool, tool_version
from ..core.models import EngineAvailability
from .logging_setup import config_dir, log_file_path

try:  # généré au build PyInstaller
    import ecotranscribe_build_info as _build_info
except ImportError:  # développement
    _build_info = None

_DEFAULT_COMMIT = getattr(_build_info, "COMMIT", "dev")
_DEFAULT_BUILD_DATE = getattr(_build_info, "BUILD_DATE", "")


def whisper_availability() -> EngineAvailability:
    """Whisper n'est jamais inclus dans l'édition lite."""
    return EngineAvailability(
        False,
        WHISPER_LITE_REASON,
        detail="L'édition lite ne contient ni torch ni openai-whisper.",
    )


def openrouter_availability() -> EngineAvailability:
    return EngineAvailability(True)


def _commit() -> str:
    return os.environ.get("ECOTRANSCRIBE_COMMIT") or _DEFAULT_COMMIT or "dev"


def _build_date() -> str:
    if os.environ.get("ECOTRANSCRIBE_BUILD_DATE"):
        return os.environ["ECOTRANSCRIBE_BUILD_DATE"]
    if _DEFAULT_BUILD_DATE:
        return _DEFAULT_BUILD_DATE
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_info() -> dict:
    return {
        "version": __version__,
        "flavor": FLAVOR,
        "commit": _commit(),
        "build_date": _build_date(),
        "license": "MIT",
        "source": PROJECT_URL,
    }


def collect_diagnostic() -> dict:
    """Construit le JSON de diagnostic sans afficher de fenêtre."""
    ffmpeg_path = resolve_tool("ffmpeg")
    ffprobe_path = resolve_tool("ffprobe")
    return {
        "app_version": __version__,
        "flavor": FLAVOR,
        "commit": _commit(),
        "build_date": _build_date(),
        "python": platform.python_version(),
        "qt": qVersion(),
        "platform": sys.platform,
        "arch": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "ffmpeg_path": ffmpeg_path,
        "ffprobe_path": ffprobe_path,
        "ffmpeg_version": (
            tool_version(ffmpeg_path) if ffmpeg_path else None
        ),
        "ffprobe_version": (
            tool_version(ffprobe_path) if ffprobe_path else None
        ),
        "whisper_available": False,
        "whisper_reason": WHISPER_LITE_REASON,
        "openrouter_model": OPENROUTER_MODEL,
        "config_dir": str(config_dir()),
        "log_file": str(log_file_path()),
    }
