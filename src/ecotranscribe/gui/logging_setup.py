"""Configuration du journal applicatif avec rotation 1 Mo × 3."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths

from ..core.config import APP_NAME, APP_SLUG

_LOG_FILENAME = "ecotranscribe.log"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def _install_identity() -> None:
    QCoreApplication.setOrganizationName(APP_SLUG)
    QCoreApplication.setApplicationName(APP_NAME)


def config_dir() -> Path:
    """Dossier de données de l'application, créé si nécessaire."""
    _install_identity()
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    path = Path(location) if location else Path.home() / ".ecotranscribe"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_file_path() -> Path:
    return config_dir() / _LOG_FILENAME


def configure_logging(log_dir: Path | None = None) -> Path:
    """Installe un handler rotatif idempotent et retourne le chemin du journal."""
    directory = Path(log_dir) if log_dir is not None else config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _LOG_FILENAME

    logger = logging.getLogger("ecotranscribe")
    logger.setLevel(logging.INFO)

    for handler in list(logger.handlers):
        if not isinstance(handler, logging.handlers.RotatingFileHandler):
            continue
        if Path(handler.baseFilename).resolve() == path.resolve():
            return path
        logger.removeHandler(handler)
        handler.close()

    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
    )
    logger.addHandler(handler)
    return path
