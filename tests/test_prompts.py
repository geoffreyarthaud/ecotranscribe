from pathlib import Path

import pytest

from ecotranscribe.core.errors import InvalidRequestError
from ecotranscribe.core.prompts import find_prompt_file, read_prompt, resolve_prompt


def test_finds_prompt_with_documented_priority(tmp_path: Path) -> None:
    source = tmp_path / "réunion.mp3"
    source.write_bytes(b"x")
    plain = tmp_path / "réunion.prompt"
    text = tmp_path / "réunion.prompt.txt"
    markdown = tmp_path / "réunion.prompt.md"
    for path in (plain, text, markdown):
        path.write_text(path.name, encoding="utf-8")

    assert find_prompt_file(source) == markdown


def test_falls_back_to_txt_then_plain(tmp_path: Path) -> None:
    source = tmp_path / "réunion.mp3"
    source.write_bytes(b"x")
    plain = tmp_path / "réunion.prompt"
    text = tmp_path / "réunion.prompt.txt"
    plain.write_text("plain", encoding="utf-8")
    text.write_text("txt", encoding="utf-8")

    assert find_prompt_file(source) == text
    text.unlink()
    assert find_prompt_file(source) == plain


def test_returns_none_without_prompt(tmp_path: Path) -> None:
    source = tmp_path / "réunion.mp3"
    source.write_bytes(b"x")
    assert find_prompt_file(source) is None
    assert resolve_prompt(source) == (None, None)


def test_reads_utf8_and_strips(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("  RGAA, DSFR, accessibilité  \n", encoding="utf-8")
    assert read_prompt(prompt) == "RGAA, DSFR, accessibilité"


def test_resolve_prompt_returns_path_and_text(tmp_path: Path) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x")
    prompt = tmp_path / "source.prompt.md"
    prompt.write_text("contexte", encoding="utf-8")
    assert resolve_prompt(source) == (prompt, "contexte")


def test_unreadable_prompt_raises_invalid_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("x", encoding="utf-8")

    def boom(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError("refusé")

    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(InvalidRequestError) as error:
        read_prompt(prompt)
    assert error.value.user_message == "Impossible de lire le fichier prompt."
