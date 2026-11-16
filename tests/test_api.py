"""Offline contract tests for GET /api/quotes. No request reaches Yahoo."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app as aurora


def chart_payload(**meta_overrides):
    """A minimal chart result with no trading periods, so the session is 'closed'
    and the headline price is always regularMarketPrice."""
    meta = {
        "regularMarketPrice": 415.0,
        "previousClose": 410.0,
        "regularMarketTime": 1_700_000_000,
        "regularMarketDayLow": 410.0,
        "regularMarketDayHigh": 420.0,
        "fiftyTwoWeekLow": 300.0,
        "fiftyTwoWeekHigh": 450.0,
        "currency": "USD",
        "instrumentType": "EQUITY",
    }
    meta.update(meta_overrides)
    return {"meta": meta, "timestamp": [], "indicators": {"quote": [{"close": []}]}}


class QuotesEndpointTest(unittest.TestCase):
    def setUp(self):
        aurora.cache.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config = Path(tmp.name) / "watchlist.json"
        config.write_text(json.dumps({"tickers": ["TEST"]}), encoding="utf-8")
        patcher = mock.patch.object(aurora, "CONFIG_PATH", config)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Fail loudly if anything tries to reach the network.
        net = mock.patch.object(aurora.session, "get", side_effect=AssertionError("network used"))
        net.start()
        self.addCleanup(net.stop)
        self.client = aurora.app.test_client()

    def tearDown(self):
        aurora.cache.clear()

    def get_quotes(self, payload):
        with mock.patch.object(aurora, "fetch_chart", side_effect=lambda symbol: payload):
            resp = self.client.get("/api/quotes")
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()

    def test_range_percentages_for_watchlist_ticker(self):
        body = self.get_quotes(chart_payload())
        quote = body["quotes"][0]
        self.assertEqual(quote["symbol"], "TEST")
        self.assertEqual(quote["session"], "closed")
        self.assertEqual(quote["day_range_pct"], 50.0)  # (415-410)/(420-410)
        self.assertEqual(quote["year_range_pct"], 76.7)  # (415-300)/(450-300) = 76.66..
        self.assertEqual(len(body["indexes"]), len(aurora.INDEXES))
        for q in body["quotes"] + body["indexes"]:
            for key in ("day_range_pct", "year_range_pct"):
                self.assertIn(key, q)

    def test_missing_or_degenerate_inputs_are_null(self):
        payload = chart_payload(regularMarketDayLow=None, fiftyTwoWeekLow=400.0, fiftyTwoWeekHigh=400.0)
        quote = self.get_quotes(payload)["quotes"][0]
        self.assertEqual(quote["symbol"], "TEST")
        self.assertIn("day_range_pct", quote)
        self.assertIn("year_range_pct", quote)
        self.assertIsNone(quote["day_range_pct"])
        self.assertIsNone(quote["year_range_pct"])


if __name__ == "__main__":
    unittest.main()
