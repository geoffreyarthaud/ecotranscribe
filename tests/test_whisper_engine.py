from pathlib import Path
from types import SimpleNamespace

import pytest

from ecotranscribe.core.engines import whisper as whisper_engine
from ecotranscribe.core.engines.whisper import (
    WhisperEngine,
    _WhisperProgress,
    frames_to_seconds,
    whisper_availability,
)
from ecotranscribe.core.errors import CancelledError, EngineUnavailableError
from ecotranscribe.core.models import (
    CancelToken,
    EngineAvailability,
    ProgressUpdate,
    Provider,
    TranscribeRequest,
)


class FakeModel:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def transcribe(self, audio: str, **options: object) -> dict:
        self.calls.append((audio, options))
        return self.result


def _request(tmp_path: Path, **overrides: object) -> TranscribeRequest:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x")
    values = {
        "input_path": source,
        "provider": Provider.WHISPER,
        "model": "tiny",
    }
    values.update(overrides)
    return TranscribeRequest(**values)


def test_availability_reports_missing_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(whisper_engine, "_module_available", lambda name: False)
    availability = whisper_availability()
    assert availability.available is False
    assert "uv sync --extra whisper" in (availability.reason or "")


def test_frames_to_seconds() -> None:
    assert frames_to_seconds(100) == 1.0


def test_build_options_includes_language_and_prompt() -> None:
    options = whisper_engine.build_options(
        language="fr", prompt="RGAA", device="cpu"
    )
    assert options["language"] == "fr"
    assert options["initial_prompt"] == "RGAA"
    assert options["carry_initial_prompt"] is True
    assert options["fp16"] is False


def test_build_options_omits_auto_language() -> None:
    options = whisper_engine.build_options(
        language=None, prompt=None, device="mps"
    )
    assert "language" not in options
    assert "initial_prompt" not in options
    assert options["fp16"] is True


def test_progress_shim_reports_audio_seconds() -> None:
    updates: list[ProgressUpdate] = []
    progress = _WhisperProgress(
        total=2000,
        total_audio_s=20.0,
        on_progress=updates.append,
    )
    progress.update(500)
    assert updates[-1].phase == "transcribing"
    assert updates[-1].current == 5.0
    assert updates[-1].total == 20.0


def test_transcribe_maps_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = FakeModel(
        {
            "text": "Bonjour",
            "language": "fr",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Bonjour"},
                {"start": 1.0, "end": 2.0, "text": "monde"},
            ],
        }
    )
    fake_whisper = SimpleNamespace(
        load_model=lambda name, device: model,
    )

    monkeypatch.setattr(whisper_engine.media, "is_video_file", lambda *a, **k: False)
    monkeypatch.setattr(
        whisper_engine.media, "get_media_duration", lambda *a, **k: 2.0
    )
    monkeypatch.setattr(
        whisper_engine,
        "whisper_availability",
        lambda: EngineAvailability(True),
    )
    engine = WhisperEngine(
        loader=lambda: fake_whisper, device_fn=lambda: "cpu"
    )
    result = engine.transcribe(_request(tmp_path), cancel=CancelToken())

    assert result.text == "Bonjour"
    assert result.language == "fr"
    assert [segment.text for segment in result.segments] == [
        "Bonjour",
        "monde",
    ]
    assert result.cost_usd is None
    assert result.duration_s == 2.0


def test_transcribe_stops_when_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    def loader() -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(
        whisper_engine,
        "whisper_availability",
        lambda: EngineAvailability(True),
    )
    token = CancelToken()
    token.cancel()
    engine = WhisperEngine(loader=loader, device_fn=lambda: "cpu")
    with pytest.raises(CancelledError):
        engine.transcribe(_request(tmp_path), cancel=token)
    assert called is False


def test_transcribe_requires_available_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        whisper_engine,
        "whisper_availability",
        lambda: whisper_engine.EngineAvailability(False, "absent"),
    )
    engine = WhisperEngine(loader=lambda: object(), device_fn=lambda: "cpu")
    with pytest.raises(EngineUnavailableError):
        engine.transcribe(_request(tmp_path), cancel=CancelToken())
