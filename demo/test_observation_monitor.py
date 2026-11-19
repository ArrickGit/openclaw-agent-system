"""Tests for the simulated game-market monitor.

Run from the demo directory with either:
    python -m pytest -v
    python -m unittest -v
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from observation_monitor import (  # noqa: E402
    InvariantViolation,
    MonitorConfig,
    Observation,
    classify_alert,
    compute_observation_id,
    is_valid_id,
    normalize,
    run_monitor,
)

NOW = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)
CONFIG = MonitorConfig(item="Example Item A", direction="sell", currency="credits")


def raw(price=1000, direction="sell", currency="credits", hours_ago=1.0,
        item="Example Item A", text=None):
    ts = NOW - timedelta(hours=hours_ago)
    return {
        "item": item,
        "direction": direction,
        "price": price,
        "currency": currency,
        "timestamp": ts.isoformat(),
        "source_text": text or f"[simulated] {item} {price} {currency}",
    }


class DeterministicIdTests(unittest.TestCase):
    def test_same_input_same_id(self):
        a = compute_observation_id(normalize(raw()))
        b = compute_observation_id(normalize(raw()))
        self.assertEqual(a, b)
        self.assertTrue(is_valid_id(a))

    def test_normalization_makes_equivalent_inputs_equal(self):
        r1 = raw(text="[simulated] Example Item A 1000")
        r2 = dict(r1, item="  example   ITEM a ", direction="SELL", currency="Credits",
                  source_text="[simulated]   Example Item A   1000")
        self.assertEqual(compute_observation_id(normalize(r1)),
                         compute_observation_id(normalize(r2)))

    def test_different_price_different_id(self):
        self.assertNotEqual(compute_observation_id(normalize(raw(price=1000))),
                            compute_observation_id(normalize(raw(price=999))))


class PipelineTests(unittest.TestCase):
    def test_duplicate_suppression(self):
        result = run_monitor([raw(), raw(), raw()], CONFIG, NOW)
        self.assertEqual(result.duplicates_suppressed, 2)
        self.assertEqual(len(result.accepted), 1)

    def test_currency_filtering(self):
        result = run_monitor([raw(price=500, currency="tokens"), raw(price=900)], CONFIG, NOW)
        self.assertEqual(result.lowest.price, 900)
        self.assertIn("currency_mismatch", [r["reason"] for r in result.rejected])

    def test_direction_filtering(self):
        result = run_monitor([raw(price=300, direction="buy"), raw(price=900)], CONFIG, NOW)
        self.assertEqual(result.lowest.price, 900)
        self.assertIn("direction_mismatch", [r["reason"] for r in result.rejected])

    def test_rolling_window_filtering(self):
        result = run_monitor([raw(price=100, hours_ago=30), raw(price=900, hours_ago=2)],
                             CONFIG, NOW)
        self.assertEqual(result.lowest.price, 900)
        self.assertIn("outside_window", [r["reason"] for r in result.rejected])

    def test_future_timestamps_rejected(self):
        result = run_monitor([raw(price=100, hours_ago=-1)], CONFIG, NOW)
        self.assertIsNone(result.lowest)
        self.assertIn("timestamp_in_future", [r["reason"] for r in result.rejected])

    def test_lowest_price_selection(self):
        result = run_monitor([raw(price=1200), raw(price=800, hours_ago=3), raw(price=950)],
                             CONFIG, NOW, previous_low_price=1000)
        self.assertEqual(result.lowest.price, 800)
        self.assertTrue(result.is_new_low)
        self.assertEqual(result.status, "alert")
        self.assertTrue(result.completed)

    def test_not_a_new_low(self):
        result = run_monitor([raw(price=1200)], CONFIG, NOW, previous_low_price=1000)
        self.assertEqual(result.status, "no_alert")
        self.assertFalse(result.is_new_low)

    def test_malformed_observation_rejected_not_crashing(self):
        result = run_monitor([raw(price="cheap"), raw(price=900)], CONFIG, NOW)
        self.assertEqual(result.lowest.price, 900)
        self.assertTrue(any(r["reason"].startswith("normalization") for r in result.rejected))


class MissingIdTests(unittest.TestCase):
    def test_classification_rejects_missing_id(self):
        unidentified = normalize(raw())  # observation_id defaults to ""
        with self.assertRaises(InvariantViolation):
            classify_alert([unidentified], previous_low_price=None)

    def test_classification_rejects_malformed_id(self):
        bad = Observation("example item a", "sell", 100, "credits", NOW, "x", "not-a-hash")
        with self.assertRaises(InvariantViolation):
            classify_alert([bad], previous_low_price=None)

    def test_faulty_id_generator_never_reaches_classification(self):
        result = run_monitor([raw(), raw(price=900)], CONFIG, NOW, id_fn=lambda _obs: "")
        self.assertEqual(len(result.accepted), 0)
        self.assertEqual([r["reason"] for r in result.rejected],
                         ["missing_or_invalid_id", "missing_or_invalid_id"])
        self.assertIsNone(result.lowest)
        self.assertNotEqual(result.status, "alert")


class EmptyInputTests(unittest.TestCase):
    def test_no_observations(self):
        result = run_monitor([], CONFIG, NOW)
        self.assertEqual(result.status, "no_valid_observations")
        self.assertIsNone(result.lowest)
        self.assertFalse(result.is_new_low)
        self.assertTrue(result.completed)

    def test_only_invalid_observations(self):
        result = run_monitor([raw(currency="tokens"), raw(direction="buy"), raw(price=-5)],
                             CONFIG, NOW)
        self.assertEqual(result.status, "no_valid_observations")
        self.assertIsNone(result.lowest)
        self.assertEqual(len(result.rejected), 3)


if __name__ == "__main__":
    unittest.main()
