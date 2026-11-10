from __future__ import annotations

import logging

from PySide6.QtNetwork import QNetworkProxy, QNetworkProxyFactory

from ecotranscribe.gui import network


def _http_proxy(host: str = "pac.proxy", port: int = 8080) -> QNetworkProxy:
    return QNetworkProxy(QNetworkProxy.ProxyType.HttpProxy, host, port)


def _socks_proxy(host: str = "socks.proxy", port: int = 1080) -> QNetworkProxy:
    return QNetworkProxy(QNetworkProxy.ProxyType.Socks5Proxy, host, port)


def test_keeps_default_when_environment_proxy_present(monkeypatch) -> None:
    monkeypatch.setattr(
        network.urllib.request,
        "getproxies",
        lambda: {"https": "http://env.proxy:8080"},
    )
    called: list[object] = []

    def fake_query(query: object) -> list[QNetworkProxy]:
        called.append(query)
        return [_http_proxy()]

    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(fake_query),
    )

    assert network.resolve_proxy_for("https://openrouter.ai") is None
    assert called == []


def test_resolves_pac_when_only_no_proxy_is_set(monkeypatch) -> None:
    monkeypatch.setattr(
        network.urllib.request, "getproxies", lambda: {"no": "*"}
    )
    called: list[object] = []

    def fake_query(query: object) -> list[QNetworkProxy]:
        called.append(query)
        return [_http_proxy()]

    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(fake_query),
    )

    assert (
        network.resolve_proxy_for("https://openrouter.ai")
        == "http://pac.proxy:8080"
    )
    assert len(called) == 1


def test_ignores_http_proxy_for_https_url(monkeypatch) -> None:
    monkeypatch.setattr(
        network.urllib.request,
        "getproxies",
        lambda: {"http": "http://env.proxy:8080"},
    )
    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(lambda query: [_http_proxy()]),
    )

    assert (
        network.resolve_proxy_for("https://openrouter.ai")
        == "http://pac.proxy:8080"
    )


def test_uses_qt_when_no_environment_proxy(monkeypatch) -> None:
    monkeypatch.setattr(network.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(lambda query: [_http_proxy()]),
    )

    assert (
        network.resolve_proxy_for("https://openrouter.ai")
        == "http://pac.proxy:8080"
    )


def test_returns_none_when_qt_has_no_proxy(monkeypatch) -> None:
    monkeypatch.setattr(network.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(lambda query: []),
    )

    assert network.resolve_proxy_for("https://openrouter.ai") is None


def test_returns_none_when_qt_returns_no_proxy(monkeypatch) -> None:
    monkeypatch.setattr(network.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(
            lambda query: [QNetworkProxy(QNetworkProxy.ProxyType.NoProxy)]
        ),
    )

    assert network.resolve_proxy_for("https://openrouter.ai") is None


def test_ignores_socks_proxy(monkeypatch) -> None:
    monkeypatch.setattr(network.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(lambda query: [_socks_proxy()]),
    )

    assert network.resolve_proxy_for("https://openrouter.ai") is None


def test_skips_socks_and_uses_later_http_proxy(monkeypatch) -> None:
    monkeypatch.setattr(network.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(
            lambda query: [_socks_proxy(), _http_proxy("http.proxy")]
        ),
    )

    assert (
        network.resolve_proxy_for("https://openrouter.ai")
        == "http://http.proxy:8080"
    )


def test_returns_none_when_qt_raises(monkeypatch, caplog) -> None:
    monkeypatch.setattr(network.urllib.request, "getproxies", lambda: {})

    def fail(query: object) -> list[QNetworkProxy]:
        raise RuntimeError("boom at pac.proxy")

    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(fail),
    )

    with caplog.at_level(logging.DEBUG, logger="ecotranscribe"):
        assert network.resolve_proxy_for("https://openrouter.ai") is None

    assert "RuntimeError" in caplog.text
    assert "pac.proxy" not in caplog.text