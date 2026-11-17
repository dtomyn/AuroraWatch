"""Aurora Watch: a local stock watchlist with pre- and post-market quotes."""
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("WATCHLIST_FILE", BASE_DIR / "watchlist.json"))
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AuroraWatch/1.0"}
TICKER_RE = re.compile(r"^\^?[A-Z0-9][A-Z0-9.\-=]{0,14}$")
CACHE_TTL = 10  # seconds a quote is served before Yahoo is asked again
MAX_CHART_POINTS = 260
INDEXES = ["SPY", "QQQ", "DIA"]

log = logging.getLogger("aurora")
app = Flask(__name__)
session = requests.Session()
session.headers.update(HEADERS)
pool = ThreadPoolExecutor(max_workers=8)


class TickerNotFound(Exception):
    pass


class UpstreamError(Exception):
    pass


# ---------------------------------------------------------------- config file
config_lock = threading.Lock()


def normalize(symbol):
    symbol = str(symbol or "").strip().upper()
    return symbol if TICKER_RE.match(symbol) else None


def load_tickers():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        tickers = data["tickers"] if isinstance(data, dict) else data
        clean = [normalize(t) for t in tickers]
        return list(dict.fromkeys(t for t in clean if t))
    except FileNotFoundError:
        return []
    except (ValueError, KeyError, TypeError) as exc:
        # Keep the unreadable file so a hand edit gone wrong can be recovered.
        backup = CONFIG_PATH.with_suffix(f".corrupt-{int(time.time())}.json")
        CONFIG_PATH.replace(backup)
        log.warning("Unreadable config (%s); moved it to %s", exc, backup)
        return []


def save_tickers(tickers):
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"tickers": tickers}, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


