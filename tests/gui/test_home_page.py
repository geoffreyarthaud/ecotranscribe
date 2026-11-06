from __future__ import annotations

from pathlib import Path

from ecotranscribe.gui.pages.home import HomePage


def test_home_page_emits_file_requests(qtbot) -> None:
    page = HomePage()
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.browse_requested):
        page.file_card.browse_button.click()
    page.set_selected_file(Path("/tmp/a.mp3"))
    with qtbot.waitSignal(page.continue_requested):
        page.file_card.continue_button.click()
    with qtbot.waitSignal(page.change_file_requested):
        page.file_card.change_button.click()


def test_home_page_card_click_depends_on_selection(qtbot) -> None:
    page = HomePage()
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.browse_requested):
        page.file_card.clicked.emit()
    page.set_selected_file(Path("/tmp/a.mp3"))
    with qtbot.waitSignal(page.continue_requested):
        page.file_card.clicked.emit()


def test_key_note_and_options(qtbot) -> None:
    page = HomePage()
    qtbot.addWidget(page)
    page.set_has_key(False)
    assert page.key_note.isVisibleTo(page)
    assert page.key_note_button.isVisibleTo(page)
    page.set_has_key(True)
    assert page.key_note.isHidden()
    with qtbot.waitSignal(page.options_requested):
        page.options_button.click()
    with qtbot.waitSignal(page.options_requested):
        page.key_note_button.click()


def test_home_error_is_inline(qtbot) -> None:
    page = HomePage()
    qtbot.addWidget(page)
    page.set_error("Le fichier est absent.")
    assert page.error_label.isVisibleTo(page)
    assert "absent" in page.error_label.text()
    page.set_error("")
    assert page.error_label.isHidden()
