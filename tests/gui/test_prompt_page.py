from __future__ import annotations

from pathlib import Path

from ecotranscribe.gui.pages.prompt import PromptPage


def test_prompt_page_shows_file_and_duration(qtbot) -> None:
    page = PromptPage()
    qtbot.addWidget(page)
    page.set_file(Path("/tmp/réunion.mp3"))
    page.set_duration(65, pending=False)
    assert "01:05" in page.duration_label.text()
    assert str(Path("/tmp/réunion.mp3")) in page.file_path.text()


def test_duration_pending_then_unavailable(qtbot) -> None:
    page = PromptPage()
    qtbot.addWidget(page)
    page.set_file(Path("/tmp/a.mp3"))
    page.set_duration(None, pending=True)
    assert "Analyse" in page.duration_label.text()
    page.set_duration(None, pending=False)
    assert "indisponible" in page.duration_label.text()


def test_prompt_is_directly_editable_and_clearable(qtbot) -> None:
    page = PromptPage()
    qtbot.addWidget(page)
    page.set_file(Path("/tmp/a.mp3"))
    page.set_prompt("Contexte initial", Path("/tmp/a.prompt.md"))
    assert "a.prompt.md" in page.prompt_source.text()
    assert page.prompt_text() == "Contexte initial"
    assert page.prompt_edited() is False
    page.prompt_edit.setPlainText("Nouveau contexte")
    assert page.prompt_edited() is True
    page.clear_button.click()
    assert page.prompt_text() is None


def test_prompt_page_signals(qtbot) -> None:
    page = PromptPage()
    qtbot.addWidget(page)
    page.set_file(Path("/tmp/a.mp3"))
    with qtbot.waitSignal(page.next_requested):
        page.next_button.click()
    with qtbot.waitSignal(page.change_file_requested):
        page.change_button.click()
    with qtbot.waitSignal(page.back_requested):
        page.back_button.click()
