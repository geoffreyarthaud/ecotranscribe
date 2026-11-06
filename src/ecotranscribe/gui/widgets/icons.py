"""Icônes Qt dessinées à la volée, sans asset externe."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication


def gear_icon(size: int = 22, color: QColor | None = None) -> QIcon:
    """Retourne une roue dentée monochrome adaptée au thème courant."""
    if color is None:
        app = QApplication.instance()
        if app is not None:
            color = app.palette().color(QPalette.ColorRole.ButtonText)
        else:
            color = QColor("#3A3A3A")

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    center = QPointF(32, 32)
    for index in range(8):
        painter.save()
        painter.translate(center)
        painter.rotate(index * 45)
        painter.drawRoundedRect(QRectF(-4, -29, 8, 12), 2, 2)
        painter.restore()
    painter.drawEllipse(center, 20, 20)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    painter.drawEllipse(center, 8, 8)
    painter.end()
    return QIcon(
        pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    )
