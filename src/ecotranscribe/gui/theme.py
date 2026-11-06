"""Thème Qt original inspiré des principes visuels du DSFR.

Aucun code, composant, logo ou asset du DSFR n'est utilisé. La police
Marianne est utilisée si elle est installée sur le système, sans être
embarquée ; Arial sert de repli. Les valeurs de couleur sont des références
visuelles issues de la documentation publique.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from string import Template

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QWidget


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    background: str
    surface: str
    surface_alt: str
    surface_contrast: str
    text: str
    text_title: str
    text_muted: str
    text_disabled: str
    border: str
    border_strong: str
    primary: str
    primary_hover: str
    primary_active: str
    primary_soft: str
    primary_softest: str
    on_primary: str
    error: str
    error_soft: str
    success: str
    success_soft: str
    warning: str
    warning_soft: str
    info: str
    info_soft: str
    focus: str


LIGHT = ThemeTokens(
    background="#FFFFFF", surface="#FFFFFF", surface_alt="#F6F6F6",
    surface_contrast="#EEEEEE", text="#3A3A3A", text_title="#161616",
    text_muted="#666666", text_disabled="#929292", border="#DDDDDD",
    border_strong="#3A3A3A", primary="#000091", primary_hover="#1212FF",
    primary_active="#2323FF", primary_soft="#E3E3FD",
    primary_softest="#F5F5FE", on_primary="#F5F5FE", error="#CE0500",
    error_soft="#FFF4F4", success="#18753C", success_soft="#DFFEE6",
    warning="#B34000", warning_soft="#FFF4F3", info="#0063CB",
    info_soft="#F4F6FF", focus="#000091",
)

DARK = ThemeTokens(
    background="#161616", surface="#1E1E1E", surface_alt="#242424",
    surface_contrast="#2A2A2A", text="#CECECE", text_title="#FFFFFF",
    text_muted="#929292", text_disabled="#666666", border="#353535",
    border_strong="#CECECE", primary="#8585F6", primary_hover="#B1B1F9",
    primary_active="#C6C6FB", primary_soft="#272747",
    primary_softest="#1B1B35", on_primary="#1B1B35", error="#FF5655",
    error_soft="#391C1C", success="#27A658", success_soft="#19271D",
    warning="#FC5D00", warning_soft="#361E19", info="#518FFF",
    info_soft="#1D2437", focus="#8585F6",
)


_QSS = Template(
    """
    QWidget {
        background: $background;
        color: $text;
        font-family: "Marianne", "Arial", "Helvetica Neue", "Liberation Sans", sans-serif;
        font-size: 16px;
    }
    QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget {
        background: $background;
    }
    QScrollArea { border: 0; }
    QLabel { background: transparent; }
    QLabel[role="pageTitle"] {
        color: $text_title; font-size: 28px; font-weight: 700;
    }
    QLabel[role="sectionTitle"] {
        color: $text_title; font-size: 20px; font-weight: 700;
    }
    QLabel[role="label"] { color: $text_title; font-size: 14px; font-weight: 500; }
    QLabel[role="muted"] { color: $text_muted; font-size: 14px; }
    QLabel[role="mention"] { color: $text_muted; font-size: 12px; }
    QLabel[role="error"] { color: $error; font-size: 14px; }
    QLabel[role="success"] { color: $success; font-size: 14px; }
    QLabel[role="badge"] {
        background: $primary_soft; color: $primary; font-size: 12px;
        padding: 2px 6px; border-radius: 0;
    }
    QPushButton {
        min-height: 40px; padding: 7px 15px; border-radius: 0;
        background: $surface; color: $primary; border: 2px solid $primary;
        font-weight: 500;
    }
    QPushButton:hover { background: $primary_soft; }
    QPushButton[variant="primary"] {
        background: $primary; color: $on_primary; border-color: $primary;
    }
    QPushButton[variant="primary"]:hover {
        background: $primary_hover; border-color: $primary_hover;
    }
    QPushButton[variant="primary"]:pressed {
        background: $primary_active; border-color: $primary_active;
    }
    QPushButton[variant="secondary"] {
        background: $surface; color: $primary; border-color: $primary;
    }
    QPushButton[variant="secondary"]:hover { background: $primary_soft; }
    QPushButton[variant="tertiary"] {
        background: transparent; color: $primary; border-color: transparent;
    }
    QPushButton[variant="tertiary"]:hover { background: $primary_soft; }
    QPushButton[variant="danger"] {
        background: transparent; color: $error; border-color: $error;
    }
    QPushButton[variant="danger"]:hover { background: $error_soft; }
    QPushButton:focus {
        background: $primary; color: $on_primary; border-color: $on_primary;
    }
    QPushButton[variant="primary"]:focus { border-color: $on_primary; }
    QPushButton[variant="secondary"]:focus {
        background: $primary; color: $on_primary; border-color: $on_primary;
    }
    QPushButton[variant="tertiary"]:focus {
        background: $primary_soft; color: $primary; border-color: $text_title;
    }
    QPushButton[variant="danger"]:focus {
        background: $error_soft; color: $error; border-color: $text_title;
    }
    QPushButton:disabled {
        background: $surface_contrast; color: $text_disabled;
        border-color: $surface_contrast;
    }
    QToolButton[variant="tertiary"] {
        background: transparent; color: $primary; border: 2px solid transparent;
        padding: 6px 10px; border-radius: 0; font-weight: 500;
    }
    QToolButton[variant="tertiary"]:hover { background: $primary_soft; }
    QToolButton[variant="tertiary"]:focus { border-color: $focus; }
    QLineEdit, QComboBox, QPlainTextEdit {
        background: $surface; color: $text; border: 1px solid $border_strong;
        border-radius: 0; padding: 8px 12px; min-height: 40px;
        selection-background-color: $primary; selection-color: $on_primary;
    }
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
        border: 2px solid $focus; padding: 7px 11px;
    }
    QLineEdit[state="error"], QComboBox[state="error"],
    QPlainTextEdit[state="error"] {
        border: 2px solid $error; padding: 7px 11px;
    }
    QLineEdit[role="path"] {
        background: transparent; border: 0; padding: 0;
        color: $text_muted; min-height: 0;
    }
    QComboBox QAbstractItemView {
        background: $surface; color: $text; border: 1px solid $border;
        selection-background-color: $primary; selection-color: $on_primary;
    }
    QCheckBox, QRadioButton { color: $text; spacing: 8px; }
    QFrame[role="card"] {
        background: $surface; border: 1px solid $border; border-radius: 0;
    }
    QFrame[role="card"][clickable="true"]:hover { border-color: $primary; }
    QFrame[role="card"][clickable="true"]:focus { border-color: $focus; }
    QFrame[role="alert"] {
        border-radius: 0; border-left: 4px solid $border; padding: 12px;
    }
    QFrame[role="alert"][severity="error"] {
        background: $error_soft; border-left-color: $error;
    }
    QFrame[role="alert"][severity="success"] {
        background: $success_soft; border-left-color: $success;
    }
    QFrame[role="alert"][severity="warning"] {
        background: $warning_soft; border-left-color: $warning;
    }
    QFrame[role="alert"][severity="info"] {
        background: $info_soft; border-left-color: $info;
    }
    QFrame[role="alert"][severity="error"] QLabel[role="alertTitle"] {
        color: $error;
    }
    QFrame[role="alert"][severity="success"] QLabel[role="alertTitle"] {
        color: $success;
    }
    QFrame[role="alert"][severity="warning"] QLabel[role="alertTitle"] {
        color: $warning;
    }
    QFrame[role="alert"][severity="info"] QLabel[role="alertTitle"] {
        color: $info;
    }
    QLabel[role="alertTitle"] { font-size: 16px; font-weight: 700; }
    QLabel[role="alertText"] { color: $text; font-size: 14px; }
    QPlainTextEdit[role="log"] {
        background: $surface_alt; border: 1px solid $border;
        font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace;
        font-size: 12px;
    }
    QProgressBar[role="transcription"] {
        background: $surface_contrast; border: 0; border-radius: 0;
        min-height: 8px; max-height: 8px;
    }
    QProgressBar[role="transcription"]::chunk {
        background: $primary; border-radius: 0;
    }
    QLabel[stepNumber="current"] {
        background: $primary; color: $on_primary; border-radius: 12px;
        min-width: 24px; max-width: 24px; min-height: 24px;
        max-height: 24px; font-size: 14px; font-weight: 700;
    }
    QLabel[stepNumber="done"] {
        background: $primary_soft; color: $primary; border-radius: 12px;
        min-width: 24px; max-width: 24px; min-height: 24px;
        max-height: 24px; font-size: 14px; font-weight: 700;
    }
    QLabel[stepNumber="future"] {
        background: $surface_contrast; color: $text_muted; border-radius: 12px;
        min-width: 24px; max-width: 24px; min-height: 24px;
        max-height: 24px; font-size: 14px; font-weight: 700;
    }
    QLabel[stepTitle="current"] {
        color: $text_title; font-size: 14px; font-weight: 700;
    }
    QLabel[stepTitle="done"] { color: $text_title; font-size: 14px; }
    QLabel[stepTitle="future"] { color: $text_muted; font-size: 14px; }
    QFrame[stepLine="done"] { background: $primary; min-height: 2px; max-height: 2px; }
    QFrame[stepLine="future"] { background: $border; min-height: 2px; max-height: 2px; }
    QToolTip {
        background: $surface_contrast; color: $text;
        border: 1px solid $border; padding: 4px;
    }
    """
)


def stylesheet(tokens: ThemeTokens) -> str:
    return _QSS.substitute(asdict(tokens))


def _palette(tokens: ThemeTokens) -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: tokens.background,
        QPalette.ColorRole.WindowText: tokens.text,
        QPalette.ColorRole.Base: tokens.surface,
        QPalette.ColorRole.AlternateBase: tokens.surface_alt,
        QPalette.ColorRole.Text: tokens.text,
        QPalette.ColorRole.Button: tokens.surface,
        QPalette.ColorRole.ButtonText: tokens.text,
        QPalette.ColorRole.Highlight: tokens.primary,
        QPalette.ColorRole.HighlightedText: tokens.on_primary,
        QPalette.ColorRole.Link: tokens.primary,
        QPalette.ColorRole.PlaceholderText: tokens.text_muted,
        QPalette.ColorRole.ToolTipBase: tokens.surface_contrast,
        QPalette.ColorRole.ToolTipText: tokens.text,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled, role, QColor(tokens.text_disabled)
        )
    return palette


def apply_theme(
    app: QApplication,
    scheme: Qt.ColorScheme | None = None,
) -> None:
    app.setStyle("Fusion")
    if scheme is None:
        scheme = QGuiApplication.styleHints().colorScheme()
    tokens = DARK if scheme == Qt.ColorScheme.Dark else LIGHT
    app.setPalette(_palette(tokens))
    app.setStyleSheet(stylesheet(tokens))


class ThemeManager(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._app = app
        QGuiApplication.styleHints().colorSchemeChanged.connect(self.apply)

    def apply(self, *_args: object) -> None:
        apply_theme(self._app)


def _repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def repolish(widget: QWidget) -> None:
    _repolish(widget)


def set_variant(widget: QWidget, value: str) -> None:
    widget.setProperty("variant", value)
    _repolish(widget)


def set_role(widget: QWidget, value: str) -> None:
    widget.setProperty("role", value)
    _repolish(widget)


def set_severity(widget: QWidget, value: str) -> None:
    widget.setProperty("severity", value)
    _repolish(widget)


def set_state(widget: QWidget, value: str) -> None:
    widget.setProperty("state", value)
    _repolish(widget)
