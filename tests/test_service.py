from pathlib import Path

import pytest

from ecotranscribe.core import service as service_module
from ecotranscribe.core.config import KEY_MISSING_MESSAGE
from ecotranscribe.core.errors import (
    CancelledError,
    EngineUnavailableError,
    InvalidRequestError,
    OutputExistsError,
    TranscribeError,
)
from ecotranscribe.core.models import (
    CancelToken,
    EngineAvailability,
    EngineResult,
    OutputFormat,
    ProgressUpdate,
    Provider,
    Segment,
    TranscribeRequest,
)
from ecotranscribe.core.service import TranscribeService


class FakeEngine:
    provider = Provider.OPENROUTER

    def __init__(
        self,
        result: EngineResult | None = None,
        *,
        available: bool = True,
        reason: str | None = None,
        cancel: bool = False,
        error: Exception | None = None,
        updates: tuple[ProgressUpdate, ...] = (),
    ) -> None:
        self.result = result or EngineResult(
            text="Bonjour",
            segments=(Segment(1, 0.5, 1.5, "Bonjour"),),
            language="fr",
            cost_usd=0.000123,
            duration_s=1.5,
        )
        self.available = available
        self.reason = reason
        self.cancel = cancel
        self.error = error
        self.updates = updates
        self.calls = 0

    def availability(self) -> EngineAvailability:
        return EngineAvailability(self.available, self.reason)

    def transcribe(self, request, *, on_progress=None, on_log=None, cancel):
        self.calls += 1
        for update in self.updates:
            if on_progress:
                on_progress(update)
        if self.cancel:
            cancel.cancel()
        if self.error:
            raise self.error
        return self.result


def _request(tmp_path: Path, **overrides: object) -> TranscribeRequest:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x")
    values = {
        "input_path": source,
        "provider": Provider.OPENROUTER,
        "model": "mistralai/voxtral-mini-transcribe-3-0",
        "api_key": "test-key",
    }
    values.update(overrides)
    return TranscribeRequest(**values)


def test_success_writes_outputs_and_reports_progress(tmp_path: Path) -> None:
    updates: list[ProgressUpdate] = []
    engine = FakeEngine(
        updates=(
            ProgressUpdate("extracting", detail="Extraction audio"),
            ProgressUpdate("transcribing", 1.5, 1.5, "Tranche 1/1"),
        )
    )
    result = TranscribeService({Provider.OPENROUTER: engine}).transcribe(
        _request(tmp_path), on_progress=updates.append
    )

    assert result.output_paths == (
        tmp_path / "source.srt",
        tmp_path / "source.txt",
    )
    assert result.cost_usd == 0.000123
    assert result.provider is Provider.OPENROUTER
    assert (tmp_path / "source.srt").read_text(encoding="utf-8") == (
        "1\n00:00:00,500 --> 00:00:01,500\nBonjour\n\n"
    )
    assert (tmp_path / "source.txt").read_text(encoding="utf-8") == (
        "Bonjour\n"
    )
    phases = [update.phase for update in updates]
    assert phases == [
        "validating",
        "extracting",
        "transcribing",
        "writing",
        "done",
    ]


def test_single_format_writes_only_requested_output(tmp_path: Path) -> None:
    result = TranscribeService({Provider.OPENROUTER: FakeEngine()}).transcribe(
        _request(tmp_path, formats=frozenset({OutputFormat.TXT}))
    )
    assert result.output_paths == (tmp_path / "source.txt",)
    assert not (tmp_path / "source.srt").exists()
    assert (tmp_path / "source.txt").read_text(encoding="utf-8") == (
        "Bonjour\n"
    )


def test_missing_input_is_invalid(tmp_path: Path) -> None:
    request = TranscribeRequest(
        input_path=tmp_path / "absent.mp3",
        provider=Provider.OPENROUTER,
        model="m",
        api_key="k",
    )
    with pytest.raises(InvalidRequestError) as error:
        TranscribeService({Provider.OPENROUTER: FakeEngine()}).transcribe(
            request
        )
    assert error.value.user_message == "Le fichier sélectionné n'existe plus."


def test_unreadable_input_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(service_module.os, "access", lambda *a, **k: False)
    with pytest.raises(InvalidRequestError) as error:
        TranscribeService({Provider.OPENROUTER: FakeEngine()}).transcribe(
            request
        )
    assert "permissions" in error.value.user_message


