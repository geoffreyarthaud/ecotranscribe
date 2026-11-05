from pathlib import Path

import pytest

from ecotranscribe.core.models import Segment
from ecotranscribe.core.writers import (
    format_timestamp,
    render_srt,
    render_txt,
    write_atomic,
    write_srt,
    write_txt,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_srt_matches_cli_golden_bytes(tmp_path: Path) -> None:
    segments = (
        Segment(
            id=1,
            start=1.3,
            end=5.9,
            text="Bonjour, je m'appelle Geoffrey et je fais de l'accessibilité "
            "avec du RGAA.",
        ),
    )
    target = tmp_path / "sample.srt"
    write_srt(target, segments)
    assert target.read_bytes() == (FIXTURES / "sample.srt").read_bytes()


def test_txt_matches_cli_golden_bytes(tmp_path: Path) -> None:
    segments = (
        Segment(
            id=1,
            start=1.3,
            end=5.9,
            text="Bonjour, je m'appelle Geoffrey et je fais de l'accessibilité "
            "avec du RGAA.",
        ),
    )
    target = tmp_path / "sample.txt"
    write_txt(target, segments)
    assert target.read_bytes() == (FIXTURES / "sample.txt").read_bytes()


def test_txt_writes_one_line_per_segment() -> None:
    segments = (
        Segment(id=1, start=0.0, end=1.0, text="  Premier  "),
        Segment(id=2, start=1.0, end=2.0, text="Deuxième"),
    )
    assert render_txt(segments) == "Premier\nDeuxième\n"


def test_empty_txt_is_empty() -> None:
    assert render_txt(()) == ""


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0.0, "00:00:00,000"),
        (3661.234, "01:01:01,234"),
        (59.9999, "00:01:00,000"),
    ],
)
def test_srt_timestamp(seconds: float, expected: str) -> None:
    assert format_timestamp(seconds) == expected


def test_srt_escapes_arrow_and_strips_text() -> None:
    segments = (Segment(id=1, start=0, end=1, text="  a --> b  "),)
    assert render_srt(segments) == "1\n00:00:00,000 --> 00:00:01,000\na -> b\n\n"


def test_srt_is_lf_only(tmp_path: Path) -> None:
    target = tmp_path / "out.srt"
    write_srt(target, (Segment(1, 0, 1, "x"),))
    assert b"\r" not in target.read_bytes()


def test_atomic_write_keeps_original_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.txt"
    target.write_text("ancien", encoding="utf-8")

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("disque plein")

    monkeypatch.setattr("ecotranscribe.core.writers.os.replace", boom)
    with pytest.raises(OSError):
        write_atomic(target, "nouveau")
    assert target.read_text(encoding="utf-8") == "ancien"
    assert list(tmp_path.iterdir()) == [target]
