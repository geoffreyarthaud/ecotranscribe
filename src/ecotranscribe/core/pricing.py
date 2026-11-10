"""Tarifs OpenRouter des modèles de transcription."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import cast

SECONDS_PER_HOUR = 3600.0
# OpenRouter ne publie pas l'unité dans l'API endpoints. Les modèles facturés
# à l'heure (MAI-Transcribe) sont deux ordres de grandeur au-dessus des
# modèles facturés à la seconde (Voxtral, Whisper).
_HOURLY_PRICE_MIN = 0.01


def parse_hourly_price(payload: object) -> float | None:
    """Extrait le tarif horaire le plus bas d'une réponse d'endpoints.

    ``pricing.prompt`` est exprimé par seconde pour la plupart des modèles
    STT, mais par heure pour certains fournisseurs (Azure/MAI-Transcribe).
    L'unité n'étant pas exposée par l'API, un seuil sépare les deux familles.
    Les endpoints facturés aux tokens (``completion`` non nul) sont ignorés :
    leur coût dépend du texte produit, pas de la durée audio.
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
        raw_completion = cast("dict[str, object]", pricing).get(
            "completion", 0
        )
        try:
            completion = float(raw_completion)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            completion = 0.0
        if math.isfinite(completion) and completion > 0:
            continue

        raw_price = cast("dict[str, object]", pricing).get("prompt")
        if not isinstance(raw_price, (int, float, str)):
            continue
        try:
            unit_price = float(raw_price)
        except ValueError:
            continue
        if not (math.isfinite(unit_price) and unit_price > 0):
            continue
        hourly_price = (
            unit_price
            if unit_price >= _HOURLY_PRICE_MIN
            else unit_price * SECONDS_PER_HOUR
        )
        prices.append(hourly_price)

    if not prices:
        return None
    return min(prices)


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
