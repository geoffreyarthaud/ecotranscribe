from __future__ import annotations

import pytest

from ecotranscribe.core.pricing import format_hourly_price, parse_hourly_price


def test_parse_hourly_price_uses_cheapest_endpoint() -> None:
    payload = {
        "data": {
            "endpoints": [
                {"pricing": {"prompt": "0.0000666667"}},
                {"pricing": {"prompt": "0.0000733333"}},
                {"pricing": {"prompt": "0.0000583333"}},
            ]
        }
    }

    assert parse_hourly_price(payload) == pytest.approx(0.21)


def test_parse_hourly_price_ignores_invalid_values() -> None:
    payload = {
        "data": {
            "endpoints": [
                {"pricing": {"prompt": None}},
                {"pricing": {"prompt": "abc"}},
                {"pricing": {"prompt": 0}},
                {"pricing": {"prompt": "-1"}},
                {"pricing": {"prompt": "inf"}},
                {"pricing": {"prompt": "nan"}},
                {"pricing": {}},
                {},
                "not-an-endpoint",
                {"pricing": {"prompt": "0.00005"}},
            ]
        }
    }

    assert parse_hourly_price(payload) == pytest.approx(0.18)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"data": None},
        {"data": {}},
        {"data": {"endpoints": None}},
        {"data": {"endpoints": []}},
    ],
)
def test_parse_hourly_price_returns_none_without_data(
    payload: object,
) -> None:
    assert parse_hourly_price(payload) is None


def test_format_hourly_price() -> None:
    assert format_hourly_price(0.24) == "≈ $0.24/h"
