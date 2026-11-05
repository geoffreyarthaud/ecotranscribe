"""Orchestration commune au CLI et à la GUI."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from .config import KEY_MISSING_MESSAGE
from .engines.base import LogCallback, ProgressCallback, TranscriptionEngine
from .errors import (
    EngineUnavailableError,
    InvalidRequestError,
    OutputExistsError,
    TranscribeError,
)
from .models import (
    CancelToken,
    OutputFormat,
    ProgressUpdate,
    Provider,
    TranscribeRequest,
    TranscribeResult,
)
from .outputs import existing_outputs, output_paths
from .writers import write_srt, write_txt

_FORMAT_ORDER = (OutputFormat.SRT, OutputFormat.TXT)


class TranscribeService:
    """Valide, exécute le moteur puis écrit les sorties atomiquement."""

    def __init__(
        self, engines: Mapping[Provider, TranscriptionEngine]
    ) -> None:
        self._engines = dict(engines)

    def transcribe(
        self,
        request: TranscribeRequest,
        *,
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> TranscribeResult:
        cancel = cancel or CancelToken()
        self._emit(
            on_progress,
            ProgressUpdate("validating", detail="Validation"),
        )
        self._validate(request)

        engine = self._engines.get(request.provider)
        if engine is None:
            raise EngineUnavailableError(
                "Ce moteur n'est pas disponible dans cette édition lite."
            )
        availability = engine.availability()
        if not availability.available:
            raise EngineUnavailableError(
                availability.reason or "Moteur indisponible.",
                availability.detail,
            )
        if request.provider is Provider.OPENROUTER and not (
            request.api_key or ""
        ).strip():
            raise EngineUnavailableError(KEY_MISSING_MESSAGE)

        output_dir = request.output_dir or request.input_path.parent
        paths = output_paths(
            request.input_path, output_dir, request.formats
        )
        for path in paths:
            if path.resolve() == request.input_path.resolve():
                raise InvalidRequestError(
                    "Le fichier de sortie écraserait le fichier source."
                )
        existing = existing_outputs(paths)
        if existing and not request.overwrite:
            raise OutputExistsError(existing)

        cancel.raise_if_cancelled()
        engine_result = engine.transcribe(
            request,
            on_progress=on_progress,
            on_log=on_log,
            cancel=cancel,
        )
        cancel.raise_if_cancelled()

        self._emit(
            on_progress,
            ProgressUpdate("writing", detail="Écriture des fichiers"),
        )
        written: list[Path] = []
        requested_formats = [
            fmt for fmt in _FORMAT_ORDER if fmt in request.formats
        ]
        pairs = list(zip(requested_formats, paths, strict=True))
        try:
            for fmt, path in pairs:
                if fmt is OutputFormat.SRT:
                    write_srt(path, engine_result.segments)
                else:
                    write_txt(path, engine_result.segments)
                written.append(path)
        except OSError as exc:
            detail = str(exc)
            if written:
                detail += "\nFichiers déjà écrits : " + ", ".join(
                    str(path) for path in written
                )
            raise TranscribeError(
                "Impossible d'écrire les fichiers de sortie.", detail
            ) from exc

        self._emit(
            on_progress,
            ProgressUpdate("done", detail="Terminé"),
        )
        return TranscribeResult(
            output_paths=tuple(written),
            text=engine_result.text,
            segments=engine_result.segments,
            language=engine_result.language,
            cost_usd=engine_result.cost_usd,
            provider=request.provider,
            model=request.model,
            duration_s=engine_result.duration_s,
        )

    @staticmethod
    def _validate(request: TranscribeRequest) -> None:
        input_path = Path(request.input_path)
        if not input_path.exists():
            raise InvalidRequestError(
                "Le fichier sélectionné n'existe plus."
            )
        if not input_path.is_file():
            raise InvalidRequestError(
                "Le fichier sélectionné n'est pas un fichier valide."
            )
        if not os.access(input_path, os.R_OK):
            raise InvalidRequestError(
                "Impossible de lire ce fichier. Vérifiez les permissions."
            )

        output_dir = request.output_dir or input_path.parent
        if not output_dir.exists():
            raise InvalidRequestError(
                "Le dossier de sortie n'existe pas."
            )
        if not output_dir.is_dir():
            raise InvalidRequestError(
                "Le dossier de sortie n'est pas un dossier."
            )
        if not os.access(output_dir, os.W_OK | os.X_OK):
            raise InvalidRequestError(
                "Le dossier de sortie n'est pas inscriptible."
            )

        if not request.formats:
            raise InvalidRequestError(
                "Choisissez au moins un format de sortie."
            )
        if not (request.model or "").strip():
            raise InvalidRequestError("Choisissez un modèle.")

    @staticmethod
    def _emit(
        callback: ProgressCallback | None, update: ProgressUpdate
    ) -> None:
        if callback is not None:
            callback(update)
