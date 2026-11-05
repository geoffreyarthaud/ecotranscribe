"""Writers SRT/TXT internes, compatibles octet pour octet avec le CLI."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .models import Segment


def format_timestamp(seconds: float) -> str:
    """Formate un timestamp SRT `HH:MM:SS,mmm` (arrondi au milliseconde)."""
    milliseconds = round(max(0.0, seconds) * 1000.0)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1_000)
    return (
        f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},"
        f"{milliseconds:03d}"
    )


def render_srt(segments: Sequence[Segment]) -> str:
    """Rend le contenu SRT complet, terminé par une ligne vide."""
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        text = segment.text.strip().replace("-->", "->")
        blocks.append(
            f"{index}\n"
            f"{format_timestamp(segment.start)} --> "
            f"{format_timestamp(segment.end)}\n"
            f"{text}\n"
        )
    return "\n".join(blocks) + ("\n" if blocks else "")


def render_txt(segments: Sequence[Segment]) -> str:
    """Rend une ligne par segment, comme le writer TXT du CLI historique."""
    return "".join(f"{segment.text.strip()}\n" for segment in segments)


def write_atomic(path: Path, content: str) -> None:
    """Écrit `content` en UTF-8/LF via un temporaire puis `os.replace`."""
    path = Path(path)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def write_srt(path: Path, segments: Sequence[Segment]) -> None:
    write_atomic(path, render_srt(segments))


def write_txt(path: Path, segments: Sequence[Segment]) -> None:
    write_atomic(path, render_txt(segments))
