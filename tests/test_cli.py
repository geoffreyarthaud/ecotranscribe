from pathlib import Path

import pytest

import ecotranscribe.cli as cli
from ecotranscribe.core.config import (
    OPENROUTER_MODEL,
    WHISPER_MODEL,
    WHISPER_NOT_INSTALLED_MESSAGE,
)
from ecotranscribe.core.formatting import format_seconds
from ecotranscribe.core.models import (
    EngineAvailability,
    OutputFormat,
    ProgressUpdate,
    Provider,
    Segment,
    TranscribeResult,
)


class FakeService:
    last_request = None
    result = TranscribeResult(
        output_paths=(),
        text="Bonjour",
        segments=(Segment(1, 0.0, 1.0, "Bonjour"),),
        language="fr",
        cost_usd=0.000123,
        provider=Provider.OPENROUTER,
        model=OPENROUTER_MODEL,
        duration_s=1.0,
    )

    def __init__(self, engines) -> None:
        self.engines = engines

    def transcribe(
        self, request, *, on_progress=None, on_log=None, cancel=None
    ):
        type(self).last_request = request
        if on_progress:
            on_progress(
                ProgressUpdate("transcribing", 1.0, 1.0, "Tranche 1/1")
            )
        if on_log:
            on_log("info", "ok")
        return self.result


class UnavailableEngine:
    provider = Provider.WHISPER

    def availability(self) -> EngineAvailability:
        return EngineAvailability(False, WHISPER_NOT_INSTALLED_MESSAGE)


def _source(tmp_path: Path, name: str = "source.mp3") -> Path:
    path = tmp_path / name
    path.write_bytes(b"x")
    return path


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0.0, "00:00"), (65.9, "01:05"), (3661.0, "1:01:01")],
)
def test_format_seconds(seconds: float, expected: str) -> None:
    assert format_seconds(seconds) == expected


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"])
    assert error.value.code == 0
    assert "ecotranscribe" in capsys.readouterr().out


def test_missing_input_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main([str(tmp_path / "absent.mp3")])
    assert error.value.code == 1
    assert "n'existe pas" in capsys.readouterr().err


def test_whisper_missing_extra_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "WhisperEngine", UnavailableEngine)
    with pytest.raises(SystemExit) as error:
        cli.main([str(_source(tmp_path))])
    assert error.value.code == 1
    assert "uv sync --extra whisper" in capsys.readouterr().err


def test_refused_overwrite_keeps_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source(tmp_path)
    existing = tmp_path / "source.srt"
    existing.write_text("ancien", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    def bomb(engines):
        raise AssertionError("le service ne doit pas être appelé")

    monkeypatch.setattr(cli, "TranscribeService", bomb)
    cli.main([str(source)])
    assert existing.read_text(encoding="utf-8") == "ancien"
    assert "conservés" in capsys.readouterr().out


def test_openrouter_request_and_cost_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source(tmp_path)
    prompt = tmp_path / "source.prompt.md"
    prompt.write_text("  RGAA  ", encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")
    monkeypatch.setattr(cli, "TranscribeService", FakeService)

    cli.main(["--provider", "openrouter", str(source)])

    request = FakeService.last_request
    assert request is not None
    assert request.provider is Provider.OPENROUTER
    assert request.model == OPENROUTER_MODEL
    assert request.prompt_text == "RGAA"
    assert request.api_key == "secret-key"
    assert request.overwrite is False
    assert request.formats == frozenset(
        {OutputFormat.SRT, OutputFormat.TXT}
    )
    out = capsys.readouterr().out
    assert "0.000123" in out
    assert "secret-key" not in out


def test_default_provider_is_whisper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "TranscribeService", FakeService)
    cli.main([str(_source(tmp_path))])
    request = FakeService.last_request
    assert request is not None
    assert request.provider is Provider.WHISPER
    assert request.model == WHISPER_MODEL
    assert request.api_key is None


def test_model_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "TranscribeService", FakeService)
    cli.main(["--model", "tiny", str(_source(tmp_path))])
    request = FakeService.last_request
    assert request is not None
    assert request.model == "tiny"


def test_confirmed_overwrite_sets_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    (tmp_path / "source.txt").write_text("ancien", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda prompt: "o")
    monkeypatch.setattr(cli, "TranscribeService", FakeService)
    cli.main([str(source)])
    request = FakeService.last_request
    assert request is not None
    assert request.overwrite is True


def test_missing_cost_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class NoCostService(FakeService):
        result = TranscribeResult(
            output_paths=(),
            text="x",
            segments=(),
            language="fr",
            cost_usd=None,
            provider=Provider.OPENROUTER,
            model=OPENROUTER_MODEL,
            duration_s=1.0,
        )

    monkeypatch.setattr(cli, "TranscribeService", NoCostService)
    cli.main(
        ["--provider", "openrouter", str(_source(tmp_path))]
    )
    assert "Coût indisponible" in capsys.readouterr().out
