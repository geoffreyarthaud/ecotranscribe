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
    page.model_combo.setEditText("custom/model")
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


def test_settings_page_price_suffix(qtbot, tmp_path) -> None:
    page = SettingsPage()
    qtbot.addWidget(page)
    page.load(_state(tmp_path))
    page.set_price(OPENROUTER_MODEL, 1.5)
    index = page._model_index(OPENROUTER_MODEL)
    assert index >= 0
    assert "1.50" in page.model_combo.itemText(index)
