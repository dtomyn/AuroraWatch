# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup and Running

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python app.py
```

App runs at http://127.0.0.1:5000. No build step — Flask serves static files directly.

**Environment variables:**
- `WATCHLIST_FILE` — path to the watchlist JSON (default: `watchlist.json` next to `app.py`)
- `PORT` — port to listen on (default: `5000`)

## Architecture

This is a single-file Flask app (`app.py`) with a vanilla JS frontend. There is no framework, bundler, or test suite.

**Data flow:**
1. The browser polls `/api/quotes` every 15 seconds
2. Flask fetches from Yahoo Finance's unofficial chart endpoint (`/v8/finance/chart/{symbol}`) with a 10-second in-memory cache (`CACHE_TTL`)
3. Quote data is parsed in `build_quote()` into pre-market, regular, and after-hours moves
4. The frontend renders cards, an SVG intraday chart, a market clock, and a heatmap — all in `static/app.js` with no dependencies

**Key backend functions (`app.py`):**
- `build_quote(symbol, raw)` — converts raw Yahoo chart JSON into the structured quote dict returned by the API; the most complex function, handling multi-day trading period windows
- `trading_days(meta)` — parses Yahoo's `tradingPeriods` structure (which differs between regular equities and 24h instruments like crypto) into a list of `{pre, regular, post}` dicts
- `get_quote(symbol)` — cache layer; serves stale data on upstream errors rather than blanking cards
- Watchlist is persisted as `{"tickers": [...]}` in `watchlist.json`; writes are atomic via a `.tmp` file + `os.replace()`

**Key frontend logic (`static/app.js`):**
- `activeMove(q)` — picks the session (pre/regular/post) to display as the headline price
- `odometer()` — rolling digit animation for price changes
- `chartMarkup(q)` — generates inline SVG from chart points, with separate colored path segments per session band
- Drag-to-reorder calls `PUT /api/watchlist` to persist order
- `state.offset` synchronizes client clock with the server to correctly identify the active trading session

**Fixed index tickers** (`SPY`, `QQQ`, `DIA`) are always fetched and shown in the header; they are not in `watchlist.json`.

**Ticker validation:** `TICKER_RE = r"^\^?[A-Z0-9][A-Z0-9.\-=]{0,14}$"` — used on both add and delete paths.
