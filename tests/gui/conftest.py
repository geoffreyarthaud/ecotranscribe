from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QSettings, QTimer, Signal

from ecotranscribe.core.errors import CancelledError, TranscribeError
from ecotranscribe.core.models import Provider, TranscribeResult
from ecotranscribe.gui.catalog import CatalogClient
from ecotranscribe.gui.pricing import PricingClient
from ecotranscribe.gui.settings import AppSettings


class FakeDialogs:
    def __init__(
        self,
        *,
        overwrite: bool = True,
        close_answer: bool = True,
        delete_key_answer: bool = True,
        discard_answer: bool = True,
    ) -> None:
        self.overwrite = overwrite
        self.close_answer = close_answer
        self.delete_key_answer = delete_key_answer
        self.discard_answer = discard_answer
        self.overwrite_calls: list[tuple[Path, ...]] = []
        self.close_calls = 0
        self.delete_calls = 0
        self.discard_calls: list[str] = []

    def confirm_overwrite(self, paths) -> bool:
        self.overwrite_calls.append(tuple(paths))
        return self.overwrite

    def confirm_close_while_running(self) -> bool:
        self.close_calls += 1
        return self.close_answer

    def confirm_delete_key(self) -> bool:
        self.delete_calls += 1
        return self.delete_key_answer

    def confirm_discard(self, message: str) -> bool:
        self.discard_calls.append(message)
        return self.discard_answer


class FakeDurationProbe(QObject):
    ready = Signal(object, object)
    failed = Signal(object, str)

    def __init__(self, value: float | None = 12.0) -> None:
        super().__init__()
        self.value = value
        self.paths: list[Path] = []

    def start(self, path: Path) -> None:
        self.paths.append(Path(path))
        QTimer.singleShot(
            0, lambda: self.ready.emit(Path(path), self.value)
        )

    def cancel(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


class FakePricingClient(PricingClient):
    def __init__(self) -> None:
        super().__init__()
        self.fetched: list[str] = []

    def fetch(self, model: str) -> None:
        self.fetched.append(model)


class FakeCatalogClient(CatalogClient):
    def __init__(self, models: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.models = models
        self.started = 0

    def start(self) -> None:
        self.started += 1
        if self.models:
            self.models_ready.emit(self.models)

    def emit(self, models: tuple[str, ...]) -> None:
        self.models = models
        self.models_ready.emit(models)


class FakeService:
    def __init__(
        self,
        *,
        result: TranscribeResult | None = None,
        error: TranscribeError | None = None,
        block: bool = False,
    ) -> None:
        self.result = result
        self.error = error
        self.block = block
        self.request = None
        self.started = threading.Event()
        self.release = threading.Event()

    def transcribe(
        self, request, *, on_progress=None, on_log=None, cancel=None
    ):
        self.request = request
        if self.block:
            self.started.set()
            self.release.wait(5)
            if cancel is not None:
                cancel.raise_if_cancelled()
        if self.error is not None:
            raise self.error
        if on_log is not None:
            on_log("info", "transcription terminée")
        if self.result is not None:
            return self.result
        return TranscribeResult(
            output_paths=(),
            text="",
            segments=(),
            language="fr",
            cost_usd=None,
            provider=Provider.OPENROUTER,
            model=request.model,
            duration_s=None,
        )


@pytest.fixture
def app_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    )
