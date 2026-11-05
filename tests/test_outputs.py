from pathlib import Path

from ecotranscribe.core.models import OutputFormat
from ecotranscribe.core.outputs import existing_outputs, output_paths


def test_output_paths_order_and_alt_dir(tmp_path: Path) -> None:
    source = tmp_path / "source" / "réunion.mp3"
    source.parent.mkdir()
    source.write_bytes(b"x")
    out = tmp_path / "sortie"
    out.mkdir()
    paths = output_paths(
        source, out, frozenset({OutputFormat.TXT, OutputFormat.SRT})
    )
    assert paths == (out / "réunion.srt", out / "réunion.txt")


def test_output_paths_with_single_format(tmp_path: Path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"x")
    assert output_paths(source, tmp_path, frozenset({OutputFormat.TXT})) == (
        tmp_path / "clip.txt",
    )


def test_existing_outputs_only_existing(tmp_path: Path) -> None:
    a, b = tmp_path / "a.srt", tmp_path / "a.txt"
    a.write_text("x", encoding="utf-8")
    assert existing_outputs((a, b)) == (a,)
