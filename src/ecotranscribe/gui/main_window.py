"""Fenêtre principale : shell et contrôleur de l'assistant."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtCore import QSize, QThread, QUrl, Qt
from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.config import (
    AUDIO_EXTENSIONS,
    KEY_MISSING_MESSAGE,
    OPENROUTER_API_URL,
    OPENROUTER_MODELS,
    VIDEO_EXTENSIONS,
)
from ..core.engines.openrouter import OpenRouterEngine
from ..core.errors import (
    EngineUnavailableError,
    InvalidRequestError,
    TranscribeError,
)
from ..core.models import (
    CancelToken,
    OutputFormat,
    ProgressUpdate,
    Provider,
    TranscribeRequest,
)
from ..core.outputs import existing_outputs, output_paths
from ..core.prompts import resolve_prompt
from ..core.service import TranscribeService
from .app_icon import app_icon_pixmap
from .availability import build_info
from .catalog import CatalogClient
from .dialogs import DialogService
from .duration import DurationProbe
from . import network
from .logging_setup import log_file_path
from .pages.done import DonePage
from .pages.home import HomePage
from .pages.key import KeyMode, KeyPage
from .pages.options import OptionsPage
from .pages.progress import ProgressPage
from .pages.prompt import PromptPage
from .pages.settings import SettingsPage
from .pricing import PricingClient
from .settings import AppSettings, KeyStore
from .state import KeySource, PageId, WizardState
from .widgets.icons import gear_icon
from .widgets.stepper import Stepper
from .worker import TranscribeWorker

logger = logging.getLogger("ecotranscribe")

_STAGE_BY_PAGE = {
    PageId.HOME: 0,
    PageId.KEY: 0,
    PageId.PROMPT: 1,
    PageId.SETTINGS: 2,
    PageId.PROGRESS: 3,
}
_STEPPER_PAGES = {PageId.KEY, PageId.PROMPT, PageId.SETTINGS, PageId.PROGRESS}
_GEAR_PAGES = {PageId.HOME, PageId.PROMPT, PageId.SETTINGS, PageId.PROGRESS}


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        settings: AppSettings,
        key_store: KeyStore,
        dialogs: DialogService,
        service_factory: Callable[[TranscribeRequest], TranscribeService]
        | None = None,
        pricing_client: PricingClient | None = None,
        catalog_client: CatalogClient | None = None,
        duration_probe: DurationProbe | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._key_store = key_store
        self._dialogs = dialogs
        self._service_factory = service_factory or self._default_service
        self._pricing_client = pricing_client
        self._catalog_client = catalog_client
        if (
            self._catalog_client is not None
            and self._catalog_client.parent() is None
        ):
            self._catalog_client.setParent(self)
        self._catalog_models: tuple[str, ...] | None = None
        self._priced_models: set[str] = set()
        self._duration_probe = duration_probe or DurationProbe(parent=self)
        self._state = WizardState()
        self._history: list[PageId] = []
        self._current = PageId.HOME
        self._thread: QThread | None = None
        self._worker: TranscribeWorker | None = None
        self._cancel_token: CancelToken | None = None
        self._close_when_done = False
        self._pending_new = False
        self._busy = False
        self._writing = False
        self._settings_loaded = False
        self._pricing_attached = False
        self._keyring_available = True
        self._keyring_key: str | None = None
        self._env_key: str | None = None
        self._active_key: str | None = None
        self._restore_state()
        self._load_keys()
        self._build_ui()
        self._connect_signals()
        self._refresh_key_source()
        self._show_page(PageId.HOME, push=False)
        if self._catalog_client is not None:
            self._catalog_client.start()

    @property
    def state(self) -> WizardState:
        return self._state

    @property
    def current_page(self) -> PageId:
        return self._current

    @property
    def is_busy(self) -> bool:
        return self._busy or self._thread is not None

    # ── Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("EcoTranscribe Desktop")
        self.setMinimumSize(760, 640)
        self.resize(900, 820)
        self.setAcceptDrops(True)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(32, 16, 32, 16)
        self.logo_label = QLabel()
        self.logo_label.setObjectName("appLogo")
        self.logo_label.setPixmap(app_icon_pixmap(32))
        self.logo_label.setFixedSize(40, 40)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setAccessibleName("EcoTranscribe")
        title = QLabel("EcoTranscribe")
        title.setObjectName("appTitle")
        title.setProperty("role", "sectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gear_button = QToolButton()
        self.gear_button.setIcon(gear_icon())
        self.gear_button.setIconSize(QSize(22, 22))
        self.gear_button.setToolTip("Options")
        self.gear_button.setAccessibleName("Options")
        self.gear_button.setFixedSize(40, 40)
        self.gear_button.setProperty("variant", "tertiary")
        header_layout.addWidget(self.logo_label)
        header_layout.addStretch(1)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.gear_button)
        root.addWidget(header)

        self._stepper_wrap = QWidget()
        stepper_layout = QHBoxLayout(self._stepper_wrap)
        stepper_layout.setContentsMargins(32, 8, 32, 8)
        self.stepper = Stepper()
        stepper_layout.addWidget(self.stepper)
        root.addWidget(self._stepper_wrap)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.home_page = HomePage()
        self.key_page = KeyPage()
        self.prompt_page = PromptPage()
        self.settings_page = SettingsPage()
        self.progress_page = ProgressPage()
        self.done_page = DonePage()
        self.options_page = OptionsPage()
        self._pages = {
            PageId.HOME: self.home_page,
            PageId.KEY: self.key_page,
            PageId.PROMPT: self.prompt_page,
            PageId.SETTINGS: self.settings_page,
            PageId.PROGRESS: self.progress_page,
            PageId.DONE: self.done_page,
            PageId.OPTIONS: self.options_page,
        }
        for page in self._pages.values():
            self.stack.addWidget(page)
        self.setCentralWidget(central)
        self.key_page.key_form.remember.setChecked(
            self._settings.remember_api_key
        )
        self.options_page.key_form.remember.setChecked(
            self._settings.remember_api_key
        )

    def _connect_signals(self) -> None:
        self.gear_button.clicked.connect(self._open_options)
        self.home_page.browse_requested.connect(self._browse_file)
        self.home_page.continue_requested.connect(self._continue_from_home)
        self.home_page.change_file_requested.connect(self._change_file)
        self.home_page.options_requested.connect(self._open_options)
        self.key_page.submitted.connect(self._on_key_submitted)
        self.key_page.back_requested.connect(self._on_key_back)
        self.prompt_page.next_requested.connect(self._on_prompt_next)
        self.prompt_page.back_requested.connect(self._back)
        self.prompt_page.change_file_requested.connect(self._change_file)
        self.settings_page.launch_requested.connect(self._launch)
        self.settings_page.back_requested.connect(self._back)
        self.settings_page.browse_output_requested.connect(self._browse_output)
        self.settings_page.use_source_requested.connect(self._use_source_dir)
        self.progress_page.cancel_requested.connect(self.cancel_transcription)
        self.progress_page.back_to_settings_requested.connect(self._back_to_settings)
        self.progress_page.home_requested.connect(self._home_from_progress)
        self.progress_page.open_log_requested.connect(self._open_log)
        self.progress_page.open_folder_requested.connect(self._open_output_folder)
        self.progress_page.edit_key_requested.connect(self._edit_key_after_error)
        self.progress_page.change_file_requested.connect(self._change_file)
        self.done_page.open_folder_requested.connect(self._open_output_folder)
        self.done_page.new_transcription_requested.connect(self._new_transcription)
        self.options_page.save_key_requested.connect(self._save_options_key)
        self.options_page.delete_key_requested.connect(self._delete_options_key)
        self.options_page.back_requested.connect(self._back)
        self._duration_probe.ready.connect(self._on_duration_ready)
        self._duration_probe.failed.connect(self._on_duration_failed)
        if self._catalog_client is not None:
            self._catalog_client.models_ready.connect(self._on_catalog_ready)
        self._shortcuts: list[QShortcut] = []
        self._add_shortcut(QKeySequence.StandardKey.Open, self._browse_file)
        self._add_shortcut(QKeySequence("Ctrl+Return"), self._primary_shortcut)
        self._add_shortcut(QKeySequence("Ctrl+Enter"), self._primary_shortcut)
        self._add_shortcut(QKeySequence("Meta+Return"), self._primary_shortcut)
        self._add_shortcut(QKeySequence(Qt.Key.Key_Escape), self._escape)

    def _add_shortcut(self, sequence, callback) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _attach_pricing(self) -> None:
        if self._pricing_client is None or self._pricing_attached:
            return
        self._pricing_attached = True
        if self._pricing_client.parent() is None:
            self._pricing_client.setParent(self)
        self._pricing_client.price_ready.connect(self.settings_page.set_price)
        self._fetch_prices(OPENROUTER_MODELS)
        if self._catalog_models is not None:
            self._fetch_prices(self._catalog_models)

    def _fetch_prices(self, models: Iterable[object]) -> None:
        if self._pricing_client is None:
            return
        for model in models:
            if not isinstance(model, str) or model in self._priced_models:
                continue
            self._priced_models.add(model)
            self._pricing_client.fetch(model)

    def _on_catalog_ready(self, models: object) -> None:
        if not isinstance(models, (tuple, list)):
            return
        catalog = tuple(
            model
            for model in models
            if isinstance(model, str) and model.strip()
        )
        if not catalog or catalog == self._catalog_models:
            return
        self._catalog_models = catalog
        if self._settings_loaded:
            self.settings_page.set_catalog(catalog)
            for model in self._settings.recent_models:
                self.settings_page.add_model(model)
        if self._pricing_attached:
            self._fetch_prices(catalog)

    def _restore_state(self) -> None:
        self._state.model = self._settings.model
        self._state.language = self._settings.language or None
        self._state.formats = frozenset(
            OutputFormat(value) for value in self._settings.formats
        )
        if self._settings.output_dir:
            self._state.output_dir = Path(self._settings.output_dir)
            self._state.output_dir_user_set = True

    def _load_keys(self) -> None:
        try:
            value = self._key_store.get()
        except Exception as exc:
            logger.warning("Lecture du trousseau impossible : %s", exc)
            self._keyring_available = False
            value = None
        self._keyring_key = (value or "").strip() or None
        self._env_key = (
            os.environ.get("OPENROUTER_API_KEY") or ""
        ).strip() or None
        self._refresh_key_source()

    def _refresh_key_source(self) -> None:
        if self._state.session_key:
            self._state.key_source = KeySource.SESSION
            self._active_key = self._state.session_key
        elif self._keyring_key:
            self._state.key_source = KeySource.KEYRING
            self._active_key = self._keyring_key
        elif self._env_key:
            self._state.key_source = KeySource.ENV
            self._active_key = self._env_key
        else:
            self._state.key_source = KeySource.NONE
            self._active_key = None
        if hasattr(self, "home_page"):
            self.home_page.set_has_key(self._active_key is not None)
            self.key_page.set_keyring_available(self._keyring_available)
            self.key_page.set_status(self._key_status_text())
            self._update_options_status()

    def _update_options_status(self) -> None:
        self.options_page.set_status(self._key_status_text())
        self.options_page.set_keyring_available(self._keyring_available)
        self.options_page.set_can_delete(self._can_delete_key())

    def _key_status_text(self) -> str:
        return {
            KeySource.NONE: "Aucune clé active",
            KeySource.SESSION: "Clé de session (non enregistrée)",
            KeySource.KEYRING: "Clé enregistrée dans le trousseau",
            KeySource.ENV: "Clé fournie par l'environnement",
        }[self._state.key_source]

    def _can_delete_key(self) -> bool:
        return self._state.key_source in (
            KeySource.SESSION,
            KeySource.KEYRING,
        )

    # ── Navigation ─────────────────────────────────────────────────────────

    def _show_page(self, page: PageId, *, push: bool = True) -> None:
        if push and self._current != page:
            self._history.append(self._current)
        self._current = page
        self.stack.setCurrentWidget(self._pages[page])
        self._stepper_wrap.setVisible(page in _STEPPER_PAGES)
        if page in _STAGE_BY_PAGE:
            self.stepper.set_current(_STAGE_BY_PAGE[page])
        self._update_gear()
        self._pages[page].focus_primary()

    def _update_gear(self) -> None:
        visible = self._current in _GEAR_PAGES
        self.gear_button.setVisible(visible)
        self.gear_button.setEnabled(visible and not self.is_busy)

    def _back(self) -> None:
        if self.is_busy:
            return
        if self._current == PageId.PROMPT:
            self._capture_prompt()
        if self._current == PageId.SETTINGS:
            self._capture_settings()
        if self._current == PageId.OPTIONS and self.options_page.is_dirty():
            if not self._dialogs.confirm_discard(
                "La clé saisie n'est pas enregistrée. Quitter ?"
            ):
                return
        self.options_page.mark_clean()
        if not self._history:
            return
        target = self._history.pop()
        self._show_page(target, push=False)

    def _rewind_to(self, page: PageId) -> None:
        if page in self._history:
            index = len(self._history) - 1 - self._history[::-1].index(page)
            self._history = self._history[:index]
        self._show_page(page, push=False)

    def _go_home(self, *, reset: bool) -> None:
        if self._thread is not None:
            return
        if reset:
            self._state.reset_task()
        else:
            self._state.clear_result()
        self._history = []
        self.done_page.reset()
        self.home_page.set_selected_file(self._state.input_path)
        self.home_page.set_error("")
        self._show_page(PageId.HOME, push=False)

    def _home_from_progress(self) -> None:
        self._go_home(reset=False)

    def _new_transcription(self) -> None:
        if self._thread is not None:
            self._pending_new = True
            return
        self._go_home(reset=True)

    def _continue_from_home(self) -> None:
        if self._state.input_path is None:
            self._browse_file()
            return
        if self._active_key:
            self._go_prompt()
        else:
            self._go_key(KeyMode.INITIAL)

    def _capture_prompt(self) -> None:
        if self._current == PageId.PROMPT and self._state.input_path is not None:
            self._state.prompt_text = self.prompt_page.prompt_text()
            self._state.prompt_edited = self.prompt_page.prompt_edited()

    def _capture_settings(self) -> None:
        if self._current == PageId.SETTINGS and self._settings_loaded:
            self.settings_page.capture(self._state)

    def _prompt_has_edits(self) -> bool:
        if self._state.prompt_edited:
            return True
        return (
            self._current == PageId.PROMPT
            and self.prompt_page.prompt_edited()
        )

    # ── Fichier ────────────────────────────────────────────────────────────

    def _browse_file(self) -> None:
        if self.is_busy or self._current not in (
            PageId.HOME,
            PageId.PROMPT,
        ):
            return
        start_dir = self._settings.last_input_dir or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un fichier", start_dir, self._media_filter()
        )
        if path:
            self.select_file(Path(path), confirm_prompt=True)

    def _change_file(self) -> None:
        if self.is_busy:
            return
        start_dir = self._settings.last_input_dir or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un fichier", start_dir, self._media_filter()
        )
        if path:
            self.select_file(Path(path), confirm_prompt=True)

    def select_file(self, path: Path, *, confirm_prompt: bool = False) -> None:
        if self.is_busy:
            return
        path = Path(path).expanduser()
        error = self._validate_input(path)
        if error:
            if self._current == PageId.HOME:
                self.home_page.set_error(error)
            elif self._current == PageId.PROMPT:
                self.prompt_page.set_error(error)
            elif self._current == PageId.SETTINGS:
                self.settings_page.show_message(error)
            else:
                self.progress_page.append_log(error)
            return
        if confirm_prompt and self._prompt_has_edits():
            if not self._dialogs.confirm_discard(
                "Les modifications du prompt seront perdues. Continuer ?"
            ):
                return
        self._state.input_path = path
        self._state.prompt_path = None
        self._state.prompt_text = None
        self._state.prompt_edited = False
        self._state.prompt_error = None
        self._state.duration_s = None
        self._state.duration_path = None
        self._state.duration_pending = False
        self._state.clear_result()
        self._settings.last_input_dir = str(path.parent)
        self.home_page.set_selected_file(path)
        self.home_page.set_error("")
        self.prompt_page.set_error("")
        if self._active_key:
            self._go_prompt()
        else:
            self._go_key(KeyMode.INITIAL)

    @staticmethod
    def _validate_input(path: Path) -> str | None:
        if not path.exists():
            return "Le fichier sélectionné n'existe plus."
        if not path.is_file():
            return "Le fichier sélectionné n'est pas un fichier valide."
        if not os.access(path, os.R_OK):
            return "Impossible de lire ce fichier. Vérifiez les permissions."
        return None

    @staticmethod
    def _media_filter() -> str:
        extensions = sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS)
        patterns = " ".join(f"*{extension}" for extension in extensions)
        return f"Médias ({patterns});;Tous les fichiers (*)"

    # ── Clé ────────────────────────────────────────────────────────────────

    def _go_key(
        self, mode: KeyMode, *, return_page: PageId = PageId.PROMPT
    ) -> None:
        self._state.key_return_page = return_page
        self.key_page.set_mode(mode)
        self.key_page.set_keyring_available(self._keyring_available)
        self.key_page.set_status(self._key_status_text())
        self.key_page.clear_field()
        self._show_page(PageId.KEY)

    def _on_key_back(self) -> None:
        if self._state.key_return_page == PageId.SETTINGS:
            self._rewind_to(PageId.SETTINGS)
        else:
            self._back()

    def _on_key_submitted(self, key: str, remember: bool) -> None:
        key = key.strip()
        if not key:
            self.key_page.set_error("Saisissez une clé OpenRouter.")
            return
        self.options_page.key_form.remember.setChecked(remember)
        if (
            self._state.session_key == key
            and self._state.key_source is KeySource.SESSION
            and not remember
        ):
            self._after_key()
            return
        if remember:
            try:
                self._key_store.set(key)
            except Exception as exc:
                logger.warning("Écriture du trousseau impossible : %s", exc)
                self._keyring_available = False
                self._state.session_key = key
                self._refresh_key_source()
                self.key_page.set_keyring_available(False)
                self.key_page.set_error(
                    "Impossible d'enregistrer la clé dans le trousseau ; "
                    "elle reste valable pour cette session."
                )
                return
            self._keyring_key = key
            self._state.session_key = None
        else:
            self._state.session_key = key
        self._refresh_key_source()
        self._after_key()

    def _after_key(self) -> None:
        if self._state.key_return_page == PageId.SETTINGS:
            self.settings_page.show_message("")
            self._rewind_to(PageId.SETTINGS)
        else:
            back = self._history[-1] if self._history else PageId.HOME
            self._history = [back]
            self._go_prompt(push=False)

    # ── Prompt et durée ────────────────────────────────────────────────────

    def _go_prompt(self, *, push: bool = True) -> None:
        path = self._state.input_path
        if path is None:
            self._go_home(reset=False)
            return
        if (
            not self._state.prompt_edited
            and self._state.prompt_path is None
            and self._state.prompt_text is None
            and self._state.prompt_error is None
        ):
            self._load_prompt(path)
        self.prompt_page.set_file(path)
        if self._state.duration_path == path:
            self.prompt_page.set_duration(
                self._state.duration_s,
                pending=self._state.duration_pending,
            )
        else:
            self.prompt_page.set_duration(None, pending=True)
        self.prompt_page.set_prompt(
            self._state.prompt_text,
            self._state.prompt_path,
            self._state.prompt_error,
            edited=self._state.prompt_edited,
        )
        self._show_page(PageId.PROMPT, push=push)
        if self._state.duration_path != path and not self._state.duration_pending:
            self._probe_duration(path)

    def _load_prompt(self, path: Path) -> None:
        try:
            prompt_path, prompt_text = resolve_prompt(path)
        except InvalidRequestError as exc:
            self._state.prompt_path = None
            self._state.prompt_text = None
            self._state.prompt_error = exc.user_message
        else:
            self._state.prompt_path = prompt_path
            self._state.prompt_text = prompt_text
            self._state.prompt_error = None
        self._state.prompt_edited = False

    def _probe_duration(self, path: Path) -> None:
        if self._state.duration_path == path and (
            self._state.duration_s is not None
            or self._state.duration_pending
        ):
            return
        self._state.duration_path = path
        self._state.duration_s = None
        self._state.duration_pending = True
        if self._current == PageId.PROMPT and self._state.input_path == path:
            self.prompt_page.set_duration(None, pending=True)
        self._duration_probe.start(path)

    def _on_duration_ready(self, path: object, value: object) -> None:
        path = Path(path)
        if self._state.input_path != path or self._state.duration_path != path:
            return
        self._state.duration_pending = False
        self._state.duration_s = None if value is None else float(value)
        self.settings_page.set_duration(self._state.duration_s)
        if self._current == PageId.PROMPT:
            self.prompt_page.set_duration(self._state.duration_s, pending=False)

    def _on_duration_failed(self, path: object, message: str) -> None:
        path = Path(path)
        if self._state.input_path != path or self._state.duration_path != path:
            return
        self._state.duration_pending = False
        self._state.duration_s = None
        self.settings_page.set_duration(None)
        logger.warning("Durée indisponible pour %s : %s", path, message)
        if self._current == PageId.PROMPT:
            self.prompt_page.set_duration(None, pending=False)

    def _on_prompt_next(self) -> None:
        path = self._state.input_path
        if path is None:
            return
        error = self._validate_input(path)
        if error:
            self.prompt_page.set_error(error)
            self.prompt_page.next_button.setEnabled(False)
            return
        self._state.prompt_text = self.prompt_page.prompt_text()
        self._state.prompt_edited = self.prompt_page.prompt_edited()
        self._open_settings()

    # ── Réglages et lancement ──────────────────────────────────────────────

    def _open_settings(self) -> None:
        self._settings_loaded = True
        self.settings_page.load(self._state)
        if self._catalog_models is not None:
            self.settings_page.set_catalog(self._catalog_models)
        for model in self._settings.recent_models:
            self.settings_page.add_model(model)
        self._attach_pricing()
        self._show_page(PageId.SETTINGS)

    def _browse_output(self) -> None:
        start_dir = (
            self.settings_page.output_edit.text().strip()
            or self._settings.last_input_dir
            or str(Path.home())
        )
        path = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier de sortie", start_dir
        )
        if path:
            self.settings_page.set_output_dir(Path(path))

    def _use_source_dir(self) -> None:
        if self._state.input_path is not None:
            self.settings_page.set_output_dir(
                self._state.input_path.parent, user_set=False
            )

    def _launch(self) -> None:
        if self.is_busy:
            return
        if not self.settings_page.commit(self._state):
            return
        if self._state.input_path is None:
            return
        if not self._active_key:
            self.settings_page.show_message(KEY_MISSING_MESSAGE)
            self._go_key(KeyMode.CORRECTION, return_page=PageId.SETTINGS)
            return
        output_dir = self._state.output_dir or self._state.input_path.parent
        paths = output_paths(self._state.input_path, output_dir, self._state.formats)
        existing = existing_outputs(paths)
        if existing and not self._dialogs.confirm_overwrite(existing):
            self.settings_page.show_message(
                "Transcription annulée : les fichiers existants sont conservés."
            )
            return
        self._settings.add_recent_model(self._state.model)
        self.save_settings()
        request = TranscribeRequest(
            input_path=self._state.input_path,
            provider=Provider.OPENROUTER,
            model=self._state.model,
            language=self._state.language,
            prompt_text=self._state.prompt_text,
            output_dir=output_dir,
            formats=self._state.formats,
            overwrite=bool(existing),
            api_key=self._active_key,
        )
        try:
            self._start_worker(request)
        except Exception as exc:
            logger.warning("Démarrage de la tâche impossible : %s", exc)
            self.settings_page.show_message(
                "Impossible de démarrer la transcription."
            )

    def _start_worker(self, request: TranscribeRequest) -> None:
        self._cancel_token = CancelToken()
        service = self._service_factory(request)
        worker = TranscribeWorker(service, request, self._cancel_token)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.log.connect(self._on_log)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        for signal in (worker.finished, worker.failed, worker.cancelled):
            signal.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._thread = thread
        self._busy = True
        self._writing = False
        self._pending_new = False
        self._state.clear_result()
        self.progress_page.start_task(request.input_path.name)
        self._show_page(PageId.PROGRESS)
        thread.start()

    def _on_progress(self, update: ProgressUpdate) -> None:
        if update.phase == "writing":
            self._writing = True
        self.progress_page.update_progress(update)

    def _on_log(self, text: str) -> None:
        self.progress_page.append_log(text)

    def _on_finished(self, result) -> None:
        self._state.result = result
        self._state.error = None
        self._state.cancelled = False
        self.progress_page.update_progress(
            ProgressUpdate("done", detail="Terminé")
        )
        file_name = self._state.input_path.name if self._state.input_path else ""
        self.done_page.show_result(result, file_name)
        self._show_page(PageId.DONE)
        logger.info("Transcription terminée")

    def _on_failed(self, error: TranscribeError) -> None:
        self._state.error = error
        self._state.result = None
        self._state.cancelled = False
        self._writing = False
        can_edit_key = isinstance(error, EngineUnavailableError)
        can_change_file = (
            isinstance(error, InvalidRequestError)
            and "fichier" in error.user_message.lower()
        )
        can_open_folder = (
            self._state.output_dir is not None
            and self._state.output_dir.is_dir()
        )
        self.progress_page.show_error(
            error,
            can_edit_key=can_edit_key,
            can_change_file=can_change_file,
            can_open_folder=can_open_folder,
        )
        self.progress_page.set_busy(self.is_busy)
        logger.warning("Transcription échouée : %s", error.user_message)

    def _on_cancelled(self) -> None:
        self._state.cancelled = True
        self._state.error = None
        self._state.result = None
        self._writing = False
        self.progress_page.show_cancelled()
        self.progress_page.set_busy(self.is_busy)
        logger.info("Transcription annulée")

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._cancel_token = None
        self._busy = False
        self._writing = False
        self.progress_page.set_busy(False)
        self._update_gear()
        if self._close_when_done:
            self._close_when_done = False
            self.close()
            return
        if self._pending_new:
            self._pending_new = False
            self._go_home(reset=True)

    def cancel_transcription(self) -> None:
        if (
            self._thread is None
            or self._cancel_token is None
            or self._writing
        ):
            return
        self._cancel_token.cancel()
        self.progress_page.show_cancelling()
        logger.info("Annulation demandée")

    def _back_to_settings(self) -> None:
        if self._thread is not None:
            return
        self._rewind_to(PageId.SETTINGS)

    def _edit_key_after_error(self) -> None:
        if self._thread is not None:
            return
        self._go_key(KeyMode.CORRECTION, return_page=PageId.SETTINGS)

    def _open_log(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_file_path())))

    def _open_output_folder(self) -> None:
        result = self._state.result
        folder = (
            result.output_paths[0].parent
            if result is not None and result.output_paths
            else self._state.output_dir
        )
        if folder is not None and folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # ── Options ────────────────────────────────────────────────────────────

    def _open_options(self) -> None:
        if self.is_busy or self._current == PageId.OPTIONS:
            return
        if self._current == PageId.PROMPT:
            self._capture_prompt()
        if self._current == PageId.SETTINGS:
            self._capture_settings()
        self.options_page.load(
            self._key_status_text(),
            self._keyring_available,
            build_info(),
            self._can_delete_key(),
        )
        self._show_page(PageId.OPTIONS)

    def _save_options_key(self, key: str, remember: bool) -> None:
        key = key.strip()
        if not key:
            self.options_page.set_error("Saisissez une clé OpenRouter.")
            return
        self.key_page.key_form.remember.setChecked(remember)
        if remember:
            try:
                self._key_store.set(key)
            except Exception as exc:
                logger.warning("Écriture du trousseau impossible : %s", exc)
                self._keyring_available = False
                self._state.session_key = key
                self._refresh_key_source()
                self.options_page.set_keyring_available(False)
                self.options_page.set_error(
                    "Impossible d'enregistrer la clé dans le trousseau ; "
                    "elle reste valable pour cette session."
                )
                return
            self._keyring_key = key
            self._state.session_key = None
            self.options_page.show_saved(
                "Clé enregistrée dans le trousseau."
            )
        else:
            self._state.session_key = key
            self.options_page.show_saved(
                "Clé de session enregistrée pour cette exécution."
            )
        self._refresh_key_source()

    def _delete_options_key(self) -> None:
        if not self._dialogs.confirm_delete_key():
            return
        if self._keyring_key is not None:
            try:
                self._key_store.delete()
            except Exception as exc:
                logger.warning("Suppression du trousseau impossible : %s", exc)
                self.options_page.set_error(
                    "Impossible de supprimer la clé du trousseau."
                )
                return
        self._keyring_key = None
        self._state.session_key = None
        self._refresh_key_source()
        self.options_page.clear_field()
        self.options_page.set_error("")
        if self._state.key_source is KeySource.ENV:
            self.options_page.show_saved(
                "Clé du trousseau supprimée ; la clé d'environnement reste "
                "active."
            )
        else:
            self.options_page.show_saved("Clé supprimée.")

    # ── Réglages, fermeture et raccourcis ──────────────────────────────────

    def save_settings(self) -> None:
        if self._settings_loaded:
            self.settings_page.capture(self._state)
        self._settings.geometry = self.saveGeometry()
        if self._state.input_path is not None:
            self._settings.last_input_dir = str(self._state.input_path.parent)
        self._settings.model = self._state.model
        self._settings.language = self._state.language or ""
        self._settings.formats = {
            fmt.value for fmt in self._state.formats
        }
        self._settings.output_dir = (
            str(self._state.output_dir)
            if self._state.output_dir_user_set and self._state.output_dir
            else ""
        )
        self._settings.remember_api_key = (
            self.key_page.key_form.remember.isChecked()
        )
        self._settings.save()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_busy:
            if not self._dialogs.confirm_close_while_running():
                event.ignore()
                return
            self._close_when_done = True
            self.cancel_transcription()
            event.ignore()
            return
        if self._current == PageId.OPTIONS and self.options_page.is_dirty():
            if not self._dialogs.confirm_discard(
                "La clé saisie n'est pas enregistrée. Quitter ?"
            ):
                event.ignore()
                return
        self.save_settings()
        self._duration_probe.shutdown()
        super().closeEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if self.is_busy or self._current not in (
            PageId.HOME,
            PageId.PROMPT,
        ):
            event.ignore()
            return
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_file():
                    self.select_file(path, confirm_prompt=True)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _primary_shortcut(self) -> None:
        if self._current == PageId.HOME:
            self._continue_from_home()
        elif self._current == PageId.KEY:
            self.key_page.next_button.click()
        elif self._current == PageId.PROMPT:
            self.prompt_page.next_button.click()
        elif self._current == PageId.SETTINGS:
            self.settings_page.launch_button.click()

    def _escape(self) -> None:
        if self._current == PageId.PROGRESS:
            if self.is_busy:
                self.cancel_transcription()
            else:
                self._back_to_settings()
        elif self._current == PageId.KEY:
            self._on_key_back()
        elif self._current in (
            PageId.PROMPT,
            PageId.SETTINGS,
            PageId.OPTIONS,
        ):
            self._back()
        elif self._current == PageId.HOME:
            self.close()
        elif self._current == PageId.DONE:
            self._go_home(reset=False)

    def _default_service(
        self, request: TranscribeRequest
    ) -> TranscribeService:
        proxy = network.resolve_proxy_for(OPENROUTER_API_URL)
        return TranscribeService(
            {Provider.OPENROUTER: OpenRouterEngine(proxy=proxy)}
        )
