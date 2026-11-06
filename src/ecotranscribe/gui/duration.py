"""Mesure asynchrone de la durée d'un média via ffprobe."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core.media import get_media_duration
from ..core.models import CancelToken

logger = logging.getLogger("ecotranscribe")

ProbeFn = Callable[[Path, CancelToken], float | None]

_SHUTDOWN_BUDGET_S = 0.1

# Registre module-level des threads vivants : garantit qu'un thread en cours
# n'est pas récupéré par le GC quand le DurationProbe est détruit ou que son
# budget d'arrêt est dépassé. Nettoyé par _ThreadReaper à la fin du thread.
_ACTIVE_THREADS: set[QThread] = set()


class _ThreadReaper(QObject):
    """Retire les threads terminés du registre, sur le thread graphique."""

    @Slot()
    def retire(self) -> None:
        thread = self.sender()
        if isinstance(thread, QThread):
            _ACTIVE_THREADS.discard(thread)


_reaper: _ThreadReaper | None = None


def _thread_reaper() -> _ThreadReaper:
    global _reaper
    if _reaper is None:
        _reaper = _ThreadReaper()
    return _reaper


class _ProbeThread(QThread):
    """Thread autoporteur : aucune ressource à détruire dans un autre thread."""

    done = Signal(int, object, object)
    failed = Signal(int, object, str)

    def __init__(
        self,
        request: int,
        path: Path,
        probe: ProbeFn,
        cancel: CancelToken,
    ) -> None:
        super().__init__()
        self._request = request
        self._path = path
        self._probe = probe
        self._cancel = cancel

    def run(self) -> None:
        try:
            value = self._probe(self._path, self._cancel)
        except Exception as exc:
            logger.warning("Durée indisponible pour %s : %s", self._path, exc)
            self.failed.emit(self._request, self._path, str(exc))
            return
        self.done.emit(self._request, self._path, value)


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
        self._request = 0
        self._pending: int | None = None
        self._cancel: CancelToken | None = None
        self._threads: set[QThread] = set()

    def start(self, path: Path) -> None:
        self.cancel()
        path = Path(path)
        self._request += 1
        request = self._request
        self._pending = request
        cancel = CancelToken()
        thread = _ProbeThread(request, path, self._probe, cancel)
        thread.done.connect(self._on_done)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(_thread_reaper().retire)
        thread.finished.connect(self._on_thread_finished)
        self._threads.add(thread)
        _ACTIVE_THREADS.add(thread)
        self._cancel = cancel
        thread.start()

    def cancel(self) -> None:
        if self._cancel is not None:
            self._cancel.cancel()
        self._cancel = None
        self._pending = None

    def shutdown(self) -> None:
        """Annule la sonde en cours et borne l'attente totale à 100 ms.

        Une sonde qui ignore le ``CancelToken`` continue de tourner : son
        QThread n'est ni tué ni récupéré, il reste retenu par le registre
        module-level jusqu'à la fin du thread.
        """
        self.cancel()
        threads = list(self._threads)
        if not threads:
            return
        for thread in threads:
            thread.quit()
        deadline = time.monotonic() + _SHUTDOWN_BUDGET_S
        for thread in threads:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            thread.wait(max(1, int(remaining * 1000)))

    @Slot(int, object, object)
    def _on_done(self, request: int, path: object, value: object) -> None:
        if request != self._pending:
            return
        path = Path(path)
        self._pending = None
        self._cancel = None
        if value is None:
            self.ready.emit(path, None)
            return
        try:
            duration = float(value)
        except (TypeError, ValueError) as exc:
            logger.warning("Durée invalide pour %s : %r", path, value)
            self.failed.emit(path, str(exc))
            return
        self.ready.emit(path, duration)

    @Slot(int, object, str)
    def _on_failed(self, request: int, path: object, message: str) -> None:
        if request != self._pending:
            return
        path = Path(path)
        self._pending = None
        self._cancel = None
        self.failed.emit(path, message)

    @Slot()
    def _on_thread_finished(self) -> None:
        thread = self.sender()
        if isinstance(thread, QThread):
            self._threads.discard(thread)


def _default_probe(path: Path, cancel: CancelToken) -> float | None:
    return get_media_duration(path, cancel=cancel)