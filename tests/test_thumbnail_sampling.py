import unittest

from src.managers.thumbnail_sampling import (
    choose_random_start_candidate,
    choose_replacement_timestamp,
    frame_quality_score,
    sample_timestamps,
)


class ThumbnailSamplingTest(unittest.TestCase):
    def test_sample_timestamps_always_returns_twelve_for_short_video(self):
        result = sample_timestamps(duration_ms=5000)

        self.assertEqual(len(result), 12)
        self.assertTrue(all(0 <= value <= 5000 for value in result))
        self.assertEqual(result, sorted(result))

    def test_sample_timestamps_always_returns_twelve_for_long_video(self):
        result = sample_timestamps(duration_ms=30 * 60 * 1000)

        self.assertEqual(len(result), 12)
        self.assertGreater(result[0], 0)
        self.assertLess(result[-1], 30 * 60 * 1000)

    def test_random_start_prefers_good_quality_candidate(self):
        timestamps = [1000, 2000, 3000, 4000]
        scores = [0.1, 0.95, 0.2, 0.3]

        result = choose_random_start_candidate(timestamps, scores, duration_ms=5000, seed=1)

        self.assertEqual(result, 2000)

    def test_random_start_keeps_existing_upper_bound(self):
        timestamps = [85000, 95000]
        scores = [0.8, 0.99]

        result = choose_random_start_candidate(timestamps, scores, duration_ms=100000, seed=1)

        self.assertEqual(result, 85000)

    def test_random_start_returns_none_without_candidates(self):
        self.assertIsNone(choose_random_start_candidate([], [], duration_ms=10000, seed=1))


class ThumbnailQualityTest(unittest.TestCase):
    def test_black_frame_scores_low(self):
        score = frame_quality_score(brightness=2.0, contrast=1.0, blur=50.0, similarity=0.1)

        self.assertLess(score, 0.3)

    def test_clear_distinct_frame_scores_high(self):
        score = frame_quality_score(brightness=120.0, contrast=45.0, blur=180.0, similarity=0.25)

        self.assertGreater(score, 0.7)

    def test_replacement_stays_near_original_time(self):
        replacement = choose_replacement_timestamp(
            original_ms=10000,
            duration_ms=60000,
            attempt_index=1,
        )

        self.assertTrue(7000 <= replacement <= 13000)
