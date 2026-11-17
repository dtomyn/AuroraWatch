"""Builders for synthetic Yahoo chart payloads used by the offline tests."""

# Fixed historical windows, so time.time() always sees every day as started.
PRE = (1699980800, 1700000000)
REGULAR = (1700000000, 1700023400)
POST = (1700023400, 1700037800)


def chart_payload(
    candles,
    previous_close=100.0,
    price=None,
    has_ext=False,
    windows=((PRE, REGULAR, POST),),
    day_high=None,
    day_low=None,
):
    """Return a raw chart result dict.

    candles: list of (epoch, close) pairs.
    previous_close: meta.previousClose, or None to omit it (and chartPreviousClose).
    windows: one (pre, regular, post) tuple of (start, end) per trading day.
    day_high / day_low: meta.regularMarketDayHigh / regularMarketDayLow, omitted when None.
    """
    def periods(index):
        return [[{"start": w[index][0], "end": w[index][1]}] for w in windows]

    last_regular = windows[-1][1]
    meta = {
        "currency": "USD",
        "instrumentType": "EQUITY",
        "hasPrePostMarketData": has_ext,
        "regularMarketPrice": price if price is not None else (candles[-1][1] if candles else 100.0),
        "regularMarketTime": last_regular[1],
        "tradingPeriods": {"pre": periods(0), "regular": periods(1), "post": periods(2)},
    }
    if previous_close is not None:
        meta["previousClose"] = previous_close
    if day_high is not None:
        meta["regularMarketDayHigh"] = day_high
    if day_low is not None:
        meta["regularMarketDayLow"] = day_low
    return {
        "meta": meta,
        "timestamp": [t for t, _ in candles],
        "indicators": {"quote": [{"close": [c for _, c in candles]}]},
    }


def regular_candles(*closes, start=REGULAR[0]):
    """One candle per minute from the start of the regular window."""
    return [(start + 60 * i, c) for i, c in enumerate(closes)]


def pre_candles(*closes, start=PRE[0]):
    return [(start + 60 * i, c) for i, c in enumerate(closes)]
