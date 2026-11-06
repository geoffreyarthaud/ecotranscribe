"""Écran d'accueil : fichier, URL indisponible, options."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from ..widgets.cards import DisabledCard, FileCard
from ..widgets.layout import WizardPage


class HomePage(WizardPage):
    browse_requested = Signal()
    continue_requested = Signal()
    change_file_requested = Signal()
    options_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("EcoTranscribe Desktop", parent)
        self.title_label.setVisible(False)
        self.action_bar.setVisible(False)
        self._has_file = False
        subtitle = QLabel("Transcrire un fichier audio ou vidéo")
        subtitle.setProperty("role", "muted")
        self.file_card = FileCard(
            "Transcrire un fichier",
            "Formats audio et vidéo : MP3, WAV, M4A, MP4, MOV… "
            "Glissez-déposez un fichier ou cliquez pour le choisir.",
        )
        self.url_card = DisabledCard(
            "Transcrire une URL", "Bientôt disponible"
        )
        self.key_note = QLabel(
            "Une clé OpenRouter est requise pour transcrire."
        )
        self.key_note.setProperty("role", "mention")
        self.key_note.setWordWrap(True)
        self.key_note_button = QPushButton("Configurer la clé")
        self.key_note_button.setProperty("variant", "tertiary")
        self.error_label = QLabel("")
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)

        self.content_layout.addWidget(subtitle)
        self.content_layout.addWidget(self.file_card)
        self.content_layout.addWidget(self.url_card)
        self.content_layout.addWidget(self.key_note)
        self.content_layout.addWidget(self.key_note_button)
        self.content_layout.addWidget(self.error_label)
        self.content_layout.addStretch(1)

        self.file_card.clicked.connect(self._on_card_clicked)
        self.file_card.continue_requested.connect(self.continue_requested)
        self.file_card.change_requested.connect(self.change_file_requested)
        self.key_note_button.clicked.connect(self.options_requested)

    def _on_card_clicked(self) -> None:
        if self._has_file:
            self.continue_requested.emit()
        else:
            self.browse_requested.emit()

    def set_selected_file(self, path: Path | None) -> None:
        self._has_file = path is not None
        self.file_card.set_selected_file(path)
        self.file_card.set_description(
            "Fichier sélectionné. Continuez ou changez de fichier."
            if path is not None
            else "Formats audio et vidéo : MP3, WAV, M4A, MP4, MOV… "
            "Glissez-déposez un fichier ou cliquez pour le choisir."
        )

    def set_has_key(self, has_key: bool) -> None:
        self.key_note.setVisible(not has_key)
        self.key_note_button.setVisible(not has_key)

    def set_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def focus_primary(self) -> None:
        if self._has_file:
            self.file_card.continue_button.setFocus()
        else:
            self.file_card.setFocus()
