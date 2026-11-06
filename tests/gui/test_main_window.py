from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QPushButton

from ecotranscribe.core.config import OPENROUTER_MODEL
from ecotranscribe.core.errors import EngineUnavailableError, TranscribeError
from ecotranscribe.core.models import (
    OutputFormat,
    Provider,
    TranscribeResult,
)
from ecotranscribe.gui.main_window import MainWindow
from ecotranscribe.gui.settings import AppSettings, MemoryStore
from ecotranscribe.gui.state import PageId

from .conftest import (
    FakeDialogs,
    FakeDurationProbe,
    FakePricingClient,
    FakeService,
)


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "a.mp3"
    path.write_bytes(b"x")
    return path


def _result(tmp_path: Path) -> TranscribeResult:
    srt = tmp_path / "a.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nBonjour\n", encoding="utf-8")
    return TranscribeResult(
        output_paths=(srt,),
        text="Bonjour",
        segments=(),
        language="fr",
        cost_usd=0.001234,
        provider=Provider.OPENROUTER,
        model=OPENROUTER_MODEL,
        duration_s=1.0,
    )


def _window(
    qtbot,
    settings: AppSettings,
    *,
    key: str = "",
    duration: float = 12.0,
    service: FakeService | None = None,
    dialogs: FakeDialogs | None = None,
    store: MemoryStore | None = None,
):
    dialogs = dialogs or FakeDialogs()
    service = service or FakeService()
    probe = FakeDurationProbe(duration)
    store = store or MemoryStore(key)
    window = MainWindow(
        settings=settings,
        key_store=store,
        dialogs=dialogs,
        service_factory=lambda request: service,
        pricing_client=FakePricingClient(),
        duration_probe=probe,
    )
    qtbot.addWidget(window)
    window.show()
    return window, service, dialogs, probe, store


def test_home_without_key_shows_note(qtbot, app_settings, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    window, _service, _dialogs, _probe, _store = _window(qtbot, app_settings)
    assert window.current_page is PageId.HOME
    assert window.home_page.key_note.isVisibleTo(window.home_page)
    assert window.gear_button.isVisibleTo(window)
    assert not window.gear_button.icon().isNull()
    assert window.gear_button.text() == ""


def test_select_file_with_key_skips_key_page(qtbot, app_settings, tmp_path) -> None:
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret"
    )
    window.select_file(_source(tmp_path))
    assert window.current_page is PageId.PROMPT


def test_select_file_without_key_goes_to_key(qtbot, app_settings, tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    window, _service, _dialogs, _probe, store = _window(qtbot, app_settings)
    window.select_file(_source(tmp_path))
    assert window.current_page is PageId.KEY
    window.key_page.key_form.key_edit.setText("sk-or-secret")
    window.key_page.next_button.click()
    assert window.current_page is PageId.PROMPT
    assert store.get() == "sk-or-secret"


def test_prompt_detection_and_async_duration(qtbot, app_settings, tmp_path) -> None:
    source = _source(tmp_path)
    (tmp_path / "a.prompt.md").write_text("Contexte initial", encoding="utf-8")
    window, _service, _dialogs, probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", duration=42.0
    )
    window.select_file(source)
    qtbot.waitUntil(
        lambda: "00:42" in window.prompt_page.duration_label.text(),
        timeout=2000,
    )
    assert window.prompt_page.prompt_text() == "Contexte initial"
    assert "a.prompt.md" in window.prompt_page.prompt_source.text()
    assert probe.paths == [source]


def test_back_history_skips_key_when_key_exists(qtbot, app_settings, tmp_path) -> None:
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret"
    )
    window.select_file(_source(tmp_path))
    assert window.current_page is PageId.PROMPT
    window.prompt_page.back_button.click()
    assert window.current_page is PageId.HOME


def test_prompt_invalid_file_disables_next(qtbot, app_settings, tmp_path) -> None:
    source = _source(tmp_path)
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret"
    )
    window.select_file(source)
    source.unlink()
    window.prompt_page.next_button.click()
    assert window.current_page is PageId.PROMPT
    assert window.prompt_page.error_label.isVisibleTo(window.prompt_page)
    assert window.prompt_page.next_button.isEnabled() is False


