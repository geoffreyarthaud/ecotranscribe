"""Page Options : clé OpenRouter et à propos."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..widgets.key_form import KeyForm
from ..widgets.layout import Section, WizardPage


class OptionsPage(WizardPage):
    save_key_requested = Signal(str, bool)
    delete_key_requested = Signal()
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Options", parent)
        key_section = Section("Clé OpenRouter")
        self.key_form = KeyForm()
        self.save_button = QPushButton("Enregistrer la clé")
        self.save_button.setProperty("variant", "primary")
        self.delete_button = QPushButton("Supprimer la clé")
        self.delete_button.setProperty("variant", "danger")
        buttons = QHBoxLayout()
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        key_section.add(self.key_form)
        key_section.add_layout(buttons)

        self.feedback = QLabel("")
        self.feedback.setProperty("role", "success")
        self.feedback.setWordWrap(True)
        self.feedback.setVisible(False)

        about_section = Section("À propos")
        self.about_label = QLabel("")
        self.about_label.setWordWrap(True)
        self.about_label.setOpenExternalLinks(True)
        self.about_label.setTextFormat(Qt.TextFormat.RichText)
        about_section.add(self.about_label)

        self.content_layout.addWidget(key_section)
        self.content_layout.addWidget(self.feedback)
        self.content_layout.addWidget(about_section)
        self.content_layout.addStretch(1)

        self.back_button = QPushButton("Retour")
        self.back_button.setProperty("variant", "secondary")
        self.add_secondary(self.back_button)

        self.save_button.clicked.connect(self._save)
        self.delete_button.clicked.connect(self.delete_key_requested)
        self.back_button.clicked.connect(self.back_requested)
        self.key_form.changed.connect(self._on_changed)

    def load(
        self,
        status: str,
        keyring_available: bool,
        about: dict,
        can_delete: bool,
    ) -> None:
        self.key_form.set_status(status)
        self.key_form.set_keyring_available(keyring_available)
        self.set_can_delete(can_delete)
        self.about_label.setText(
            f"<b>EcoTranscribe Desktop {about['version']}</b><br>"
            f"Commit : {about['commit']}<br>"
            f"Build : {about['build_date']}<br>"
            f"Licence : {about['license']}<br>"
            f"Source : <a href=\"{about['source']}\">{about['source']}</a><br>"
            "Notices tierces : THIRD_PARTY_NOTICES.md, inclus dans "
            "l'application."
        )
        self.key_form.clear_field()
        self.key_form.mark_clean()
        self.feedback.clear()
        self.feedback.setVisible(False)

    def set_status(self, text: str) -> None:
        self.key_form.set_status(text)

    def set_keyring_available(self, available: bool) -> None:
        self.key_form.set_keyring_available(available)

    def set_can_delete(self, can_delete: bool) -> None:
        self.delete_button.setEnabled(can_delete)

    def show_saved(self, message: str) -> None:
        self.feedback.setText(message)
        self.feedback.setVisible(True)
        self.key_form.clear_field()
        self.key_form.mark_clean()

    def set_error(self, text: str) -> None:
        self.key_form.set_error(text)

    def is_dirty(self) -> bool:
        return self.key_form.is_dirty()

    def mark_clean(self) -> None:
        self.key_form.mark_clean()

    def clear_field(self) -> None:
        self.key_form.clear_field()

    def focus_primary(self) -> None:
        self.key_form.key_edit.setFocus()

    def _save(self) -> None:
        key = self.key_form.key()
        if not key:
            self.key_form.set_error("Saisissez une clé OpenRouter.")
            return
        self.key_form.set_error("")
        self.save_key_requested.emit(key, self.key_form.remember_key())

    def _on_changed(self) -> None:
        self.feedback.setVisible(False)
