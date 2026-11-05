from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from ecotranscribe.gui.settings import AppSettings


class FakeDialogs:
    def __init__(
        self,
        *,
        overwrite: bool = True,
        close_answer: bool = False,
    ) -> None:
        self.overwrite = overwrite
        self.close_answer = close_answer
        self.overwrite_calls: list[tuple[Path, ...]] = []
        self.errors: list[tuple[str, str, str]] = []
        self.infos: list[tuple[str, str]] = []

    def confirm_overwrite(self, paths) -> bool:
        self.overwrite_calls.append(tuple(paths))
        return self.overwrite

    def show_error(self, title: str, message: str, detail: str) -> None:
        self.errors.append((title, message, detail))

    def show_info(self, title: str, message: str) -> None:
        self.infos.append((title, message))

    def confirm_close_while_running(self) -> bool:
        return self.close_answer


@pytest.fixture
def app_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    )
