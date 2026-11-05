import logging
import logging.handlers
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from ecotranscribe.core.config import OPENROUTER_MODEL
from ecotranscribe.gui import logging_setup, settings as settings_module
from ecotranscribe.gui.settings import (
    AppSettings,
    EnvStore,
    KeyringStore,
    MemoryStore,
)


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    )


def test_defaults(tmp_path: Path) -> None:
    app = _settings(tmp_path)
    assert app.model == OPENROUTER_MODEL
    assert app.language == "fr"
    assert app.formats == {"srt", "txt"}
    assert app.remember_api_key is True
    assert app.log_visible is False
    assert app.output_dir == ""
    assert app.recent_models == []


def test_round_trip(tmp_path: Path) -> None:
    app = _settings(tmp_path)
    app.model = "mistralai/other"
    app.language = "en"
    app.formats = {"txt"}
    app.remember_api_key = False
    app.log_visible = True
    app.output_dir = str(tmp_path / "out")
    app.last_input_dir = str(tmp_path)
    app.add_recent_model("a")
    app.save()

    reloaded = _settings(tmp_path)
    assert reloaded.model == "mistralai/other"
    assert reloaded.language == "en"
    assert reloaded.formats == {"txt"}
    assert reloaded.remember_api_key is False
    assert reloaded.log_visible is True
    assert reloaded.output_dir == str(tmp_path / "out")
    assert reloaded.last_input_dir == str(tmp_path)
    assert reloaded.recent_models == ["a"]


def test_recent_models_dedupe_and_limit(tmp_path: Path) -> None:
    app = _settings(tmp_path)
    for model in ["a", "b", "c", "d", "e", "f"]:
        app.add_recent_model(model)
    assert app.recent_models == ["f", "e", "d", "c", "b"]
    app.add_recent_model("d")
    assert app.recent_models == ["d", "f", "e", "c", "b"]


def test_memory_store() -> None:
    store = MemoryStore()
    assert store.get() is None
    store.set("secret")
    assert store.get() == "secret"
    store.delete()
    assert store.get() is None


def test_env_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert EnvStore().get() == "from-env"
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert EnvStore().get() is None


class FakeKeyring:
    def __init__(self, *, fail: bool = False, stored: str | None = None) -> None:
        self.fail = fail
        self.stored = stored
        self.set_calls: list[tuple[str, str, str]] = []
        self.delete_calls: list[tuple[str, str]] = []

    def get_password(self, service: str, user: str):
        if self.fail:
            raise RuntimeError("trousseau verrouillé")
        return self.stored

    def set_password(self, service: str, user: str, key: str) -> None:
        if self.fail:
            raise RuntimeError("trousseau verrouillé")
        self.set_calls.append((service, user, key))

    def delete_password(self, service: str, user: str) -> None:
        self.delete_calls.append((service, user))


def test_keyring_store_falls_back_to_env_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    monkeypatch.setattr(
        settings_module, "_keyring_module", lambda: FakeKeyring(fail=True)
    )
    assert KeyringStore().get() == "env-key"


def test_keyring_store_reads_keyring_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    fake = FakeKeyring(stored="ring-key")
    monkeypatch.setattr(settings_module, "_keyring_module", lambda: fake)
    store = KeyringStore()
    assert store.get() == "ring-key"
    store.set("new-key")
    assert fake.set_calls == [("ecotranscribe", "openrouter", "new-key")]
    store.delete()
    assert fake.delete_calls == [("ecotranscribe", "openrouter")]


def test_keyring_error_does_not_log_secret(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        settings_module, "_keyring_module", lambda: FakeKeyring(fail=True)
    )
    with caplog.at_level(logging.WARNING, logger="ecotranscribe"):
        KeyringStore().get()
    assert "trousseau" in caplog.text.lower()
    assert "sk-or" not in caplog.text


def test_configure_logging_writes_utf8_and_rotates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(logging_setup, "config_dir", lambda: tmp_path)
    path = logging_setup.configure_logging(log_dir=tmp_path)
    logger = logging.getLogger("ecotranscribe")
    logger.info("accentué — test")
    for handler in logger.handlers:
        handler.flush()

    assert path == tmp_path / "ecotranscribe.log"
    assert "accentué" in path.read_text(encoding="utf-8")
    handler = next(
        item
        for item in logger.handlers
        if isinstance(item, logging.handlers.RotatingFileHandler)
    )
    assert handler.maxBytes == 1_000_000
    assert handler.backupCount == 3


def test_log_file_path_uses_config_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(logging_setup, "config_dir", lambda: tmp_path)
    assert logging_setup.log_file_path() == tmp_path / "ecotranscribe.log"
