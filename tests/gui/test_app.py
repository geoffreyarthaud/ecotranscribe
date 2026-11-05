import json
from pathlib import Path

import pytest

from ecotranscribe.gui import app as app_module
from ecotranscribe.gui.app import main

DIAGNOSTIC = {
    "app_version": "0.2.0",
    "flavor": "lite",
    "commit": "abc",
    "build_date": "2026-11-05T12:00:00Z",
    "python": "3.13.3",
    "qt": "6.12.0",
    "platform": "darwin",
    "arch": "arm64",
    "frozen": False,
    "ffmpeg_path": "/bundle/bin/ffmpeg",
    "ffprobe_path": "/bundle/bin/ffprobe",
    "ffmpeg_version": "ffmpeg version 9.0.2",
    "ffprobe_version": "ffprobe version 9.0.2",
    "whisper_available": False,
    "whisper_reason": "non inclus dans l'édition lite",
    "openrouter_model": "mistralai/voxtral-mini-transcribe-3-0",
    "config_dir": "/tmp/config",
    "log_file": "/tmp/config/ecotranscribe.log",
}


def test_diagnose_writes_json_without_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "nested" / "diag.json"
    monkeypatch.setattr(app_module, "collect_diagnostic", lambda: DIAGNOSTIC)
    monkeypatch.setattr(app_module, "configure_logging", lambda: tmp_path)

    def no_window(*args, **kwargs):
        raise AssertionError("aucune fenêtre en mode diagnostic")

    monkeypatch.setattr(app_module, "MainWindow", no_window)
    result = main(["--diagnose", "--diagnose-output", str(output)])

    assert result == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["flavor"] == "lite"
    assert payload["whisper_available"] is False
    assert "app_version" in capsys.readouterr().out


def test_diagnose_returns_one_when_tools_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "diag.json"
    missing = dict(DIAGNOSTIC)
    missing["ffmpeg_path"] = None
    missing["ffprobe_path"] = None
    monkeypatch.setattr(app_module, "collect_diagnostic", lambda: missing)
    monkeypatch.setattr(app_module, "configure_logging", lambda: tmp_path)

    result = main(["--diagnose", "--diagnose-output", str(output)])

    assert result == 1
    assert output.exists()


def test_diagnose_writes_utf8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "diag.json"
    accent = dict(DIAGNOSTIC)
    accent["whisper_reason"] = "édition lite — accentué"
    monkeypatch.setattr(app_module, "collect_diagnostic", lambda: accent)
    monkeypatch.setattr(app_module, "configure_logging", lambda: tmp_path)
    main(["--diagnose", "--diagnose-output", str(output)])
    assert "accentué" in output.read_text(encoding="utf-8")


def test_parser_rejects_unknown_option() -> None:
    with pytest.raises(SystemExit):
        main(["--unknown"])
