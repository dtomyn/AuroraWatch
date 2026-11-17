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
    volumes=None,
):
    """Return a raw chart result dict.

    candles: list of (epoch, close) pairs.
    previous_close: meta.previousClose, or None to omit it (and chartPreviousClose).
    windows: one (pre, regular, post) tuple of (start, end) per trading day.
    volumes: optional list aligned with candles, emitted as indicators.quote[0].volume.
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
    quote = {"close": [c for _, c in candles]}
    if volumes is not None:
        quote["volume"] = list(volumes)
    return {
        "meta": meta,
        "timestamp": [t for t, _ in candles],
        "indicators": {"quote": [quote]},
    }


def day_windows(n):
    """n consecutive (pre, regular, post) days, oldest first, ending on PRE/REGULAR/POST."""
    def shift(window, days):
        return (window[0] - 86400 * days, window[1] - 86400 * days)

    return tuple(
        (shift(PRE, back), shift(REGULAR, back), shift(POST, back))
        for back in range(n - 1, -1, -1)
    )


def regular_candles(*closes, start=REGULAR[0]):
    """One candle per minute from the start of the regular window."""
    return [(start + 60 * i, c) for i, c in enumerate(closes)]


def pre_candles(*closes, start=PRE[0]):
    return [(start + 60 * i, c) for i, c in enumerate(closes)]
