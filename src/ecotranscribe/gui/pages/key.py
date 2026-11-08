"""Porte conditionnelle de la clé OpenRouter."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from ..widgets.key_form import KeyForm
from ..widgets.layout import WizardPage

_INITIAL_COPY = (
    "EcoTranscribe utilise OpenRouter pour transcrire. "
    "Saisissez votre clé API pour continuer."
)
_CORRECTION_COPY = (
    "La clé a été refusée. Saisissez une nouvelle clé, puis relancez "
    "la transcription depuis les réglages."
)


class KeyMode(str, Enum):
    INITIAL = "initial"
    CORRECTION = "correction"


class KeyPage(WizardPage):
    submitted = Signal(str, bool)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Clé OpenRouter", parent, show_title=False)
        self.intro = QLabel(_INITIAL_COPY)
        self.intro.setWordWrap(True)
        self.key_form = KeyForm()
        self.content_layout.addWidget(self.intro)
        self.content_layout.addWidget(self.key_form)
        self.content_layout.addStretch(1)
        self.next_button = QPushButton("Suivant")
        self.next_button.setProperty("variant", "primary")
        self.back_button = QPushButton("Retour")
        self.back_button.setProperty("variant", "secondary")
        self.add_secondary(self.back_button)
        self.add_primary(self.next_button)
        self.next_button.clicked.connect(self._submit)
        self.back_button.clicked.connect(self.back_requested)
        self.key_form.set_status("Aucune clé active")

    def _submit(self) -> None:
        key = self.key_form.key()
        if not key:
            self.key_form.set_error("Saisissez une clé OpenRouter.")
            return
        self.key_form.set_error("")
        self.submitted.emit(key, self.key_form.remember_key())

    def set_mode(self, mode: KeyMode) -> None:
        if mode is KeyMode.CORRECTION:
            self.intro.setText(_CORRECTION_COPY)
            self.key_form.set_status("Clé refusée")
            self.back_button.setText("Retour aux réglages")
        else:
            self.intro.setText(_INITIAL_COPY)
            self.key_form.set_status("Aucune clé active")
            self.back_button.setText("Retour")

    def set_keyring_available(self, available: bool) -> None:
        self.key_form.set_keyring_available(available)

    def set_status(self, text: str) -> None:
        self.key_form.set_status(text)

    def set_error(self, text: str) -> None:
        self.key_form.set_error(text)

    def clear_field(self) -> None:
        self.key_form.clear_field()

    def focus_primary(self) -> None:
        self.key_form.key_edit.setFocus()
