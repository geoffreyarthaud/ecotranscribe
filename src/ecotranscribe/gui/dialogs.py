"""Dialogues injectables, isolés du worker et du cœur."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from PySide6.QtWidgets import QMessageBox, QWidget


class DialogService(Protocol):
    def confirm_overwrite(self, paths: Sequence[Path]) -> bool: ...

    def show_error(
        self, title: str, message: str, detail: str
    ) -> None: ...

    def show_info(self, title: str, message: str) -> None: ...

    def confirm_close_while_running(self) -> bool: ...


class QtDialogService:
    """Implémentation de production, toujours exécutée sur le thread UI."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._parent = parent

    def confirm_overwrite(self, paths: Sequence[Path]) -> bool:
        if not paths:
            return True
        box = QMessageBox(self._parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Fichiers existants")
        box.setText("Ces fichiers existent déjà :")
        box.setInformativeText("\n".join(str(path) for path in paths))
        overwrite = box.addButton(
            "Écraser", QMessageBox.ButtonRole.AcceptRole
        )
        cancel = box.addButton(
            "Annuler", QMessageBox.ButtonRole.RejectRole
        )
        box.setDefaultButton(cancel)  # type: ignore[arg-type]
        box.exec()
        return box.clickedButton() is overwrite

    def show_error(self, title: str, message: str, detail: str) -> None:
        box = QMessageBox(self._parent)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.setDetailedText(detail)
        box.exec()

    def show_info(self, title: str, message: str) -> None:
        box = QMessageBox(self._parent)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()

    def confirm_close_while_running(self) -> bool:
        answer = QMessageBox.question(
            self._parent,
            "Transcription en cours",
            "Une transcription est en cours. L'annuler et quitter ?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
