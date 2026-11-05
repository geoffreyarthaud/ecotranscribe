import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QLineEdit

from ecotranscribe.core.config import OPENROUTER_MODEL
from ecotranscribe.core.errors import CancelledError, TranscribeError
from ecotranscribe.core.models import (
    ProgressUpdate,
    Provider,
    Segment,
    TranscribeResult,
)
from ecotranscribe.gui.main_window import MainWindow
from ecotranscribe.gui.settings import AppSettings, MemoryStore

from .conftest import FakeDialogs


def _window(
    settings: AppSettings,
    *,
    key_store: MemoryStore | None = None,
    dialogs: FakeDialogs | None = None,
    service_factory=None,
) -> MainWindow:
    return MainWindow(
        settings=settings,
        key_store=key_store or MemoryStore(),
        dialogs=dialogs or FakeDialogs(),
        service_factory=service_factory,
    )


def test_window_construction_without_network(
    qtbot, app_settings: AppSettings
) -> None:
    def should_not_run(request):
        raise AssertionError("aucun service ne doit être créé")

    window = _window(app_settings, service_factory=should_not_run)
    qtbot.addWidget(window)

    assert window.minimumWidth() >= 760
    assert window.minimumHeight() >= 640
    assert window.provider_openrouter.isChecked()
    assert window.provider_whisper.isEnabled() is False
    assert "édition lite" in window.whisper_reason.text()
    assert "Édition full" in window.whisper_reason.text()
    assert window.launch_button.isEnabled() is False
    assert window.model_combo.currentText() == OPENROUTER_MODEL
    assert window.language_combo.currentData() == "fr"
    assert window.srt_checkbox.isChecked()
    assert window.txt_checkbox.isChecked()
    assert "OpenRouter" in window.cloud_warning.text()
    assert window.acceptDrops() is True
    assert window.api_key_edit.echoMode() == QLineEdit.EchoMode.Password
    assert window.api_key_edit.placeholderText() == "OPENROUTER_API_KEY"


def test_shortcuts_are_registered(
    qtbot, app_settings: AppSettings
) -> None:
    window = _window(app_settings)
    qtbot.addWidget(window)
    shortcuts = {
        shortcut.key().toString(QKeySequence.SequenceFormat.PortableText)
        for shortcut in window.findChildren(QShortcut)
    }
    assert "Ctrl+O" in shortcuts
    assert "Ctrl+Return" in shortcuts or "Ctrl+Enter" in shortcuts
    assert "Esc" in shortcuts


