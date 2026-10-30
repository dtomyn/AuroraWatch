"""Records docs/demo/aurora-watch-demo.mp4 by driving the real app with live quotes.

Uses a temporary watchlist, so your own watchlist.json is not touched.
Setup: pip install -r docs/demo/requirements.txt && playwright install chromium
Run:   python docs/demo/record_demo.py
"""
import base64, json, os, shutil, subprocess, tempfile, time, urllib.request
from pathlib import Path
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

SCRATCH = Path(tempfile.gettempdir()) / "aurora_demo_build"
SCRATCH.mkdir(exist_ok=True)
PROJECT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent / "aurora-watch-demo.mp4"
MAX_MB = 10  # GitHub limit for videos in READMEs and issues on free accounts
FRAMES = SCRATCH / "frames"
CFG = SCRATCH / "demo_watchlist.json"
PORT = 5077
W, H = 1440, 810

INIT = r"""
Element.prototype.scrollIntoView = function () {};
addEventListener('DOMContentLoaded', () => {
  const css = document.createElement('style');
  css.textContent = `
    html { overflow: hidden !important; height: 100%; }
    body { background: transparent !important; transform-origin: 0 0; transition: transform 1.25s cubic-bezier(.65,0,.2,1); overflow: visible !important; }
    #demo { position: fixed; inset: 0; z-index: 9999; pointer-events: none; font-family: "Space Grotesk", sans-serif; color: #eef1fb; }
    #cursor { position: absolute; left: 0; top: 0; width: 26px; height: 26px; filter: drop-shadow(0 3px 5px rgba(0,0,0,.6)); }
    .ripple { position: absolute; width: 44px; height: 44px; margin: -22px; border-radius: 50%; border: 2px solid #4de2d0; animation: rip .55s ease-out forwards; }
    @keyframes rip { from { transform: scale(.2); opacity: 1 } to { transform: scale(1.3); opacity: 0 } }
    #caption { position: absolute; left: 50%; bottom: 30px; transform: translate(-50%, 16px); opacity: 0; transition: .4s; max-width: 80%; padding: 13px 26px; border-radius: 14px; background: rgba(9,12,24,.93); border: 1px solid rgba(77,226,208,.5); font-size: 23px; font-weight: 500; white-space: nowrap; box-shadow: 0 14px 44px rgba(0,0,0,.6); }
    #caption.on { transform: translate(-50%, 0); opacity: 1; }
    #card { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; background: #070a14; opacity: 0; transition: opacity .7s; }
    #card.on { opacity: 1; }
    #card h1 { font-size: 76px; margin: 18px 0 8px; letter-spacing: -.03em; }
    #card p { font-size: 27px; color: #98a2c2; margin: 0; }
    #card code { font: 500 22px "JetBrains Mono", monospace; color: #4de2d0; display: block; margin-top: 30px; }
    #card svg { width: 92px; height: 92px; padding: 16px; border-radius: 24px; background: linear-gradient(145deg, rgba(77,226,208,.24), rgba(180,145,255,.24)); border: 1px solid rgba(160,180,255,.28); fill: none; stroke: #4de2d0; stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round; }
    #file { position: absolute; right: 44px; top: 90px; width: 400px; padding: 18px 22px; border-radius: 16px; background: #0c1020; border: 1px solid rgba(77,226,208,.5); box-shadow: 0 24px 70px rgba(0,0,0,.7); opacity: 0; transform: translateY(12px); transition: .45s; font: 500 19px/1.5 "JetBrains Mono", monospace; white-space: pre; }
    #file.on { opacity: 1; transform: none; }
    #file b { display: block; color: #98a2c2; font-size: 15px; font-weight: 500; margin-bottom: 8px; }
  `;
  document.head.append(css);
  const aurora = document.querySelector('.aurora');
  document.documentElement.prepend(aurora);
  const demo = document.createElement('div');
  demo.id = 'demo';
  demo.innerHTML = `<div id="caption"></div><div id="file"></div>
    <div id="card" class="on"><svg viewBox="0 0 32 32"><path d="M3 24 12 12l6 7 11-14"/></svg><h1 id="cardT"></h1><p id="cardS"></p><code id="cardC"></code></div>
    <svg id="cursor" viewBox="0 0 24 24"><path d="M4 2l15 12-7 1 4 7-3 1.6-4-7-5 5z" fill="#fff" stroke="#111" stroke-width="1.2"/></svg>`;
  document.documentElement.append(demo);
  addEventListener('mousemove', e => { document.getElementById('cursor').style.transform = `translate(${e.clientX}px, ${e.clientY}px)`; });
  addEventListener('mousedown', e => { const r = document.createElement('div'); r.className = 'ripple'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; demo.append(r); setTimeout(() => r.remove(), 600); });
  window.demoCaption = t => { const c = document.getElementById('caption'); if (t) c.textContent = t; c.classList.toggle('on', !!t); };
  window.demoCard = (on, t, s, code) => { if (t !== undefined) { cardT.textContent = t; cardS.textContent = s || ''; cardC.textContent = code || ''; } document.getElementById('card').classList.toggle('on', on); };
  window.demoFile = t => { const f = document.getElementById('file'); if (t) f.innerHTML = '<b>watchlist.json</b>' + t; f.classList.toggle('on', !!t); };
  window.demoCam = (sel, pad = 24, maxS = 3) => {
    const body = document.body;
    if (!sel) { body.style.transform = 'none'; return; }
    const m = new DOMMatrix(getComputedStyle(body).transform);
    const r = document.querySelector(sel).getBoundingClientRect();
    const x0 = (r.left - m.e) / m.a, y0 = (r.top - m.f) / m.a, w = r.width / m.a, h = r.height / m.a;
    const s = Math.min(innerWidth / (w + 2 * pad), (innerHeight - 110) / (h + 2 * pad), maxS);
    const docH = body.scrollHeight;
    let x = x0 + w / 2 - innerWidth / s / 2, y = y0 + h / 2 - (innerHeight - 80) / s / 2;
    x = Math.max(0, Math.min(x, innerWidth - innerWidth / s));
    y = Math.max(0, Math.min(y, Math.max(0, docH - innerHeight / s)));
    body.style.transform = `translate(${-x * s}px, ${-y * s}px) scale(${s})`;
  };
});
"""

