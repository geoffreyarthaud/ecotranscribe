from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ecotranscribe.core.errors import CancelledError
from ecotranscribe.core.models import (
    CancelToken,
    OutputFormat,
    Segment,
    TranscribeRequest,
)


def test_request_defaults_output_dir_to_parent(tmp_path: Path) -> None:
    source = tmp_path / "réunion.mp3"
    source.write_bytes(b"x")
    request = TranscribeRequest(
        input_path=source, provider="openrouter", model="m"
    )
    assert request.output_dir == tmp_path
    assert request.formats == frozenset({OutputFormat.SRT, OutputFormat.TXT})
    assert request.language == "fr"
    assert request.overwrite is False
    assert request.api_key is None


def test_request_normalizes_empty_prompt_to_none(tmp_path: Path) -> None:
    source = tmp_path / "a.mp3"
    source.write_bytes(b"x")
    request = TranscribeRequest(
        input_path=source, provider="whisper", model="tiny", prompt_text="  "
    )
    assert request.prompt_text is None


def test_cancel_token_is_idempotent() -> None:
    token = CancelToken()
    assert not token.is_cancelled()
    token.cancel()
    token.cancel()
    assert token.is_cancelled()
    with pytest.raises(CancelledError):
        token.raise_if_cancelled()


def test_segment_is_frozen() -> None:
    segment = Segment(id=1, start=0.0, end=1.0, text="Bonjour")
    with pytest.raises(FrozenInstanceError):
        segment.text = "Autre"  # type: ignore[misc]
