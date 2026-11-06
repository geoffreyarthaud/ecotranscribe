from __future__ import annotations

import threading
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