"""Catalogue de modèles distant et cache local."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

from ..core.catalog import parse_catalog
from ..core.config import MODELS_CATALOG_URL
from .logging_setup import config_dir

logger = logging.getLogger("ecotranscribe")

_REQUEST_TIMEOUT_MS = 5_000
_CACHE_FILENAME = "models-cache.json"


class CatalogClient(QObject):
    """Interface d'un client de catalogue, injectable pour les tests."""

    models_ready = Signal(object)

    def start(self) -> None:
        raise NotImplementedError


def default_cache_path() -> Path:
    return config_dir() / _CACHE_FILENAME


def read_catalog_cache(path: Path) -> tuple[str, ...] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return parse_catalog(payload)


def write_catalog_cache(path: Path, payload: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    except OSError as exc:
        logger.debug("Écriture du cache du catalogue impossible : %s", exc)


class GitHubCatalogClient(CatalogClient):
    """Télécharge le catalogue public et conserve le dernier exemplaire valide."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        cache_file: Path | None = None,
        url: str = MODELS_CATALOG_URL,
        manager: QNetworkAccessManager | None = None,
    ) -> None:
        super().__init__(parent)
        self._cache_file = (
            Path(cache_file) if cache_file is not None else default_cache_path()
        )
        self._url = url
        self._manager = manager or QNetworkAccessManager(self)

    def start(self) -> None:
        cached = read_catalog_cache(self._cache_file)
        if cached is not None:
            self.models_ready.emit(cached)
        self._fetch()

    def _fetch(self) -> None:
        request = QNetworkRequest(QUrl(self._url))
        request.setTransferTimeout(_REQUEST_TIMEOUT_MS)
        request.setRawHeader(b"Accept", b"application/json")
        reply = self._manager.get(request)
        reply.finished.connect(
            lambda reply=reply: self._on_finished(reply)
        )

    def _on_finished(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                logger.debug(
                    "Catalogue de modèles indisponible : %s",
                    reply.errorString(),
                )
                return
            self.handle_payload(bytes(reply.readAll()))
        finally:
            reply.deleteLater()

    def handle_payload(self, payload: bytes) -> None:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            logger.debug("Catalogue de modèles illisible : %s", exc)
            return
        models = parse_catalog(data)
        if models is None:
            logger.debug("Catalogue de modèles invalide.")
            return
        write_catalog_cache(self._cache_file, payload)
        self.models_ready.emit(models)
