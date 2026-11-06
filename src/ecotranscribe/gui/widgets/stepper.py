"""Indicateur d'étapes non cliquable, inspiré du composant DSFR."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..theme import repolish


class Stepper(QWidget):
    STEPS = ("Fichier", "Prompt", "Réglages", "Transcription")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current = 0
        self._numbers: list[QLabel] = []
        self._titles: list[QLabel] = []
        self._lines: list[QFrame] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for index, title in enumerate(self.STEPS):
            column = QVBoxLayout()
            number = QLabel(str(index + 1))
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label = QLabel(title)
            title_label.setProperty("role", "mention")
            self._numbers.append(number)
            self._titles.append(title_label)
            column.addWidget(number, 0, Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(title_label, 0, Qt.AlignmentFlag.AlignHCenter)
            layout.addLayout(column)
            if index < len(self.STEPS) - 1:
                line = QFrame()
                line.setFixedHeight(2)
                self._lines.append(line)
                layout.addWidget(line, 1)
        self.set_current(0)

    def set_current(self, index: int) -> None:
        self.current = max(0, min(index, len(self.STEPS) - 1))
        for position, number in enumerate(self._numbers):
            if position < self.current:
                state = "done"
            elif position == self.current:
                state = "current"
            else:
                state = "future"
            number.setProperty("stepNumber", state)
            self._titles[position].setProperty("stepTitle", state)
            repolish(number)
            repolish(self._titles[position])
        for position, line in enumerate(self._lines):
            line.setProperty("stepLine", "done" if position < self.current else "future")
            repolish(line)
        self.setAccessibleName(
            f"Étape {self.current + 1} sur {len(self.STEPS)} : "
            f"{self.STEPS[self.current]}"
        )
