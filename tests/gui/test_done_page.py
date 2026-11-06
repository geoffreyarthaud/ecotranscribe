from __future__ import annotations

from pathlib import Path

from ecotranscribe.core.models import Provider, TranscribeResult
from ecotranscribe.gui.pages.done import DonePage


def _result(tmp_path: Path, cost: float | None = 0.001234) -> TranscribeResult:
    srt = tmp_path / "a.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nBonjour\n", encoding="utf-8")
    return TranscribeResult(
        output_paths=(srt,),
        text="Bonjour",
        segments=(),
        language="fr",
        cost_usd=cost,
        provider=Provider.OPENROUTER,
        model="model",
        duration_s=1.0,
    )


def test_done_page_shows_outputs_and_cost(qtbot, tmp_path) -> None:
    page = DonePage()
    qtbot.addWidget(page)
    page.show_result(_result(tmp_path), "a.mp3")
    assert "a.srt" in page.outputs_label.text()
    assert "$0.001234" in page.cost_label.text()
    assert page.open_button.isEnabled() is True


def test_done_page_cost_unavailable(qtbot, tmp_path) -> None:
    page = DonePage()
    qtbot.addWidget(page)
    page.show_result(_result(tmp_path, cost=None), "a.mp3")
    assert "indisponible" in page.cost_label.text()


def test_done_page_actions(qtbot, tmp_path) -> None:
    page = DonePage()
    qtbot.addWidget(page)
    page.show_result(_result(tmp_path), "a.mp3")
    with qtbot.waitSignal(page.open_folder_requested):
        page.open_button.click()
    with qtbot.waitSignal(page.new_transcription_requested):
        page.new_button.click()
