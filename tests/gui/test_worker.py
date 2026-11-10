from pathlib import Path

import pytest

from ecotranscribe.core.errors import CancelledError, TranscribeError
from ecotranscribe.core.models import (
    CancelToken,
    ProgressUpdate,
    Provider,
    Segment,
    TranscribeRequest,
    TranscribeResult,
)
from ecotranscribe.gui.worker import TranscribeWorker


class FakeService:
    def __init__(self, behaviour: str = "ok") -> None:
        self.behaviour = behaviour
        self.request = None
        self.cancel = None

    def transcribe(
        self, request, *, on_progress=None, on_log=None, cancel=None
    ):
        self.request = request
        self.cancel = cancel
        on_progress(ProgressUpdate("transcribing", 1.0, 2.0, "Tranche 1/2"))
        on_log("info", "message")
        on_log("warning", "attention")
        if self.behaviour == "cancel":
            raise CancelledError()
        if self.behaviour == "error":
            raise TranscribeError("échec utilisateur", detail="détail")
        if self.behaviour == "hint":
            raise TranscribeError(
                "échec utilisateur", detail="détail", hint="indice"
            )
        if self.behaviour == "unexpected":
            raise RuntimeError("boom")
        return TranscribeResult(
            output_paths=(Path("/tmp/out.srt"),),
            text="ok",
            segments=(Segment(1, 0.0, 1.0, "ok"),),
            language="fr",
            cost_usd=None,
            provider=Provider.OPENROUTER,
            model="m",
            duration_s=1.0,
        )


def _request(tmp_path: Path) -> TranscribeRequest:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x")
    return TranscribeRequest(
        input_path=source,
        provider=Provider.OPENROUTER,
        model="m",
        api_key="key",
    )


def test_worker_emits_progress_log_and_finished(
    qtbot, tmp_path: Path
) -> None:
    service = FakeService()
    worker = TranscribeWorker(
        lambda request: service, _request(tmp_path), CancelToken()
    )
    progress: list[ProgressUpdate] = []
    logs: list[str] = []
    finished: list[TranscribeResult] = []
    worker.progress.connect(progress.append)
    worker.log.connect(logs.append)
    worker.finished.connect(finished.append)

    worker.run()

    assert progress == [
        ProgressUpdate("transcribing", 1.0, 2.0, "Tranche 1/2")
    ]
    assert logs == ["message", "WARNING : attention"]
    assert len(finished) == 1
    assert finished[0].text == "ok"


def test_worker_maps_cancellation(qtbot, tmp_path: Path) -> None:
    worker = TranscribeWorker(
        lambda request: FakeService("cancel"),
        _request(tmp_path),
        CancelToken(),
    )
    seen: list[bool] = []
    worker.cancelled.connect(lambda: seen.append(True))
    worker.run()
    assert seen == [True]


def test_worker_maps_expected_error(qtbot, tmp_path: Path) -> None:
    worker = TranscribeWorker(
        lambda request: FakeService("error"),
        _request(tmp_path),
        CancelToken(),
    )
    failures: list[TranscribeError] = []
    worker.failed.connect(failures.append)
    worker.run()
    assert len(failures) == 1
    assert failures[0].user_message == "échec utilisateur"
    assert failures[0].detail == "détail"


def test_worker_maps_unexpected_error(qtbot, tmp_path: Path) -> None:
    worker = TranscribeWorker(
        lambda request: FakeService("unexpected"),
        _request(tmp_path),
        CancelToken(),
    )
    failures: list[TranscribeError] = []
    worker.failed.connect(failures.append)
    worker.run()
    assert len(failures) == 1
    assert failures[0].user_message == "La transcription a échoué."
    assert failures[0].detail == "boom"


def test_worker_preserves_error_hint(qtbot, tmp_path: Path) -> None:
    worker = TranscribeWorker(
        lambda request: FakeService("hint"),
        _request(tmp_path),
        CancelToken(),
    )
    failures: list[TranscribeError] = []
    worker.failed.connect(failures.append)
    worker.run()
    assert len(failures) == 1
    assert failures[0].hint == "indice"


def test_worker_factory_runs_on_worker_thread(
    qtbot, tmp_path: Path
) -> None:
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication

    main_thread = QApplication.instance().thread()
    seen: list[QThread] = []
    service = FakeService()

    def factory(request: TranscribeRequest) -> FakeService:
        seen.append(QThread.currentThread())
        return service

    worker = TranscribeWorker(factory, _request(tmp_path), CancelToken())
    finished: list[TranscribeResult] = []
    worker.finished.connect(finished.append)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    thread.start()
    qtbot.waitUntil(lambda: len(finished) == 1, timeout=3000)
    thread.wait(3000)

    assert seen
    assert seen[0] is not main_thread
