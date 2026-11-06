"""Mesure asynchrone de la durée d'un média via ffprobe."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core.media import get_media_duration
from ..core.models import CancelToken

logger = logging.getLogger("ecotranscribe")

ProbeFn = Callable[[Path, CancelToken], float | None]


class _ProbeWorker(QObject):
    done = Signal(object, object)
    failed = Signal(object, str)

    def __init__(self, path: Path, probe: ProbeFn, cancel: CancelToken) -> None:
        super().__init__()
        self._path = path
        self._probe = probe
        self._cancel = cancel

    @Slot()
    def run(self) -> None:
        try:
            value = self._probe(self._path, self._cancel)
        except Exception as exc:
            logger.warning("Durée indisponible pour %s : %s", self._path, exc)
            self.failed.emit(self._path, str(exc))
        else:
            self.done.emit(self._path, value)


class DurationProbe(QObject):
    ready = Signal(object, object)
    failed = Signal(object, str)

    def __init__(
        self,
        probe: ProbeFn | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._probe = probe or _default_probe
        self._current: Path | None = None
        self._cancel: CancelToken | None = None
        self._threads: set[tuple[QThread, _ProbeWorker]] = set()

    def start(self, path: Path) -> None:
        self.cancel()
        path = Path(path)
        self._current = path
        cancel = CancelToken()
        thread = QThread()
        worker = _ProbeWorker(path, self._probe, cancel)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.done.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        job = (thread, worker)
        self._threads.add(job)
        thread.finished.connect(lambda: self._threads.discard(job))
        self._cancel = cancel
        thread.start()

    def cancel(self) -> None:
        if self._cancel is not None:
            self._cancel.cancel()
        self._cancel = None
        self._current = None

    def shutdown(self) -> None:
        self.cancel()
        for thread, _worker in list(self._threads):
            thread.quit()
            thread.wait(1000)

    def _on_done(self, path: object, value: object) -> None:
        path = Path(path)
        if self._current != path:
            return
        self._current = None
        self._cancel = None
        self.ready.emit(path, None if value is None else float(value))

    def _on_failed(self, path: object, message: str) -> None:
        path = Path(path)
        if self._current != path:
            return
        self._current = None
        self._cancel = None
        self.failed.emit(path, message)


def _default_probe(path: Path, cancel: CancelToken) -> float | None:
    return get_media_duration(path, cancel=cancel)