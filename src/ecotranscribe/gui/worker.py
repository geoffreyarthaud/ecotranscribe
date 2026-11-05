"""Worker QObject exécuté dans un QThread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ..core.errors import CancelledError, TranscribeError
from ..core.models import CancelToken, TranscribeRequest
from ..core.service import TranscribeService


class TranscribeWorker(QObject):
    progress = Signal(object)
    log = Signal(str)
    finished = Signal(object)
    failed = Signal(str, str)
    cancelled = Signal()

    def __init__(
        self,
        service: TranscribeService,
        request: TranscribeRequest,
        cancel: CancelToken,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._request = request
        self._cancel = cancel

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.transcribe(
                self._request,
                on_progress=self.progress.emit,
                on_log=self._on_log,
                cancel=self._cancel,
            )
        except CancelledError:
            self.cancelled.emit()
        except TranscribeError as exc:
            self.failed.emit(exc.user_message, exc.detail or "")
        except Exception as exc:  # garde-fou UI
            self.failed.emit(
                "La transcription a échoué.", str(exc)
            )
        else:
            self.finished.emit(result)

    def _on_log(self, level: str, message: str) -> None:
        if level in ("warning", "error"):
            message = f"{level.upper()} : {message}"
        self.log.emit(message)
