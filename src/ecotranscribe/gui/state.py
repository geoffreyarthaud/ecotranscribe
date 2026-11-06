"""État interne de l'assistant de transcription."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ..core.errors import TranscribeError
from ..core.models import OutputFormat, TranscribeResult


class KeySource(str, Enum):
    NONE = "none"
    SESSION = "session"
    KEYRING = "keyring"
    ENV = "env"


class PageId(str, Enum):
    HOME = "home"
    KEY = "key"
    PROMPT = "prompt"
    SETTINGS = "settings"
    PROGRESS = "progress"
    DONE = "done"
    OPTIONS = "options"


@dataclass(slots=True)
class WizardState:
    input_path: Path | None = None
    prompt_path: Path | None = None
    prompt_text: str | None = None
    prompt_edited: bool = False
    prompt_error: str | None = None
    duration_s: float | None = None
    duration_path: Path | None = None
    duration_pending: bool = False
    session_key: str | None = None
    key_source: KeySource = KeySource.NONE
    model: str = ""
    language: str | None = None
    formats: frozenset[OutputFormat] = field(default_factory=frozenset)
    output_dir: Path | None = None
    output_dir_user_set: bool = False
    result: TranscribeResult | None = None
    error: TranscribeError | None = None
    cancelled: bool = False
    key_return_page: PageId = PageId.HOME

    def clear_result(self) -> None:
        self.result = None
        self.error = None
        self.cancelled = False

    def reset_task(self) -> None:
        self.input_path = None
        self.prompt_path = None
        self.prompt_text = None
        self.prompt_edited = False
        self.prompt_error = None
        self.duration_s = None
        self.duration_path = None
        self.duration_pending = False
        self.key_return_page = PageId.HOME
        self.clear_result()
