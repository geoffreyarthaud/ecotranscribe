from pathlib import Path

import pytest

from ecotranscribe.core.engines import openrouter
from ecotranscribe.core.engines.openrouter import (
    OpenRouterEngine,
    _ChunkTimeout,
    build_payload,
    choose_cut_points,
    normalize_context_bias,
    offset_segments,
)
from ecotranscribe.core.errors import CancelledError
from ecotranscribe.core.models import (
    CancelToken,
    Provider,
    ProgressUpdate,
    Segment,
    TranscribeRequest,
)

MODEL = "mistralai/voxtral-mini-transcribe-3-0"


def test_uses_silence_near_target() -> None:
    silences = [(1180.0, 1200.0), (2380.0, 2400.0)]
    cuts = choose_cut_points(3600.0, silences, 1200.0, search_window=60.0)
    assert cuts == [1190.0, 2390.0]


def test_falls_back_to_fixed_cut_without_silence() -> None:
    assert choose_cut_points(3600.0, [], 1200.0, search_window=60.0) == [
        1200.0,
        2400.0,
    ]


def test_ignores_silence_outside_search_window() -> None:
    silences = [(1000.0, 1010.0)]
    assert choose_cut_points(3600.0, silences, 1200.0, search_window=60.0) == [
        1200.0,
        2400.0,
    ]


def test_drops_last_chunk_shorter_than_minimum() -> None:
    assert choose_cut_points(1210.0, [], 1200.0, search_window=60.0) == []


def test_keeps_last_chunk_at_minimum() -> None:
    assert choose_cut_points(1300.0, [], 1200.0, search_window=60.0) == [1200.0]


def test_silence_cut_does_not_create_short_tail() -> None:
    silences = [(1240.0, 1250.0)]
    assert choose_cut_points(1250.0, silences, 1200.0, search_window=60.0) == []


def test_offsets_timestamps_and_renumbers() -> None:
    segments = (
        Segment(7, 0.0, 1.5, " Bonjour"),
        Segment(8, 1.5, 3.0, " monde"),
    )
    shifted = offset_segments(segments, 1200.0)
    assert [segment.id for segment in shifted] == [1, 2]
    assert [segment.start for segment in shifted] == [1200.0, 1201.5]
    assert [segment.end for segment in shifted] == [1201.5, 1203.0]
    assert segments[0].start == 0.0


def test_normalize_context_bias_collapses_whitespace() -> None:
    assert (
        normalize_context_bias("  RGAA,\n DSFR\taccessibilité  ")
        == "RGAA, DSFR accessibilité"
    )


def test_build_payload_includes_language() -> None:
    payload = build_payload(MODEL, "YWJj", "fr", None)
    assert payload["language"] == "fr"
    assert payload["input_audio"] == {"data": "YWJj", "format": "mp3"}
    assert payload["response_format"] == "verbose_json"
    assert payload["timestamp_granularities"] == ["segment"]


def test_build_payload_omits_none_language() -> None:
    assert "language" not in build_payload(MODEL, "YWJj", None, None)


def test_build_payload_adds_mistral_context_bias() -> None:
    payload = build_payload(MODEL, "YWJj", "fr", "  RGAA,\nDSFR ")
    assert payload["provider"] == {
        "options": {"mistral": {"context_bias": "RGAA, DSFR"}}
    }


def test_build_payload_ignores_prompt_for_non_mistral() -> None:
    payload = build_payload("openai/whisper-1", "YWJj", "fr", "contexte")
    assert "provider" not in payload


def _request(tmp_path: Path, **overrides) -> TranscribeRequest:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"x")
    values = {
        "input_path": source,
        "provider": Provider.OPENROUTER,
        "model": MODEL,
        "api_key": "test-key",
    }
    values.update(overrides)
    return TranscribeRequest(**values)


def _install_fake_media(
    monkeypatch: pytest.MonkeyPatch, duration: float
) -> list[tuple[float, float]]:
    calls: list[tuple[float, float]] = []

    def fake_extract(src: Path, dst: Path, *, cancel=None) -> None:
        dst.write_bytes(b"wav")

    def fake_duration(path: Path, *, cancel=None) -> float:
        return duration

    def fake_silences(path: Path, *, cancel=None) -> list[tuple[float, float]]:
        return []

    def fake_chunk(
        src: Path, dst: Path, start: float, chunk_duration: float, *, cancel=None
    ) -> None:
        calls.append((start, chunk_duration))
        dst.write_bytes(b"mp3")

    monkeypatch.setattr(openrouter.media, "extract_audio", fake_extract)
    monkeypatch.setattr(openrouter.media, "get_media_duration", fake_duration)
    monkeypatch.setattr(openrouter.media, "detect_silences", fake_silences)
    monkeypatch.setattr(openrouter.media, "extract_chunk_mp3", fake_chunk)
    return calls


