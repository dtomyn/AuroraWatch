# Aurora Watch: Technical Specification

| | |
|---|---|
| **Status** | Current: describes the implementation as built |
| **Date** | 2026-10-30 |
| **Companion** | [Product requirements](PRD.md) |

## 1. Architecture

```
Browser (HTML/CSS/vanilla JS)
   |  JSON over HTTP, polled every 15 s
Flask server on 127.0.0.1:5000
   |-- watchlist.json      list of tickers
   |-- in-memory cache     quotes, 10 s TTL
   |-- HTTPS -> Yahoo Finance chart and search endpoints
```

| File | Purpose |
|---|---|
| `app.py` | Server: config storage, quote fetching and calculation, API routes |
| `templates/index.html` | Page structure |
| `static/app.js` | Polling, rendering, charts and interactions |
| `static/style.css` | Visual design and responsive layout |
| `watchlist.json` | User's tickers, created on first change |
| `requirements.txt` | Flask 3.1.3, requests 2.34.2 |

There is no database and no front-end build step or framework. Fonts (Space Grotesk, JetBrains Mono) load from Google Fonts and fall back to system fonts.

## 2. Configuration

| Setting | Default | Notes |
|---|---|---|
| `WATCHLIST_FILE` (env) | `watchlist.json` beside `app.py` | Config location |
| `PORT` (env) | `5000` | Host is fixed to `127.0.0.1` |
| `CACHE_TTL` (code) | 10 s | Per-ticker quote cache |
| `MAX_CHART_POINTS` (code) | 260 | Approximate cap on chart points per card |
| `INDEXES` (code) | SPY, QQQ, DIA | Always fetched |
| `POLL_MS` (`app.js`) | 15000 | Browser refresh interval |

### Config file format

```json
{
  "tickers": ["AAPL", "NVDA"]
}
```

- A bare JSON array is also accepted when reading.
- On load, entries are normalized, invalid ones dropped and duplicates removed.
- Saves write to a `.tmp` file, then replace the original with `os.replace`.
- An unparseable file is renamed `watchlist.corrupt-<timestamp>.json`.
- A process-wide lock guards each read-change-write. This does not protect against several server processes or hand edits made during a save.

### Ticker format

Pattern: `^\^?[A-Z0-9][A-Z0-9.\-=]{0,14}$`, applied after trimming and upper-casing. It admits forms such as `AAPL`, `BRK-B`, `BTC-USD`, `^GSPC` and `ES=F`.

## 3. HTTP API

All responses are JSON except `/`. Errors use the form `{"error": "message"}`.

| Method and path | Body or query | Success | Errors |
|---|---|---|---|
| `GET /` | | 200 HTML page | |
| `GET /api/quotes` | | 200 `{quotes, indexes, server_time}` | Per-ticker errors appear inside `quotes` |
| `POST /api/watchlist` | `{"symbol": "AAPL"}` | 201 `{quote, tickers}` | 400 invalid, 404 unknown, 409 duplicate, 415 not JSON, 502 source unavailable |
| `DELETE /api/watchlist/<symbol>` | | 200 `{tickers}` | 404 not on list |
| `PUT /api/watchlist` | `{"tickers": [...]}` | 200 `{tickers}` | 400 not a list, 415 not JSON |
| `GET /api/search` | `?q=term` (first 40 characters used) | 200 `{results: [{symbol, name, exchange}]}` | Failures return an empty list |

`PUT` only reorders. Unknown tickers in the request are ignored, and existing tickers missing from it are appended, so it can't add or delete entries.

### Quote object

| Field | Description |
|---|---|
| `symbol`, `name`, `exchange`, `currency`, `type`, `timezone` | Identity and display details |
| `has_ext` | Instrument offers extended hours (false for crypto) |
| `session` | `pre`, `regular`, `post` or `closed` |
| `pre`, `regular`, `post` | `{price, change, pct, base, time}` or `null` |
| `previous_close` | Base used for the regular session |
| `day_high`, `day_low`, `year_high`, `year_low`, `volume` | Reference stats |
| `periods` | Yahoo's current trading periods, used by the market clock |
| `chart` | `{points: [[epoch, price], ...], bands: {pre, regular, post}}`, each band `[start, end]` |
| `stale` | True when serving the last good quote after a failure |

A ticker that fails returns `{symbol, error}`.

## 4. Quote source

- **Quotes:** `GET query1.finance.yahoo.com/v8/finance/chart/<symbol>?range=5d&interval=1m&includePrePost=true`
- **Search:** `GET query1.finance.yahoo.com/v1/finance/search?q=<term>&quotesCount=6&newsCount=0&listsCount=0`
- A browser-style `User-Agent` is required.
- HTTP 404 or an empty result means unknown ticker. Other failures are upstream errors.

