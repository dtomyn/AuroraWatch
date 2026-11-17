---
title: Keep --pre CSS colour for pre-market session state only
summary: In static/style.css, `--pre` (amber) marks the pre-market session and stale notices, so don't reuse it to highlight unrelated data such as volume.
applies_to: static/style.css, static/app.js
source: job-5 (issue #5)
added: 2026-11-17
---

# Keep --pre CSS colour for pre-market session state only

`--pre` (#ffb454) is the pre-market session accent. Every use of it in static/style.css is session or staleness state: the clock state, the ribbon segment, the session label and live border, the pre chart line, and the `.stale` notice.

A review in job-5 sent a change back because `.relvol.hot` used `--pre` for a 1.5× volume highlight. That reads as pre-market state. The fix was `var(--up)`.

When adding emphasis for non-session data, use another existing token such as `--up` or `--down`. Do not add `--pre` for it. If you reuse a session colour on purpose, say so in a CSS comment.

## Evidence

static/style.css:11 (definition); uses at :75, :89, :159, :165, :172, :189 are all session or stale state; the fixed usage is at :188 (`.stats .relvol.hot { color: var(--up) }`). Prompted by the round-1 ui finding on `.relvol.hot`.
