import unittest

from whisper_transcribe.main import (
    _choose_cut_points,
    _normalize_context_bias,
    _offset_segments,
)


class ChooseCutPointsTest(unittest.TestCase):
    def test_uses_silence_near_target(self) -> None:
        silences = [(1180.0, 1200.0), (2380.0, 2400.0)]

        cuts = _choose_cut_points(3600.0, silences, 1200.0, search_window=60.0)

        self.assertEqual(cuts, [1190.0, 2390.0])

    def test_falls_back_to_fixed_cut_without_silence(self) -> None:
        cuts = _choose_cut_points(3600.0, [], 1200.0, search_window=60.0)

        self.assertEqual(cuts, [1200.0, 2400.0])

    def test_ignores_silence_outside_search_window(self) -> None:
        silences = [(1000.0, 1010.0)]

        cuts = _choose_cut_points(3600.0, silences, 1200.0, search_window=60.0)

        self.assertEqual(cuts, [1200.0, 2400.0])

    def test_drops_last_chunk_shorter_than_minimum(self) -> None:
        cuts = _choose_cut_points(1210.0, [], 1200.0, search_window=60.0)

        self.assertEqual(cuts, [])

    def test_keeps_last_chunk_at_minimum(self) -> None:
        cuts = _choose_cut_points(1300.0, [], 1200.0, search_window=60.0)

        self.assertEqual(cuts, [1200.0])

    def test_silence_cut_does_not_create_short_tail(self) -> None:
        silences = [(1240.0, 1250.0)]

        cuts = _choose_cut_points(1250.0, silences, 1200.0, search_window=60.0)

        self.assertEqual(cuts, [])


class OffsetSegmentsTest(unittest.TestCase):
    def test_offsets_timestamps_and_renumbers(self) -> None:
        segments = [
            {"id": 7, "start": 0.0, "end": 1.5, "text": " Bonjour"},
            {"id": 8, "start": 1.5, "end": 3.0, "text": " monde"},
        ]

        shifted = _offset_segments(segments, 1200.0)

        self.assertEqual([segment["id"] for segment in shifted], [0, 1])
        self.assertEqual([segment["start"] for segment in shifted], [1200.0, 1201.5])
        self.assertEqual([segment["end"] for segment in shifted], [1201.5, 1203.0])
        self.assertEqual(segments[0]["start"], 0.0)


class NormalizeContextBiasTest(unittest.TestCase):
    def test_collapses_whitespace(self) -> None:
        self.assertEqual(
            _normalize_context_bias("  RGAA,\n DSFR\taccessibilité  "),
            "RGAA, DSFR accessibilité",
        )


if __name__ == "__main__":
    unittest.main()