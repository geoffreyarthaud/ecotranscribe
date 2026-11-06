"""Formulaire de clé partagé par l'écran Clé et la page Options."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

OPENROUTER_KEYS_URL = "https://openrouter.ai/keys"


class KeyForm(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dirty = False
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        label = QLabel("Nouvelle clé OpenRouter")
        label.setProperty("role", "label")
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("Collez votre clé OpenRouter")
        self.remember = QCheckBox("Mémoriser dans le trousseau")
        self.remember.setChecked(True)
        self.link = QPushButton("Où trouver ma clé ?")
        self.link.setProperty("variant", "tertiary")
        self.link.clicked.connect(self._open_keys_page)
        self.note = QLabel(
            "La clé n'est jamais écrite dans les réglages ni dans le journal."
        )
        self.note.setProperty("role", "mention")
        self.note.setWordWrap(True)
        self.error_label = QLabel("")
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)

        layout.addWidget(self.status_label)
        layout.addWidget(label)
        layout.addWidget(self.key_edit)
        layout.addWidget(self.remember)
        layout.addWidget(self.link)
        layout.addWidget(self.note)
        layout.addWidget(self.error_label)

        self.key_edit.textChanged.connect(self._on_changed)
        self.remember.toggled.connect(self._on_changed)

    def key(self) -> str:
        return self.key_edit.text().strip()

    def remember_key(self) -> bool:
        return self.remember.isEnabled() and self.remember.isChecked()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_keyring_available(self, available: bool) -> None:
        self._loading = True
        self.remember.setEnabled(available)
        if not available:
            self.remember.setChecked(False)
            self.remember.setToolTip(
                "Le trousseau système est indisponible ; la clé restera "
                "valable pour cette session."
            )
        else:
            self.remember.setToolTip("")
        self._loading = False

    def set_error(self, text: str) -> None:
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))

    def clear_field(self) -> None:
        self._loading = True
        self.key_edit.clear()
        self.error_label.clear()
        self.error_label.setVisible(False)
        self._loading = False

    def mark_clean(self) -> None:
        self._dirty = False

    def is_dirty(self) -> bool:
        return self._dirty

    def _open_keys_page(self) -> None:
        QDesktopServices.openUrl(QUrl(OPENROUTER_KEYS_URL))

    def _on_changed(self, *_args: object) -> None:
        if not self._loading:
            self._dirty = True
            self.changed.emit()
