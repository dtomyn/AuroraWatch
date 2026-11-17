"""Tests for the intraday swing figure: swing_pct(), build_quote and /api/quotes."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app
from tests.helpers import chart_payload, regular_candles


def payload_with_range(low, high, previous_close=100.0):
    payload = chart_payload(regular_candles(101.0, 102.0), previous_close=previous_close)
    if low is not None:
        payload["meta"]["regularMarketDayLow"] = low
    if high is not None:
        payload["meta"]["regularMarketDayHigh"] = high
    return payload


class SwingPctTest(unittest.TestCase):
    def test_normal_swing(self):
        self.assertEqual(app.swing_pct(98.0, 102.2, 100.0), 4.2)

    def test_rounds_to_two_decimals(self):
        self.assertEqual(app.swing_pct(10, 11, 3), 33.33)

    def test_missing_input_is_none(self):
        self.assertIsNone(app.swing_pct(None, 102.0, 100.0))
        self.assertIsNone(app.swing_pct(98.0, None, 100.0))
        self.assertIsNone(app.swing_pct(98.0, 102.0, None))

    def test_zero_base_is_none(self):
        self.assertIsNone(app.swing_pct(98.0, 102.0, 0))

    def test_inverted_range_is_none(self):
        self.assertIsNone(app.swing_pct(102.0, 98.0, 100.0))

    def test_flat_range_is_zero(self):
        self.assertEqual(app.swing_pct(100.0, 100.0, 100.0), 0.0)


class BuildQuoteSwingTest(unittest.TestCase):
    def test_swing_uses_returned_previous_close(self):
        quote = app.build_quote("AAPL", payload_with_range(97.5, 101.25, previous_close=125.0))
        self.assertEqual(quote["previous_close"], 125.0)
        self.assertEqual(quote["day_swing_pct"], 3.0)

    def test_missing_high_is_none(self):
        quote = app.build_quote("AAPL", payload_with_range(98.0, None))
        self.assertIsNone(quote["day_swing_pct"])

    def test_missing_low_is_none(self):
        quote = app.build_quote("AAPL", payload_with_range(None, 102.0))
        self.assertIsNone(quote["day_swing_pct"])

    def test_missing_previous_close_is_none(self):
        quote = app.build_quote("AAPL", payload_with_range(98.0, 102.0, previous_close=None))
        self.assertIsNone(quote["day_swing_pct"])

    def test_zero_previous_close_is_none(self):
        quote = app.build_quote("AAPL", payload_with_range(98.0, 102.0, previous_close=0))
        self.assertIsNone(quote["day_swing_pct"])


class ApiQuotesSwingTest(unittest.TestCase):
    def setUp(self):
        app.cache.clear()
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.config = Path(path)
        self.config.write_text(json.dumps({"tickers": ["AAPL"]}), encoding="utf-8")
        self.payload = payload_with_range(98.0, 102.2, previous_close=100.0)
        config_patch = mock.patch.object(app, "CONFIG_PATH", self.config)
        fetch_patch = mock.patch.object(app, "fetch_chart", side_effect=lambda s: self.payload)
        config_patch.start()
        self.addCleanup(config_patch.stop)
        fetch_patch.start()
        self.addCleanup(fetch_patch.stop)

    def tearDown(self):
        app.cache.clear()
        self.config.unlink(missing_ok=True)

    def test_quotes_include_day_swing_pct(self):
        resp = app.app.test_client().get("/api/quotes")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        [quote] = data["quotes"]
        self.assertEqual(quote["symbol"], "AAPL")
        self.assertEqual(quote["day_swing_pct"], 4.2)
        for index in data["indexes"]:
            self.assertEqual(index["day_swing_pct"], 4.2)


if __name__ == "__main__":
    unittest.main()
