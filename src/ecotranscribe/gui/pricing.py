"""Récupération asynchrone des tarifs OpenRouter."""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

from ..core.config import OPENROUTER_MODELS_URL
from ..core.pricing import parse_hourly_price

logger = logging.getLogger("ecotranscribe")

_REQUEST_TIMEOUT_MS = 5_000


class PricingClient(QObject):
    """Interface d'un client de tarifs, injectable pour les tests."""

    price_ready = Signal(str, float)

    def fetch(self, model: str) -> None:
        raise NotImplementedError


class OpenRouterPricingClient(PricingClient):
    """Interroge l'API publique OpenRouter sans bloquer l'interface."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)

    def fetch(self, model: str) -> None:
        request = QNetworkRequest(
            QUrl(f"{OPENROUTER_MODELS_URL}/{model}/endpoints")
        )
        request.setTransferTimeout(_REQUEST_TIMEOUT_MS)
        request.setRawHeader(b"Accept", b"application/json")
        reply = self._manager.get(request)
        reply.finished.connect(
            lambda reply=reply, model=model: self._on_finished(model, reply)
        )

    def _on_finished(self, model: str, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                logger.debug(
                    "Tarif OpenRouter indisponible pour %s : %s",
                    model,
                    reply.errorString(),
                )
                return
            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            price = parse_hourly_price(payload)
            if price is not None:
                self.price_ready.emit(model, price)
        except (UnicodeDecodeError, ValueError) as exc:
            logger.debug(
                "Réponse de tarif OpenRouter illisible pour %s : %s",
                model,
                exc,
            )
        finally:
            reply.deleteLater()