def test_launch_runs_service_and_shows_done(qtbot, app_settings, tmp_path) -> None:
    source = _source(tmp_path)
    service = FakeService(result=_result(tmp_path))
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", service=service
    )
    window.select_file(source)
    window.prompt_page.next_button.click()
    window.settings_page.launch_button.click()
    qtbot.waitUntil(lambda: window.current_page is PageId.DONE, timeout=3000)
    qtbot.waitUntil(lambda: not window.is_busy, timeout=3000)
    assert service.request is not None
    assert service.request.api_key == "sk-or-secret"
    assert service.request.input_path == source
    assert service.request.provider is Provider.OPENROUTER
    assert "$0.001234" in window.done_page.cost_label.text()


def test_failure_is_inline_with_hint_and_detail(qtbot, app_settings, tmp_path) -> None:
    service = FakeService(
        error=TranscribeError("Échec", detail="Trace technique", hint="Vérifiez la clé.")
    )
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", service=service
    )
    window.select_file(_source(tmp_path))
    window.prompt_page.next_button.click()
    window.settings_page.launch_button.click()
    qtbot.waitUntil(lambda: window.progress_page.alert is not None, timeout=3000)
    qtbot.waitUntil(lambda: not window.is_busy, timeout=3000)
    assert window.current_page is PageId.PROGRESS
    assert "Vérifiez la clé" in window.progress_page.alert.text_label.text()
    assert window.progress_page.alert.detail_view.toPlainText() == "Trace technique"


def test_cancel_shows_neutral_state(qtbot, app_settings, tmp_path) -> None:
    service = FakeService(block=True)
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", service=service
    )
    window.select_file(_source(tmp_path))
    window.prompt_page.next_button.click()
    window.settings_page.launch_button.click()
    qtbot.waitUntil(service.started.is_set, timeout=2000)
    window.progress_page.cancel_button.click()
    service.release.set()
    qtbot.waitUntil(lambda: window.progress_page.alert is not None, timeout=3000)
    qtbot.waitUntil(lambda: not window.is_busy, timeout=3000)
    assert "annulée" in window.progress_page.alert.title_label.text()
    assert window.progress_page.alert.property("severity") == "info"


def test_overwrite_refusal_keeps_settings(qtbot, app_settings, tmp_path) -> None:
    source = _source(tmp_path)
    (tmp_path / "a.srt").write_text("ancien", encoding="utf-8")
    dialogs = FakeDialogs(overwrite=False)
    service = FakeService()
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", service=service, dialogs=dialogs
    )
    window.select_file(source)
    window.prompt_page.next_button.click()
    window.settings_page.launch_button.click()
    assert window.current_page is PageId.SETTINGS
    assert service.request is None
    assert "conservés" in window.settings_page.message.text()


def test_options_save_and_delete_key(qtbot, app_settings, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    window, _service, dialogs, _probe, store = _window(qtbot, app_settings)
    window.gear_button.click()
    assert window.current_page is PageId.OPTIONS
    window.options_page.key_form.key_edit.setText("sk-or-new")
    window.options_page.save_button.click()
    assert store.get() == "sk-or-new"
    window.options_page.delete_button.click()
    assert dialogs.delete_calls == 1
    assert store.get() is None


class _FailingDeleteStore(MemoryStore):
    def delete(self) -> None:
        raise RuntimeError("boom")


def test_remembering_session_key_saves_to_keyring(
    qtbot, app_settings, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    window, _service, _dialogs, _probe, store = _window(qtbot, app_settings)
    window.state.session_key = "sk-or-session"
    window._refresh_key_source()
    window._on_key_submitted("sk-or-session", True)
    assert store.get() == "sk-or-session"
    assert window.state.key_source.value == "keyring"


def test_delete_session_key_does_not_touch_keyring(
    qtbot, app_settings, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, store=_FailingDeleteStore("")
    )
    window._save_options_key("sk-or-session", remember=False)
    assert window.state.session_key == "sk-or-session"
    window.options_page.delete_button.click()
    assert window.state.session_key is None
    assert window.state.key_source.value == "none"


def test_prompt_change_requires_confirmation(qtbot, app_settings, tmp_path) -> None:
    first = _source(tmp_path)
    second = tmp_path / "b.mp3"
    second.write_bytes(b"x")
    dialogs = FakeDialogs(discard_answer=False)
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", dialogs=dialogs
    )
    window.select_file(first)
    window.prompt_page.prompt_edit.setPlainText("Prompt édité")
    window.select_file(second, confirm_prompt=True)
    assert window.state.input_path == first
    assert len(dialogs.discard_calls) == 1


def test_key_never_written_to_settings_or_log(qtbot, tmp_path) -> None:
    settings_path = tmp_path / "settings.ini"
    settings = AppSettings(
        QSettings(str(settings_path), QSettings.IniFormat)
    )
    service = FakeService(result=_result(tmp_path))
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, settings, key="sk-or-very-secret", service=service
    )
    window.select_file(_source(tmp_path))
    window.prompt_page.next_button.click()
    window.settings_page.launch_button.click()
    qtbot.waitUntil(lambda: window.current_page is PageId.DONE, timeout=3000)
    qtbot.waitUntil(lambda: not window.is_busy, timeout=3000)
    window.save_settings()
    assert "sk-or-very-secret" not in settings_path.read_text(encoding="utf-8")
    assert "sk-or-very-secret" not in window.progress_page.log.toPlainText()


