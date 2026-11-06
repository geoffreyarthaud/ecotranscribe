"""Dialogues injectables de confirmation, isolés du worker et du cœur."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from PySide6.QtWidgets import QMessageBox, QWidget


class DialogService(Protocol):
    def confirm_overwrite(self, paths: Sequence[Path]) -> bool: ...

    def confirm_close_while_running(self) -> bool: ...

    def confirm_delete_key(self) -> bool: ...

    def confirm_discard(self, message: str) -> bool: ...


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
        overwrite = box.addButton("Écraser", QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)  # type: ignore[arg-type]
        box.exec()
        return box.clickedButton() is overwrite

    def confirm_close_while_running(self) -> bool:
        answer = QMessageBox.question(
            self._parent,
            "Transcription en cours",
            "Une transcription est en cours. L'annuler et quitter ? "
            "L'arrêt peut attendre la fin de la requête en cours.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def confirm_delete_key(self) -> bool:
        answer = QMessageBox.question(
            self._parent,
            "Supprimer la clé",
            "Supprimer la clé OpenRouter mémorisée ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def confirm_discard(self, message: str) -> bool:
        answer = QMessageBox.question(
            self._parent,
            "Abandonner les modifications",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
