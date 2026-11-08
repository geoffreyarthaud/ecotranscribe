"""Écran de résumé du fichier et de saisie du prompt."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from ...core.formatting import format_seconds
from ..widgets.layout import Section, WizardPage


class PromptPage(WizardPage):
    next_requested = Signal()
    back_requested = Signal()
    change_file_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Fichier et prompt", parent, show_title=False)
        self._has_file = False
        self._edited = False
        self._loading = False

        file_section = Section("Fichier", spacing=10)
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setProperty("role", "path")
        self.duration_label = QLabel("")
        self.duration_label.setProperty("role", "muted")
        self.change_button = QPushButton("Changer de fichier")
        self.change_button.setProperty("variant", "tertiary")
        file_section.add(self.file_path)
        file_section.add(self.duration_label)
        file_section.add(self.change_button)

        prompt_section = Section("Prompt (optionnel)", spacing=10)
        self.prompt_source = QLabel("")
        self.prompt_source.setProperty("role", "muted")
        self.prompt_source.setWordWrap(True)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setFixedHeight(170)
        self.prompt_edit.setPlaceholderText(
            "Ex. : Réunion d'équipe. Intervenants : Camille, Nour. "
            "Vocabulaire : EcoTranscribe, SRT, OpenRouter."
        )
        self.prompt_help = QLabel(
            "Contexte, noms propres, vocabulaire, style. "
            "Le prompt est optionnel."
        )
        self.prompt_help.setProperty("role", "muted")
        self.prompt_help.setWordWrap(True)
        self.prompt_note = QLabel(
            "Les modifications ne sont pas enregistrées dans le fichier."
        )
        self.prompt_note.setProperty("role", "mention")
        self.prompt_note.setWordWrap(True)
        self.clear_button = QPushButton("Effacer le prompt")
        self.clear_button.setProperty("variant", "tertiary")
        prompt_section.add(self.prompt_source)
        prompt_section.add(self.prompt_edit)
        prompt_section.add(self.prompt_help)
        prompt_section.add(self.prompt_note)
        prompt_section.add(self.clear_button)

        self.error_label = QLabel("")
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)

        self.content_layout.addWidget(file_section)
        self.content_layout.addWidget(prompt_section)
        self.content_layout.addWidget(self.error_label)
        self.content_layout.addStretch(1)

        self.next_button = QPushButton("Suivant")
        self.next_button.setProperty("variant", "primary")
        self.next_button.setEnabled(False)
        self.back_button = QPushButton("Retour")
        self.back_button.setProperty("variant", "secondary")
        self.add_secondary(self.back_button)
        self.add_primary(self.next_button)

        self.next_button.clicked.connect(self.next_requested)
        self.back_button.clicked.connect(self.back_requested)
        self.change_button.clicked.connect(self.change_file_requested)
        self.clear_button.clicked.connect(self._clear)
        self.prompt_edit.textChanged.connect(self._on_text_changed)

    def set_file(self, path: Path) -> None:
        self._has_file = True
        self.file_path.setText(str(path))
        self.next_button.setEnabled(True)
        self.set_error("")

    def set_duration(self, value: float | None, *, pending: bool) -> None:
        if pending:
            text = "Durée : Analyse…"
        elif value is None:
            text = "Durée indisponible"
        else:
            text = f"Durée : {format_seconds(value)}"
        self.duration_label.setText(text)

    def set_prompt(
        self,
        text: str | None,
        source: Path | None,
        error: str | None = None,
        *,
        edited: bool = False,
    ) -> None:
        self._loading = True
        self.prompt_edit.setPlainText(text or "")
        self._loading = False
        self._edited = edited
        if error:
            self.prompt_source.setText(f"Prompt illisible : {error}")
        elif source is not None:
            self.prompt_source.setText(f"Détecté depuis {source}")
        else:
            self.prompt_source.setText("Aucun fichier prompt détecté")

    def prompt_text(self) -> str | None:
        text = self.prompt_edit.toPlainText().strip()
        return text or None

    def prompt_edited(self) -> bool:
        return self._edited

    def set_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def _on_text_changed(self) -> None:
        if not self._loading:
            self._edited = True

    def _clear(self) -> None:
        self._loading = True
        self.prompt_edit.clear()
        self._loading = False
        self._edited = True

    def focus_primary(self) -> None:
        self.prompt_edit.setFocus()
