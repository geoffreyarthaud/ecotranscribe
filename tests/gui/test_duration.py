from __future__ import annotations

import threading
import time
from pathlib import Path

from ecotranscribe.gui.duration import DurationProbe


def test_ready_emits_duration(qtbot) -> None:
    probe = DurationProbe(probe=lambda path, cancel: 12.5)
    with qtbot.waitSignal(probe.ready, timeout=2000) as blocker:
        probe.start(Path("a.mp3"))
    assert blocker.args == [Path("a.mp3"), 12.5]


def test_failure_emits_failed(qtbot) -> None:
    def boom(path: Path, cancel) -> float:
        raise RuntimeError("ffprobe cassé")

    probe = DurationProbe(probe=boom)
    with qtbot.waitSignal(probe.failed, timeout=2000) as blocker:
        probe.start(Path("a.mp3"))
    assert blocker.args[0] == Path("a.mp3")
    assert "ffprobe cassé" in blocker.args[1]


def test_none_is_forwarded_as_unavailable(qtbot) -> None:
    probe = DurationProbe(probe=lambda path, cancel: None)
    with qtbot.waitSignal(probe.ready, timeout=2000) as blocker:
        probe.start(Path("a.mp3"))
    assert blocker.args == [Path("a.mp3"), None]


def test_stale_result_is_ignored(qtbot) -> None:
    release = threading.Event()

    def probe(path: Path, cancel) -> float:
        if path.name == "a.mp3":
            release.wait(3)
            return 1.0
        return 2.0

    duration = DurationProbe(probe=probe)
    duration.start(Path("a.mp3"))
    with qtbot.waitSignal(duration.ready, timeout=2000) as blocker:
        duration.start(Path("b.mp3"))
    assert blocker.args == [Path("b.mp3"), 2.0]
    release.set()
    qtbot.wait(100)


def test_stale_same_path_result_is_ignored(qtbot) -> None:
    release = threading.Event()
    first_running = threading.Event()
    calls: list[Path] = []

    def probe(path: Path, cancel) -> float:
        calls.append(path)
        if len(calls) == 1:
            first_running.set()
            release.wait(3)
            return 1.0
        return 2.0

    duration = DurationProbe(probe=probe)
    seen: list[tuple[Path, float | None]] = []
    duration.ready.connect(lambda path, value: seen.append((path, value)))
    duration.start(Path("a.mp3"))
    assert first_running.wait(2)
    duration.start(Path("a.mp3"))
    qtbot.waitUntil(lambda: bool(seen), timeout=2000)
    assert seen == [(Path("a.mp3"), 2.0)]
    release.set()
    qtbot.wait(100)
    assert seen == [(Path("a.mp3"), 2.0)]


def test_invalid_value_emits_failed(qtbot) -> None:
    probe = DurationProbe(probe=lambda path, cancel: "pas un nombre")
    with qtbot.waitSignal(probe.failed, timeout=2000) as blocker:
        probe.start(Path("a.mp3"))
    assert blocker.args[0] == Path("a.mp3")
    assert "pas un nombre" in blocker.args[1]


def test_shutdown_is_bounded_and_retains_running_thread(qtbot) -> None:
    release = threading.Event()
    started = threading.Event()

    def probe(path: Path, cancel) -> float:
        started.set()
        release.wait(5)
        return 1.0

    duration = DurationProbe(probe=probe)
    duration.start(Path("a.mp3"))
    assert started.wait(2)
    begin = time.monotonic()
    duration.shutdown()
    elapsed = time.monotonic() - begin
    assert elapsed < 0.2
    release.set()
    qtbot.waitUntil(lambda: not duration._threads, timeout=2000)


def test_thread_registry_is_cleared(qtbot) -> None:
    from ecotranscribe.gui import duration as module

    probe = module.DurationProbe(probe=lambda path, cancel: 1.0)
    with qtbot.waitSignal(probe.ready, timeout=2000):
        probe.start(Path("a.mp3"))
    qtbot.waitUntil(lambda: not module._ACTIVE_THREADS, timeout=2000)
