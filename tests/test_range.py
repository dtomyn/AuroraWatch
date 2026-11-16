"""Pure-function tests for the range-position helpers in app.py."""
import unittest

import app as aurora


class RangePctTest(unittest.TestCase):
    def test_mid_range(self):
        self.assertEqual(aurora.range_pct(15, 10, 20), 50.0)

    def test_at_low_and_high(self):
        self.assertEqual(aurora.range_pct(10, 10, 20), 0.0)
        self.assertEqual(aurora.range_pct(20, 10, 20), 100.0)

    def test_clamps_outside_range(self):
        self.assertEqual(aurora.range_pct(25, 10, 20), 100.0)
        self.assertEqual(aurora.range_pct(5, 10, 20), 0.0)

    def test_rounds_to_one_decimal(self):
        self.assertEqual(aurora.range_pct(1, 0, 3), 33.3)

    def test_missing_input_is_none(self):
        self.assertIsNone(aurora.range_pct(None, 10, 20))
        self.assertIsNone(aurora.range_pct(15, None, 20))
        self.assertIsNone(aurora.range_pct(15, 10, None))

    def test_zero_width_range_is_none(self):
        self.assertIsNone(aurora.range_pct(10, 10, 10))

    def test_inverted_range_is_none(self):
        self.assertIsNone(aurora.range_pct(15, 20, 10))


def leg(price, when):
    return {"price": price, "change": None, "pct": None, "base": None, "time": when}


class HeadlinePriceTest(unittest.TestCase):
    """Mirrors activeMove(q) in static/app.js."""

    def setUp(self):
        self.regular = leg(100.0, 1000)

    def test_live_pre_returns_pre_price(self):
        self.assertEqual(aurora.headline_price("pre", leg(101.0, 900), self.regular, None), 101.0)

    def test_live_post_returns_post_price(self):
        self.assertEqual(aurora.headline_price("post", None, self.regular, leg(99.0, 1100)), 99.0)

    def test_pre_session_without_pre_falls_back_to_regular(self):
        self.assertEqual(aurora.headline_price("pre", None, self.regular, leg(99.0, 1100)), 100.0)

    def test_closed_with_newer_post_returns_post_price(self):
        self.assertEqual(aurora.headline_price("closed", None, self.regular, leg(99.0, 1100)), 99.0)

    def test_closed_with_older_post_returns_regular_price(self):
        self.assertEqual(aurora.headline_price("closed", None, self.regular, leg(99.0, 900)), 100.0)

    def test_regular_session_ignores_extended_prices(self):
        self.assertEqual(
            aurora.headline_price("regular", leg(101.0, 900), self.regular, leg(99.0, 1100)), 100.0
        )

    def test_closed_with_post_and_no_regular_returns_post_price(self):
        self.assertEqual(aurora.headline_price("closed", None, None, leg(99.0, 1100)), 99.0)

    def test_no_regular_and_no_extended_price_is_none(self):
        self.assertIsNone(aurora.headline_price("closed", None, None, None))
        self.assertIsNone(aurora.headline_price("pre", None, None, None))


if __name__ == "__main__":
    unittest.main()
