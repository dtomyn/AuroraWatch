"""Tests for the day swing: the swing_pct() helper and day_swing_pct in build_quote."""
import unittest

import app
from tests.helpers import chart_payload, regular_candles


class SwingPctTest(unittest.TestCase):
    def test_normal_swing(self):
        self.assertEqual(app.swing_pct(98.0, 102.2, 100.0), 4.2)

    def test_rounds_to_two_decimals(self):
        self.assertEqual(app.swing_pct(100.0, 101.2345, 100.0), 1.23)

    def test_missing_input_is_none(self):
        self.assertIsNone(app.swing_pct(None, 102.2, 100.0))
        self.assertIsNone(app.swing_pct(98.0, None, 100.0))
        self.assertIsNone(app.swing_pct(98.0, 102.2, None))

    def test_zero_base_is_none(self):
        self.assertIsNone(app.swing_pct(98.0, 102.2, 0))

    def test_inverted_range_is_none(self):
        self.assertIsNone(app.swing_pct(102.2, 98.0, 100.0))

    def test_zero_width_range_is_zero(self):
        self.assertEqual(app.swing_pct(100.0, 100.0, 100.0), 0.0)


class BuildQuoteDaySwingTest(unittest.TestCase):
    def quote(self, **kwargs):
        kwargs.setdefault("previous_close", 100.0)
        return app.build_quote("TEST", chart_payload(regular_candles(99.0, 101.0), **kwargs))

    def test_normal_day(self):
        q = self.quote(day_low=98.0, day_high=102.2)
        self.assertEqual(q["day_swing_pct"], 4.2)

    def test_flat_day_is_zero(self):
        q = self.quote(day_low=100.0, day_high=100.0)
        self.assertEqual(q["day_swing_pct"], 0.0)

    def test_missing_day_high(self):
        self.assertIsNone(self.quote(day_low=98.0)["day_swing_pct"])

    def test_missing_day_low(self):
        self.assertIsNone(self.quote(day_high=102.2)["day_swing_pct"])

    def test_missing_previous_close(self):
        q = self.quote(day_low=98.0, day_high=102.2, previous_close=None)
        self.assertIsNone(q["previous_close"])
        self.assertIsNone(q["day_swing_pct"])

    def test_zero_previous_close(self):
        q = self.quote(day_low=98.0, day_high=102.2, previous_close=0.0)
        self.assertIsNone(q["day_swing_pct"])

    def test_inverted_range(self):
        q = self.quote(day_low=102.2, day_high=98.0)
        self.assertIsNone(q["day_swing_pct"])

    def test_base_is_returned_previous_close_on_multi_day_payload(self):
        day1 = (
            (1699894400, 1699913600),
            (1699913600, 1699937000),
            (1699937000, 1699951400),
        )
        day2 = ((1699980800, 1700000000), (1700000000, 1700023400), (1700023400, 1700037800))
        candles = regular_candles(90.0, 95.0, start=day1[1][0]) + regular_candles(99.0, 98.0)
        raw = chart_payload(
            candles, previous_close=97.0, windows=(day1, day2), day_low=96.0, day_high=100.85
        )
        q = app.build_quote("TEST", raw)
        self.assertEqual(q["previous_close"], 97.0)
        self.assertEqual(q["day_swing_pct"], 5.0)


if __name__ == "__main__":
    unittest.main()
