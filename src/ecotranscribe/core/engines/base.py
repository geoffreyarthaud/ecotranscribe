"""Contrat commun aux moteurs de transcription."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ..models import (
    CancelToken,
    EngineAvailability,
    EngineResult,
    ProgressUpdate,
    Provider,
    TranscribeRequest,
)

ProgressCallback = Callable[[ProgressUpdate], None]
LogCallback = Callable[[str, str], None]


class TranscriptionEngine(Protocol):
    provider: Provider

    def availability(self) -> EngineAvailability:
        """Indique si le moteur peut être utilisé."""
        ...

    def transcribe(
        self,
        request: TranscribeRequest,
        *,
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
        cancel: CancelToken,
    ) -> EngineResult:
        """Transcrit la requête et retourne le résultat brut du moteur."""
        ...
