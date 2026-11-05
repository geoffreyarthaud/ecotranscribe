"""Contrats de données partagés par le CLI et la GUI."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from .errors import CancelledError

ProgressPhase = Literal[
    "validating",
    "extracting",
    "detecting_silences",
    "transcribing",
    "writing",
    "done",
]


class Provider(str, Enum):
    OPENROUTER = "openrouter"
    WHISPER = "whisper"


class OutputFormat(str, Enum):
    SRT = "srt"
    TXT = "txt"


@dataclass(frozen=True, slots=True)
class Segment:
    id: int
    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class TranscribeRequest:
    input_path: Path
    provider: Provider
    model: str
    language: str | None = "fr"
    prompt_text: str | None = None
    output_dir: Path | None = None
    formats: frozenset[OutputFormat] = frozenset(
        {OutputFormat.SRT, OutputFormat.TXT}
    )
    overwrite: bool = False
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.output_dir is None:
            object.__setattr__(self, "output_dir", self.input_path.parent)
        if not isinstance(self.provider, Provider):
            object.__setattr__(self, "provider", Provider(self.provider))
        formats = frozenset(
            fmt if isinstance(fmt, OutputFormat) else OutputFormat(fmt)
            for fmt in self.formats
        )
        object.__setattr__(self, "formats", formats)
        if not (self.prompt_text or "").strip():
            object.__setattr__(self, "prompt_text", None)


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    phase: ProgressPhase
    current: float = 0.0
    total: float | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class EngineAvailability:
    available: bool
    reason: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class EngineResult:
    text: str
    segments: tuple[Segment, ...]
    language: str | None
    cost_usd: float | None
    duration_s: float | None


@dataclass(frozen=True, slots=True)
class TranscribeResult:
    output_paths: tuple[Path, ...]
    text: str
    segments: tuple[Segment, ...]
    language: str | None
    cost_usd: float | None
    provider: Provider
    model: str
    duration_s: float | None


class CancelToken:
    """Jeton d'annulation idempotent et sûr entre threads."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise CancelledError()
