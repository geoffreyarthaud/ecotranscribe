from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

from ecotranscribe.gui.catalog import (
    GitHubCatalogClient,
    read_catalog_cache,
    write_catalog_cache,
)


class FakeReply(QObject):
    finished = Signal()

    def __init__(
        self,
        payload: bytes = b"",
        *,
        error: QNetworkReply.NetworkError = QNetworkReply.NetworkError.NoError,
    ) -> None:
        super().__init__()
        self._payload = payload
        self._error = error
        self.deleted = False

    def error(self) -> QNetworkReply.NetworkError:
        return self._error

    def errorString(self) -> str:
        return "fake error"

    def readAll(self) -> bytes:
        return self._payload

    def deleteLater(self) -> None:
        self.deleted = True


class FakeManager:
    def __init__(self, reply: FakeReply) -> None:
        self.reply = reply
        self.requests: list[QNetworkRequest] = []

    def get(self, request: QNetworkRequest) -> FakeReply:
        self.requests.append(request)
        return self.reply


def _catalog(*models: str) -> bytes:
    return json.dumps({"schema": 1, "models": list(models)}).encode("utf-8")


def test_client_emits_cache_then_remote_and_writes_cache(qtbot, tmp_path) -> None:
    cache = tmp_path / "models.json"
    cache.write_text(
        json.dumps({"schema": 1, "models": ["cached/model"]}),
        encoding="utf-8",
    )
    reply = FakeReply(_catalog("remote/one", "remote/two"))
    manager = FakeManager(reply)
    client = GitHubCatalogClient(  # type: ignore[arg-type]
        cache_file=cache, manager=manager
    )
    received: list[tuple[str, ...]] = []
    client.models_ready.connect(received.append)

    client.start()
    assert received == [("cached/model",)]
    assert len(manager.requests) == 1

    reply.finished.emit()

    assert received == [
        ("cached/model",),
        ("remote/one", "remote/two"),
    ]
    assert read_catalog_cache(cache) == ("remote/one", "remote/two")
    assert reply.deleted is True


def test_client_keeps_cache_on_invalid_payload(qtbot, tmp_path) -> None:
    cache = tmp_path / "models.json"
    cache.write_text(
        json.dumps({"schema": 1, "models": ["cached/model"]}),
        encoding="utf-8",
    )
    reply = FakeReply(b"not json")
    client = GitHubCatalogClient(  # type: ignore[arg-type]
        cache_file=cache, manager=FakeManager(reply)
    )
    received: list[tuple[str, ...]] = []
    client.models_ready.connect(received.append)

    client.start()
    reply.finished.emit()

    assert received == [("cached/model",)]
    assert read_catalog_cache(cache) == ("cached/model",)


def test_client_ignores_network_error(qtbot, tmp_path) -> None:
    cache = tmp_path / "models.json"
    reply = FakeReply(
        _catalog("remote/one"),
        error=QNetworkReply.NetworkError.ConnectionRefusedError,
    )
    client = GitHubCatalogClient(  # type: ignore[arg-type]
        cache_file=cache, manager=FakeManager(reply)
    )
    received: list[tuple[str, ...]] = []
    client.models_ready.connect(received.append)

    client.start()
    reply.finished.emit()

    assert received == []
    assert not cache.exists()


def test_cache_helpers_ignore_invalid_content(tmp_path) -> None:
    cache = tmp_path / "models.json"
    write_catalog_cache(cache, _catalog("cached/model"))
    assert read_catalog_cache(cache) == ("cached/model",)

    cache.write_text("not json", encoding="utf-8")
    assert read_catalog_cache(cache) is None
    assert read_catalog_cache(tmp_path / "absent.json") is None
