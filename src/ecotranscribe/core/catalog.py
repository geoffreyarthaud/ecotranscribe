"""Validation du catalogue de modèles publié dans le dépôt."""

from __future__ import annotations

import re
from typing import cast

CATALOG_SCHEMA = 1
MAX_CATALOG_MODELS = 50
_MAX_MODEL_ID_LENGTH = 128
_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*\Z")


def parse_catalog(payload: object) -> tuple[str, ...] | None:
    """Valide un catalogue et retourne ses identifiants de modèles.

    Un catalogue structurellement invalide est rejeté en bloc. Les entrées
    individuelles invalides sont ignorées, ainsi que les doublons.
    """
    if not isinstance(payload, dict):
        return None
    data = cast("dict[str, object]", payload)
    schema = data.get("schema")
    if (
        isinstance(schema, bool)
        or not isinstance(schema, int)
        or schema != CATALOG_SCHEMA
    ):
        return None
    raw_models = data.get("models")
    if not isinstance(raw_models, list):
        return None

    models: list[str] = []
    seen: set[str] = set()
    for item in raw_models:
        if len(models) >= MAX_CATALOG_MODELS:
            break
        if not isinstance(item, str):
            continue
        model = item.strip()
        if not model or len(model) > _MAX_MODEL_ID_LENGTH:
            continue
        if not _MODEL_ID.fullmatch(model) or model in seen:
            continue
        seen.add(model)
        models.append(model)
    return tuple(models) if models else None
