"""Adaptateur OpenRouter, avec découpage, retries et annulation."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from .. import media
from ..config import (
    KEY_MISSING_MESSAGE,
    OPENROUTER_API_URL,
    OPENROUTER_CHUNK_SECONDS,
    OPENROUTER_CUT_SEARCH_WINDOW,
    OPENROUTER_MAX_RETRIES,
    OPENROUTER_MIN_CHUNK_SECONDS,
    OPENROUTER_REQUEST_TIMEOUT,
)
from ..errors import EngineUnavailableError, TranscribeError
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

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 529})
_CHUNK_TIMEOUT_STATUS = frozenset({504, 524})


class _ChunkTimeout(RuntimeError):
    """Le provider a dépassé son timeout : la tranche doit être coupée."""


def normalize_context_bias(prompt: str) -> str:
    """Compacte le prompt en une seule chaîne pour context_bias."""
    return " ".join(prompt.split())


def choose_cut_points(
    duration: float,
    silences: Sequence[tuple[float, float]],
    chunk_seconds: float = OPENROUTER_CHUNK_SECONDS,
    search_window: float = OPENROUTER_CUT_SEARCH_WINDOW,
    min_chunk_seconds: float = OPENROUTER_MIN_CHUNK_SECONDS,
) -> list[float]:
    """Choisit les coupures cibles, décalées vers le silence le plus proche."""
    cuts: list[float] = []
    target = chunk_seconds

    while target < duration - min_chunk_seconds:
        candidates = [
            (start + end) / 2.0
            for start, end in silences
            if abs((start + end) / 2.0 - target) <= search_window
        ]
        cut = (
            min(candidates, key=lambda value: abs(value - target))
            if candidates
            else target
        )
        previous = cuts[-1] if cuts else 0.0
        if cut - previous >= min_chunk_seconds:
            cuts.append(cut)
        target += chunk_seconds

    if cuts and duration - cuts[-1] < min_chunk_seconds:
        cuts.pop()

    return cuts


def offset_segments(
    segments: Sequence[Segment], offset: float
) -> tuple[Segment, ...]:
    """Décale des segments et les renumérote à partir de 1."""
    return tuple(
        Segment(
            id=index,
            start=segment.start + offset,
            end=segment.end + offset,
            text=segment.text,
        )
        for index, segment in enumerate(segments, start=1)
    )


def build_payload(
    model: str,
    audio_b64: str,
    language: str | None,
    prompt: str | None,
) -> dict:
    """Construit le payload STT OpenRouter."""
    payload: dict = {
        "model": model,
        "input_audio": {"data": audio_b64, "format": "mp3"},
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment"],
    }
    if language is not None:
        payload["language"] = language
    if prompt and model.startswith("mistralai/"):
        payload["provider"] = {
            "options": {
                "mistral": {"context_bias": normalize_context_bias(prompt)}
            }
        }
    return payload


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except OSError:
        return f"HTTP {exc.code}"
    try:
        payload = json.loads(body)
        message = payload.get("error", {}).get("message")
        if message:
            return str(message)
    except (json.JSONDecodeError, AttributeError):
        pass
    return body.strip() or f"HTTP {exc.code}"


def _interruptible_sleep(
    seconds: float,
    cancel: CancelToken,
    sleep: Callable[[float], None],
) -> None:
    deadline = time.monotonic() + seconds
    while True:
        cancel.raise_if_cancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        sleep(min(0.2, remaining))


def _post_openrouter(
    payload: dict,
    api_key: str,
    *,
    url: str,
    cancel: CancelToken,
    sleep: Callable[[float], None] = time.sleep,
    on_log: LogCallback | None = None,
    timeout: float = OPENROUTER_REQUEST_TIMEOUT,
    max_retries: int = OPENROUTER_MAX_RETRIES,
) -> dict:
    """Envoie une requête STT avec retries transitoires, sans logger la clé."""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None

    for attempt in range(max_retries):
        cancel.raise_if_cancelled()
        request = urllib.request.Request(
            url, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                try:
                    decoded = json.load(response)
                except json.JSONDecodeError as exc:
                    raise TranscribeError(
                        "Réponse OpenRouter invalide.", detail=str(exc)
                    ) from exc
                if not isinstance(decoded, dict):
                    raise TranscribeError(
                        "Réponse OpenRouter invalide.",
                        detail="Le JSON racine n'est pas un objet.",
                    )
                return decoded
        except urllib.error.HTTPError as exc:
            message = _read_http_error(exc)
            if exc.code in _CHUNK_TIMEOUT_STATUS:
                raise _ChunkTimeout(message) from exc
            if exc.code == 401:
                raise EngineUnavailableError(
                    "Clé OpenRouter refusée. Vérifiez-la dans vos réglages "
                    "OpenRouter.",
                    detail=message,
                ) from exc
            if exc.code == 402:
                raise TranscribeError(
                    "Crédit OpenRouter insuffisant.", detail=message
                ) from exc
            if (
                exc.code in _RETRYABLE_STATUS
                and attempt + 1 < max_retries
            ):
                last_error = exc
                if on_log:
                    on_log(
                        "warning",
                        f"OpenRouter HTTP {exc.code}, nouvelle tentative.",
                    )
                _interruptible_sleep(2**attempt, cancel, sleep)
                continue
            raise TranscribeError(
                f"OpenRouter a renvoyé une erreur (HTTP {exc.code}).",
                detail=message,
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
            if attempt + 1 < max_retries:
                if on_log:
                    on_log(
                        "warning",
                        "OpenRouter injoignable, nouvelle tentative.",
                    )
                _interruptible_sleep(2**attempt, cancel, sleep)
                continue
            raise TranscribeError(
                "OpenRouter est injoignable. Vérifiez votre connexion.",
                detail=str(exc),
            ) from exc

    raise TranscribeError(
        "OpenRouter est injoignable. Vérifiez votre connexion.",
        detail=f"Échec après {max_retries} tentatives : {last_error}",
    )


def _parse_cost(response: dict) -> float | None:
    usage = response.get("usage")
    if not isinstance(usage, dict) or usage.get("cost") is None:
        return None
    try:
        return float(usage["cost"])
    except (TypeError, ValueError):
        return None


class OpenRouterEngine:
    """Moteur OpenRouter découpant l'audio en tranches."""

    provider = Provider.OPENROUTER

    def __init__(
        self,
        *,
        api_url: str = OPENROUTER_API_URL,
        http_post: Callable[..., dict] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = OPENROUTER_REQUEST_TIMEOUT,
        max_retries: int = OPENROUTER_MAX_RETRIES,
    ) -> None:
        self._api_url = api_url
        self._http_post = http_post or _post_openrouter
        self._sleep = sleep
        self._timeout = timeout
        self._max_retries = max_retries

    def availability(self) -> EngineAvailability:
        return EngineAvailability(True)

    def transcribe(
        self,
        request: TranscribeRequest,
        *,
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> EngineResult:
        cancel = cancel or CancelToken()
        api_key = (request.api_key or "").strip()
        if not api_key:
            raise EngineUnavailableError(KEY_MISSING_MESSAGE)

        prompt = (request.prompt_text or "").strip() or None
        if prompt and not request.model.startswith("mistralai/"):
            if on_log:
                on_log(
                    "warning",
                    "Prompt ignoré : context_bias n'est supporté que par "
                    "les modèles Mistral.",
                )
            prompt = None

        with TemporaryDirectory(prefix="ecotranscribe-") as temporary:
            temporary_dir = Path(temporary)
            wav_path = temporary_dir / "audio.wav"

            self._emit(
                on_progress,
                ProgressUpdate(
                    "extracting", detail="Extraction audio"
                ),
            )
            if on_log:
                on_log("info", "Extraction de l'audio en cours…")
            media.extract_audio(
                request.input_path, wav_path, cancel=cancel
            )

            duration = media.get_media_duration(wav_path, cancel=cancel)
            if duration is None or duration <= 0:
                raise TranscribeError(
                    "Impossible de lire la durée du média. Le fichier est "
                    "peut-être corrompu."
                )

            self._emit(
                on_progress,
                ProgressUpdate(
                    "detecting_silences", detail="Détection des silences"
                ),
            )
            if on_log:
                on_log("info", "Détection des silences…")
            silences = media.detect_silences(wav_path, cancel=cancel)
            cuts = choose_cut_points(
                duration, silences, OPENROUTER_CHUNK_SECONDS
            )
            boundaries = [0.0, *cuts, duration]
            ranges = list(zip(boundaries, boundaries[1:]))

            self._emit(
                on_progress,
                ProgressUpdate(
                    "transcribing",
                    current=0.0,
                    total=duration,
                    detail=f"Tranche 1/{len(ranges)}",
                ),
            )
            if on_log:
                on_log(
                    "info",
                    f"{len(ranges)} tranche(s) d'environ "
                    f"{OPENROUTER_CHUNK_SECONDS // 60} min.",
                )

            all_segments: list[Segment] = []
            texts: list[str] = []
            total_cost: float | None = None
            completed = 0.0

            for index, (start, end) in enumerate(ranges, start=1):
                cancel.raise_if_cancelled()
                segments, text, cost = self._transcribe_range(
                    wav_path,
                    temporary_dir,
                    start,
                    end,
                    prompt,
                    request.language,
                    request.model,
                    api_key,
                    cancel,
                    on_log,
                )
                all_segments.extend(segments)
                if text:
                    texts.append(text)
                if cost is not None:
                    total_cost = (
                        cost if total_cost is None else total_cost + cost
                    )
                completed += end - start
                self._emit(
                    on_progress,
                    ProgressUpdate(
                        "transcribing",
                        current=completed,
                        total=duration,
                        detail=f"Tranche {index}/{len(ranges)}",
                    ),
                )

        final_segments = tuple(
            Segment(
                id=index,
                start=segment.start,
                end=segment.end,
                text=segment.text,
            )
            for index, segment in enumerate(all_segments, start=1)
        )
        return EngineResult(
            text=" ".join(texts).strip(),
            segments=final_segments,
            language=request.language,
            cost_usd=total_cost,
            duration_s=duration,
        )

    def _transcribe_range(
        self,
        wav_path: Path,
        temporary_dir: Path,
        start: float,
        end: float,
        prompt: str | None,
        language: str | None,
        model: str,
        api_key: str,
        cancel: CancelToken,
        on_log: LogCallback | None,
    ) -> tuple[tuple[Segment, ...], str, float | None]:
        cancel.raise_if_cancelled()
        try:
            return self._transcribe_chunk(
                wav_path,
                temporary_dir,
                start,
                end,
                prompt,
                language,
                model,
                api_key,
                cancel,
                on_log,
            )
        except _ChunkTimeout as exc:
            if end - start <= OPENROUTER_MIN_CHUNK_SECONDS:
                raise TranscribeError(
                    "OpenRouter a mis trop de temps à transcrire ce passage.",
                    detail=str(exc),
                ) from exc
            middle = (start + end) / 2.0
            left_segments, left_text, left_cost = self._transcribe_range(
                wav_path,
                temporary_dir,
                start,
                middle,
                prompt,
                language,
                model,
                api_key,
                cancel,
                on_log,
            )
            right_segments, right_text, right_cost = self._transcribe_range(
                wav_path,
                temporary_dir,
                middle,
                end,
                prompt,
                language,
                model,
                api_key,
                cancel,
                on_log,
            )
            costs = [
                cost
                for cost in (left_cost, right_cost)
                if cost is not None
            ]
            cost = sum(costs) if costs else None
            return (
                left_segments + right_segments,
                " ".join(
                    part for part in (left_text, right_text) if part
                ),
                cost,
            )

    def _transcribe_chunk(
        self,
        wav_path: Path,
        temporary_dir: Path,
        start: float,
        end: float,
        prompt: str | None,
        language: str | None,
        model: str,
        api_key: str,
        cancel: CancelToken,
        on_log: LogCallback | None,
    ) -> tuple[tuple[Segment, ...], str, float | None]:
        chunk_path = temporary_dir / f"chunk_{int(start * 1000):09d}.mp3"
        media.extract_chunk_mp3(
            wav_path,
            chunk_path,
            start,
            end - start,
            cancel=cancel,
        )
        cancel.raise_if_cancelled()

        audio_b64 = base64.b64encode(chunk_path.read_bytes()).decode("ascii")
        payload = build_payload(model, audio_b64, language, prompt)
        response = self._http_post(
            payload,
            api_key,
            url=self._api_url,
            cancel=cancel,
            sleep=self._sleep,
            on_log=on_log,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )
        cancel.raise_if_cancelled()

        text = str(response.get("text", "")).strip()
        raw_segments = response.get("segments") or [
            {"start": 0.0, "end": end - start, "text": text}
        ]
        segments = tuple(
            Segment(
                id=0,
                start=float(segment.get("start", 0.0)),
                end=float(segment.get("end", end - start)),
                text=str(segment.get("text") or ""),
            )
            for segment in raw_segments
        )
        return offset_segments(segments, start), text, _parse_cost(response)

    @staticmethod
    def _emit(
        callback: ProgressCallback | None, update: ProgressUpdate
    ) -> None:
        if callback is not None:
            callback(update)