def test_settings_are_captured_on_close(qtbot, tmp_path) -> None:
    settings_path = tmp_path / "settings.ini"
    settings = AppSettings(
        QSettings(str(settings_path), QSettings.IniFormat)
    )
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, settings, key="sk-or-secret"
    )
    window.select_file(_source(tmp_path))
    window.prompt_page.next_button.click()
    window.settings_page.model_combo.setEditText("custom/model")
    window.close()
    reloaded = AppSettings(
        QSettings(str(settings_path), QSettings.IniFormat)
    )
    assert reloaded.model == "custom/model"


def test_gear_is_disabled_while_running(qtbot, app_settings, tmp_path) -> None:
    service = FakeService(block=True)
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", service=service
    )
    window.select_file(_source(tmp_path))
    window.prompt_page.next_button.click()
    window.settings_page.launch_button.click()
    qtbot.waitUntil(service.started.is_set, timeout=2000)
    assert window.gear_button.isEnabled() is False
    service.release.set()
    qtbot.waitUntil(lambda: not window.is_busy, timeout=3000)


def test_back_after_key_entry_returns_home(qtbot, app_settings, tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    window, _service, _dialogs, _probe, _store = _window(qtbot, app_settings)
    window.select_file(_source(tmp_path))
    window.key_page.key_form.key_edit.setText("sk-or-secret")
    window.key_page.next_button.click()
    assert window.current_page is PageId.PROMPT
    window.prompt_page.back_button.click()
    assert window.current_page is PageId.HOME


def test_key_error_opens_correction_and_returns_settings(qtbot, app_settings, tmp_path) -> None:
    service = FakeService(error=EngineUnavailableError("Clé refusée"))
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", service=service
    )
    window.select_file(_source(tmp_path))
    window.prompt_page.next_button.click()
    window.settings_page.launch_button.click()
    qtbot.waitUntil(lambda: window.progress_page.alert is not None, timeout=3000)
    qtbot.waitUntil(lambda: not window.is_busy, timeout=3000)
    buttons = window.progress_page.alert.findChildren(QPushButton)
    edit = next(button for button in buttons if button.text() == "Modifier la clé")
    edit.click()
    assert window.current_page is PageId.KEY
    window.key_page.key_form.key_edit.setText("sk-or-new")
    window.key_page.next_button.click()
    assert window.current_page is PageId.SETTINGS


def test_close_while_running_waits_then_closes(qtbot, app_settings, tmp_path) -> None:
    service = FakeService(block=True)
    dialogs = FakeDialogs(close_answer=True)
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret", service=service, dialogs=dialogs
    )
    window.select_file(_source(tmp_path))
    window.prompt_page.next_button.click()
    window.settings_page.launch_button.click()
    qtbot.waitUntil(service.started.is_set, timeout=2000)
    window.close()
    assert dialogs.close_calls == 1
    service.release.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=3000)


def test_old_provider_widgets_are_gone(qtbot, app_settings) -> None:
    window, _service, _dialogs, _probe, _store = _window(
        qtbot, app_settings, key="sk-or-secret"
    )
    assert not hasattr(window, "provider_openrouter")
    assert not hasattr(window, "whisper_reason")
    assert not hasattr(window, "api_key_edit")
    assert not hasattr(window, "launch_button")
