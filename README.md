# Aurora Watch

A local stock watchlist that shows pre-market, regular and after-hours quotes.

Want an even simpler Windows version? see: https://github.com/dtomyn/AuroraWatchLite

https://github.com/user-attachments/assets/fc4f0571-cc68-4cb2-9a3d-755d3ec829fb

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python app.py
```

Open http://127.0.0.1:5000. Add and remove tickers in the app; they are saved to `watchlist.json` as you go.
Set `WATCHLIST_FILE` or `PORT` to change the config path or port.

Quotes come from Yahoo Finance's public chart endpoint, which is unofficial and may be delayed.

## Dev container

With Docker and the VS Code Dev Containers extension installed, run **Dev Containers: Reopen in Container**, then:

```bash
python app.py
```

VS Code forwards port 5000 to http://localhost:5000. To re-record the demo video in the container, run `python docs/demo/record_demo.py`.

## Architecture

```mermaid
flowchart LR
    subgraph machine["Your computer"]
        subgraph browser["Browser"]
            ui["Web UI<br/>index.html, app.js, style.css"]
        end
        subgraph server["Flask server, 127.0.0.1:5000 (app.py)"]
            api["REST API<br/>/api/quotes, /api/watchlist, /api/search"]
            quotes["Quote builder<br/>pre, regular and post moves"]
            cache[("In-memory cache<br/>10 s per ticker")]
        end
        config[("watchlist.json<br/>saved tickers")]
    end
    yahoo["Yahoo Finance<br/>chart and search endpoints"]

    ui -- "polls every 15 s,<br/>add, remove, reorder, search" --> api
    api -- "read and atomic write" --> config
    api --> quotes
    quotes <--> cache
    quotes -- "HTTPS, on cache miss" --> yahoo
    api -- "ticker search" --> yahoo
```

See the [product requirements](docs/PRD.md) and [technical specification](docs/SPECIFICATION.md) for details.
