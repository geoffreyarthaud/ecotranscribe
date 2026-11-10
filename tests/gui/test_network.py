from __future__ import annotations

from PySide6.QtNetwork import QNetworkProxy, QNetworkProxyFactory

from ecotranscribe.gui import network


def test_keeps_default_when_environment_proxy_present(monkeypatch) -> None:
    monkeypatch.setattr(
        network.urllib.request,
        "getproxies",
        lambda: {"https": "http://env.proxy:8080"},
    )
    called: list[object] = []

    def fake_query(query: object) -> list[QNetworkProxy]:
        called.append(query)
        return [
            QNetworkProxy(
                QNetworkProxy.ProxyType.HttpProxy, "pac.proxy", 8080
            )
        ]

    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(fake_query),
    )

    assert network.resolve_proxy_for("https://openrouter.ai") is None
    assert called == []


def test_uses_qt_when_no_environment_proxy(monkeypatch) -> None:
    monkeypatch.setattr(network.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(
        QNetworkProxyFactory,
        "systemProxyForQuery",
        staticmethod(
            lambda query: [
                QNetworkProxy(
                    QNetworkProxy.ProxyType.HttpProxy, "pac.proxy", 8080
                )
            ]
        ),
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
