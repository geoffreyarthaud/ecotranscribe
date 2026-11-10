"""Résolution du proxy système, y compris PAC, pour les moteurs du cœur."""

from __future__ import annotations

import urllib.request

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import (
    QNetworkProxy,
    QNetworkProxyFactory,
    QNetworkProxyQuery,
)

_HTTP_TYPES = {
    QNetworkProxy.ProxyType.HttpProxy,
}
_SOCKS_TYPES = {
    QNetworkProxy.ProxyType.Socks5Proxy,
}


def resolve_proxy_for(url: str) -> str | None:
    """Retourne un proxy utilisable par urllib, ou None pour le défaut."""
    if urllib.request.getproxies():
        return None
    try:
        proxies = QNetworkProxyFactory.systemProxyForQuery(
            QNetworkProxyQuery(QUrl(url))
        )
    except Exception:
        return None
    for proxy in proxies:
        if proxy.type() in _HTTP_TYPES:
            return f"http://{proxy.hostName()}:{proxy.port()}"
        if proxy.type() in _SOCKS_TYPES:
            return f"socks5://{proxy.hostName()}:{proxy.port()}"
    return None
