"""Page et section communes aux écrans de l'assistant."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class WizardPage(QWidget):
    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        *,
        show_title: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setAccessibleName(title)
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 20, 32, 20)
        root.setSpacing(16)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "pageTitle")
        self.title_label.setVisible(show_title)
        root.addWidget(self.title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        scroll.setWidget(self.content)
        root.addWidget(scroll, 1)

        self.action_bar = QWidget()
        actions = QHBoxLayout(self.action_bar)
        actions.setContentsMargins(0, 0, 0, 0)
        self._left = QHBoxLayout()
        self._right = QHBoxLayout()
        actions.addLayout(self._left)
        actions.addStretch(1)
        actions.addLayout(self._right)
        root.addWidget(self.action_bar)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def add_secondary(self, button: QPushButton) -> None:
        self._left.addWidget(button)

    def add_primary(self, button: QPushButton) -> None:
        self._right.addWidget(button)

    def focus_primary(self) -> None:
        for layout in (self._right, self._left):
            for index in range(layout.count()):
                widget = layout.itemAt(index).widget()
                if isinstance(widget, QPushButton) and widget.isEnabled():
                    widget.setFocus()
                    return


class Section(QFrame):
    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        *,
        spacing: int = 12,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 16, 24, 16)
        self._layout.setSpacing(spacing)
        if title:
            label = QLabel(title)
            label.setProperty("role", "sectionTitle")
            self._layout.addWidget(label)

    def add(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout: QLayout) -> None:
        self._layout.addLayout(layout)
