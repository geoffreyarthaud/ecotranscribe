"""Icône de l'application, chargée depuis les PNG multi-tailles embarqués."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    """Retourne l'icône multi-tailles (Dock, barre des tâches, fenêtres)."""
    assets = files("ecotranscribe.gui").joinpath("assets")
    icon = QIcon()
    # Qt/Cocoa prend la première taille disponible pour l'icône du Dock :
    # ajouter la plus grande en premier évite un Dock en 16×16.
    for size in reversed(ICON_SIZES):
        data = (assets / f"icon-{size}.png").read_bytes()
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            raise RuntimeError(f"Icône d'application illisible : icon-{size}.png")
        icon.addPixmap(pixmap)
    return icon


def app_icon_pixmap(size: int) -> QPixmap:
    """Retourne un pixmap net pour l'écran principal, Retina inclus."""
    screen = QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    return app_icon().pixmap(QSize(size, size), ratio)
