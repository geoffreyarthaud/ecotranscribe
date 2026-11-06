from __future__ import annotations

from pathlib import Path

from ecotranscribe.core.errors import TranscribeError
from ecotranscribe.core.models import ProgressUpdate
from ecotranscribe.gui.pages.progress import ProgressPage


def test_determinate_progress_and_phase(qtbot) -> None:
    page = ProgressPage()
    qtbot.addWidget(page)
    page.start_task("a.mp3")
    page.update_progress(
        ProgressUpdate("transcribing", current=30.0, total=60.0, detail="Tranche 1/2")
    )
    assert page.progress.maximum() == 1000
    assert page.progress.value() == 500
    assert "50 %" in page.phase_label.text()
    assert "a.mp3" in page.file_label.text()


def test_writing_disables_cancel(qtbot) -> None:
    page = ProgressPage()
    qtbot.addWidget(page)
    page.start_task("a.mp3")
    page.show_writing()
    assert page.cancel_button.isEnabled() is False
    assert "Écriture" in page.phase_label.text()


def test_error_shows_hint_detail_and_actions(qtbot) -> None:
    page = ProgressPage()
    qtbot.addWidget(page)
    page.start_task("a.mp3")
    error = TranscribeError(
        "La transcription a échoué.",
        detail="Trace technique",
        hint="Vérifiez votre clé.",
    )
    page.show_error(
        error, can_edit_key=True, can_change_file=False, can_open_folder=False
    )
    assert page.alert is not None
    assert "Vérifiez votre clé" in page.alert.text_label.text()
    assert page.alert.detail_view.toPlainText() == "Trace technique"
    texts = [button.text() for button in page.alert.findChildren(type(page.cancel_button))]
    assert "Retour aux réglages" in texts
    assert "Modifier la clé" in texts


def test_cancel_is_neutral(qtbot) -> None:
    page = ProgressPage()
    qtbot.addWidget(page)
    page.start_task("a.mp3")
    page.show_cancelled()
    assert page.alert is not None
    assert "annulée" in page.alert.title_label.text()
    assert page.alert.property("severity") == "info"


def test_log_append_and_open_signal(qtbot) -> None:
    page = ProgressPage()
    qtbot.addWidget(page)
    page.append_log("ligne 1")
    assert "ligne 1" in page.log.toPlainText()
    with qtbot.waitSignal(page.open_log_requested):
        page.log_button.click()
