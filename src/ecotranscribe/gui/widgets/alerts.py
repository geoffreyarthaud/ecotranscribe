"""Encart d'alerte inline, inspiré des alertes DSFR sans en reprendre le code."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class Alert(QFrame):
    def __init__(
        self,
        severity: str,
        title: str,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "alert")
        self.setProperty("severity", severity)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "alertTitle")
        self.title_label.setWordWrap(True)
        self.text_label = QLabel(text)
        self.text_label.setProperty("role", "alertText")
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.detail_button = QToolButton()
        self.detail_button.setText("Détails techniques")
        self.detail_button.setProperty("variant", "tertiary")
        self.detail_button.setCheckable(True)
        self.detail_button.setVisible(False)
        self.detail_view = QPlainTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setVisible(False)
        self.detail_view.setMaximumHeight(180)
        self._actions = QHBoxLayout()
        self._actions.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.detail_button)
        layout.addWidget(self.detail_view)
        layout.addLayout(self._actions)
        self.detail_button.toggled.connect(self.detail_view.setVisible)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def set_text(self, text: str) -> None:
        self.text_label.setText(text)

    def set_severity(self, severity: str) -> None:
        self.setProperty("severity", severity)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_detail(self, text: str | None) -> None:
        has_detail = bool(text and text.strip())
        self.detail_button.setVisible(has_detail)
        self.detail_view.setPlainText(text or "")
        self.detail_view.setVisible(has_detail and self.detail_button.isChecked())

    def add_action(self, button: QPushButton, *, primary: bool = False) -> None:
        if primary:
            self._actions.addStretch(1)
            self._actions.addWidget(button)
        else:
            self._actions.addWidget(button)