def test_file_selection_updates_output_and_prompt(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    source = tmp_path / "réunion accentuée.mp3"
    source.write_bytes(b"x")
    prompt = tmp_path / "réunion accentuée.prompt.md"
    prompt.write_text("RGAA\nDSFR\nAccessibilité", encoding="utf-8")
    window = _window(app_settings)
    qtbot.addWidget(window)

    window.set_input_path(source)

    assert window.input_edit.text() == str(source)
    assert window.output_edit.text() == str(tmp_path)
    assert window.prompt_path_label.text().endswith(".prompt.md")
    assert "RGAA" in window.prompt_preview.text()
    assert window.launch_button.isEnabled() is True


def test_new_selection_resets_edited_prompt(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    first = tmp_path / "first.mp3"
    first.write_bytes(b"x")
    (tmp_path / "first.prompt.md").write_text("prompt A", encoding="utf-8")
    second = tmp_path / "second.mp3"
    second.write_bytes(b"x")
    (tmp_path / "second.prompt.txt").write_text("prompt B", encoding="utf-8")

    window = _window(app_settings)
    qtbot.addWidget(window)
    window.set_input_path(first)
    window._prompt_text = "édité"
    window.set_input_path(second)

    assert window._prompt_text == "prompt B"
    assert window.prompt_path_label.text().endswith(".prompt.txt")
    assert "prompt B" in window.prompt_preview.text()


def test_key_is_loaded_into_password_field(
    qtbot, app_settings: AppSettings
) -> None:
    window = _window(app_settings, key_store=MemoryStore("sk-or-secret"))
    qtbot.addWidget(window)
    assert window.api_key_edit.text() == "sk-or-secret"


def test_settings_are_persisted_and_reloaded(
    qtbot, tmp_path: Path
) -> None:
    path = tmp_path / "settings.ini"
    settings = AppSettings(QSettings(str(path), QSettings.IniFormat))
    window = _window(settings)
    qtbot.addWidget(window)
    window.model_combo.setCurrentText("custom/model")
    window.language_combo.setCurrentIndex(
        window.language_combo.findData("en")
    )
    window.srt_checkbox.setChecked(False)
    window.remember_checkbox.setChecked(False)
    window.log_toggle.setChecked(True)
    window.save_settings()

    reloaded_settings = AppSettings(
        QSettings(str(path), QSettings.IniFormat)
    )
    second = _window(reloaded_settings)
    qtbot.addWidget(second)
    assert second.model_combo.currentText() == "custom/model"
    assert second.language_combo.currentData() == "en"
    assert second.srt_checkbox.isChecked() is False
    assert second.txt_checkbox.isChecked() is True
    assert second.remember_checkbox.isChecked() is False
    assert second.log_view.isVisibleTo(second) is True


def test_key_never_written_to_qsettings(
    qtbot, tmp_path: Path
) -> None:
    path = tmp_path / "settings.ini"
    settings = AppSettings(QSettings(str(path), QSettings.IniFormat))
    window = _window(settings, key_store=MemoryStore("sk-or-secret"))
    qtbot.addWidget(window)
    window.save_settings()
    assert "sk-or-secret" not in path.read_text(encoding="utf-8")


def test_about_uses_dialog_service(
    qtbot, app_settings: AppSettings
) -> None:
    dialogs = FakeDialogs()
    window = _window(app_settings, dialogs=dialogs)
    qtbot.addWidget(window)
    window.show_about()
    assert dialogs.infos
    text = dialogs.infos[0][1]
    assert "0.2.0" in text
    assert "lite" in text
    assert "MIT" in text


class FakeService:
    def __init__(
        self,
        result: TranscribeResult | None = None,
        *,
        cancel: bool = False,
        error: Exception | None = None,
        block: bool = False,
    ) -> None:
        self.result = result or TranscribeResult(
            output_paths=(Path("/tmp/out.srt"),),
            text="Bonjour",
            segments=(Segment(1, 0.0, 1.0, "Bonjour"),),
            language="fr",
            cost_usd=0.000123,
            provider=Provider.OPENROUTER,
            model=OPENROUTER_MODEL,
            duration_s=1.0,
        )
        self.cancel = cancel
        self.error = error
        self.block = block
        self.request = None
        self.cancel_token = None
        self.started = threading.Event()

    def transcribe(
        self, request, *, on_progress=None, on_log=None, cancel=None
    ):
        self.request = request
        self.cancel_token = cancel
        on_progress(
            ProgressUpdate("transcribing", 30.0, 120.0, "Tranche 1/4")
        )
        on_log("info", "message de test")
        self.started.set()
        if self.block:
            while not cancel.is_cancelled():
                time.sleep(0.01)
            raise CancelledError()
        if self.cancel:
            cancel.cancel()
            raise CancelledError()
        if self.error:
            raise self.error
        return self.result


def _ready_window(
    qtbot,
    app_settings: AppSettings,
    tmp_path: Path,
    *,
    service: FakeService | None = None,
    dialogs: FakeDialogs | None = None,
    key: str = "sk-test",
) -> tuple[MainWindow, FakeService, FakeDialogs]:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x")
    fake = service or FakeService()
    dialogs = dialogs or FakeDialogs()
    window = MainWindow(
        settings=app_settings,
        key_store=MemoryStore(key),
        dialogs=dialogs,
        service_factory=lambda request: fake,
    )
    qtbot.addWidget(window)
    window.set_input_path(source)
    window.api_key_edit.setText(key)
    return window, fake, dialogs


def test_launch_requires_file(
    qtbot, app_settings: AppSettings
) -> None:
    created: list[object] = []

    def factory(request):
        created.append(request)
        return FakeService()

    window = _window(app_settings, service_factory=factory)
    qtbot.addWidget(window)
    window.start_transcription()
    assert created == []
    assert window.source_error.isVisibleTo(window) is True


def test_missing_output_dir_is_inline_error(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    window, fake, _ = _ready_window(qtbot, app_settings, tmp_path)
    window.output_edit.setText(str(tmp_path / "absent"))
    window.start_transcription()
    assert window.output_error.isVisibleTo(window) is True
    assert fake.request is None


def test_missing_format_is_inline_error(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    window, fake, _ = _ready_window(qtbot, app_settings, tmp_path)
    window.srt_checkbox.setChecked(False)
    window.txt_checkbox.setChecked(False)
    window.start_transcription()
    assert window.formats_error.isVisibleTo(window) is True
    assert fake.request is None


def test_missing_key_is_inline_error(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x")
    fake = FakeService()
    window = MainWindow(
        settings=app_settings,
        key_store=MemoryStore(),
        dialogs=FakeDialogs(),
        service_factory=lambda request: fake,
    )
    qtbot.addWidget(window)
    window.set_input_path(source)
    window.api_key_edit.clear()
    window.start_transcription()
    assert window.api_error.isVisibleTo(window) is True
    assert "Clé OpenRouter" in window.api_error.text()
    assert fake.request is None


def test_overwrite_refusal_does_not_start(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x")
    (tmp_path / "source.srt").write_text("ancien", encoding="utf-8")
    fake = FakeService()
    dialogs = FakeDialogs(overwrite=False)
    window = MainWindow(
        settings=app_settings,
        key_store=MemoryStore("sk-test"),
        dialogs=dialogs,
        service_factory=lambda request: fake,
    )
    qtbot.addWidget(window)
    window.set_input_path(source)
    window.start_transcription()
    assert dialogs.overwrite_calls == [(tmp_path / "source.srt",)]
    assert fake.request is None
    assert "conservés" in window.status_label.text()
    assert (tmp_path / "source.srt").read_text(encoding="utf-8") == "ancien"


def test_overwrite_accepted_sets_request_flag(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x")
    (tmp_path / "source.srt").write_text("ancien", encoding="utf-8")
    fake = FakeService()
    dialogs = FakeDialogs(overwrite=True)
    window = MainWindow(
        settings=app_settings,
        key_store=MemoryStore("sk-test"),
        dialogs=dialogs,
        service_factory=lambda request: fake,
    )
    qtbot.addWidget(window)
    window.set_input_path(source)
    window.start_transcription()
    qtbot.waitUntil(lambda: window.launch_button.isEnabled(), timeout=3000)
    assert fake.request is not None
    assert fake.request.overwrite is True


def test_progress_determinate_and_indeterminate(
    qtbot, app_settings: AppSettings
) -> None:
    window = _window(app_settings)
    qtbot.addWidget(window)
    window._task_started = time.monotonic() - 10.0
    window.on_worker_progress(
        ProgressUpdate("transcribing", 30.0, 120.0, "Tranche 1/4")
    )
    assert window.progress_bar.maximum() == 1000
    assert window.progress_bar.value() == 250
    assert "25 %" in window.phase_label.text()
    assert "00:30" in window.phase_label.text()
    assert "02:00" in window.phase_label.text()
    assert "ETA" in window.elapsed_label.text()

    window.on_worker_progress(
        ProgressUpdate("extracting", detail="Extraction audio")
    )
    assert window.progress_bar.maximum() == 0
    assert "Extraction" in window.phase_label.text()


def test_writing_phase_disables_cancel(
    qtbot, app_settings: AppSettings
) -> None:
    window = _window(app_settings)
    qtbot.addWidget(window)
    window._running = True
    window.cancel_button.setEnabled(True)
    window.on_worker_progress(
        ProgressUpdate("writing", detail="Écriture des fichiers")
    )
    assert window.cancel_button.isEnabled() is False
    assert window.progress_bar.maximum() == 0


def test_cancel_calls_token_and_shows_pending(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    fake = FakeService(block=True)
    window, _, _ = _ready_window(
        qtbot, app_settings, tmp_path, service=fake
    )
    window.start_transcription()
    assert fake.started.wait(timeout=3)
    window.cancel_transcription()
    assert fake.cancel_token is not None
    assert fake.cancel_token.is_cancelled() is True
    assert "Annulation" in window.status_label.text()
    assert window.cancel_button.isEnabled() is False
    qtbot.waitUntil(lambda: window.launch_button.isEnabled(), timeout=3000)
    assert "annulée" in window.status_label.text()


def test_finished_updates_result_and_reenables(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    fake = FakeService()
    window, _, _ = _ready_window(
        qtbot, app_settings, tmp_path, service=fake
    )
    window.start_transcription()
    qtbot.waitUntil(lambda: window.launch_button.isEnabled(), timeout=3000)
    assert "terminée" in window.status_label.text()
    assert "0.000123" in window.cost_label.text()
    assert window.open_folder_button.isEnabled() is True
    assert "message de test" in window.log_view.toPlainText()


def test_failed_shows_dialog(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    fake = FakeService(error=TranscribeError("échec", detail="détail"))
    window, _, dialogs = _ready_window(
        qtbot, app_settings, tmp_path, service=fake
    )
    window.start_transcription()
    qtbot.waitUntil(lambda: window.launch_button.isEnabled(), timeout=3000)
    assert dialogs.errors
    assert dialogs.errors[0][1] == "échec"
    assert "détail" in dialogs.errors[0][2]


def test_key_never_appears_in_log(
    qtbot, app_settings: AppSettings, tmp_path: Path
) -> None:
    secret = "sk-or-very-secret"
    fake = FakeService()
    window, _, _ = _ready_window(
        qtbot, app_settings, tmp_path, service=fake, key=secret
    )
    window.start_transcription()
    qtbot.waitUntil(lambda: window.launch_button.isEnabled(), timeout=3000)
    assert secret not in window.log_view.toPlainText()
