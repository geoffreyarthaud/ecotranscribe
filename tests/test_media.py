import sys
import threading
import time
from pathlib import Path

import pytest

from ecotranscribe.core import media
from ecotranscribe.core.errors import CancelledError, MediaToolMissingError, TranscribeError
from ecotranscribe.core.models import CancelToken

posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="outils factices POSIX"
)


def _write_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


@posix_only
def test_env_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _write_tool(tmp_path / "ffmpeg", "exit 0\n")
    monkeypatch.setenv("ECOTRANSCRIBE_FFMPEG_DIR", str(tmp_path))
    monkeypatch.setattr(media.shutil, "which", lambda name: "/bin/" + name)
    assert media.resolve_tool("ffmpeg") == str(tool)


@posix_only
def test_bundle_wins_over_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = tmp_path / "bundle" / "bin"
    bundle.mkdir(parents=True)
    tool = _write_tool(bundle / "ffprobe", "exit 0\n")
    monkeypatch.delenv("ECOTRANSCRIBE_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(media.sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setattr(media.shutil, "which", lambda name: "/bin/" + name)
    assert media.resolve_tool("ffprobe") == str(tool)


def test_path_is_last_resort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ECOTRANSCRIBE_FFMPEG_DIR", raising=False)
    monkeypatch.delattr(media.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(media.shutil, "which", lambda name: "/usr/bin/" + name)
    expected = "/usr/bin/ffmpeg.exe" if sys.platform == "win32" else "/usr/bin/ffmpeg"
    assert media.resolve_tool("ffmpeg") == expected


def test_missing_tool_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ECOTRANSCRIBE_FFMPEG_DIR", raising=False)
    monkeypatch.delattr(media.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    with pytest.raises(MediaToolMissingError):
        media.get_media_duration(tmp_path / "x.wav")


def test_run_media_decodes_utf8() -> None:
    result = media.run_media(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write("
            "'accentué — ok'.encode('utf-8'))",
        ],
        timeout=10,
    )
    assert result.returncode == 0
    assert "accentué" in result.stdout


def test_cancel_terminates_process() -> None:
    token = CancelToken()
    timer = threading.Timer(0.3, token.cancel)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(CancelledError):
            media.run_media(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cancel=token,
            )
    finally:
        timer.join()
    assert time.monotonic() - started < 4.0


def test_timeout_raises_transcribe_error() -> None:
    with pytest.raises(TranscribeError):
        media.run_media(
            [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.3
        )


def test_windows_creation_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media.sys, "platform", "win32")
    assert media.creation_flags() == media.CREATE_NO_WINDOW


@posix_only
def test_get_media_duration_parses_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _write_tool(
        tmp_path / "ffprobe",
        "echo '{\"format\": {\"duration\": \"12.5\"}}'\n",
    )
    monkeypatch.setenv("ECOTRANSCRIBE_FFMPEG_DIR", str(tmp_path))
    assert media.get_media_duration(tmp_path / "x.wav") == 12.5
    assert tool.exists()


@posix_only
def test_detect_silences_parses_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_tool(
        tmp_path / "ffmpeg",
        "echo 'silence_start: 1.5' >&2\n"
        "echo 'silence_end: 2.5 | silence_duration: 1.0' >&2\n",
    )
    monkeypatch.setenv("ECOTRANSCRIBE_FFMPEG_DIR", str(tmp_path))
    assert media.detect_silences(tmp_path / "x.wav") == [(1.5, 2.5)]


@posix_only
def test_extract_audio_failure_reports_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_tool(tmp_path / "ffmpeg", "echo 'boom' >&2\nexit 1\n")
    monkeypatch.setenv("ECOTRANSCRIBE_FFMPEG_DIR", str(tmp_path))
    with pytest.raises(TranscribeError) as error:
        media.extract_audio(tmp_path / "in.mp4", tmp_path / "out.wav")
    assert "boom" in (error.value.detail or "")


@posix_only
def test_tool_version_reads_first_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _write_tool(
        tmp_path / "ffmpeg", "echo 'ffmpeg version 9.0.2'\necho 'more'\n"
    )
    assert media.tool_version(str(tool)) == "ffmpeg version 9.0.2"


def test_is_video_detects_extension(tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")
    assert media.is_video_file(path)
