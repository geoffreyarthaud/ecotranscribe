"""Tarifs OpenRouter des modèles de transcription."""

from __future__ import annotations

import math
from decimal import Decimal
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


def format_video_cost(hourly_price: float, duration_s: float) -> str:
    """Estime le coût OpenRouter d'un média en dollars.

    Le tarif est exprimé par heure d'audio. Le montant est arrondi à deux
    chiffres significatifs et rendu avec la virgule décimale française.
    """
    cost = hourly_price * duration_s / SECONDS_PER_HOUR
    text = format(cost, "#.2g")
    if "e" in text or "E" in text:
        text = format(Decimal(text), "f")
    return f"≈ {text.replace('.', ',')} $"
