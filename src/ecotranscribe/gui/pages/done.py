"""Écran de confirmation de fin de transcription."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from ...core.models import TranscribeResult
from ..widgets.layout import WizardPage


class DonePage(WizardPage):
    open_folder_requested = Signal()
    new_transcription_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Transcription terminée", parent)
        self._folder: Path | None = None
        self.file_label = QLabel("")
        self.file_label.setProperty("role", "sectionTitle")
        self.outputs_label = QLabel("")
        self.outputs_label.setWordWrap(True)
        self.outputs_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.cost_label = QLabel("")
        self.cost_label.setProperty("role", "muted")
        self.content_layout.addWidget(self.file_label)
        self.content_layout.addWidget(self.outputs_label)
        self.content_layout.addWidget(self.cost_label)
        self.content_layout.addStretch(1)

        self.open_button = QPushButton("Ouvrir le dossier")
        self.open_button.setProperty("variant", "primary")
        self.new_button = QPushButton("Nouvelle transcription")
        self.new_button.setProperty("variant", "secondary")
        self.add_secondary(self.new_button)
        self.add_primary(self.open_button)
        self.open_button.clicked.connect(self.open_folder_requested)
        self.new_button.clicked.connect(self.new_transcription_requested)

    def show_result(self, result: TranscribeResult, file_name: str) -> None:
        self.file_label.setText(file_name)
        self.outputs_label.setText(
            "\n".join(str(path) for path in result.output_paths)
        )
        if result.cost_usd is None:
            cost = "Coût indisponible"
        else:
            cost = f"Coût : ${result.cost_usd:.6f}"
        self.cost_label.setText(cost)
        self._folder = (
            result.output_paths[0].parent if result.output_paths else None
        )
        self.open_button.setEnabled(
            self._folder is not None and self._folder.is_dir()
        )

    def reset(self) -> None:
        self.file_label.clear()
        self.outputs_label.clear()
        self.cost_label.clear()
        self._folder = None
        self.open_button.setEnabled(False)

    def focus_primary(self) -> None:
        self.open_button.setFocus()
