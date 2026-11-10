"""Résolution du proxy système, y compris PAC, pour les moteurs du cœur."""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import (
    QNetworkProxy,
    QNetworkProxyFactory,
    QNetworkProxyQuery,
)

logger = logging.getLogger("ecotranscribe")


def resolve_proxy_for(url: str) -> str | None:
    """Retourne un proxy utilisable par urllib, ou None pour le défaut."""
    scheme = urllib.parse.urlsplit(url).scheme
    if urllib.request.getproxies().get(scheme):
        return None
    try:
        proxies = QNetworkProxyFactory.systemProxyForQuery(
            QNetworkProxyQuery(QUrl(url))
        )
    except Exception as exc:
        logger.debug(
            "Résolution du proxy PAC impossible (%s).",
            type(exc).__name__,
        )
        return None
    for proxy in proxies:
        if proxy.type() == QNetworkProxy.ProxyType.HttpProxy:
            return f"http://{proxy.hostName()}:{proxy.port()}"
    return None
