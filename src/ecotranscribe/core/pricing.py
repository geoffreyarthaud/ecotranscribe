"""Tarifs OpenRouter des modèles de transcription."""

from __future__ import annotations

import math
from typing import cast

SECONDS_PER_HOUR = 3600.0


def parse_hourly_price(payload: object) -> float | None:
    """Extrait le tarif horaire le plus bas d'une réponse d'endpoints.

    Pour les modèles STT, ``pricing.prompt`` est exprimé en dollars par
    seconde d'audio. Une valeur absente, non numérique, nulle ou infinie est
    ignorée. Retourne ``None`` si aucun tarif exploitable n'est présent.
    """
    if not isinstance(payload, dict):
        return None
    data = cast("dict[str, object]", payload).get("data")
    if not isinstance(data, dict):
        return None
    endpoints = cast("dict[str, object]", data).get("endpoints")
    if not isinstance(endpoints, list):
        return None

    prices: list[float] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            continue
        pricing = cast("dict[str, object]", endpoint).get("pricing")
        if not isinstance(pricing, dict):
            continue
        raw_price = cast("dict[str, object]", pricing).get("prompt")
        if not isinstance(raw_price, (int, float, str)):
            continue
        try:
            per_second = float(raw_price)
        except ValueError:
            continue
        if math.isfinite(per_second) and per_second > 0:
            prices.append(per_second)

    if not prices:
        return None
    return min(prices) * SECONDS_PER_HOUR


def format_hourly_price(price: float) -> str:
    """Formate un tarif horaire en dollars pour la liste des modèles."""
    return f"≈ ${price:.2f}/h"
