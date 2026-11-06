from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from ecotranscribe.gui.widgets.cards import DisabledCard, FileCard


def test_file_card_shows_selected_file(qtbot) -> None:
    card = FileCard("Transcrire un fichier", "MP3, WAV, MP4")
    qtbot.addWidget(card)
    card.set_selected_file(Path("/tmp/réunion.mp3"))
    assert "réunion.mp3" in card.path_label.text()
    assert card.continue_button.isVisibleTo(card)
    assert card.change_button.isVisibleTo(card)


def test_file_card_clears_selection(qtbot) -> None:
    card = FileCard("Transcrire un fichier", "MP3, WAV, MP4")
    qtbot.addWidget(card)
    card.set_selected_file(Path("/tmp/a.mp3"))
    card.set_selected_file(None)
    assert card.path_label.text() == ""
    assert card.browse_button.isVisibleTo(card)
    assert card.continue_button.isHidden()


def test_disabled_card_is_not_focusable(qtbot) -> None:
    card = DisabledCard("Transcrire une URL", "Bientôt disponible")
    qtbot.addWidget(card)
    assert card.focusPolicy() == Qt.FocusPolicy.NoFocus