# ---------------------------------------------------------------- quote logic
def fetch_chart(symbol):
    try:
        resp = session.get(
            CHART_URL.format(requests.utils.quote(symbol, safe="")),
            params={"range": "5d", "interval": "1m", "includePrePost": "true"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise UpstreamError(str(exc)) from exc
    if resp.status_code == 404:
        raise TickerNotFound(symbol)
    if resp.status_code != 200:
        raise UpstreamError(f"Yahoo returned HTTP {resp.status_code}")
    try:
        result = resp.json()["chart"]["result"]
    except (ValueError, KeyError) as exc:
        raise UpstreamError("Unexpected response from Yahoo") from exc
    if not result:
        raise TickerNotFound(symbol)
    return result[0]


def trading_days(meta):
    """Return one {pre, regular, post} dict of (start, end) tuples per trading day."""
    periods = meta.get("tradingPeriods")
    if isinstance(periods, list):  # 24h instruments return a bare list of regular periods
        periods = {"regular": periods}
    if not isinstance(periods, dict):
        return []
    days = []
    regular = periods.get("regular") or []
    for i, entry in enumerate(regular):
        day = {"regular": (entry[0]["start"], entry[0]["end"])}
        for name in ("pre", "post"):
            rows = periods.get(name) or []
            if i < len(rows) and rows[i][0]["end"] > rows[i][0]["start"]:
                day[name] = (rows[i][0]["start"], rows[i][0]["end"])
        days.append(day)
    return days


def candles_in(candles, window):
    if not window:
        return []
    return [c for c in candles if window[0] <= c[0] < window[1]]


def move(price, base, when=None):
    if price is None:
        return None
    change = price - base if base else None
    return {
        "price": price,
        "change": change,
        "pct": change / base * 100 if base else None,
        "base": base,
        "time": when,
    }


def range_pct(price, low, high):
    """Position of price between low and high as 0-100, clamped and rounded to 1 decimal.

    None when an input is missing or the range has no width (or is inverted).
    """
    if price is None or low is None or high is None or high <= low:
        return None
    return round(min(max((price - low) / (high - low) * 100, 0.0), 100.0), 1)


def swing_pct(low, high, base):
    """Intraday swing (high - low) as a percentage of base, rounded to 2 decimals.

    None when an input is missing, base is zero, or the range is inverted.
    """
    if low is None or high is None or not base or high < low:
        return None
    return round((high - low) / base * 100, 2)


def headline_price(session, pre, regular, post):
    """The price the card shows in large type.

    Must stay in sync with activeMove(q) in static/app.js.
    """
    if session == "pre" and pre:
        return pre["price"]
    if session == "post" and post:
        return post["price"]
    regular_time = (regular or {}).get("time") or 0
    if session == "closed" and post and post.get("time") is not None and post["time"] > regular_time:
        return post["price"]
    return regular["price"] if regular else None


def build_quote(symbol, raw):
    meta = raw["meta"]
    quote = (raw.get("indicators", {}).get("quote") or [{}])[0]
    candles = [
        (t, c)
        for t, c in zip(raw.get("timestamp") or [], quote.get("close") or [])
        if c is not None
    ]
    now = time.time()
    days = trading_days(meta)
    price = meta.get("regularMarketPrice")
    market_time = meta.get("regularMarketTime") or 0
    previous_close = meta.get("previousClose") or meta.get("chartPreviousClose")

    current = None
    for i, day in enumerate(days):
        if day.get("pre", day["regular"])[0] <= now:
            current = i

    # The last day whose regular session traded. Yahoo's headline price and previous
    # close describe that day, and are official closes rather than the last 1m candle.
    last_regular = None
    for i, day in enumerate(days):
        if candles_in(candles, day["regular"]):
            last_regular = i

    def official_close(i):
        if i is None or i < 0 or i >= len(days):
            return None
        if i == last_regular and market_time >= days[i]["regular"][0]:
            return price
        if last_regular is not None and i == last_regular - 1 and previous_close:
            return previous_close
        rows = candles_in(candles, days[i]["regular"])
        return rows[-1][1] if rows else None

    pre = post = None
    has_ext = bool(meta.get("hasPrePostMarketData")) and meta.get("instrumentType") != "CRYPTOCURRENCY"
    if has_ext and current is not None:
        rows = candles_in(candles, days[current].get("pre"))
        if rows:
            pre = move(rows[-1][1], official_close(current - 1), rows[-1][0])
        # Before today's after-hours session has traded, show the most recent one.
        for i in (current, current - 1):
            if i < 0:
                continue
            rows = candles_in(candles, days[i].get("post"))
            if rows:
                post = move(rows[-1][1], official_close(i), rows[-1][0])
                break

    regular_base = official_close(last_regular - 1) if last_regular else previous_close
    regular = move(price, regular_base, market_time)

    # The open is the first one-minute candle of the last regular session.
    open_rows = candles_in(candles, days[last_regular]["regular"]) if last_regular is not None else []
    open_price = open_rows[0][1] if open_rows else None
    # Relative volume: the last regular day's regular-session volume against the mean of
    # the earlier days that traded a regular session. Extended hours are never counted.
    vol_candles = [(t, v or 0) for t, v in zip(raw.get("timestamp") or [], quote.get("volume") or [])]

    def regular_volume(i):
        return sum(v for _, v in candles_in(vol_candles, days[i]["regular"]))

    avg_volume = rel_volume = None
    if last_regular is not None:
        earlier = [regular_volume(i) for i in range(last_regular) if candles_in(candles, days[i]["regular"])]
        if earlier:
            mean = sum(earlier) / len(earlier)
            avg_volume = round(mean)
            if mean:
                rel_volume = round(regular_volume(last_regular) / mean, 2)

    gap = None
    if open_price is not None and regular_base:
        gap = {
            "change": round(open_price - regular_base, 4),
            "pct": round((open_price - regular_base) / regular_base * 100, 2),
        }

    trading_period = meta.get("currentTradingPeriod") or {}
    market_session = "closed"
    for name in ("pre", "regular", "post"):
        window = trading_period.get(name) or {}
        if window.get("start", 0) <= now < window.get("end", 0):
            market_session = name
    shown_price = headline_price(market_session, pre, regular, post)

    chart_day = days[current] if current is not None else None
    chart = {"points": [], "bands": {}}
    if chart_day:
        start = chart_day.get("pre", chart_day["regular"])[0]
        end = chart_day.get("post", chart_day["regular"])[1]
        rows = [c for c in candles if start <= c[0] < end]
        if not rows and current > 0:  # today has no prints yet: chart the last active day
            chart_day = days[current - 1]
            start = chart_day.get("pre", chart_day["regular"])[0]
            end = chart_day.get("post", chart_day["regular"])[1]
            rows = [c for c in candles if start <= c[0] < end]
        step = max(1, len(rows) // MAX_CHART_POINTS)
        sampled = rows[::step]
        if rows and sampled[-1] != rows[-1]:
            sampled.append(rows[-1])
        chart = {
            "points": [[t, round(p, 4)] for t, p in sampled],
            "bands": {k: v for k, v in chart_day.items()},
        }

    return {
        "symbol": symbol,
        "name": meta.get("longName") or meta.get("shortName") or symbol,
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or "",
        "currency": meta.get("currency") or "",
        "type": meta.get("instrumentType") or "",
        "timezone": meta.get("exchangeTimezoneName") or "America/New_York",
        "has_ext": has_ext,
        "session": market_session,
        "regular": regular,
        "pre": pre,
        "post": post,
        "previous_close": regular_base,
        "open": round(open_price, 4) if open_price is not None else None,
        "gap": gap,
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "year_high": meta.get("fiftyTwoWeekHigh"),
        "year_low": meta.get("fiftyTwoWeekLow"),
        "day_range_pct": range_pct(
            shown_price, meta.get("regularMarketDayLow"), meta.get("regularMarketDayHigh")
        ),
        "day_swing_pct": swing_pct(
            meta.get("regularMarketDayLow"), meta.get("regularMarketDayHigh"), regular_base
        ),
        "year_range_pct": range_pct(
            shown_price, meta.get("fiftyTwoWeekLow"), meta.get("fiftyTwoWeekHigh")
        ),
        "volume": meta.get("regularMarketVolume"),
        "avg_volume": avg_volume,
        "rel_volume": rel_volume,
        "periods": trading_period,
        "chart": chart,
        "stale": False,
    }


cache = {}
cache_lock = threading.Lock()


def get_quote(symbol):
    with cache_lock:
        cached = cache.get(symbol)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    try:
        quote = build_quote(symbol, fetch_chart(symbol))
    except UpstreamError as exc:
        if cached:  # a brief Yahoo failure should not blank a card that has data
            log.warning("Serving stale %s: %s", symbol, exc)
            return {**cached[1], "stale": True}
        raise
    with cache_lock:
        cache[symbol] = (time.time(), quote)
    return quote


def quote_or_error(symbol):
    try:
        return get_quote(symbol)
    except TickerNotFound:
        return {"symbol": symbol, "error": "No data found for this ticker"}
    except UpstreamError as exc:
        return {"symbol": symbol, "error": str(exc)}
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        log.exception("Could not parse %s", symbol)
        return {"symbol": symbol, "error": f"Could not read quote ({exc})"}


# ------------------------------------------------------------------------ API
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/quotes")
def quotes():
    with config_lock:
        tickers = load_tickers()
    results = list(pool.map(quote_or_error, tickers + INDEXES))
    return jsonify(
        quotes=results[: len(tickers)],
        indexes=results[len(tickers):],
        server_time=time.time(),
    )


@app.post("/api/watchlist")
def add_ticker():
    # get_json refuses non-JSON bodies, so a form on another site cannot post here.
    symbol = normalize((request.get_json(silent=False) or {}).get("symbol"))
    if not symbol:
        return jsonify(error="That doesn't look like a ticker symbol"), 400
    with config_lock:
        if symbol in load_tickers():
            return jsonify(error=f"{symbol} is already on your watchlist"), 409
    try:
        quote = get_quote(symbol)
    except TickerNotFound:
        return jsonify(error=f"Couldn't find a ticker called {symbol}"), 404
    except UpstreamError:
        return jsonify(error="Quote service is unavailable, so the ticker couldn't be checked"), 502
    with config_lock:
        tickers = load_tickers()
        if symbol not in tickers:
            tickers.append(symbol)
            save_tickers(tickers)
    return jsonify(quote=quote, tickers=tickers), 201


@app.delete("/api/watchlist/<path:symbol>")
def remove_ticker(symbol):
    symbol = normalize(symbol)
    with config_lock:
        tickers = load_tickers()
        if symbol not in tickers:
            return jsonify(error="That ticker isn't on your watchlist"), 404
        tickers.remove(symbol)
        save_tickers(tickers)
    return jsonify(tickers=tickers)


@app.put("/api/watchlist")
def reorder():
    wanted = (request.get_json(silent=False) or {}).get("tickers")
    if not isinstance(wanted, list):
        return jsonify(error="Expected a list of tickers"), 400
    with config_lock:
        tickers = load_tickers()
        ordered = [t for t in dict.fromkeys(map(normalize, wanted)) if t in tickers]
        ordered += [t for t in tickers if t not in ordered]
        save_tickers(ordered)
    return jsonify(tickers=ordered)


@app.get("/api/search")
def search():
    term = request.args.get("q", "").strip()[:40]
    if not term:
        return jsonify(results=[])
    try:
        resp = session.get(
            SEARCH_URL,
            params={"q": term, "quotesCount": 6, "newsCount": 0, "listsCount": 0},
            timeout=5,
        )
        resp.raise_for_status()
        rows = resp.json().get("quotes", [])
    except (requests.RequestException, ValueError):
        return jsonify(results=[])  # suggestions are optional; typing a ticker still works
    return jsonify(
        results=[
            {
                "symbol": r["symbol"],
                "name": r.get("shortname") or r.get("longname") or "",
                "exchange": r.get("exchDisp") or "",
            }
            for r in rows
            if r.get("symbol") and normalize(r["symbol"])
        ]
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Loopback only: the app has no login and can change the local config file.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), threaded=True)
