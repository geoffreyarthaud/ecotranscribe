"""Fenêtre principale EcoTranscribe Desktop (édition lite)."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, QUrl, Qt
from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.config import (
    AUDIO_EXTENSIONS,
    KEY_MISSING_MESSAGE,
    OPENROUTER_MODEL,
    PROJECT_URL,
    VIDEO_EXTENSIONS,
    WHISPER_LITE_REASON,
)
from ..core.engines.openrouter import OpenRouterEngine
from ..core.errors import InvalidRequestError, TranscribeError
from ..core.formatting import format_seconds
from ..core.models import (
    CancelToken,
    OutputFormat,
    ProgressUpdate,
    Provider,
    TranscribeRequest,
    TranscribeResult,
)
from ..core.outputs import existing_outputs, output_paths
from ..core.prompts import resolve_prompt
from ..core.service import TranscribeService
from .availability import build_info, whisper_availability
from .dialogs import DialogService
from .settings import AppSettings, KeyStore
from .worker import TranscribeWorker

logger = logging.getLogger("ecotranscribe")

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

_PHASE_LABELS = {
    "validating": "Validation",
    "extracting": "Extraction audio",
    "detecting_silences": "Détection des silences",
    "transcribing": "Transcription",
    "writing": "Écriture des fichiers",
    "done": "Terminé",
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        settings: AppSettings,
        key_store: KeyStore,
        dialogs: DialogService,
        service_factory: Callable[[TranscribeRequest], TranscribeService]
        | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._key_store = key_store
        self._dialogs = dialogs
        self._service_factory = service_factory or self._default_service

        self._input_path: Path | None = None
        self._prompt_path: Path | None = None
        self._prompt_text: str | None = None
        self._output_dir_user_set = False
        self._output_folder: Path | None = None

        self._cancel_token: CancelToken | None = None
        self._worker: TranscribeWorker | None = None
        self._thread: QThread | None = None
        self._running = False
        self._writing = False
        self._close_when_done = False
        self._task_started = 0.0
        self._last_progress: ProgressUpdate | None = None

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed)

        self._build_ui()
        self._connect_signals()
        self._restore_settings()
        self._update_state()

    # ── Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("EcoTranscribe Desktop")
        self.setMinimumSize(760, 640)
        self.resize(900, 820)
        self.setAcceptDrops(True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        self.setCentralWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # En-tête
        header = QHBoxLayout()
        title = QLabel("EcoTranscribe Desktop")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        badge = QLabel("Édition lite — OpenRouter")
        badge.setStyleSheet(
            "background: #ccfbf1; color: #134e4a; border-radius: 6px; "
            "padding: 4px 8px;"
        )
        self.about_button = QPushButton("À propos")
        header.addWidget(title)
        header.addWidget(badge)
        header.addStretch(1)
        header.addWidget(self.about_button)
        layout.addLayout(header)

        # Source
        source_group = QGroupBox("Source")
        source_layout = QVBoxLayout(source_group)
        source_row = QHBoxLayout()
        source_label = QLabel("Fichier :")
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(
            "Chemin du fichier audio ou vidéo"
        )
        source_label.setBuddy(self.input_edit)
        self.browse_button = QPushButton("Parcourir…")
        source_row.addWidget(source_label)
        source_row.addWidget(self.input_edit, 1)
        source_row.addWidget(self.browse_button)
        self.drop_hint = QLabel(
            "Glissez-déposez un fichier audio ou vidéo dans la fenêtre"
        )
        self.drop_hint.setStyleSheet("color: #6b7280; font-style: italic;")
        self.source_error = self._new_error_label()
        source_layout.addLayout(source_row)
        source_layout.addWidget(self.drop_hint)
        source_layout.addWidget(self.source_error)
        layout.addWidget(source_group)

        # Fournisseur
        provider_group = QGroupBox("Fournisseur")
        provider_layout = QVBoxLayout(provider_group)
        provider_row = QHBoxLayout()
        self.provider_openrouter = QRadioButton("OpenRouter (cloud)")
        self.provider_openrouter.setChecked(True)
        self.provider_whisper = QRadioButton("Whisper local")
        self.provider_whisper.setEnabled(False)
        provider_row.addWidget(self.provider_openrouter)
        provider_row.addWidget(self.provider_whisper)
        provider_row.addStretch(1)
        self.whisper_reason = QLabel(
            f"{WHISPER_LITE_REASON} "
            f"<a href=\"{PROJECT_URL}\">Édition full</a>"
        )
        self.whisper_reason.setOpenExternalLinks(True)
        self.cloud_warning = QLabel(
            "L'audio est envoyé à OpenRouter ; le prompt l'est si le "
            "modèle le supporte."
        )
        self.cloud_warning.setWordWrap(True)
        self.cloud_warning.setStyleSheet("color: #92400e;")
        provider_layout.addLayout(provider_row)
        provider_layout.addWidget(self.whisper_reason)
        provider_layout.addWidget(self.cloud_warning)
        layout.addWidget(provider_group)

        # Réglages
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_combo.addItem(OPENROUTER_MODEL)
        model_label = QLabel("Modèle :")
        model_label.setBuddy(self.model_combo)
        form.addRow(model_label, self.model_combo)
        self.model_error = self._new_error_label()
        form.addRow("", self.model_error)

        self.language_combo = QComboBox()
        for label, code in _LANGUAGES:
            self.language_combo.addItem(label, code)
        language_label = QLabel("Langue :")
        language_label.setBuddy(self.language_combo)
        form.addRow(language_label, self.language_combo)

        prompt_widget = QWidget()
        prompt_layout = QVBoxLayout(prompt_widget)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_buttons = QHBoxLayout()
        self.prompt_path_label = QLabel("Aucun prompt détecté")
        self.prompt_path_label.setWordWrap(True)
        self.edit_prompt_button = QPushButton("Éditer…")
        self.clear_prompt_button = QPushButton("Effacer")
        prompt_buttons.addWidget(self.prompt_path_label, 1)
        prompt_buttons.addWidget(self.edit_prompt_button)
        prompt_buttons.addWidget(self.clear_prompt_button)
        self.prompt_preview = QLabel("")
        self.prompt_preview.setWordWrap(True)
        self.prompt_preview.setStyleSheet("color: #4b5563;")
        self.prompt_error = self._new_error_label()
        prompt_layout.addLayout(prompt_buttons)
        prompt_layout.addWidget(self.prompt_preview)
        prompt_layout.addWidget(self.prompt_error)
        prompt_label = QLabel("Prompt :")
        prompt_label.setBuddy(self.edit_prompt_button)
        form.addRow(prompt_label, prompt_widget)

        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Dossier de sortie (défaut : dossier de la source)"
        )
        self.output_browse_button = QPushButton("Parcourir…")
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_browse_button)
        formats_row = QHBoxLayout()
        self.srt_checkbox = QCheckBox("SRT")
        self.txt_checkbox = QCheckBox("TXT")
        self.srt_checkbox.setChecked(True)
        self.txt_checkbox.setChecked(True)
        formats_row.addWidget(self.srt_checkbox)
        formats_row.addWidget(self.txt_checkbox)
        formats_row.addStretch(1)
        self.output_error = self._new_error_label()
        self.formats_error = self._new_error_label()
        output_layout.addLayout(output_row)
        output_layout.addLayout(formats_row)
        output_layout.addWidget(self.output_error)
        output_layout.addWidget(self.formats_error)
        output_label = QLabel("Sortie :")
        output_label.setBuddy(self.output_edit)
        form.addRow(output_label, output_widget)

        key_widget = QWidget()
        key_layout = QVBoxLayout(key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_row = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("OPENROUTER_API_KEY")
        self.remember_checkbox = QCheckBox("Mémoriser")
        self.remember_checkbox.setChecked(True)
        self.delete_key_button = QPushButton("Supprimer")
        key_row.addWidget(self.api_key_edit, 1)
        key_row.addWidget(self.remember_checkbox)
        key_row.addWidget(self.delete_key_button)
        self.api_error = self._new_error_label()
        key_layout.addLayout(key_row)
        key_layout.addWidget(self.api_error)
        key_label = QLabel("Clé API :")
        key_label.setBuddy(self.api_key_edit)
        form.addRow(key_label, key_widget)

        layout.addLayout(form)

        # Actions et progression
        action_group = QGroupBox("Transcription")
        action_layout = QVBoxLayout(action_group)
        action_row = QHBoxLayout()
        self.launch_button = QPushButton("Lancer")
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setEnabled(False)
        action_row.addWidget(self.launch_button)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)
        action_layout.addLayout(action_row)

        self.phase_label = QLabel("Choisissez un fichier")
        self.phase_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(True)
        self.elapsed_label = QLabel("")
        self.elapsed_label.setStyleSheet("color: #4b5563;")
        self.log_toggle = QToolButton()
        self.log_toggle.setText("Journal")
        self.log_toggle.setCheckable(True)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setMinimumHeight(120)
        self.log_view.setVisible(False)
        action_layout.addWidget(self.phase_label)
        action_layout.addWidget(self.progress_bar)
        action_layout.addWidget(self.elapsed_label)
        action_layout.addWidget(self.log_toggle)
        action_layout.addWidget(self.log_view)
        layout.addWidget(action_group)

        # Résultat
        result_group = QGroupBox("Résultat")
        result_layout = QVBoxLayout(result_group)
        self.status_label = QLabel("Choisissez un fichier")
        self.result_paths_label = QLabel("")
        self.result_paths_label.setWordWrap(True)
        self.result_paths_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.cost_label = QLabel("")
        self.open_folder_button = QPushButton("Ouvrir le dossier")
        self.open_folder_button.setEnabled(False)
        result_layout.addWidget(self.status_label)
        result_layout.addWidget(self.result_paths_label)
        result_layout.addWidget(self.cost_label)
        result_layout.addWidget(self.open_folder_button)
        layout.addWidget(result_group)
        layout.addStretch(1)

        self._editable_widgets = [
            self.input_edit,
            self.browse_button,
            self.provider_openrouter,
            self.model_combo,
            self.language_combo,
            self.edit_prompt_button,
            self.clear_prompt_button,
            self.output_edit,
            self.output_browse_button,
            self.srt_checkbox,
            self.txt_checkbox,
            self.api_key_edit,
            self.remember_checkbox,
            self.delete_key_button,
        ]

    def _new_error_label(self) -> QLabel:
        label = QLabel("")
        label.setWordWrap(True)
        label.setStyleSheet("color: #b91c1c;")
        label.setVisible(False)
        return label

    def _connect_signals(self) -> None:
        self.browse_button.clicked.connect(self._browse_file)
        self.input_edit.returnPressed.connect(self._on_input_edited)
        self.output_browse_button.clicked.connect(self._browse_output)
        self.output_edit.textEdited.connect(self._on_output_edited)
        self.edit_prompt_button.clicked.connect(self._edit_prompt)
        self.clear_prompt_button.clicked.connect(self._clear_prompt)
        self.srt_checkbox.toggled.connect(self._on_format_changed)
        self.txt_checkbox.toggled.connect(self._on_format_changed)
        self.delete_key_button.clicked.connect(self._delete_key)
        self.launch_button.clicked.connect(self.start_transcription)
        self.cancel_button.clicked.connect(self.cancel_transcription)
        self.log_toggle.toggled.connect(self._on_log_toggle)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        self.about_button.clicked.connect(self.show_about)

        self._shortcuts = [
            self._make_shortcut(QKeySequence.StandardKey.Open, self._browse_file),
            self._make_shortcut(
                QKeySequence("Ctrl+Return"), self.start_transcription
            ),
            self._make_shortcut(
                QKeySequence("Ctrl+Enter"), self.start_transcription
            ),
            self._make_shortcut(
                QKeySequence(Qt.Key.Key_Escape), self._on_escape
            ),
        ]

    def _make_shortcut(
        self, sequence: QKeySequence | QKeySequence.StandardKey, callback
    ) -> QShortcut:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(callback)
        return shortcut

    def _restore_settings(self) -> None:
        geometry = self._settings.geometry
        if geometry:
            self.restoreGeometry(geometry)

        for model in self._settings.recent_models:
            if self.model_combo.findText(model) < 0:
                self.model_combo.addItem(model)
        self.model_combo.setCurrentText(self._settings.model)

        language = self._settings.language
        data = None if language in ("", "auto") else language
        index = self.language_combo.findData(data)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        formats = self._settings.formats
        self.srt_checkbox.setChecked("srt" in formats)
        self.txt_checkbox.setChecked("txt" in formats)

        if self._settings.output_dir:
            self.output_edit.setText(self._settings.output_dir)
            self._output_dir_user_set = True

        self.remember_checkbox.setChecked(self._settings.remember_api_key)
        self.log_toggle.setChecked(self._settings.log_visible)

        try:
            key = self._key_store.get()
        except Exception as exc:
            logger.warning("Lecture du trousseau impossible : %s", exc)
            key = os.environ.get("OPENROUTER_API_KEY")
        if key:
            self.api_key_edit.setText(key)

    # ── État et validation ─────────────────────────────────────────────────

    def _update_state(self) -> None:
        busy = self._running or self._thread is not None
        for widget in self._editable_widgets:
            widget.setEnabled(not busy)
        self.whisper_reason.setEnabled(True)
        self.launch_button.setEnabled(
            self._input_path is not None and not busy
        )
        self.cancel_button.setEnabled(self._running and not self._writing)

    def _clear_errors(self) -> None:
        for label in (
            self.source_error,
            self.model_error,
            self.prompt_error,
            self.output_error,
            self.formats_error,
            self.api_error,
        ):
            label.clear()
            label.setVisible(False)

    @staticmethod
    def _set_error(label: QLabel, message: str) -> None:
        label.setText(message)
        label.setVisible(bool(message))

    def _resolve_api_key(self) -> str | None:
        key = self.api_key_edit.text().strip()
        if key:
            return key
        try:
            key = self._key_store.get()
        except Exception as exc:
            logger.warning("Lecture du trousseau impossible : %s", exc)
            key = os.environ.get("OPENROUTER_API_KEY")
        return (key or "").strip() or None

    def _validate_form(self):
        self._clear_errors()
        valid = True

        if self._input_path is None:
            self._set_error(
                self.source_error, "Choisissez un fichier audio ou vidéo."
            )
            valid = False
        elif not self._input_path.exists():
            self._set_error(
                self.source_error,
                "Le fichier sélectionné n'existe plus.",
            )
            valid = False
        elif not self._input_path.is_file():
            self._set_error(
                self.source_error,
                "Le fichier sélectionné n'est pas un fichier valide.",
            )
            valid = False
        elif not os.access(self._input_path, os.R_OK):
            self._set_error(
                self.source_error,
                "Impossible de lire ce fichier. Vérifiez les permissions.",
            )
            valid = False

        output_text = self.output_edit.text().strip()
        output_dir = (
            Path(output_text).expanduser()
            if output_text
            else (
                self._input_path.parent
                if self._input_path is not None
                else Path.cwd()
            )
        )
        if not output_dir.exists():
            self._set_error(
                self.output_error, "Le dossier de sortie n'existe pas."
            )
            valid = False
        elif not output_dir.is_dir():
            self._set_error(
                self.output_error,
                "Le dossier de sortie n'est pas un dossier.",
            )
            valid = False
        elif not os.access(output_dir, os.W_OK | os.X_OK):
            self._set_error(
                self.output_error,
                "Le dossier de sortie n'est pas inscriptible.",
            )
            valid = False

        formats = self._selected_formats()
        if not formats:
            self._set_error(
                self.formats_error,
                "Choisissez au moins un format de sortie.",
            )
            valid = False

        model = self.model_combo.currentText().strip()
        if not model:
            self._set_error(self.model_error, "Choisissez un modèle.")
            valid = False

        api_key = self._resolve_api_key()
        if not api_key:
            self._set_error(self.api_error, KEY_MISSING_MESSAGE)
            valid = False

        if not valid or self._input_path is None:
            return None
        return self._input_path, output_dir, formats, model, api_key

    def _selected_formats(self) -> frozenset[OutputFormat]:
        formats = set()
        if self.srt_checkbox.isChecked():
            formats.add(OutputFormat.SRT)
        if self.txt_checkbox.isChecked():
            formats.add(OutputFormat.TXT)
        return frozenset(formats)

    # ── Sélection de fichiers ──────────────────────────────────────────────

    def _media_filter(self) -> str:
        extensions = sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS)
        patterns = " ".join(f"*{extension}" for extension in extensions)
        return f"Médias ({patterns});;Tous les fichiers (*)"

    def _browse_file(self) -> None:
        start_dir = self._settings.last_input_dir or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un fichier", start_dir, self._media_filter()
        )
        if path:
            self.set_input_path(Path(path))
            self._settings.last_input_dir = str(Path(path).parent)
            self._settings.save()

    def _on_input_edited(self) -> None:
        text = self.input_edit.text().strip()
        if text:
            self.set_input_path(Path(text))
        else:
            self._input_path = None
            self._clear_result()
            self._update_state()

    def set_input_path(self, path: Path) -> None:
        path = Path(path).expanduser()
        self._clear_errors()
        if not path.exists():
            self._set_error(
                self.source_error, "Le fichier sélectionné n'existe plus."
            )
            self._input_path = None
            self._update_state()
            return
        if not path.is_file():
            self._set_error(
                self.source_error,
                "Le fichier sélectionné n'est pas un fichier valide.",
            )
            self._input_path = None
            self._update_state()
            return
        if not os.access(path, os.R_OK):
            self._set_error(
                self.source_error,
                "Impossible de lire ce fichier. Vérifiez les permissions.",
            )
            self._input_path = None
            self._update_state()
            return

        self._input_path = path
        self.input_edit.setText(str(path))
        if not self._output_dir_user_set or not self.output_edit.text().strip():
            self.output_edit.setText(str(path.parent))
        self._load_prompt(path)
        self._clear_result()
        self._update_state()

    def _load_prompt(self, path: Path) -> None:
        self._prompt_path = None
        self._prompt_text = None
        try:
            prompt_path, prompt_text = resolve_prompt(path)
        except InvalidRequestError as exc:
            self.prompt_path_label.setText("Prompt illisible")
            self.prompt_preview.setText("")
            self._set_error(self.prompt_error, exc.user_message)
            return
        if prompt_path is None:
            self.prompt_path_label.setText("Aucun prompt détecté")
            self.prompt_preview.setText("")
            return
        self._prompt_path = prompt_path
        self._prompt_text = prompt_text
        self.prompt_path_label.setText(str(prompt_path))
        self.prompt_preview.setText(self._preview(prompt_text or ""))

    @staticmethod
    def _preview(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        preview = " / ".join(lines[:2])
        if len(lines) > 2 or len(preview) > 180:
            preview = preview[:180] + "…"
        return preview

    def _edit_prompt(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Modifier le prompt")
        dialog.resize(620, 380)
        layout = QVBoxLayout(dialog)
        editor = QPlainTextEdit()
        editor.setPlainText(self._prompt_text or "")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._prompt_text = editor.toPlainText().strip() or None
            self.prompt_preview.setText(
                self._preview(self._prompt_text or "")
            )

    def _clear_prompt(self) -> None:
        self._prompt_path = None
        self._prompt_text = None
        self.prompt_path_label.setText("Aucun prompt")
        self.prompt_preview.setText("")

    def _browse_output(self) -> None:
        start_dir = self.output_edit.text().strip() or str(
            self._settings.last_input_dir or Path.home()
        )
        path = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier de sortie", start_dir
        )
        if path:
            self.output_edit.setText(path)
            self._output_dir_user_set = True

    def _on_output_edited(self) -> None:
        self._output_dir_user_set = True
        self._set_error(self.output_error, "")

    def _on_format_changed(self) -> None:
        self._set_error(self.formats_error, "")

    # ── Clé API ────────────────────────────────────────────────────────────

    def _delete_key(self) -> None:
        try:
            self._key_store.delete()
        except Exception as exc:
            logger.warning("Suppression du trousseau impossible : %s", exc)
            self._set_error(
                self.api_error,
                "Impossible de supprimer la clé du trousseau.",
            )
        self.api_key_edit.clear()

    # ── Tâche ──────────────────────────────────────────────────────────────

    def _default_service(
        self, request: TranscribeRequest
    ) -> TranscribeService:
        return TranscribeService(
            {Provider.OPENROUTER: OpenRouterEngine()}
        )

    def start_transcription(self) -> None:
        if self._running or self._thread is not None:
            return
        validated = self._validate_form()
        if validated is None:
            return
        input_path, output_dir, formats, model, api_key = validated
        prompt_text = (self._prompt_text or "").strip() or None

        paths = output_paths(input_path, output_dir, formats)
        existing = existing_outputs(paths)
        if existing and not self._dialogs.confirm_overwrite(existing):
            self.status_label.setText(
                "Transcription annulée : les fichiers existants sont "
                "conservés."
            )
            return

        if (
            self.remember_checkbox.isChecked()
            and self.api_key_edit.text().strip()
        ):
            try:
                self._key_store.set(self.api_key_edit.text().strip())
            except Exception as exc:
                logger.warning("Écriture du trousseau impossible : %s", exc)
                self._set_error(
                    self.api_error,
                    "Impossible d'enregistrer la clé dans le trousseau ; "
                    "elle reste valable pour cette session.",
                )

        self._settings.add_recent_model(model)
        if self.model_combo.findText(model) < 0:
            self.model_combo.addItem(model)
        self.save_settings()

        request = TranscribeRequest(
            input_path=input_path,
            provider=Provider.OPENROUTER,
            model=model,
            language=self.language_combo.currentData(),
            prompt_text=prompt_text,
            output_dir=output_dir,
            formats=formats,
            overwrite=bool(existing),
            api_key=api_key,
        )
        try:
            self._start_worker(request)
        except Exception as exc:
            logger.warning("Démarrage de la tâche impossible : %s", exc)
            self._dialogs.show_error(
                "Transcription impossible",
                "Impossible de démarrer la transcription.",
                str(exc),
            )

    def _start_worker(self, request: TranscribeRequest) -> None:
        self._cancel_token = CancelToken()
        service = self._service_factory(request)
        worker = TranscribeWorker(service, request, self._cancel_token)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.on_worker_progress)
        worker.log.connect(self.on_worker_log)
        worker.finished.connect(self.on_worker_finished)
        worker.failed.connect(self.on_worker_failed)
        worker.cancelled.connect(self.on_worker_cancelled)
        for signal in (
            worker.finished,
            worker.failed,
            worker.cancelled,
        ):
            signal.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._thread = thread

        self._running = True
        self._writing = False
        self._task_started = time.monotonic()
        self._last_progress = None
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("")
        self.phase_label.setText("Validation…")
        self.elapsed_label.setText("")
        self.status_label.setText("Transcription en cours…")
        self.cost_label.setText("")
        self.result_paths_label.setText("")
        self.open_folder_button.setEnabled(False)
        self._elapsed_timer.start()
        self._update_state()
        thread.start()

    def cancel_transcription(self) -> None:
        if (
            self._running
            and not self._writing
            and self._cancel_token is not None
        ):
            self._cancel_token.cancel()
            self.status_label.setText("Annulation en cours…")
            self.cancel_button.setEnabled(False)
            logger.info("Annulation demandée")

    def on_worker_progress(self, update: ProgressUpdate) -> None:
        self._last_progress = update
        if update.phase == "writing":
            self._writing = True
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("")
            self.phase_label.setText("Écriture des fichiers…")
            self._update_state()
            self._update_elapsed()
            return
        if update.phase == "done":
            if update.total is not None and update.total > 0:
                self.progress_bar.setRange(0, 1000)
                self.progress_bar.setValue(1000)
                self.progress_bar.setFormat("100 %")
            else:
                self.progress_bar.setRange(0, 0)
                self.progress_bar.setFormat("")
            self.phase_label.setText("Terminé")
            self._update_elapsed()
            return

        label = _PHASE_LABELS.get(update.phase, update.phase)
        detail = update.detail.strip()
        if update.total is not None and update.total > 0:
            ratio = min(max(update.current, 0.0), update.total) / update.total
            percent = round(ratio * 1000)
            self.progress_bar.setRange(0, 1000)
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"{percent // 10} %")
            audio = (
                f"{format_seconds(update.current)} / "
                f"{format_seconds(update.total)}"
            )
            parts = [label, audio, f"{percent // 10} %"]
            if detail and detail != label:
                parts.append(detail)
            self.phase_label.setText(" — ".join(parts))
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("")
            self.phase_label.setText(
                f"{label} — {detail}" if detail and detail != label else label
            )
        self._update_elapsed()

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
            eta = elapsed * (
                progress.total - progress.current
            ) / progress.current
            text += f" — ETA : {format_seconds(max(0.0, eta))}"
        self.elapsed_label.setText(text)

    def on_worker_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)
        logger.info("%s", text)

    def on_worker_finished(self, result: TranscribeResult) -> None:
        self._finish_task()
        self.status_label.setText("Transcription terminée")
        self.result_paths_label.setText(
            "\n".join(str(path) for path in result.output_paths)
        )
        if result.cost_usd is None:
            self.cost_label.setText("Coût OpenRouter : Coût indisponible")
        else:
            self.cost_label.setText(
                f"Coût OpenRouter : ${result.cost_usd:.6f}"
            )
        if result.output_paths:
            self._output_folder = result.output_paths[0].parent
        else:
            text = self.output_edit.text().strip()
            self._output_folder = Path(text) if text else None
        self.open_folder_button.setEnabled(
            self._output_folder is not None
            and self._output_folder.is_dir()
        )
        logger.info("Transcription terminée")

    def on_worker_failed(self, message: str, detail: str) -> None:
        self._finish_task()
        self.status_label.setText("Échec de la transcription")
        self.open_folder_button.setEnabled(False)
        full_detail = detail or ""
        journal = self.log_view.toPlainText()[-4000:]
        if journal:
            full_detail += "\n\nJournal :\n" + journal
        self._dialogs.show_error(
            "Transcription impossible",
            message or "La transcription a échoué.",
            full_detail,
        )
        logger.warning("Transcription échouée : %s", message)

    def on_worker_cancelled(self) -> None:
        self._finish_task()
        self.status_label.setText("Transcription annulée.")
        self.result_paths_label.setText("")
        self.cost_label.setText("")
        self.open_folder_button.setEnabled(False)
        logger.info("Transcription annulée")

    def _finish_task(self) -> None:
        self._running = False
        self._writing = False
        self._elapsed_timer.stop()
        self._update_state()

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._update_state()
        if self._close_when_done:
            self._close_when_done = False
            self.close()

    # ── Fin de fenêtre et divers ───────────────────────────────────────────

    def _on_escape(self) -> None:
        if self._running:
            self.cancel_transcription()
        else:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._running or self._thread is not None:
            if not self._dialogs.confirm_close_while_running():
                event.ignore()
                return
            self._close_when_done = True
            self.cancel_transcription()
            event.ignore()
            return
        super().closeEvent(event)

    def _open_output_folder(self) -> None:
        if self._output_folder is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._output_folder))
            )

    def _on_log_toggle(self, checked: bool) -> None:
        self.log_view.setVisible(checked)
        self._settings.log_visible = checked
        self._settings.save()

    def show_about(self) -> None:
        info = build_info()
        text = (
            f"EcoTranscribe Desktop {info['version']}\n"
            f"Édition {info['flavor']} — OpenRouter\n"
            f"Commit : {info['commit']}\n"
            f"Build : {info['build_date']}\n"
            f"Licence : {info['license']}\n"
            f"Source : {info['source']}\n\n"
            "Notices tierces : THIRD_PARTY_NOTICES.md, inclus dans "
            "l'application."
        )
        self._dialogs.show_info("À propos d'EcoTranscribe Desktop", text)

    def save_settings(self) -> None:
        self._settings.geometry = self.saveGeometry()
        if self._input_path is not None:
            self._settings.last_input_dir = str(self._input_path.parent)
        self._settings.output_dir = (
            self.output_edit.text().strip()
            if self._output_dir_user_set
            else ""
        )
        self._settings.model = self.model_combo.currentText().strip()
        language = self.language_combo.currentData()
        self._settings.language = language or ""
        self._settings.formats = {
            value
            for value, checked in (
                ("srt", self.srt_checkbox.isChecked()),
                ("txt", self.txt_checkbox.isChecked()),
            )
            if checked
        }
        self._settings.remember_api_key = self.remember_checkbox.isChecked()
        self._settings.log_visible = self.log_toggle.isChecked()
        self._settings.save()

    def _clear_result(self) -> None:
        self.status_label.setText(
            "Prêt à transcrire"
            if self._input_path is not None
            else "Choisissez un fichier"
        )
        self.result_paths_label.setText("")
        self.cost_label.setText("")
        self.open_folder_button.setEnabled(False)

    # ── Drag & drop ────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_file():
                    self.set_input_path(path)
                    event.acceptProposedAction()
                    return
        event.ignore()
