# Aurora Watch: Product Requirements Document

| | |
|---|---|
| **Status** | Current: describes the product as built |
| **Date** | 2026-10-30 |
| **Companion** | [Technical specification](SPECIFICATION.md) |

Requirements describe current behaviour, so they are written as "shall" statements about what exists. Goals and gaps not met by the build are listed separately in sections 8 and 9.

## 1. Summary

Aurora Watch is a single-user Python web app, run locally, for watching a personal list of stocks. Its focus is the prices that many watchlists hide: where a stock traded before the open and after the close. Tickers are added and removed in the app and stored in a local config file.

## 2. Problem

Pre-market and after-hours moves often signal how a stock will open or how the market reacted to news after the close. These figures are usually secondary in general-purpose finance tools and often need a separate lookup for each ticker. The user wants them side by side with regular-session prices, for their own list, without an account.

## 3. Goals

- Show pre-market, regular and post-market quotes together for every watched ticker.
- Make managing the list quick, from inside the app, with changes kept between runs.
- Make the current market session obvious at a glance.
- Deliver a striking visual experience (the original brief asked for a "WOW factor").

## 4. Non-goals

- Trading, order entry or brokerage integration.
- Investment advice, alerts or notifications.
- User accounts, multi-user use or hosted deployment.
- Portfolio tracking (holdings, cost basis, profit and loss).
- Historical charts beyond the current or latest trading day.
- Guaranteed real-time or exchange-licensed data.

## 5. Users

**Primary user:** an individual investor or market follower running the app on their own computer, who checks prices around the open and close. They are comfortable running a Python command but should not need to edit files to use the app.

## 6. Key user stories

| ID | As a user, I want to... | So that... |
|---|---|---|
| US-1 | add a ticker by symbol or company name | I can build my list without knowing exact symbols |
| US-2 | remove a ticker | my list stays relevant |
| US-3 | have my list still there after a restart | I only set it up once |
| US-4 | compare pre, regular and post prices on one card | I can see the overnight story at a glance |
| US-5 | know which session is live and how long it has left | I can read the prices in context |
| US-6 | see which of my stocks are moving most | I know where to look first |
| US-7 | arrange my list in my own order | the stocks I care about most come first |
| US-8 | see when data is stale or unavailable | I don't act on old prices unknowingly |

## 7. Functional requirements

### Watchlist management

| ID | Requirement |
|---|---|
| FR-1 | The user shall be able to add a ticker by typing a symbol and submitting. |
| FR-2 | While the user types, the app shall suggest matching symbols with company name and exchange, selectable by mouse or arrow keys and Enter. |
| FR-3 | Input shall be converted to upper case and checked against the allowed ticker format. |
| FR-4 | A ticker shall only be added after the quote source confirms it exists. |
| FR-5 | Adding an unknown, malformed or duplicate ticker shall show an error message and leave the list unchanged. |
| FR-6 | If the quote source is unavailable, the add shall be refused with a message saying the ticker couldn't be checked. |
| FR-7 | The user shall be able to remove any ticker from its card, including a card showing an error. |
| FR-8 | The user shall be able to drag cards to reorder the list. |
| FR-9 | The empty state shall offer one-click buttons for popular tickers. |
| FR-10 | Pressing `/` shall focus the add box. |

### Persistence

| ID | Requirement |
|---|---|
| FR-11 | Every add, remove and reorder shall be saved immediately to a local JSON config file. |
| FR-12 | The list and its order shall be restored on restart. |
| FR-13 | An unreadable config file shall be kept under a new backup name, and the app shall start with an empty list. |

### Quotes

| ID | Requirement |
|---|---|
| FR-14 | Each card shall show price, change and percent change for the pre-market, regular and post-market sessions. |
| FR-15 | Pre-market change shall be measured from the previous regular close. |
| FR-16 | Post-market change shall be measured from the regular close of the same trading day. |
| FR-17 | Regular change shall be measured from the prior regular close. |
| FR-18 | The live session shall be highlighted. Other sessions shall show the time of the last trade, or its date if not from today. |
| FR-19 | When today's after-hours session has no trades yet, the most recent earlier after-hours price shall be shown with its date. |
| FR-20 | A session with no trades shall read "No trades yet". Instruments without extended hours, such as crypto, shall read "Not offered". |
| FR-21 | Each card's headline shall show the most relevant price: the live session's, or when closed, the latest print. |
| FR-22 | Each card shall show company name, day range, 52-week range and volume. |
| FR-23 | Quotes shall refresh automatically every 15 seconds without a page reload. |

