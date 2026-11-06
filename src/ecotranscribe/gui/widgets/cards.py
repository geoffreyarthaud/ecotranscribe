"""Cartes cliquables et cartes désactivées de l'accueil."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FileCard(QFrame):
    clicked = Signal()
    browse_requested = Signal()
    continue_requested = Signal()
    change_requested = Signal()

    def __init__(
        self,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setProperty("clickable", "true")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "sectionTitle")
        self.description_label = QLabel(description)
        self.description_label.setProperty("role", "muted")
        self.description_label.setWordWrap(True)
        self.path_label = QLabel("")
        self.path_label.setProperty("role", "mention")
        self.path_label.setWordWrap(True)
        self.browse_button = QPushButton("Choisir un fichier")
        self.browse_button.setProperty("variant", "primary")
        self.continue_button = QPushButton("Continuer")
        self.continue_button.setProperty("variant", "primary")
        self.change_button = QPushButton("Changer de fichier")
        self.change_button.setProperty("variant", "secondary")

        buttons = QHBoxLayout()
        buttons.addWidget(self.browse_button)
        buttons.addWidget(self.continue_button)
        buttons.addWidget(self.change_button)
        buttons.addStretch(1)

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(self.path_label)
        layout.addLayout(buttons)

        for label in (self.title_label, self.description_label, self.path_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.browse_button.clicked.connect(self.browse_requested)
        self.continue_button.clicked.connect(self.continue_requested)
        self.change_button.clicked.connect(self.change_requested)
        self.set_selected_file(None)

    def set_selected_file(self, path: Path | None) -> None:
        has_file = path is not None
        self.path_label.setText(str(path) if path is not None else "")
        self.path_label.setVisible(has_file)
        self.browse_button.setVisible(not has_file)
        self.continue_button.setVisible(has_file)
        self.change_button.setVisible(has_file)

    def set_description(self, text: str) -> None:
        self.description_label.setText(text)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class DisabledCard(QFrame):
    def __init__(
        self,
        title: str,
        badge: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)
        row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setProperty("role", "sectionTitle")
        badge_label = QLabel(badge)
        badge_label.setProperty("role", "badge")
        row.addWidget(title_label)
        row.addWidget(badge_label)
        row.addStretch(1)
        layout.addLayout(row)
