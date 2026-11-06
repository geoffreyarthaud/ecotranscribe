from __future__ import annotations

from ecotranscribe.gui.widgets.key_form import KeyForm


def test_key_form_never_prefills_and_is_password(qtbot) -> None:
    form = KeyForm()
    qtbot.addWidget(form)
    assert form.key() == ""
    assert form.key_edit.echoMode().name == "Password"


def test_remember_is_enabled_by_default_and_can_be_disabled(qtbot) -> None:
    form = KeyForm()
    qtbot.addWidget(form)
    assert form.remember_key() is True
    form.set_keyring_available(False)
    assert form.remember_key() is False
    assert form.remember.isEnabled() is False


def test_dirty_tracks_field_and_remember(qtbot) -> None:
    form = KeyForm()
    qtbot.addWidget(form)
    assert form.is_dirty() is False
    form.key_edit.setText("sk-or-secret")
    assert form.is_dirty() is True
    form.mark_clean()
    assert form.is_dirty() is False


def test_status_and_error_are_visible(qtbot) -> None:
    form = KeyForm()
    qtbot.addWidget(form)
    form.set_status("Clé enregistrée dans le trousseau")
    form.set_error("Saisissez une clé OpenRouter.")
    assert "trousseau" in form.status_label.text()
    assert form.error_label.isVisibleTo(form)
    assert "Saisissez" in form.error_label.text()
