"""Réglages QSettings et accès à la clé OpenRouter."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QSettings, QStandardPaths

from ..core.config import OPENROUTER_MODEL

logger = logging.getLogger("ecotranscribe")


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


class AppSettings:
    """Accès typé aux clés QSettings documentées dans la spec."""

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    @property
    def geometry(self):
        return self._settings.value("window/geometry")

    @geometry.setter
    def geometry(self, value) -> None:
        self._settings.setValue("window/geometry", value)

    @property
    def last_input_dir(self) -> str:
        default = (
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.HomeLocation
            )
            or str(Path.home())
        )
        return str(self._settings.value("paths/last_input_dir", default))

    @last_input_dir.setter
    def last_input_dir(self, value: str) -> None:
        self._settings.setValue("paths/last_input_dir", value)

    @property
    def output_dir(self) -> str:
        return str(self._settings.value("paths/output_dir", "") or "")

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        self._settings.setValue("paths/output_dir", value)

    @property
    def model(self) -> str:
        return str(
            self._settings.value("transcription/model", OPENROUTER_MODEL)
            or OPENROUTER_MODEL
        )

    @model.setter
    def model(self, value: str) -> None:
        self._settings.setValue("transcription/model", value)

    @property
    def language(self) -> str:
        return str(
            self._settings.value("transcription/language", "fr") or ""
        )

    @language.setter
    def language(self, value: str) -> None:
        self._settings.setValue("transcription/language", value)

    @property
    def formats(self) -> set[str]:
        values = _string_list(
            self._settings.value("output/formats", ["srt", "txt"])
        )
        formats = {value for value in values if value in ("srt", "txt")}
        return formats or {"srt", "txt"}

    @formats.setter
    def formats(self, value: set[str]) -> None:
        self._settings.setValue("output/formats", sorted(value))

    @property
    def remember_api_key(self) -> bool:
        return bool(
            self._settings.value("api_key/remember", True, type=bool)
        )

    @remember_api_key.setter
    def remember_api_key(self, value: bool) -> None:
        self._settings.setValue("api_key/remember", value)

    @property
    def recent_models(self) -> list[str]:
        return _string_list(
            self._settings.value("models/recent", [])
        )

    @recent_models.setter
    def recent_models(self, value: list[str]) -> None:
        self._settings.setValue("models/recent", value)

    def add_recent_model(self, model: str) -> None:
        model = model.strip()
        if not model:
            return
        recent = [model]
        recent.extend(
            item for item in self.recent_models if item != model
        )
        self.recent_models = recent[:5]

    def save(self) -> None:
        self._settings.sync()


class KeyStore(Protocol):
    def get(self) -> str | None: ...

    def set(self, key: str) -> None: ...

    def delete(self) -> None: ...


def _keyring_module():
    import keyring

    return keyring


class KeyringStore:
    """Trousseau système ; l'appelant gère le fallback environnement."""

    service = "ecotranscribe"
    user = "openrouter"

    def get(self) -> str | None:
        return _keyring_module().get_password(self.service, self.user)

    def set(self, key: str) -> None:
        _keyring_module().set_password(self.service, self.user, key)

    def delete(self) -> None:
        _keyring_module().delete_password(self.service, self.user)


class MemoryStore:
    """Store en mémoire pour les tests et la session courante."""

    def __init__(
        self, initial: str | None = None, *, env_fallback: bool = False
    ) -> None:
        self._key = initial
        self._env_fallback = env_fallback

    def get(self) -> str | None:
        if self._key:
            return self._key
        if self._env_fallback:
            return os.environ.get("OPENROUTER_API_KEY")
        return None

    def set(self, key: str) -> None:
        self._key = key

    def delete(self) -> None:
        self._key = None



