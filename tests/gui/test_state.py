from __future__ import annotations

from pathlib import Path

from ecotranscribe.core.models import OutputFormat
from ecotranscribe.gui.state import KeySource, PageId, WizardState


def test_defaults_are_empty() -> None:
    state = WizardState()
    assert state.input_path is None
    assert state.prompt_text is None
    assert state.key_source is KeySource.NONE
    assert state.formats == frozenset()
    assert state.key_return_page is PageId.HOME


def test_clear_result_keeps_task_context() -> None:
    state = WizardState(
        input_path=Path("a.mp3"),
        prompt_text="contexte",
        result=None,
        cancelled=True,
    )
    state.clear_result()
    assert state.input_path == Path("a.mp3")
    assert state.prompt_text == "contexte"
    assert state.cancelled is False


def test_reset_task_clears_source_and_keeps_preferences() -> None:
    state = WizardState(
        input_path=Path("a.mp3"),
        prompt_path=Path("a.prompt.md"),
        prompt_text="contexte",
        prompt_edited=True,
        prompt_error="erreur",
        duration_s=12.0,
        duration_path=Path("a.mp3"),
        duration_pending=True,
        session_key="sk-or-secret",
        key_source=KeySource.SESSION,
        model="model",
        language="fr",
        formats=frozenset({OutputFormat.SRT}),
        output_dir=Path("/tmp"),
        output_dir_user_set=True,
        key_return_page=PageId.SETTINGS,
    )
    state.reset_task()
    assert state.input_path is None
    assert state.prompt_path is None
    assert state.prompt_text is None
    assert state.prompt_edited is False
    assert state.prompt_error is None
    assert state.duration_s is None
    assert state.duration_pending is False
    assert state.session_key == "sk-or-secret"
    assert state.model == "model"
    assert state.formats == frozenset({OutputFormat.SRT})
    assert state.output_dir == Path("/tmp")
    assert state.key_return_page is PageId.HOME
