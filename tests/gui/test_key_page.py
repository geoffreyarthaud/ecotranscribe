from __future__ import annotations

from ecotranscribe.gui.pages.key import KeyMode, KeyPage


def test_key_page_rejects_empty_key(qtbot) -> None:
    page = KeyPage()
    qtbot.addWidget(page)
    with qtbot.assertNotEmitted(page.submitted):
        page.next_button.click()
    assert page.key_form.error_label.isVisibleTo(page)
    assert "Saisissez" in page.key_form.error_label.text()


def test_key_page_submits_key_and_remember_state(qtbot) -> None:
    page = KeyPage()
    qtbot.addWidget(page)
    page.key_form.key_edit.setText("sk-or-secret")
    page.key_form.remember.setChecked(False)
    with qtbot.waitSignal(page.submitted) as blocker:
        page.next_button.click()
    assert blocker.args == ["sk-or-secret", False]


def test_key_page_correction_mode_changes_copy(qtbot) -> None:
    page = KeyPage()
    qtbot.addWidget(page)
    page.set_mode(KeyMode.CORRECTION)
    assert "refusée" in page.intro.text()
    assert page.back_button.text() == "Retour aux réglages"
    page.set_mode(KeyMode.INITIAL)
    assert page.back_button.text() == "Retour"


def test_key_page_back_signal(qtbot) -> None:
    page = KeyPage()
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.back_requested):
        page.back_button.click()


def test_keyring_unavailable_disables_remember(qtbot) -> None:
    page = KeyPage()
    qtbot.addWidget(page)
    page.set_keyring_available(False)
    assert page.key_form.remember.isEnabled() is False
