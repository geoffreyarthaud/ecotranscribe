"""Écran des réglages de génération."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ...core.config import OPENROUTER_MODEL, OPENROUTER_MODELS
from ...core.models import OutputFormat
from ...core.pricing import format_video_cost
from ..state import WizardState
from ..widgets.layout import Section, WizardPage

_LANGUAGES = (
    ("Français", "fr"),
    ("Auto", None),
    ("Anglais", "en"),
    ("Espagnol", "es"),
    ("Allemand", "de"),
    ("Italien", "it"),
    ("Portugais", "pt"),
    ("Néerlandais", "nl"),
)


class SettingsPage(WizardPage):
    launch_requested = Signal()
    back_requested = Signal()
    browse_output_requested = Signal()
    use_source_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Réglages", parent, show_title=False)
        self._user_set = False
        self._prices: dict[str, float] = {}
        self._duration_s: float | None = None

        generation = Section("Modèle et langue")
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_label = QLabel("Modèle")
        self.model_label.setProperty("role", "label")
        self.model_label.setBuddy(self.model_combo)
        self.language_combo = QComboBox()
        for label, code in _LANGUAGES:
            self.language_combo.addItem(label, code)
        self.language_label = QLabel("Langue")
        self.language_label.setProperty("role", "label")
        self.language_label.setBuddy(self.language_combo)
        self.model_error = self._error_label()
        generation.add(self.model_label)
        generation.add(self.model_combo)
        generation.add(self.model_error)
        generation.add(self.language_label)
        generation.add(self.language_combo)

        output = Section("Sortie")
        formats = QHBoxLayout()
        self.srt = QCheckBox("SRT")
        self.txt = QCheckBox("TXT")
        self.srt.setChecked(True)
        self.txt.setChecked(True)
        formats.addWidget(self.srt)
        formats.addWidget(self.txt)
        formats.addStretch(1)
        self.output_label = QLabel("Dossier de sortie")
        self.output_label.setProperty("role", "label")
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Dossier de sortie (défaut : dossier de la source)"
        )
        self.output_label.setBuddy(self.output_edit)
        self.output_browse = QPushButton("Parcourir…")
        self.output_browse.setProperty("variant", "secondary")
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_browse)
        self.use_source = QPushButton("Utiliser le dossier de la source")
        self.use_source.setProperty("variant", "tertiary")
        self.use_source.setVisible(False)
        self.formats_error = self._error_label()
        self.output_error = self._error_label()
        output.add(self.output_label)
        output.add_layout(output_row)
        output.add(self.use_source)
        output.add_layout(formats)
        output.add(self.formats_error)
        output.add(self.output_error)

        self.privacy = QLabel(
            "L'audio est envoyé à OpenRouter pour transcription. "
            "Le prompt l'est si le modèle le prend en charge."
        )
        self.privacy.setProperty("role", "mention")
        self.privacy.setWordWrap(True)
        self.message = QLabel("")
        self.message.setProperty("role", "muted")
        self.message.setWordWrap(True)
        self.message.setVisible(False)

        self.content_layout.addWidget(generation)
        self.content_layout.addWidget(output)
        self.content_layout.addWidget(self.privacy)
        self.content_layout.addWidget(self.message)
        self.content_layout.addStretch(1)

        self.launch_button = QPushButton("Lancer la transcription")
        self.launch_button.setProperty("variant", "primary")
        self.back_button = QPushButton("Retour")
        self.back_button.setProperty("variant", "secondary")
        self.add_secondary(self.back_button)
        self.add_primary(self.launch_button)

        self.launch_button.clicked.connect(self.launch_requested)
        self.back_button.clicked.connect(self.back_requested)
        self.output_browse.clicked.connect(self.browse_output_requested)
        self.use_source.clicked.connect(self.use_source_requested)
        self.output_edit.textEdited.connect(self._on_output_edited)
        self.srt.toggled.connect(self._clear_format_error)
        self.txt.toggled.connect(self._clear_format_error)

    def _error_label(self) -> QLabel:
        label = QLabel("")
        label.setProperty("role", "error")
        label.setWordWrap(True)
        label.setVisible(False)
        return label

    def load(self, state: WizardState) -> None:
        self.clear_errors()
        self.message.setVisible(False)
        self.use_source.setVisible(False)
        for model in OPENROUTER_MODELS:
            self._add_model(model)
        self._add_model(state.model)
        index = self._model_index(state.model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        elif self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)
        self.set_duration(state.duration_s)
        language_index = self.language_combo.findData(state.language)
        if language_index < 0:
            language_index = 0
        self.language_combo.setCurrentIndex(language_index)
        self.srt.setChecked(OutputFormat.SRT in state.formats)
        self.txt.setChecked(OutputFormat.TXT in state.formats)
        self._user_set = state.output_dir_user_set
        if state.output_dir_user_set and state.output_dir is not None:
            self.output_edit.setText(str(state.output_dir))
        elif state.input_path is not None:
            self.output_edit.setText(str(state.input_path.parent))
        elif state.output_dir is not None:
            self.output_edit.setText(str(state.output_dir))
        else:
            self.output_edit.clear()

    def commit(self, state: WizardState) -> bool:
        self.clear_errors()
        self.message.setVisible(False)
        valid = True
        model = self._current_model()
        if not model:
            self._set_error(self.model_error, "Choisissez un modèle.")
            valid = False
        formats = self._selected_formats()
        if not formats:
            self._set_error(
                self.formats_error,
                "Choisissez au moins un format de sortie.",
            )
            valid = False
        output_text = self.output_edit.text().strip()
        if output_text:
            output_dir: Path | None = Path(output_text).expanduser()
        elif state.input_path is not None:
            output_dir = state.input_path.parent
        else:
            output_dir = None
        if output_dir is None:
            self._set_error(
                self.output_error,
                "Choisissez un dossier de sortie.",
            )
            self.use_source.setVisible(False)
            valid = False
        elif not output_dir.exists():
            self._set_error(
                self.output_error,
                "Le dossier de sortie n'existe pas.",
            )
            self.use_source.setVisible(state.input_path is not None)
            valid = False
        elif not output_dir.is_dir():
            self._set_error(
                self.output_error,
                "Le dossier de sortie n'est pas un dossier.",
            )
            self.use_source.setVisible(False)
            valid = False
        elif not os.access(output_dir, os.W_OK | os.X_OK):
            self._set_error(
                self.output_error,
                "Le dossier de sortie n'est pas inscriptible.",
            )
            self.use_source.setVisible(False)
            valid = False
        if not valid:
            return False
        self.capture(state)
        return True

    def capture(self, state: WizardState) -> None:
        state.model = self._current_model() or state.model
        state.language = self.language_combo.currentData()
        formats = self._selected_formats()
        if formats:
            state.formats = formats
        output_text = self.output_edit.text().strip()
        if output_text:
            state.output_dir = Path(output_text).expanduser()
            state.output_dir_user_set = self._user_set
        elif state.input_path is not None:
            state.output_dir = state.input_path.parent
            state.output_dir_user_set = False
        else:
            state.output_dir = None
            state.output_dir_user_set = False

    def set_price(self, model: str, price: float) -> None:
        self._prices[model] = price
        self._refresh_model_costs()

    def set_duration(self, seconds: float | None) -> None:
        self._duration_s = (
            float(seconds) if seconds is not None and seconds > 0 else None
        )
        self._refresh_model_costs()

    def _refresh_model_costs(self) -> None:
        for index in range(self.model_combo.count()):
            model = self.model_combo.itemData(index)
            if not isinstance(model, str) or not model:
                continue
            price = self._prices.get(model)
            if price is None or self._duration_s is None:
                self.model_combo.setItemText(index, model)
            else:
                self.model_combo.setItemText(
                    index,
                    f"{model} ({format_video_cost(price, self._duration_s)})",
                )

    def set_output_dir(self, path: Path, *, user_set: bool = True) -> None:
        self._user_set = user_set
        self.output_edit.setText(str(path))
        self._set_error(self.output_error, "")
        self.use_source.setVisible(False)

    def show_message(self, text: str) -> None:
        self.message.setText(text)
        self.message.setVisible(bool(text))

    def clear_errors(self) -> None:
        for label in (self.model_error, self.formats_error, self.output_error):
            label.clear()
            label.setVisible(False)

    def focus_primary(self) -> None:
        self.model_combo.setFocus()

    def add_model(self, model: str) -> None:
        self._add_model(model)

    def _add_model(self, model: str) -> None:
        model = (model or "").strip()
        if model and self._model_index(model) < 0:
            self.model_combo.addItem(model, model)

    def _model_index(self, model: str) -> int:
        wanted = (model or "").strip()
        for index in range(self.model_combo.count()):
            if self.model_combo.itemData(index) == wanted:
                return index
        return -1

    def _current_model(self) -> str:
        data = self.model_combo.currentData()
        return data if isinstance(data, str) else ""

    def _selected_formats(self) -> frozenset[OutputFormat]:
        formats = set()
        if self.srt.isChecked():
            formats.add(OutputFormat.SRT)
        if self.txt.isChecked():
            formats.add(OutputFormat.TXT)
        return frozenset(formats)

    def _on_output_edited(self) -> None:
        self._user_set = True
        self.use_source.setVisible(False)
        self._set_error(self.output_error, "")

    def _clear_format_error(self) -> None:
        self._set_error(self.formats_error, "")

    @staticmethod
    def _set_error(label: QLabel, message: str) -> None:
        label.setText(message)
        label.setVisible(bool(message))
