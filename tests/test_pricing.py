from __future__ import annotations

import pytest

from ecotranscribe.core.pricing import format_video_cost, parse_hourly_price


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


@pytest.mark.parametrize(
    ("hourly_price", "duration_s", "expected"),
    [
        (0.24, 3600.0, "≈ 0,24 $"),
        (0.24, 3450.0, "≈ 0,23 $"),
        (0.24, 0.615, "≈ 0,000041 $"),
        (1.5, 3600.0, "≈ 1,5 $"),
    ],
)
def test_format_video_cost(
    hourly_price: float, duration_s: float, expected: str
) -> None:
    assert format_video_cost(hourly_price, duration_s) == expected


def test_parse_hourly_price_keeps_hourly_billed_models() -> None:
    payload = {
        "data": {
            "endpoints": [
                {"pricing": {"prompt": "0.1", "completion": "0"}},
            ]
        }
    }

    assert parse_hourly_price(payload) == pytest.approx(0.1)


def test_parse_hourly_price_ignores_token_priced_models() -> None:
    payload = {
        "data": {
            "endpoints": [
                {
                    "pricing": {
                        "prompt": "0.0000025",
                        "completion": "0.00001",
                    }
                },
            ]
        }
    }

    assert parse_hourly_price(payload) is None