CFG.write_text('{"tickers": []}\n')
if FRAMES.exists():
    shutil.rmtree(FRAMES)
FRAMES.mkdir()
server = subprocess.Popen(
    [str(PROJECT / ".venv/Scripts/python.exe"), str(PROJECT / "app.py")],
    env={**os.environ, "WATCHLIST_FILE": str(CFG), "PORT": str(PORT)},
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
for _ in range(40):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/quotes", timeout=20); break
    except Exception:
        time.sleep(.5)

log = []
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=4 / 3)
        page = ctx.new_page()
        page.add_init_script(INIT)
        page.goto(f"http://127.0.0.1:{PORT}/")
        page.wait_for_function("window.demoCard && document.fonts.status === 'loaded'")
        page.evaluate("demoCard(true, 'Aurora Watch', 'Before the bell. After the close.')")
        page.wait_for_selector("#indexes .index", timeout=30000)

        cdp = ctx.new_cdp_session(page)
        def on_frame(ev):
            i = len(log)
            (FRAMES / f"{i:06d}.jpg").write_bytes(base64.b64decode(ev["data"]))
            log.append(ev["metadata"]["timestamp"])
            cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        cdp.on("Page.screencastFrame", on_frame)
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080})

        mouse = [W * .8, H * .25]
        wait = page.wait_for_timeout
        cap = lambda t=None: page.evaluate("t => demoCaption(t)", t)
        def cam(sel=None, pad=24, maxS=3, settle=1450):
            page.evaluate("([s,p,m]) => demoCam(s,p,m)", [sel, pad, maxS])
            wait(settle)
        def glide(x, y, ms=650):
            n = max(8, ms // 22)
            sx, sy = mouse
            for i in range(1, n + 1):
                t = i / n; e = t * t * (3 - 2 * t)
                page.mouse.move(sx + (x - sx) * e, sy + (y - sy) * e)
                wait(16)
            mouse[:] = [x, y]
        def to(sel):
            b = page.locator(sel).first.bounding_box()
            glide(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        def click(sel):
            to(sel); wait(150); page.mouse.down(); page.mouse.up()
        def add(text, delay=95):
            page.keyboard.type(text, delay=delay)

        page.mouse.move(*mouse)
        wait(2800)
        page.evaluate("demoCard(false)")
        wait(900)

        # Add the first ticker from company-name search
        cap("Start with an empty watchlist"); wait(2600)
        cap("Search by company name or ticker")
        cam(".top", pad=20, maxS=1.9)
        click("#addInput"); wait(300)
        add("nvidia", 130)
        page.wait_for_selector("#suggest li", timeout=8000); wait(1600)
        page.keyboard.press("ArrowDown"); wait(700)
        page.keyboard.press("Enter")
        page.wait_for_selector('.card[data-symbol="NVDA"]', timeout=15000)
        cap("Each ticker is checked, then saved right away")
        cam(None, settle=1800)

        # Add more
        cap("Add as many as you like")
        for s in ("AAPL", "TSLA", "MSFT"):
            add(s, 120); wait(300); page.keyboard.press("Enter")
            page.wait_for_selector(f'.card[data-symbol="{s}"]', timeout=15000); wait(700)
        wait(500)
        cap("Unknown tickers are rejected")
        add("ZZZZQQ", 90); wait(250); page.keyboard.press("Enter")
        page.wait_for_selector(".toast", timeout=15000); wait(2300)
        page.evaluate("document.getElementById('addInput').value=''; document.activeElement.blur()")

        # Clock
        cap("The market clock shows the session and the next bell")
        cam(".clock", pad=16, maxS=1.6); wait(3400)

        # Sessions
        cap("Pre-market, regular and after-hours, side by side")
        cam('.card[data-symbol="NVDA"] .sessions', pad=18, maxS=2.6); wait(3800)

        # Chart
        cap("Each session has its own color on the chart. Hover for any price")
        cam('.card[data-symbol="NVDA"] .chart', pad=18, maxS=2.6)
        b = page.locator('.card[data-symbol="NVDA"] .chart').bounding_box()
        y = b["y"] + b["height"] / 2
        glide(b["x"] + b["width"] * .08, y, 500)
        glide(b["x"] + b["width"] * .62, y, 3200)
        wait(700)

        # Pulse and sort
        glide(W * .95, H * .1, 300)
        cap("See every mover at a glance")
        cam(".pulse", pad=18, maxS=1.9); wait(2800)
        cap("Sort by top movers, or drag cards into your own order")
        cam(".toolbar", pad=280, maxS=1.3, settle=1300)
        click('[data-sort="movers"]'); wait(2300)
        click('[data-sort="mine"]'); wait(900)

        # Remove and show file
        cap("Remove a ticker with one click")
        cam("#grid", pad=16, maxS=1.0, settle=1400)
        page.hover('.card[data-symbol="TSLA"]')
        click('.card[data-symbol="TSLA"] .remove'); wait(1500)
        real = json.dumps(json.loads(CFG.read_text()), indent=2)
        assert "TSLA" not in real
        cap("Your list lives in a simple local file")
        cam(None, settle=1000)
        page.evaluate("t => demoFile(t)", real); wait(3200)
        page.evaluate("demoFile(null)")
        cap(None)
        glide(W + 40, H / 2, 300)

        page.evaluate("demoCard(true, 'Aurora Watch', 'A local stock watchlist built with Python and Flask.', 'python app.py')")
        wait(3600)
        cdp.send("Page.stopScreencast")
        browser.close()
finally:
    server.terminate()

Path(SCRATCH / "frames.txt").write_text(
    "".join(f"file 'frames/{i:06d}.jpg'\nduration {max(log[i+1]-log[i], .001):.4f}\n" for i in range(len(log) - 1))
    + f"file 'frames/{len(log)-2:06d}.jpg'\n"
)
print("frames", len(log), "seconds", round(log[-1] - log[0], 1), "fps", round(len(log) / (log[-1] - log[0]), 1))

for crf in (25, 27, 29, 31, 33):
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-i", str(SCRATCH / "frames.txt"),
         "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
         "-crf", str(crf), "-an", "-movflags", "+faststart", str(OUTPUT)],
        check=True,
    )
    size = OUTPUT.stat().st_size / 1e6
    print(f"crf {crf}: {size:.1f} MB")
    if size < MAX_MB * .97:
        break
else:
    raise SystemExit(f"Could not get under {MAX_MB} MB")
