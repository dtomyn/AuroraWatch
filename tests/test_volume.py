import unittest

import app
from tests.helpers import chart_payload, day_windows


def day_candles(window, volumes, close=100.0):
    """One candle per minute from the start of window, paired with its volume."""
    return [((window[0] + 60 * i, close), v) for i, v in enumerate(volumes)]


def payload(per_day, has_ext=False):
    """per_day: one dict per trading day mapping 'pre'/'regular'/'post' to a volume list."""
    windows = day_windows(len(per_day))
    rows = []
    for window, sessions in zip(windows, per_day):
        for index, name in enumerate(("pre", "regular", "post")):
            rows += day_candles(window[index], sessions.get(name, []))
    candles = [c for c, _ in rows]
    volumes = [v for _, v in rows]
    return chart_payload(candles, has_ext=has_ext, windows=windows, volumes=volumes)


class RelativeVolumeTest(unittest.TestCase):
    def quote(self, per_day, has_ext=False):
        return app.build_quote("TEST", payload(per_day, has_ext=has_ext))

    def test_average_of_earlier_days_and_ratio(self):
        q = self.quote([
            {"regular": [400, 600]},
            {"regular": [2000]},
            {"regular": [1000, 2000]},
            {"regular": [1500, 1500]},
        ])
        self.assertEqual(q["avg_volume"], 2000)
        self.assertIsInstance(q["avg_volume"], int)
        self.assertEqual(q["rel_volume"], 1.5)

    def test_last_day_below_average(self):
        q = self.quote([{"regular": [2000]}, {"regular": [1000]}])
        self.assertEqual(q["avg_volume"], 2000)
        self.assertEqual(q["rel_volume"], 0.5)

    def test_rounding_uses_unrounded_average(self):
        q = self.quote([{"regular": [1000]}, {"regular": [1001]}, {"regular": [1234]}])
        self.assertEqual(q["avg_volume"], 1000)
        self.assertEqual(q["rel_volume"], round(1234 / 1000.5, 2))
        self.assertEqual(q["rel_volume"], 1.23)

    def test_extended_hours_volume_is_ignored(self):
        plain = self.quote([{"regular": [1000]}, {"regular": [3000]}, {"regular": [3000]}], has_ext=True)
        busy = self.quote(
            [
                {"pre": [10**9], "regular": [1000], "post": [10**9]},
                {"pre": [10**9], "regular": [3000], "post": [10**9]},
                {"pre": [10**9], "regular": [3000], "post": [10**9]},
            ],
            has_ext=True,
        )
        self.assertEqual(plain["avg_volume"], 2000)
        self.assertEqual(plain["rel_volume"], 1.5)
        self.assertEqual(busy["avg_volume"], plain["avg_volume"])
        self.assertEqual(busy["rel_volume"], plain["rel_volume"])

    def test_null_volumes_count_as_zero(self):
        q = self.quote([{"regular": [1000, None, 1000]}, {"regular": [None, 500]}])
        self.assertEqual(q["avg_volume"], 2000)
        self.assertEqual(q["rel_volume"], 0.25)

    def test_single_trading_day(self):
        q = self.quote([{"regular": [1000, 2000]}])
        self.assertIsNone(q["avg_volume"])
        self.assertIsNone(q["rel_volume"])

    def test_earlier_day_without_regular_candles_is_excluded(self):
        q = self.quote(
            [{"regular": [1000]}, {"pre": [5000]}, {"regular": [3000]}, {"regular": [4000]}],
            has_ext=True,
        )
        self.assertEqual(q["avg_volume"], 2000)
        self.assertEqual(q["rel_volume"], 2.0)

    def test_zero_average(self):
        q = self.quote([{"regular": [0, None]}, {"regular": [0]}, {"regular": [1000]}])
        self.assertEqual(q["avg_volume"], 0)
        self.assertIsNone(q["rel_volume"])

    def test_no_regular_candles_at_all(self):
        q = self.quote([{"pre": [1000]}, {"pre": [2000]}], has_ext=True)
        self.assertIsNone(q["avg_volume"])
        self.assertIsNone(q["rel_volume"])

    def test_missing_volume_list(self):
        raw = payload([{"regular": [1000]}, {"regular": [1000]}])
        del raw["indicators"]["quote"][0]["volume"]
        q = app.build_quote("TEST", raw)
        self.assertEqual(q["avg_volume"], 0)
        self.assertIsNone(q["rel_volume"])


if __name__ == "__main__":
    unittest.main()
