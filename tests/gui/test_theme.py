from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from ecotranscribe.gui.theme import DARK, LIGHT, ThemeTokens, apply_theme


def _luminance(value: str) -> float:
    raw = value.lstrip("#")
    channels = [int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("tokens", [LIGHT, DARK])
def test_text_contrast_is_accessible(tokens: ThemeTokens) -> None:
    assert _contrast(tokens.text, tokens.background) >= 4.5
    assert _contrast(tokens.text_title, tokens.background) >= 4.5
    assert _contrast(tokens.text_muted, tokens.background) >= 4.5
    assert _contrast(tokens.on_primary, tokens.primary) >= 4.5


@pytest.mark.parametrize("tokens", [LIGHT, DARK])
def test_semantic_and_focus_contrast(tokens: ThemeTokens) -> None:
    pairs = (
        (tokens.error, tokens.error_soft),
        (tokens.success, tokens.success_soft),
        (tokens.warning, tokens.warning_soft),
        (tokens.info, tokens.info_soft),
    )
    assert all(_contrast(fg, bg) >= 4.5 for fg, bg in pairs)
    assert _contrast(tokens.border_strong, tokens.background) >= 3.0
    assert _contrast(tokens.focus, tokens.background) >= 3.0


def test_apply_theme_sets_fusion_and_palette(qtbot) -> None:
    app = QApplication.instance()
    assert app is not None
    old_style_name = app.style().objectName()
    old_palette = QPalette(app.palette())
    old_qss = app.styleSheet()
    try:
        apply_theme(app, Qt.ColorScheme.Light)
        # A stylesheet wraps the active style in QStyleSheetStyle, whose
        # objectName/name are empty; clear it briefly to expose the base style.
        qss = app.styleSheet()
        assert qss
        app.setStyleSheet("")
        assert app.style().objectName().lower() == "fusion"
        app.setStyleSheet(qss)
        assert app.palette().color(QPalette.ColorRole.Window).name().lower() == LIGHT.background.lower()
        apply_theme(app, Qt.ColorScheme.Dark)
        assert app.palette().color(QPalette.ColorRole.Window).name().lower() == DARK.background.lower()
    finally:
        app.setStyle(old_style_name)
        app.setPalette(old_palette)
        app.setStyleSheet(old_qss)