### Charts and market overview

| ID | Requirement |
|---|---|
| FR-24 | Each card shall chart the trading day, colour-coded by session, with a dashed previous-close line. |
| FR-25 | Hovering a chart shall show the price and time at that point. |
| FR-26 | A market clock shall show New York time, the current session, a countdown to the next session change, and a position marker on a session ribbon. |
| FR-27 | The app shall show SPY, QQQ and DIA percent moves. |
| FR-28 | A summary shall show counts of advancing and declining tickers, and a heat map coloured by percent move. Clicking a tile shall locate that stock's card. |
| FR-29 | A scrolling ticker tape shall show the indexes and watched tickers, pausing on hover. |
| FR-30 | Cards shall be sortable by user order, top movers or A-Z. Only user order is saved. |

### Status and errors

| ID | Requirement |
|---|---|
| FR-31 | The app shall show the time since the last successful update, and a warning state if the server can't be reached. |
| FR-32 | If a refresh fails for a ticker with earlier data, the last good quote shall stay on screen, marked as delayed. |
| FR-33 | A ticker with no earlier data that can't be loaded shall show an error on its own card without affecting other cards. |

## 8. Non-functional requirements

Status: **Met** = checked during the build. **By design** = true of the implementation but not separately measured. **Partial** = see note.

| ID | Category | Requirement | Status |
|---|---|---|---|
| NFR-1 | Performance | Quotes from the source shall be cached for 10 seconds per ticker, so several tabs don't multiply requests. | By design |
| NFR-2 | Performance | Tickers shall be fetched in parallel, up to 8 at once. | By design |
| NFR-3 | Performance | Requests to the source shall time out: 10 seconds for quotes, 5 for search. | By design |
| NFR-4 | Reliability | Config writes shall be atomic, so an interrupted save can't corrupt the existing list. | By design |
| NFR-5 | Reliability | Concurrent config changes shall be serialized within the server process. | By design |
| NFR-6 | Reliability | A failed search shall not block adding a ticker by symbol. | By design |
| NFR-7 | Security | The server shall accept connections from the local machine only. | By design |
| NFR-8 | Security | State-changing POST and PUT requests shall require a JSON body, so plain forms on other sites can't change the list. | Met |
| NFR-9 | Security | Ticker input shall be validated against an allow-list pattern before use in file or network operations. | Met |
| NFR-10 | Security | Text from the quote source shall be escaped before being rendered in the page. | By design |
| NFR-11 | Privacy | No account or personal data shall be needed. Only ticker symbols and search terms leave the machine. Loading web fonts also contacts Google. | By design |
| NFR-12 | Usability | Layout shall work at phone width (375 px) with no horizontal scroll. | Met |
| NFR-13 | Accessibility | Motion shall be reduced under the operating system's reduced-motion setting. | By design |
| NFR-14 | Accessibility | Controls shall have visible keyboard focus. Direction shall be shown by sign as well as colour. | Partial: drag reorder and chart values have no keyboard equivalent |
| NFR-15 | Portability | The app shall run on Python 3.12 with two pinned dependencies and no build step. Tested on Windows 11 only. | Met |
| NFR-16 | Maintainability | Config path and port shall be settable through environment variables. | By design |
| NFR-17 | Compliance | The interface shall state that quotes may be delayed and are for information only. | Met |

## 9. Known gaps and risks

| Item | Impact |
|---|---|
| The quote source is Yahoo's unofficial endpoint, with no service guarantee or licence for this data. | It may change, throttle or stop without notice. Suitable for personal use only. |
| Extended-hours views were verified by replaying saved data, not during a live session. | Real pre-market and after-hours screens are unconfirmed. |
| Market holidays are untested. | Clock and session display on those days are unconfirmed. |
| There is no automated test suite. | Regressions must be caught by hand. |
| An unexpected response format while adding a ticker isn't handled as cleanly as during refresh. | The add fails with a generic server error. |
| The server uses Flask's development server. | Acceptable for one local user, not for hosting. |

## 10. Success criteria

The product meets its original brief when a user can:

1. Start the app with one command and add a ticker within seconds.
2. See pre and post-market prices for every ticker without extra clicks.
3. Restart and find the same list in the same order.
4. Tell the current session at a glance.

Criteria 1, 2 and 4 were met in testing, with the extended-hours caveat in section 9. Criterion 3 is met by design, since the list is re-read from the config file on every request, but an actual server restart and a mouse drag reorder were not exercised.
