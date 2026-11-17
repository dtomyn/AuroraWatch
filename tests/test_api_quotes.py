import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app
from tests.helpers import chart_payload, regular_candles


class ApiQuotesTest(unittest.TestCase):
    def setUp(self):
        app.cache.clear()
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.config = Path(path)
        self.config.write_text(json.dumps({"tickers": ["AAPL"]}), encoding="utf-8")
        self.payload = chart_payload(regular_candles(101.2345, 102.0), previous_close=100.0)
        config_patch = mock.patch.object(app, "CONFIG_PATH", self.config)
        fetch_patch = mock.patch.object(app, "fetch_chart", side_effect=lambda s: self.payload)
        config_patch.start()
        self.addCleanup(config_patch.stop)
        self.fetch = fetch_patch.start()
        self.addCleanup(fetch_patch.stop)

    def tearDown(self):
        app.cache.clear()
        self.config.unlink(missing_ok=True)

    def test_quotes_include_open_and_gap(self):
        resp = app.app.test_client().get("/api/quotes")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        [quote] = data["quotes"]
        self.assertEqual(quote["symbol"], "AAPL")
        self.assertEqual(quote["open"], 101.2345)
        self.assertEqual(quote["gap"], {"change": 1.2345, "pct": 1.23})
        self.assertEqual([q["symbol"] for q in data["indexes"]], app.INDEXES)
        called = sorted(c.args[0] for c in self.fetch.call_args_list)
        self.assertEqual(called, sorted(["AAPL"] + app.INDEXES))

    def test_quotes_include_day_swing(self):
        self.payload = chart_payload(
            regular_candles(99.0, 101.0), previous_close=100.0, day_low=98.0, day_high=102.2
        )
        resp = app.app.test_client().get("/api/quotes")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        [quote] = data["quotes"]
        self.assertEqual(quote["symbol"], "AAPL")
        self.assertEqual(quote["day_swing_pct"], 4.2)
        self.assertEqual(len(data["indexes"]), len(app.INDEXES))
        for index in data["indexes"]:
            self.assertEqual(index["day_swing_pct"], 4.2)


if __name__ == "__main__":
    unittest.main()
