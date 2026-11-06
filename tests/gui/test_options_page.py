from __future__ import annotations

from ecotranscribe.gui.pages.options import OptionsPage

ABOUT = {
    "version": "0.3.0",
    "commit": "abc123",
    "build_date": "2026-11-06T10:00:00Z",
    "license": "MIT",
    "source": "https://github.com/ecotranscribe/ecotranscribe",
}


def test_options_page_saves_key(qtbot) -> None:
    page = OptionsPage()
    qtbot.addWidget(page)
    page.load("Aucune clé active", True, ABOUT, False)
    page.key_form.key_edit.setText("sk-or-secret")
    with qtbot.waitSignal(page.save_key_requested) as blocker:
        page.save_button.click()
    assert blocker.args == ["sk-or-secret", True]


def test_options_page_rejects_empty_key(qtbot) -> None:
    page = OptionsPage()
    qtbot.addWidget(page)
    page.load("Aucune clé active", True, ABOUT, False)
    with qtbot.assertNotEmitted(page.save_key_requested):
        page.save_button.click()
    assert "Saisissez" in page.key_form.error_label.text()


def test_options_page_about_and_delete(qtbot) -> None:
    page = OptionsPage()
    qtbot.addWidget(page)
    page.load("Clé enregistrée dans le trousseau", True, ABOUT, True)
    assert "0.3.0" in page.about_label.text()
    assert "MIT" in page.about_label.text()
    with qtbot.waitSignal(page.delete_key_requested):
        page.delete_button.click()


def test_options_page_env_cannot_delete(qtbot) -> None:
    page = OptionsPage()
    qtbot.addWidget(page)
    page.load("Clé fournie par l'environnement", True, ABOUT, False)
    assert page.delete_button.isEnabled() is False


def test_options_page_dirty_state(qtbot) -> None:
    page = OptionsPage()
    qtbot.addWidget(page)
    page.load("Aucune clé active", True, ABOUT, False)
    assert page.is_dirty() is False
    page.key_form.key_edit.setText("sk")
    assert page.is_dirty() is True
    page.show_saved("Clé enregistrée.")
    assert page.is_dirty() is False