def test_transcribe_accumulates_cost_and_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_media(monkeypatch, 2500.0)
    costs = iter([0.1, None, 0.0])
    payloads: list[dict] = []

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        payloads.append(payload)
        cost = next(costs)
        return {
            "text": "Bonjour",
            "segments": [{"start": 0.0, "end": 10.0, "text": "Bonjour"}],
            "usage": {} if cost is None else {"cost": cost},
        }

    engine = OpenRouterEngine(http_post=fake_post)
    updates: list[ProgressUpdate] = []
    result = engine.transcribe(
        _request(tmp_path), on_progress=updates.append, cancel=CancelToken()
    )

    assert result.cost_usd == pytest.approx(0.1)
    assert len(payloads) == 3
    assert all("Authorization" not in payload for payload in payloads)
    transcribing = [u for u in updates if u.phase == "transcribing"]
    assert transcribing[0].current == 0.0
    assert transcribing[-1].current == 2500.0
    assert all(u.total == 2500.0 for u in transcribing)
    assert transcribing[-1].detail == "Tranche 3/3"


def test_cost_is_none_when_usage_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_media(monkeypatch, 10.0)

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        return {"text": "ok", "segments": []}

    result = OpenRouterEngine(http_post=fake_post).transcribe(
        _request(tmp_path), cancel=CancelToken()
    )
    assert result.cost_usd is None


def test_zero_cost_is_a_valid_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_media(monkeypatch, 10.0)

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        return {"text": "ok", "segments": [], "usage": {"cost": 0.0}}

    result = OpenRouterEngine(http_post=fake_post).transcribe(
        _request(tmp_path), cancel=CancelToken()
    )
    assert result.cost_usd == 0.0


def test_prompt_logged_and_ignored_for_non_mistral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_media(monkeypatch, 10.0)
    payloads: list[dict] = []
    logs: list[tuple[str, str]] = []

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        payloads.append(payload)
        return {"text": "ok", "segments": []}

    result = OpenRouterEngine(http_post=fake_post).transcribe(
        _request(tmp_path, model="openai/whisper-1", prompt_text="RGAA"),
        on_log=lambda level, message: logs.append((level, message)),
        cancel=CancelToken(),
    )

    assert "provider" not in payloads[0]
    assert any(level == "warning" for level, _ in logs)
    assert result.language == "fr"


def test_cancel_after_http_response_stops_before_next_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_media(monkeypatch, 2500.0)
    token = CancelToken()
    calls = 0

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        nonlocal calls
        calls += 1
        token.cancel()
        return {"text": "ok", "segments": []}

    with pytest.raises(CancelledError):
        OpenRouterEngine(http_post=fake_post).transcribe(
            _request(tmp_path), cancel=token
        )
    assert calls == 1


def test_timeout_splits_chunk_recursively(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chunks = _install_fake_media(monkeypatch, 130.0)
    calls = 0

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _ChunkTimeout("timeout")
        return {
            "text": "ok",
            "segments": [{"start": 0.0, "end": 5.0, "text": "ok"}],
        }

    result = OpenRouterEngine(http_post=fake_post).transcribe(
        _request(tmp_path), cancel=CancelToken()
    )
    assert calls == 3
    assert len(chunks) == 3
    assert [segment.start for segment in result.segments] == [0.0, 65.0]


def test_engine_never_reads_api_key_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_media(monkeypatch, 10.0)
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    seen: list[str] = []

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        seen.append(api_key)
        return {"text": "ok", "segments": []}

    OpenRouterEngine(http_post=fake_post).transcribe(
        _request(tmp_path, api_key="request-key"), cancel=CancelToken()
    )
    assert seen == ["request-key"]


def test_engine_uses_proxy_opener_when_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_media(monkeypatch, 10.0)
    seen: list[object] = []

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        seen.append(kwargs.get("opener"))
        return {"text": "ok", "segments": []}

    engine = OpenRouterEngine(
        proxy="http://proxy.example:8080", http_post=fake_post
    )
    engine.transcribe(_request(tmp_path), cancel=CancelToken())

    assert len(seen) == 1
    assert seen[0] is not None


def test_engine_keeps_default_opener_without_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_media(monkeypatch, 10.0)
    seen: list[object] = []

    def fake_post(payload: dict, api_key: str, **kwargs: object) -> dict:
        seen.append(("opener" in kwargs, kwargs.get("opener")))
        return {"text": "ok", "segments": []}

    engine = OpenRouterEngine(http_post=fake_post)
    engine.transcribe(_request(tmp_path), cancel=CancelToken())

    assert seen == [(True, None)]
