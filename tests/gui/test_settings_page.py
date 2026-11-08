from __future__ import annotations

from pathlib import Path

from ecotranscribe.core.config import OPENROUTER_MODEL
from ecotranscribe.core.models import OutputFormat
from ecotranscribe.gui.pages.settings import SettingsPage
from ecotranscribe.gui.state import WizardState


def _state(tmp_path: Path) -> WizardState:
    source = tmp_path / "a.mp3"
    source.write_bytes(b"x")
    output = tmp_path / "out"
    output.mkdir()
    return WizardState(
        input_path=source,
        model=OPENROUTER_MODEL,
        language="fr",
        formats=frozenset({OutputFormat.SRT}),
        output_dir=output,
        output_dir_user_set=True,
    )


def test_settings_page_loads_state(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    page = SettingsPage()
    qtbot.addWidget(page)
    page.load(state)
    assert page.model_combo.currentData() == OPENROUTER_MODEL
    assert page.language_combo.currentData() == "fr"
    assert page.srt.isChecked() is True
    assert page.txt.isChecked() is False
    assert page.output_edit.text() == str(state.output_dir)


def test_settings_page_requires_one_format(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    page = SettingsPage()
    qtbot.addWidget(page)
    page.load(state)
    page.srt.setChecked(False)
    page.txt.setChecked(False)
    assert page.commit(state) is False
    assert page.formats_error.isVisibleTo(page)


def test_settings_page_commits_values(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    page = SettingsPage()
    qtbot.addWidget(page)
    page.load(state)
    page.add_model("custom/model")
    page.model_combo.setCurrentIndex(page._model_index("custom/model"))
    page.language_combo.setCurrentIndex(page.language_combo.findData(None))
    page.txt.setChecked(True)
    assert page.commit(state) is True
    assert state.model == "custom/model"
    assert state.language is None
    assert state.formats == frozenset({OutputFormat.SRT, OutputFormat.TXT})


def test_settings_page_invalid_output_offers_source(qtbot, tmp_path) -> None:
    state = _state(tmp_path)
    page = SettingsPage()
    qtbot.addWidget(page)
    page.load(state)
    page.output_edit.setText(str(tmp_path / "absent"))
    assert page.commit(state) is False
    assert "n'existe pas" in page.output_error.text()
    assert page.use_source.isVisibleTo(page)


def test_settings_page_shows_video_cost(qtbot, tmp_path) -> None:
    page = SettingsPage()
    qtbot.addWidget(page)
    page.load(_state(tmp_path))
    index = page._model_index(OPENROUTER_MODEL)
    assert index >= 0
    page.set_price(OPENROUTER_MODEL, 0.24)
    page.set_duration(3600)
    assert "≈ 0,24 $" in page.model_combo.itemText(index)
    page.set_duration(3450)
    assert "≈ 0,23 $" in page.model_combo.itemText(index)
    page.set_duration(None)
    assert "≈" not in page.model_combo.itemText(index)


def test_settings_page_model_choice_is_strict(qtbot, tmp_path) -> None:
    page = SettingsPage()
    qtbot.addWidget(page)
    page.load(_state(tmp_path))
    assert page.model_combo.isEditable() is False
