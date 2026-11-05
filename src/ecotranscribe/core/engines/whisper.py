"""Moteur Whisper local, importé uniquement si l'extra [whisper] est présent."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType

from .. import media
from ..config import (
    WHISPER_HOP_LENGTH,
    WHISPER_NOT_INSTALLED_MESSAGE,
    WHISPER_OPTIONS,
    WHISPER_SAMPLE_RATE,
)
from ..errors import CancelledError, EngineUnavailableError, TranscribeError
from ..models import (
    CancelToken,
    EngineAvailability,
    EngineResult,
    ProgressUpdate,
    Provider,
    Segment,
    TranscribeRequest,
)
from .base import LogCallback, ProgressCallback


def frames_to_seconds(frames: int) -> float:
    """Convertit les frames mel Whisper en secondes audio."""
    return frames * WHISPER_HOP_LENGTH / WHISPER_SAMPLE_RATE


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def whisper_availability() -> EngineAvailability:
    """Vérifie la présence de Whisper et torch, sans importer torch."""
    missing = [
        name
        for name in ("whisper", "torch")
        if not _module_available(name)
    ]
    if missing:
        return EngineAvailability(
            False,
            WHISPER_NOT_INSTALLED_MESSAGE,
            detail="Modules manquants : " + ", ".join(missing),
        )
    return EngineAvailability(True)


def get_device() -> str:
    """MPS, CUDA, puis CPU."""
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def build_options(
    *, language: str | None, prompt: str | None, device: str
) -> dict:
    """Construit les options Whisper sans langue implicite en mode Auto."""
    options = dict(WHISPER_OPTIONS)
    if language is None:
        options.pop("language", None)
    else:
        options["language"] = language
    options["fp16"] = device in ("mps", "cuda")
    if prompt:
        options["initial_prompt"] = prompt
        options["carry_initial_prompt"] = True
    return options


class _WhisperProgress:
    """Remplace tqdm dans whisper.transcribe pour émettre des ProgressUpdate."""

    def __init__(
        self,
        total: int = 0,
        total_audio_s: float = 0.0,
        on_progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
        **_ignored: object,
    ) -> None:
        self._total_frames = total
        self._audio_total_s = total_audio_s or frames_to_seconds(total)
        self._on_progress = on_progress
        self._cancel = cancel
        self._frames = 0
        self._emit()

    @property
    def total_audio_s(self) -> float:
        return self._audio_total_s

    def _emit(self) -> None:
        if self._on_progress is None:
            return
        total = self._audio_total_s if self._audio_total_s > 0 else None
        self._on_progress(
            ProgressUpdate(
                "transcribing",
                current=frames_to_seconds(self._frames),
                total=total,
                detail="Transcription Whisper",
            )
        )

    def __enter__(self) -> "_WhisperProgress":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def update(self, n: int = 1) -> None:
        if self._cancel is not None:
            self._cancel.raise_if_cancelled()
        self._frames += n
        self._emit()

    def set_postfix(self, **_: object) -> None:
        pass

    def set_postfix_str(self, *_: object, **__: object) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeTqdmModule:
    """Faux module tqdm injecté dans whisper.transcribe."""

    def __init__(
        self,
        on_progress: ProgressCallback | None,
        cancel: CancelToken | None,
        total_audio_s: float,
    ) -> None:
        self._on_progress = on_progress
        self._cancel = cancel
        self._total_audio_s = total_audio_s

    def tqdm(
        self, *_args: object, total: int = 0, **_kwargs: object
    ) -> _WhisperProgress:
        return _WhisperProgress(
            total=total,
            total_audio_s=self._total_audio_s,
            on_progress=self._on_progress,
            cancel=self._cancel,
        )


def _load_whisper() -> ModuleType:
    import whisper

    return whisper


class WhisperEngine:
    """Adaptateur Whisper local, sans dépendance à l'extra au chargement."""

    provider = Provider.WHISPER

    def __init__(
        self,
        *,
        loader: Callable[[], ModuleType] | None = None,
        device_fn: Callable[[], str] | None = None,
    ) -> None:
        self._loader = loader or _load_whisper
        self._device_fn = device_fn or get_device

    def availability(self) -> EngineAvailability:
        return whisper_availability()

    def transcribe(
        self,
        request: TranscribeRequest,
        *,
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> EngineResult:
        cancel = cancel or CancelToken()
        availability = self.availability()
        if not availability.available:
            raise EngineUnavailableError(
                availability.reason or WHISPER_NOT_INSTALLED_MESSAGE,
                availability.detail,
            )
        cancel.raise_if_cancelled()

        try:
            total_audio_s = (
                media.get_media_duration(request.input_path, cancel=cancel)
                or 0.0
            )
        except TranscribeError:
            total_audio_s = 0.0

        try:
            with TemporaryDirectory(prefix="ecotranscribe-whisper-") as tmp:
                audio_path = request.input_path
                if media.is_video_file(request.input_path, cancel=cancel):
                    extracted = Path(tmp) / "audio.wav"
                    self._emit(
                        on_progress,
                        ProgressUpdate(
                            "extracting", detail="Extraction audio"
                        ),
                    )
                    if on_log:
                        on_log(
                            "info",
                            "Fichier vidéo détecté, extraction de l'audio…",
                        )
                    media.extract_audio(
                        request.input_path, extracted, cancel=cancel
                    )
                    audio_path = extracted
                    if total_audio_s <= 0:
                        try:
                            total_audio_s = (
                                media.get_media_duration(
                                    extracted, cancel=cancel
                                )
                                or 0.0
                            )
                        except TranscribeError:
                            total_audio_s = 0.0

                cancel.raise_if_cancelled()
                whisper = self._loader()
                device = self._device_fn()
                if on_log:
                    on_log(
                        "info",
                        f"Chargement du modèle Whisper '{request.model}' "
                        f"sur {device}…",
                    )
                model = whisper.load_model(request.model, device=device)
                cancel.raise_if_cancelled()

                options = build_options(
                    language=request.language,
                    prompt=request.prompt_text,
                    device=device,
                )
                self._emit(
                    on_progress,
                    ProgressUpdate(
                        "transcribing",
                        current=0.0,
                        total=total_audio_s or None,
                        detail="Transcription Whisper",
                    ),
                )
                result = self._transcribe_with_progress(
                    model,
                    audio_path,
                    total_audio_s,
                    options,
                    on_progress,
                    cancel,
                )
                cancel.raise_if_cancelled()
        except (TranscribeError, CancelledError):
            raise
        except Exception as exc:
            raise TranscribeError(
                "La transcription Whisper a échoué.", detail=str(exc)
            ) from exc

        raw_segments = result.get("segments") or []
        segments = tuple(
            Segment(
                id=index,
                start=float(segment.get("start", 0.0)),
                end=float(segment.get("end", 0.0)),
                text=str(segment.get("text") or ""),
            )
            for index, segment in enumerate(raw_segments, start=1)
        )
        return EngineResult(
            text=str(result.get("text") or "").strip(),
            segments=segments,
            language=result.get("language") or request.language,
            cost_usd=None,
            duration_s=total_audio_s or None,
        )

    def _transcribe_with_progress(
        self,
        model: object,
        audio_path: Path,
        total_audio_s: float,
        options: dict,
        on_progress: ProgressCallback | None,
        cancel: CancelToken,
    ) -> dict:
        transcribe_module = sys.modules.get("whisper.transcribe")
        original = getattr(transcribe_module, "tqdm", None)
        if transcribe_module is not None:
            transcribe_module.tqdm = _FakeTqdmModule(  # type: ignore[attr-defined]
                on_progress, cancel, total_audio_s
            )
        try:
            return model.transcribe(  # type: ignore[attr-defined]
                str(audio_path), verbose=False, **options
            )
        finally:
            if transcribe_module is not None and original is not None:
                transcribe_module.tqdm = original  # type: ignore[attr-defined]

    @staticmethod
    def _emit(
        callback: ProgressCallback | None, update: ProgressUpdate
    ) -> None:
        if callback is not None:
            callback(update)