def test_missing_output_dir_is_invalid(tmp_path: Path) -> None:
    with pytest.raises(InvalidRequestError) as error:
        TranscribeService({Provider.OPENROUTER: FakeEngine()}).transcribe(
            _request(tmp_path, output_dir=tmp_path / "absent")
        )
    assert error.value.user_message == "Le dossier de sortie n'existe pas."


def test_empty_formats_is_invalid(tmp_path: Path) -> None:
    with pytest.raises(InvalidRequestError) as error:
        TranscribeService({Provider.OPENROUTER: FakeEngine()}).transcribe(
            _request(tmp_path, formats=frozenset())
        )
    assert error.value.user_message == (
        "Choisissez au moins un format de sortie."
    )


def test_missing_provider_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(EngineUnavailableError):
        TranscribeService({}).transcribe(_request(tmp_path))


def test_unavailable_engine_is_rejected(tmp_path: Path) -> None:
    engine = FakeEngine(available=False, reason="Whisper absent")
    with pytest.raises(EngineUnavailableError) as error:
        TranscribeService({Provider.OPENROUTER: engine}).transcribe(
            _request(tmp_path)
        )
    assert error.value.user_message == "Whisper absent"
    assert engine.calls == 0


def test_missing_api_key_is_rejected(tmp_path: Path) -> None:
    engine = FakeEngine()
    with pytest.raises(EngineUnavailableError) as error:
        TranscribeService({Provider.OPENROUTER: engine}).transcribe(
            _request(tmp_path, api_key=None)
        )
    assert error.value.user_message == KEY_MISSING_MESSAGE
    assert engine.calls == 0


def test_existing_output_requires_overwrite(tmp_path: Path) -> None:
    engine = FakeEngine()
    existing = tmp_path / "source.srt"
    existing.write_text("ancien", encoding="utf-8")
    with pytest.raises(OutputExistsError) as error:
        TranscribeService({Provider.OPENROUTER: engine}).transcribe(
            _request(tmp_path)
        )
    assert error.value.paths == (existing,)
    assert existing.read_text(encoding="utf-8") == "ancien"
    assert engine.calls == 0


def test_overwrite_replaces_existing_output(tmp_path: Path) -> None:
    existing = tmp_path / "source.txt"
    existing.write_text("ancien", encoding="utf-8")
    TranscribeService({Provider.OPENROUTER: FakeEngine()}).transcribe(
        _request(tmp_path, overwrite=True)
    )
    assert existing.read_text(encoding="utf-8") == "Bonjour\n"


def test_cancellation_after_engine_prevents_writing(tmp_path: Path) -> None:
    engine = FakeEngine(cancel=True)
    with pytest.raises(CancelledError):
        TranscribeService({Provider.OPENROUTER: engine}).transcribe(
            _request(tmp_path)
        )
    assert not (tmp_path / "source.srt").exists()
    assert not (tmp_path / "source.txt").exists()


def test_engine_error_leaves_no_output(tmp_path: Path) -> None:
    engine = FakeEngine(error=TranscribeError("échec moteur", detail="x"))
    with pytest.raises(TranscribeError):
        TranscribeService({Provider.OPENROUTER: engine}).transcribe(
            _request(tmp_path)
        )
    assert not (tmp_path / "source.srt").exists()
    assert not (tmp_path / "source.txt").exists()


def test_output_cannot_replace_input(tmp_path: Path) -> None:
    source = tmp_path / "source.srt"
    source.write_bytes(b"x")
    request = TranscribeRequest(
        input_path=source,
        provider=Provider.OPENROUTER,
        model="m",
        api_key="k",
        formats=frozenset({OutputFormat.SRT}),
    )
    with pytest.raises(InvalidRequestError) as error:
        TranscribeService({Provider.OPENROUTER: FakeEngine()}).transcribe(
            request
        )
    assert "source" in error.value.user_message


def test_partial_write_error_lists_written_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(path: Path, segments: object) -> None:
        raise OSError("disque plein")

    monkeypatch.setattr(service_module, "write_txt", boom)
    with pytest.raises(TranscribeError) as error:
        TranscribeService({Provider.OPENROUTER: FakeEngine()}).transcribe(
            _request(tmp_path)
        )
    assert "source.srt" in (error.value.detail or "")
    assert (tmp_path / "source.srt").exists()
    assert not (tmp_path / "source.txt").exists()
