from pathlib import Path

import pytest

from ecotranscribe import __version__
from ecotranscribe.gui import availability as availability_module
from ecotranscribe.gui.availability import (
    collect_diagnostic,
    openrouter_availability,
    whisper_availability,
)
from ecotranscribe.core.config import OPENROUTER_MODEL


def test_whisper_is_disabled_in_desktop() -> None:
    result = whisper_availability()
    assert result.available is False
    assert "EcoTranscribe Desktop" in (result.reason or "")


def test_openrouter_is_available() -> None:
    assert openrouter_availability().available is True


def test_diagnostic_contains_documented_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        availability_module, "resolve_tool", lambda name: f"/bundle/{name}"
    )
    monkeypatch.setattr(
        availability_module,
        "tool_version",
        lambda path: f"{Path(path).name} version 9.0.2",
    )
    monkeypatch.setattr(
        availability_module, "config_dir", lambda: tmp_path
    )
    monkeypatch.setattr(
        availability_module,
        "log_file_path",
        lambda: tmp_path / "ecotranscribe.log",
    )
    monkeypatch.setenv("ECOTRANSCRIBE_COMMIT", "abc123")
    monkeypatch.setenv("ECOTRANSCRIBE_BUILD_DATE", "2026-11-05T12:00:00Z")

    diagnostic = collect_diagnostic()

    assert diagnostic["app_version"] == __version__
    assert diagnostic["flavor"] == "desktop"
    assert diagnostic["commit"] == "abc123"
    assert diagnostic["build_date"] == "2026-11-05T12:00:00Z"
    assert diagnostic["ffmpeg_path"] == "/bundle/ffmpeg"
    assert diagnostic["ffprobe_path"] == "/bundle/ffprobe"
    assert diagnostic["ffmpeg_version"] == "ffmpeg version 9.0.2"
    assert diagnostic["whisper_available"] is False
    assert diagnostic["whisper_reason"]
    assert diagnostic["openrouter_model"] == OPENROUTER_MODEL
    assert diagnostic["config_dir"] == str(tmp_path)
    assert diagnostic["log_file"] == str(tmp_path / "ecotranscribe.log")
    for key in (
        "python",
        "qt",
        "platform",
        "arch",
        "frozen",
        "ffprobe_version",
    ):
        assert key in diagnostic


def test_diagnostic_survives_missing_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(availability_module, "resolve_tool", lambda name: None)
    monkeypatch.setattr(
        availability_module, "config_dir", lambda: tmp_path
    )
    monkeypatch.setattr(
        availability_module,
        "log_file_path",
        lambda: tmp_path / "ecotranscribe.log",
    )
    diagnostic = collect_diagnostic()
    assert diagnostic["ffmpeg_path"] is None
    assert diagnostic["ffprobe_path"] is None
    assert diagnostic["ffmpeg_version"] is None
