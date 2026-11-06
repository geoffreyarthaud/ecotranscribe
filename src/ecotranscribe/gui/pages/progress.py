"""Écran de progression, journal, annulation et erreurs inline."""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from ...core.errors import TranscribeError
from ...core.formatting import format_seconds
from ...core.models import ProgressUpdate
from ..widgets.alerts import Alert
from ..widgets.layout import WizardPage

logger = logging.getLogger("ecotranscribe")

_PHASE_LABELS = {
    "validating": "Validation",
    "extracting": "Extraction audio",
    "detecting_silences": "Détection des silences",
    "transcribing": "Transcription",
    "writing": "Écriture des fichiers",
    "done": "Terminé",
}


class ProgressPage(WizardPage):
    cancel_requested = Signal()
    back_to_settings_requested = Signal()
    home_requested = Signal()
    open_log_requested = Signal()
    open_folder_requested = Signal()
    edit_key_requested = Signal()
    change_file_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Transcription", parent)
        self.alert: Alert | None = None
        self._busy = False
        self._writing = False
        self._cancelling = False
        self._action_buttons: list[QPushButton] = []
        self._last_progress: ProgressUpdate | None = None
        self._task_started = 0.0

        self.file_label = QLabel("")
        self.file_label.setProperty("role", "sectionTitle")
        self.phase_label = QLabel("")
        self.phase_label.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setProperty("role", "transcription")
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.elapsed_label = QLabel("")
        self.elapsed_label.setProperty("role", "muted")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setProperty("role", "log")
        self.log.setMaximumBlockCount(5000)
        self.log.setMinimumHeight(180)
        self.log_button = QPushButton("Ouvrir le journal")
        self.log_button.setProperty("variant", "tertiary")

        self.content_layout.addWidget(self.file_label)
        self.content_layout.addWidget(self.phase_label)
        self.content_layout.addWidget(self.progress)
        self.content_layout.addWidget(self.elapsed_label)
        self.content_layout.addWidget(self.log, 1)
        self.content_layout.addWidget(self.log_button)

        self.cancel_button = QPushButton("Annuler la transcription")
        self.cancel_button.setProperty("variant", "danger")
        self.add_secondary(self.cancel_button)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.log_button.clicked.connect(self.open_log_requested)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_elapsed)

    def start_task(self, file_name: str) -> None:
        self.reset()
        self.file_label.setText(file_name)
        self.phase_label.setText("Validation…")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setVisible(True)
        self._task_started = time.monotonic()
        self._timer.start()
        self._busy = True
        self._writing = False
        self._cancelling = False

    def update_progress(self, update: ProgressUpdate) -> None:
        self._last_progress = update
        if update.phase == "writing":
            self.show_writing()
            return
        if update.phase == "done":
            self.progress.setRange(0, 1000)
            self.progress.setValue(1000)
            self.phase_label.setText("Terminé")
            self._update_elapsed()
            self._stop_timer()
            return
        label = _PHASE_LABELS.get(update.phase, update.phase)
        detail = update.detail.strip()
        if update.total is not None and update.total > 0:
            ratio = min(max(update.current, 0.0), update.total) / update.total
            percent = round(ratio * 1000)
            self.progress.setRange(0, 1000)
            self.progress.setValue(percent)
            audio = (
                f"{format_seconds(update.current)} / "
                f"{format_seconds(update.total)}"
            )
            parts = [label, audio, f"{percent // 10} %"]
            if detail and detail != label:
                parts.append(detail)
            self.phase_label.setText(" — ".join(parts))
        else:
            self.progress.setRange(0, 0)
            self.phase_label.setText(
                f"{label} — {detail}" if detail and detail != label else label
            )
        if self._cancelling:
            self.phase_label.setText("Annulation en cours…")
        self._update_elapsed()

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)
        logger.info("%s", text)

    def show_writing(self) -> None:
        self._writing = True
        self._busy = True
        self.progress.setRange(0, 0)
        self.phase_label.setText("Écriture des fichiers…")
        self.cancel_button.setEnabled(False)
        self._update_elapsed()

    def show_cancelling(self) -> None:
        self._cancelling = True
        self.phase_label.setText("Annulation en cours…")
        self.cancel_button.setEnabled(False)

    def show_error(
        self,
        error: TranscribeError,
        *,
        can_edit_key: bool,
        can_change_file: bool,
        can_open_folder: bool,
    ) -> None:
        self._stop_timer()
        self._busy = True
        self._writing = False
        self._cancelling = False
        self.cancel_button.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.phase_label.clear()
        self.elapsed_label.clear()
        text = error.user_message
        if error.hint:
            text += f"\n\n{error.hint}"
        alert = Alert("error", "La transcription a échoué.", text)
        alert.set_detail(error.detail)
        alert.add_action(
            self._action("Accueil", "tertiary", self.home_requested)
        )
        if can_change_file:
            alert.add_action(
                self._action(
                    "Changer de fichier",
                    "secondary",
                    self.change_file_requested,
                )
            )
        if can_edit_key:
            alert.add_action(
                self._action(
                    "Modifier la clé", "secondary", self.edit_key_requested
                )
            )
        if can_open_folder:
            alert.add_action(
                self._action(
                    "Ouvrir le dossier", "secondary", self.open_folder_requested
                )
            )
        alert.add_action(
            self._action(
                "Retour aux réglages",
                "primary",
                self.back_to_settings_requested,
            )
        )
        self._install_alert(alert)

    def show_cancelled(self) -> None:
        self._stop_timer()
        self._busy = True
        self._writing = False
        self._cancelling = False
        self.cancel_button.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.phase_label.clear()
        self.elapsed_label.clear()
        alert = Alert(
            "info",
            "Transcription annulée.",
            "Aucun fichier n'a été écrit.",
        )
        alert.add_action(
            self._action("Accueil", "tertiary", self.home_requested)
        )
        alert.add_action(
            self._action(
                "Retour aux réglages",
                "primary",
                self.back_to_settings_requested,
            )
        )
        self._install_alert(alert)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in self._action_buttons:
            button.setEnabled(not busy)
        if busy:
            self.cancel_button.setEnabled(
                not self._writing and not self._cancelling
            )
        else:
            self.cancel_button.setEnabled(False)
            if self.alert is not None and self._action_buttons:
                self._action_buttons[-1].setFocus()

    def reset(self) -> None:
        self._stop_timer()
        self._busy = False
        self._writing = False
        self._cancelling = False
        self._last_progress = None
        self.file_label.clear()
        self.phase_label.clear()
        self.elapsed_label.clear()
        self.log.clear()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(False)
        self._clear_alert()

    def focus_primary(self) -> None:
        self.cancel_button.setFocus()

    def _action(self, text: str, variant: str, signal) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("variant", variant)
        button.clicked.connect(signal)
        self._action_buttons.append(button)
        return button

    def _install_alert(self, alert: Alert) -> None:
        self._clear_alert()
        self.content_layout.insertWidget(1, alert)
        self.alert = alert
        self._action_buttons = list(alert.findChildren(QPushButton))

    def _clear_alert(self) -> None:
        if self.alert is not None:
            self.content_layout.removeWidget(self.alert)
            self.alert.deleteLater()
            self.alert = None
        self._action_buttons = []

    def _stop_timer(self) -> None:
        self._timer.stop()
        self._task_started = 0.0

    def _update_elapsed(self) -> None:
        if self._task_started <= 0:
            return
        elapsed = max(0.0, time.monotonic() - self._task_started)
        text = f"Temps écoulé : {format_seconds(elapsed)}"
        progress = self._last_progress
        if (
            progress is not None
            and progress.total is not None
            and progress.total > 0
            and progress.current > 0
        ):
            eta = elapsed * (progress.total - progress.current) / progress.current
            text += f" — ETA : {format_seconds(max(0.0, eta))}"
        self.elapsed_label.setText(text)
