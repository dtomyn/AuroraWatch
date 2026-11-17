import unittest

import app
from tests.helpers import chart_payload, pre_candles, regular_candles


class BuildQuoteOpenGapTest(unittest.TestCase):
    def quote(self, raw):
        return app.build_quote("TEST", raw)

    def test_gap_up(self):
        q = self.quote(chart_payload(regular_candles(101.2345, 102.0), previous_close=100.0))
        self.assertEqual(q["open"], 101.2345)
        self.assertEqual(q["gap"], {"change": 1.2345, "pct": 1.23})

    def test_gap_down(self):
        q = self.quote(chart_payload(regular_candles(97.6543, 98.0), previous_close=100.0))
        self.assertEqual(q["open"], 97.6543)
        self.assertEqual(q["gap"], {"change": -2.3457, "pct": -2.35})

    def test_flat_open(self):
        q = self.quote(chart_payload(regular_candles(100.0, 101.0), previous_close=100.0))
        self.assertEqual(q["open"], 100.0)
        self.assertEqual(q["gap"]["change"], 0)
        self.assertEqual(q["gap"]["pct"], 0)

    def test_pre_market_candles_are_ignored(self):
        candles = pre_candles(90.0, 95.0, 99.0) + regular_candles(103.0, 104.0)
        q = self.quote(chart_payload(candles, previous_close=100.0, has_ext=True))
        self.assertIsNotNone(q["pre"])
        self.assertEqual(q["open"], 103.0)
        self.assertEqual(q["gap"], {"change": 3.0, "pct": 3.0})

    def test_no_regular_candles(self):
        q = self.quote(chart_payload(pre_candles(99.0, 99.5), previous_close=100.0, has_ext=True))
        self.assertIsNone(q["open"])
        self.assertIsNone(q["gap"])

    def test_no_candles_at_all(self):
        q = self.quote(chart_payload([], previous_close=100.0))
        self.assertIsNone(q["open"])
        self.assertIsNone(q["gap"])

    def test_missing_previous_close(self):
        q = self.quote(chart_payload(regular_candles(50.25, 51.0), previous_close=None))
        self.assertEqual(q["open"], 50.25)
        self.assertIsNone(q["gap"])

    def test_gap_base_matches_previous_close_on_multi_day_payload(self):
        day1 = (
            (1699894400, 1699913600),
            (1699913600, 1699937000),
            (1699937000, 1699951400),
        )
        day2 = ((1699980800, 1700000000), (1700000000, 1700023400), (1700023400, 1700037800))
        candles = regular_candles(90.0, 95.0, start=day1[1][0]) + regular_candles(99.0, 98.0)
        raw = chart_payload(candles, previous_close=97.0, windows=(day1, day2))
        q = self.quote(raw)
        self.assertEqual(q["previous_close"], 97.0)
        self.assertEqual(q["open"], 99.0)
        self.assertEqual(q["gap"], {"change": 2.0, "pct": 2.06})


if __name__ == "__main__":
    unittest.main()