## 5. Quote calculation

`build_quote` works from one-minute candles and per-day session windows (`meta.tradingPeriods`). Null candles are discarded. Twenty-four-hour instruments return a bare list of periods, which is treated as regular-only.

| Term | Definition |
|---|---|
| Current day | Latest day whose first session has started |
| Last regular day | Latest day with regular-session candles |
| Official close | Day = last regular: `regularMarketPrice`. Day before it: `previousClose`. Otherwise: the day's last regular candle |

Official closes are preferred because the last one-minute candle can differ from the closing auction price.

| Session | Price | Base |
|---|---|---|
| Pre | Last pre-market candle of the current day | Official close of the prior day |
| Regular | `regularMarketPrice` | Official close of the day before the last regular day, else `previousClose` |
| Post | Last post-market candle of the current day, else of the prior day | Official close of that same day |

Pre and post are `null` unless `hasPrePostMarketData` is true and the type isn't crypto.

**Headline figure (`activeMove`, client side):** live pre or post when it has a price. When closed, post if its last trade is newer than the regular price. Otherwise regular.

**Session state:** compared on the server against `currentTradingPeriod`. The clock recalculates each second from SPY's periods, corrected for the server-client time difference.

**Chart data:** the current day's candles, or the prior day's if today has none, evenly sampled with the latest point always kept.

## 6. Caching and failure handling

| Situation | Behaviour |
|---|---|
| Quote under 10 s old | Served from cache |
| Source error, cached quote exists | Old quote returned with `stale: true`, however old it is |
| Source error, no cached quote | `{symbol, error}` shown on the card |
| Ticker no longer found | Error shown on the card, ticker stays on the list until removed |
| Search failure | No suggestions shown |
| Server unreachable | Cards stay, status shows a warning once data is over 45 s old |

The cache lives in memory and is cleared on restart. Entries aren't evicted, which is negligible at watchlist scale.

## 7. Front-end behaviour

- **State:** one in-memory `state` object. The server is the source of truth for the list.
- **Rendering:** cards are matched by symbol and updated in place, so animations and hover survive refreshes. Charts redraw only when their data changes.
- **Removal:** a removed ticker is ignored in poll results for 15 s, so a request already in flight can't bring it back.
- **Search:** debounced by 180 ms, and out-of-date responses are discarded.
- **Sorting:** top-movers and A-Z are display-only. Dragging switches to "My order" and saves.

### Visual design

| Element | Treatment |
|---|---|
| Session colours | Pre amber `#ffb454`, regular teal `#4de2d0`, post violet `#b491ff` |
| Direction colours | Up `#34e3a0`, down `#ff5c7c`, plus a sign on every change |
| Background | Blurred, slowly drifting aurora shapes under translucent panels |
| Motion | Rolling digits, price-change card flash, chart reveal, cursor spotlight, scrolling tape, pulsing "now" marker |
| Responsive | Fluid card grid, with phone adjustments at 640 px and below |
| Reduced motion | Animations effectively disabled and tape hidden |

## 8. Security

| Concern | Control |
|---|---|
| Network exposure | Bound to loopback, no login |
| Cross-site changes | POST and PUT need a JSON content type, which browsers won't send cross-site without a preflight the server doesn't approve. DELETE also needs a preflight |
| Injection | Tickers checked by pattern, URL-encoded for Yahoo, never used in file paths |
| Script injection | Source text passes through `esc()` or `textContent` |

DNS rebinding isn't addressed because the server doesn't check the `Host` header. The practical exposure is limited to changing the ticker list.

## 9. Running

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python app.py
```

Open http://127.0.0.1:5000. Paths shown are for Windows.

## 10. Verification

Checks were manual, on 2026-10-30, during regular market hours. There is no automated suite.

| Area | Method | Result |
|---|---|---|
| Add, search, remove, bad ticker | Live, in browser | Pass |
| Config saved and list reloaded | Inspected file, reloaded page | Pass |
| Reorder, rejected form post, malformed ticker | Direct API calls | Pass |
| Regular-session figures | Live, compared with API values | Pass |
| Pre-market and after-hours calculations | Replayed saved AAPL data, partly with made-up candles | Pass |
| Empty state and phone-width layout | Browser | Pass |
| Drag reorder with a mouse | Not exercised | Not tested |
| Server restart with existing list | Not exercised (file is re-read on every request) | Not tested |
| Live extended-hours session, market holiday | Not exercised | Not tested |
