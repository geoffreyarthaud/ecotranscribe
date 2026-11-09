from __future__ import annotations

import json
from pathlib import Path

import pytest

from ecotranscribe.core.catalog import MAX_CATALOG_MODELS, parse_catalog
from ecotranscribe.core.config import OPENROUTER_MODEL, OPENROUTER_MODELS

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_committed_catalog_is_valid() -> None:
    payload = json.loads(
        (_REPO_ROOT / "catalog" / "models.json").read_text(encoding="utf-8")
    )

    models = parse_catalog(payload)

    assert models is not None
    assert OPENROUTER_MODEL in models
    assert models == OPENROUTER_MODELS


def test_parse_catalog_returns_valid_ids() -> None:
    payload = {
        "schema": 1,
        "updated_at": "2026-11-09",
        "models": [
            " mistralai/voxtral-small-transcribe-3-0 ",
            "mistralai/voxtral-mini-transcribe-3-0",
            "mistralai/voxtral-small-transcribe-3-0",
            "provider/model:free",
        ],
        "ignored": True,
    }

    assert parse_catalog(payload) == (
        "mistralai/voxtral-small-transcribe-3-0",
        "mistralai/voxtral-mini-transcribe-3-0",
        "provider/model:free",
    )


def test_parse_catalog_skips_invalid_entries() -> None:
    payload = {
        "schema": 1,
        "models": [
            "",
            "   ",
            "bad model",
            "-leading-dash",
            42,
            None,
            "bad\nmodel",
            "a" * 129,
            "ok/model",
        ],
    }

    assert parse_catalog(payload) == ("ok/model",)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"models": ["ok/model"]},
        {"schema": None, "models": ["ok/model"]},
        {"schema": True, "models": ["ok/model"]},
        {"schema": 1.0, "models": ["ok/model"]},
        {"schema": 2, "models": ["ok/model"]},
        {"schema": 1, "models": None},
        {"schema": 1, "models": []},
        {"schema": 1, "models": ["bad model"]},
    ],
)
def test_parse_catalog_rejects_invalid_catalog(payload: object) -> None:
    assert parse_catalog(payload) is None


def test_parse_catalog_caps_model_count() -> None:
    models = [f"provider/model-{index}" for index in range(MAX_CATALOG_MODELS + 5)]

    parsed = parse_catalog({"schema": 1, "models": models})

    assert parsed == tuple(models[:MAX_CATALOG_MODELS])
