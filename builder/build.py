#!/usr/bin/env python3
"""Build the OTO race guide site:
   out/index.html    — legs page (home): jump bar, runner/slot filter, leg cards by section
   out/overview.html — dashboard: skyline, sections, planner, all-legs table, rules
   out/print.html    — everything on one page, print CSS -> PDF
Elevation profiles: if out/elev.json exists ({"1": [[mi, ft], ...], ...}), native SVG
profiles are embedded in each leg card.
"""
import base64, importlib, io, json, os, re, html as H
import qrcode
_d = importlib.import_module(os.environ.get("OTO_DATA", "data"))
LEGS, NAMES, STRAVA, EXCHANGES, SECTIONS, RACE = _d.LEGS, _d.NAMES, _d.STRAVA, _d.EXCHANGES, _d.SECTIONS, _d.RACE
TOTAL_MI, TOTAL_GAIN, RUNNERS, PLAN, TEAM_NAME, N_RUNNERS = _d.TOTAL_MI, _d.TOTAL_GAIN, _d.RUNNERS, _d.PLAN, _d.TEAM_NAME, _d.N_RUNNERS
RACE_DAYS = getattr(_d, "RACE_DAYS", ["Fri", "Sat", "Sun"])
START_KEY = getattr(_d, "START_KEY", "0")      # STARTS key for the race start line
START_LABEL = getattr(_d, "START_LABEL", "LAKE LEATHERWOOD CITY BALLPARK")
ACCENT = getattr(_d, "ACCENT", None)            # optional accent override for a distinct look
JS_PREFIX = getattr(_d, "JS_PREFIX", "js/")
OUT_DIR = os.environ.get("OTO_OUT", "out")
RACE_ID = getattr(_d, "RACE_ID", "205")
PLAN_NOTE = getattr(_d, "PLAN_NOTE", "waves 6:00 AM–noon, assigned by team pace")

DIFF = {"Easy": "#0ca30c", "Moderate": "#fab219", "Hard": "#ec835a", "Very Hard": "#d03b3b"}
# deliberately outside the difficulty palette (green/yellow/orange/red)
SURF = {"pavement": "#64748b", "gravel": "#a97142", "trail": "#14919b"}

# starts.json: leg start/exchange coordinates from the race's official
# "Google Maps Exchange Zones" My Maps (mid=1S3rWAD35CEJBqz6sRkXKpyRrL0PEO_w),
# exported as KML July 2026. Key k = exchange zone k = start of leg k+1;
# key 0 = start line, 36 = finish line. Verified against leg distances +
# reverse-geocoded landmarks (Hobbs, Withrow, Elkins, L. Ft. Smith, Devil's Den).
STARTS = json.load(open("starts.json")) if os.path.exists("starts.json") else {}

ELEV, ELEV_META = {}, {}
for p in ("out/elev.json", "elev.json"):
    if os.path.exists(p):
        ELEV = {int(k): v for k, v in json.load(open(p)).items()}
        mp = p.replace("elev.json", "elev_meta.json")
        if os.path.exists(mp):
            ELEV_META = {int(k): v for k, v in json.load(open(mp)).items()}
        break

def qr_datauri(url, box=4):
    q = qrcode.QRCode(border=2, box_size=box)
    q.add_data(url); q.make(fit=True)
    img = q.make_image(fill_color="#0b0b0b", back_color="white")
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def esc(s): return H.escape(s, quote=False)
def fmt_mi(x): return f"{x:,.2f}".rstrip("0").rstrip(".")
def strava_url(n): return f"https://www.strava.com/routes/{STRAVA[n]}"
def ftpmi(l): return l["gain"] / l["dist"]

# ---------------- skyline ----------------
# ---------------- timeline estimates ----------------
def hm(s):
    h, m = map(int, s.split(":")); return h * 60 + m

DAYS = RACE_DAYS
def fmt_clock(t):
    d = int(t // 1440); mm = int(round(t % 1440))
    h, m = divmod(mm, 60)
    return f'{DAYS[min(d, len(DAYS)-1)]} {h % 12 or 12}:{m:02d} {"AM" if h < 12 else "PM"}'

def phase_emoji(t):
    c = t % 1440
    sr, ss = hm(PLAN["sunrise"]), hm(PLAN["sunset"])
    if sr - 45 <= c < sr + 45: return "🌅"
    if ss - 45 <= c < ss + 45: return "🌆"
    if sr + 45 <= c < ss - 45: return "☀️"
    return "🌙"

def est_start_html(l):
    t = hm(PLAN["start_hhmm"]) + PLAN["pace_min_per_mi"] * l["start_mi"]
    return f'<span class="eststart nowrap" data-mi="{l["start_mi"]}">{fmt_clock(t)} {phase_emoji(t)}</span>'

def night_regions(pace, t0):
    """Night intervals (sunset -> next sunrise) clipped to the race, in race miles."""
    t1 = t0 + pace * TOTAL_MI
    out = []
    for d in range(3):
        ns, ne = d * 1440 + hm(PLAN["sunset"]), (d + 1) * 1440 + hm(PLAN["sunrise"])
        a, b = max(ns, t0), min(ne, t1)
        if b > a:
            out.append(((a - t0) / pace, (b - t0) / pace, ns >= t0, ne <= t1))
    return out

# ---------------- skyline ----------------
SKY = dict(W=760, H=210, PADL=30, PADR=8, TOP=40, BOT=36)

def sky_layout():
    plot_w = SKY["W"] - SKY["PADL"] - SKY["PADR"]
    plot_h = SKY["H"] - SKY["TOP"] - SKY["BOT"]
    total_v = sum(ftpmi(l) for l in LEGS)
    segs, edges, xx = [], {}, SKY["PADL"]
    for l in LEGS:
        w = ftpmi(l) / total_v * plot_w
        segs.append(dict(a=l["start_mi"], b=l["end_mi"], x0=xx, x1=xx + w))
        xx += w
        edges[l["n"]] = xx
    return plot_w, plot_h, segs, edges

def mile_x(mi, segs):
    for s in segs:
        if s["a"] - 1e-9 <= mi <= s["b"] + 1e-9:
            return s["x0"] + (mi - s["a"]) / (s["b"] - s["a"]) * (s["x1"] - s["x0"])
    return segs[0]["x0"] if mi < segs[0]["a"] else segs[-1]["x1"]

def night_group(segs, plot_h):
    """Shade estimated night stretch on the skyline; regenerated live by JS when the plan changes."""
    TOP = SKY["TOP"]
    parts = []
    regions = night_regions(PLAN["pace_min_per_mi"], hm(PLAN["start_hhmm"]))
    day_spans = []
    cursor = 0.0
    for ma, mb, _, _ in regions:
        day_spans.append((cursor, ma)); cursor = mb
    day_spans.append((cursor, TOTAL_MI))
    for ma, mb, _, _ in regions:
        xa, xb = mile_x(ma, segs), mile_x(mb, segs)
        parts.append(f'<rect x="{xa:.1f}" y="{TOP}" width="{xb-xa:.1f}" height="{plot_h}" fill="var(--nightshade)"/>')
        parts.append(f'<text x="{(xa+xb)/2:.1f}" y="{TOP+10}" text-anchor="middle" font-size="9" fill="var(--ink2)">🌙 night</text>')
    for da, db in day_spans:
        if db - da > 18:
            parts.append(f'<text x="{(mile_x(da,segs)+mile_x(db,segs))/2:.1f}" y="{SKY["TOP"]+10}" text-anchor="middle" font-size="9" fill="var(--ink2)">☀️ day</text>')
    # estimated clock ticks every 6h along the bottom
    pace, t0 = PLAN["pace_min_per_mi"], hm(PLAN["start_hhmm"])
    t1 = t0 + pace * TOTAL_MI
    tick = (t0 // 360 + 1) * 360
    while tick < t1:
        x = mile_x((tick - t0) / pace, segs)
        d, mm = int(tick // 1440), int(tick % 1440)
        h = mm // 60
        lbl = f'{DAYS[min(d, len(DAYS)-1)]} {h % 12 or 12} {"AM" if h < 12 else "PM"}'
        parts.append(f'<line x1="{x:.1f}" y1="{TOP+plot_h}" x2="{x:.1f}" y2="{TOP+plot_h+4}" stroke="var(--axis)" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{TOP+plot_h+22}" text-anchor="middle" font-size="9" fill="var(--muted)">{lbl}</text>')
        tick += 360
    return f'<g id="nightg">{"".join(parts)}</g>'

def skyline_svg(legs_href="index.html"):
    """Height = leg distance, width = steepness (ft/mi), color = team-adjusted difficulty."""
    W, H_, PAD_L, PAD_R, TOP, BOT = SKY["W"], SKY["H"], SKY["PADL"], SKY["PADR"], SKY["TOP"], SKY["BOT"]
    plot_w, plot_h, segs, _ = sky_layout()
    total_v = sum(ftpmi(l) for l in LEGS)
    max_d = max(l["dist"] for l in LEGS)
    def y(d): return TOP + plot_h - d / max_d * plot_h
    parts = [f'<svg viewBox="0 0 {W} {H_}" role="img" aria-label="Every leg: bar height is distance in miles, bar width is climb rate" style="width:100%;height:auto;display:block">']
    for gv in (2, 4, 6, 8):
        parts.append(f'<line x1="{PAD_L}" y1="{y(gv):.1f}" x2="{W-PAD_R}" y2="{y(gv):.1f}" stroke="var(--grid)" stroke-width="1"/>')
        parts.append(f'<text x="{PAD_L-4}" y="{y(gv)+3:.1f}" text-anchor="end" font-size="9" fill="var(--muted)">{gv}</text>')
    parts.append(night_group(segs, plot_h))
    xx = PAD_L
    edges = {}
    for l in LEGS:
        v = ftpmi(l)
        w = v / total_v * plot_w
        rating = l["team"] or l["rating"]
        note = f'{l["rating"]} → {l["team"]} (team)' if l["team"] else l["rating"]
        slot = (l["n"] - 1) % N_RUNNERS + 1
        parts.append(f'<a class="skb" data-slot="{slot}" href="{legs_href}#leg-{l["n"]}">'
                     f'<rect x="{xx+0.6:.1f}" y="{y(l["dist"]):.1f}" width="{max(w-1.2,1.6):.1f}" height="{(TOP+plot_h-y(l["dist"])):.1f}" rx="2" '
                     f'fill="{DIFF[rating]}" stroke="rgba(0,0,0,.28)" stroke-width="0.5">'
                     f'<title>Leg {l["n"]} · {NAMES[l["n"]]} · {fmt_mi(l["dist"])} mi · +{l["gain"]:,} ft · {v:.0f} ft/mi · {note} · {RUNNERS.get(slot, "")}</title></rect>'
                     + (f'<text x="{xx+w/2:.1f}" y="{TOP+plot_h+10}" text-anchor="middle" font-size="9" fill="var(--muted)">{l["n"]}</text>' if w >= 10 else "")
                     + '</a>')
        xx += w
        edges[l["n"]] = xx
    parts.append(f'<line x1="{PAD_L}" y1="{TOP+plot_h}" x2="{W-PAD_R}" y2="{TOP+plot_h}" stroke="var(--axis)" stroke-width="1"/>')
    parts.append(f'<text x="{PAD_L}" y="{TOP-20}" text-anchor="start" font-size="8" font-weight="700" fill="var(--ink)">START</text>')
    parts.append(f'<text x="{W-PAD_R}" y="{TOP-20}" text-anchor="end" font-size="8" font-weight="700" fill="var(--ink)">FINISH</text>')
    for k in sorted(EXCHANGES):
        label = EXCHANGES[k]["name"].split("—")[0].split("State")[0].strip()
        mi = [l for l in LEGS if l["n"] == k][0]["end_mi"]
        ex = edges[k]
        parts.append(f'<line x1="{ex:.1f}" y1="{TOP-14}" x2="{ex:.1f}" y2="{TOP+plot_h}" stroke="var(--ink2)" stroke-width="0.8" stroke-dasharray="3 3"/>')
        parts.append(f'<text x="{ex:.1f}" y="{TOP-11}" text-anchor="middle" font-size="7" fill="var(--muted)">mi {fmt_mi(mi)}</text>')
        parts.append(f'<text x="{ex:.1f}" y="{TOP-20}" text-anchor="middle" font-size="8" font-weight="700" fill="var(--ink)">{esc(label)}</text>')
    parts.append(f'<text x="8" y="36" font-size="9" fill="var(--muted)">mi</text>')
    parts.append(f'<text x="30" y="{H_-4}" font-size="9" fill="var(--muted)">estimated clock time →</text>')
    parts.append("</svg>")
    return "".join(parts)

# ---------------- per-leg elevation profile ----------------
def profile_svg(n):
    pts = ELEV.get(n)
    if not pts:
        return ""
    W, H_, PL, PR, PT, PB = 620, 120, 40, 8, 8, 18
    pw, ph = W - PL - PR, H_ - PT - PB
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    lo, hi = min(ys), max(ys)
    rng = max(hi - lo, 40)
    lo_pad, hi_pad = lo - rng * 0.06, hi + rng * 0.08
    def X(d): return PL + (d - x0) / max(x1 - x0, 0.01) * pw
    def Y(e): return PT + (hi_pad - e) / (hi_pad - lo_pad) * ph
    path = f"M {X(xs[0]):.1f} {Y(ys[0]):.1f} " + " ".join(f"L {X(d):.1f} {Y(e):.1f}" for d, e in pts[1:])
    area = path + f" L {X(xs[-1]):.1f} {PT+ph} L {X(xs[0]):.1f} {PT+ph} Z"
    parts = [f'<svg viewBox="0 0 {W} {H_}" role="img" aria-label="Elevation profile leg {n}: {lo:.0f} to {hi:.0f} ft" style="width:100%;height:auto;display:block">']
    # y gridlines: round levels
    import math
    step = 100 if rng > 150 else 50
    gv = math.ceil(lo_pad / step) * step
    while gv < hi_pad:
        parts.append(f'<line x1="{PL}" y1="{Y(gv):.1f}" x2="{W-PR}" y2="{Y(gv):.1f}" stroke="var(--grid)" stroke-width="1" stroke-dasharray="3 3"/>')
        parts.append(f'<text x="{PL-4}" y="{Y(gv)+2.5:.1f}" text-anchor="end" font-size="9" fill="var(--muted)">{gv:,.0f}</text>')
        gv += step
    parts.append(f'<path d="{area}" fill="color-mix(in srgb, var(--accent) 22%, transparent)"/>')
    parts.append(f'<path d="{path}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>')
    # x ticks each mile
    m = 1
    while m < x1:
        parts.append(f'<text x="{X(m):.1f}" y="{PT+ph+11}" text-anchor="middle" font-size="9" fill="var(--muted)">{m} mi</text>')
        m += 1
    parts.append(f'<text x="{PL-4}" y="{PT+2}" text-anchor="end" font-size="9" fill="var(--muted)">ft</text>')
    parts.append("</svg>")
    return f'<div class="profile">{"".join(parts)}<div class="proflabel">Elevation profile · {lo:,.0f}–{hi:,.0f} ft <span class="tiny">(current 2026 Strava route)</span></div></div>'

# ---------------- components ----------------
def badge(label, rating):
    c = DIFF[rating]
    return (f'<span class="pill" style="--pc:{c}"><span class="dot"></span>'
            f'<span class="pl">{esc(label)}</span><b>{esc(rating)}</b></span>')

def surface_bar(l):
    seg = ""
    for pct, key in zip(l["surface"], ("pavement", "gravel", "trail")):
        if pct > 0:
            lbl = key if pct >= 22 else ""
            seg += f'<div class="seg" style="flex:{pct};background:{SURF[key]}" title="{pct}% {key}">{lbl}</div>'
    return (f'<div class="surfrow"><div class="surfbar">{seg}</div>'
            f'<div class="surftext">{esc(l["surface_text"])}</div></div>')

STEEP_ZONES = [(50, "Easy"), (100, "Moderate"), (150, "Hard"), (10**9, "Very Hard")]

def meter(l):
    v = ftpmi(l)
    zone = next(name for lim, name in STEEP_ZONES if v < lim)
    return (f'<div class="meterwrap" title="Steepness zones (ft/mi): under 50 easy · 50–100 moderate · 100–150 hard · 150+ very hard">'
            f'<div class="meter zoned"><div class="fill" style="width:{min(v/200,1)*100:.0f}%;background:{DIFF[zone]}"></div></div>'
            f'<span class="mval">{v:.0f} ft/mi</span></div>')

def climb_chips(l):
    return "".join(f'<span class="chip climb">▲ {g}% avg · {d} mi · {e:,} ft</span>' for g, e, d in l["climbs"])

def tag_chips(l):
    return "".join(f'<span class="chip warn">⚠ {esc(t)}</span>' for t in l["tags"])

def leg_card(l):
    n = l["n"]
    slot = (n - 1) % N_RUNNERS + 1
    team_b = badge("team says", l["team"]) if l["team"] else ""
    src_note = ' <span class="tiny">(rating from our sheet — missing in the note)</span>' if l.get("rating_src") else ""
    foot = f'<div class="footnote">ℹ {esc(l["footnote"])}</div>' if l.get("footnote") else ""
    m = ELEV_META.get(n)
    if m and abs(m["mi"] - l["dist"]) > 0.15:
        foot += (f'<div class="footnote">🔄 <b>2026 route update:</b> Strava now measures this leg at ~{m["mi"]:.1f} mi '
                 f'(our 2025 data: {fmt_mi(l["dist"])} mi / +{l["gain"]:,} ft). The profile below is the current route — '
                 f'expect the stats to shift a bit.</div>')
    url = strava_url(n)
    return f'''
<article class="leg" id="leg-{n}" data-slot="{slot}">
  <div class="leghead">
    <div class="legnum">{n:02d}</div>
    <div class="titleblock">
      <h3>{esc(NAMES[n])}</h3>
      <div class="meta">mile {fmt_mi(l["start_mi"])} → {fmt_mi(l["end_mi"])} · rotation slot {slot} · runner <span class="runner-name" data-slot="{slot}"><b>{esc(RUNNERS.get(slot) or "—")}</b></span> · est. start {est_start_html(l)}</div>
    </div>
    <div class="badges">{badge("official", l["rating"])}{team_b}</div>
  </div>
  <div class="statrow">
    <div class="stat"><b>{fmt_mi(l["dist"])}</b> mi</div>
    <div class="stat"><b>+{l["gain"]:,}</b> ft</div>
    {meter(l)}
    {climb_chips(l)}
  </div>
  {profile_svg(n)}
  {surface_bar(l)}
  <p class="beta"><span class="src">team beta</span>{esc(l["beta"])}{src_note}</p>
  <div class="tagrow">{tag_chips(l)}</div>
  {foot}
  <div class="legfoot">
    <a class="stravabtn web-only" href="{url}" target="_blank" rel="noopener">View route on Strava ↗</a>
    {map_links(n)}
    <div class="qrbox print-only"><img src="{qr_datauri(url)}" alt="QR: Strava route leg {n}"><span>Strava route</span></div>
  </div>
</article>'''

def nav_pair(key, label, btn_cls="stravabtn mapbtn"):
    """Google + Apple Maps navigation links (web) + coords (print) for a STARTS point."""
    st = STARTS.get(str(key))
    if not st: return ""
    ll = f'{st["lat"]:.6f},{st["lng"]:.6f}'
    return (f'<a class="{btn_cls} web-only" href="https://www.google.com/maps/dir/?api=1&amp;destination={ll}" '
            f'target="_blank" rel="noopener">📍 {label}Google Maps ↗</a>'
            f'<a class="{btn_cls} web-only" href="https://maps.apple.com/?daddr={ll}" '
            f'target="_blank" rel="noopener">📍 {label}Apple Maps ↗</a>'
            f'<span class="coords print-only">📍 {ll}</span>')

def map_links(n):
    """Navigation links to the leg's start (official exchange-zone coords)."""
    return nav_pair(n - 1, "Start · ")

def banner_exchange_row(i, first_leg):
    """Where this section begins (start line / major exchange), with nav links for the van."""
    if i == 0:
        head, note, key = f"🚩 START — {esc(START_LABEL)}", "mile 0 · race start", START_KEY
    else:
        ex = EXCHANGES[first_leg - 1]
        mi = [l for l in LEGS if l["n"] == first_leg - 1][0]["end_mi"]
        head = f'🚩 MAJOR EXCHANGE {i} — {esc(ex["name"].upper())}'
        extra = ex["note"].removeprefix(f"Major exchange {i}").strip(" ·")
        note = f'mile {fmt_mi(mi)}' + (f' · {esc(extra)}' if extra else "")
        key = str(first_leg - 1)
    return (f'<div class="secex"><div><b>{head}</b><span>{note}</span></div>'
            f'<div class="mapwrap">{nav_pair(key, "", "bannerbtn")}</div></div>')

def section_block(i, sec):
    a, b = sec["legs"]
    legs = [l for l in LEGS if a <= l["n"] <= b]
    mi = sum(l["dist"] for l in legs); gain = sum(l["gain"] for l in legs)
    origin = "Lake Leatherwood (START)" if i == 0 else SECTIONS[i - 1]["dest"]
    cards = "".join(leg_card(l) for l in legs)
    ex = "" if b in EXCHANGES else (
        '<div class="exchange finish"><span class="flag">🏁</span><div>'
        f'<b>FINISH — PRAIRIE GROVE BATTLEFIELD STATE PARK</b><span>mile {fmt_mi(TOTAL_MI)} · you did the thing</span>'
        f'<div class="mapwrap">{nav_pair(36, "Finish · ")}</div></div></div>')
    return f'''
<section class="chapter" id="sec{i+1}">
  <div class="secbanner">
    <div class="secno">SECTION {i+1}</div>
    <h2>Legs {a}–{b} · {esc(origin)} → {esc(sec["dest"])}</h2>
    <div class="sectotals">{mi:.1f} mi · +{gain:,} ft</div>
    {banner_exchange_row(i, a)}
  </div>
  {cards}
  {ex}
</section>'''

RATING_PTS = {"Easy": 1, "Moderate": 2, "Hard": 3, "Very Hard": 4}

def planner_table():
    slots = []
    for s in range(1, N_RUNNERS + 1):
        legs = [l for l in LEGS if (l["n"] - 1) % N_RUNNERS + 1 == s]
        mi = sum(l["dist"] for l in legs); gain = sum(l["gain"] for l in legs)
        pts = sum(RATING_PTS[l["team"] or l["rating"]] for l in legs)
        slots.append(dict(s=s, legs=legs, mi=mi, gain=gain, pts=pts))
    avg_mi = sum(x["mi"] for x in slots) / 6
    avg_gain = sum(x["gain"] for x in slots) / 6
    avg_pts = sum(x["pts"] for x in slots) / 6
    for x in slots:
        x["score"] = x["mi"] / avg_mi + x["gain"] / avg_gain + x["pts"] / avg_pts
    top = max(x["score"] for x in slots)
    slots.sort(key=lambda x: -x["score"])
    rows = ""
    for rank, x in enumerate(slots, 1):
        s, legs = x["s"], x["legs"]
        idx = round(100 * x["score"] / top)
        hardest = max(legs, key=lambda l: (RATING_PTS[l["team"] or l["rating"]], l["gain"], ftpmi(l)))
        dots = "".join(
            f'<span class="dotc" style="background:{DIFF[l["team"] or l["rating"]]}" '
            f'title="Leg {l["n"]} · {esc(NAMES[l["n"]])} · {l["team"] or l["rating"]}"></span>'
            for l in legs)
        rows += (f'<tr><td class="c"><b>{rank}</b></td><td class="c"><b>{s}</b></td>'
                 + (f'<td class="runner-name" data-slot="{s}"><b>{esc(RUNNERS[s])}</b></td>' if RUNNERS.get(s)
                    else f'<td class="blankcell runner-name" data-slot="{s}">&nbsp;</td>')
                 + f'<td>{", ".join(str(l["n"]) for l in legs)}</td><td class="r">{x["mi"]:.1f}</td><td class="r">{x["gain"]:,}</td>'
                 f'<td class="nowrap">{dots}</td>'
                 f'<td><div class="meterwrap"><div class="meter"><div class="fill" style="width:{idx}%"></div></div>'
                 f'<span class="mval">{idx}</span></div></td>'
                 f'<td>Leg {hardest["n"]} · {esc(NAMES[hardest["n"]])} ({hardest["team"] or hardest["rating"]} · +{hardest["gain"]:,} ft)</td></tr>')
    return f'''<div class="tscroll"><table class="tbl">
<thead><tr><th>Rank</th><th>Slot</th><th>Runner</th><th>Legs</th><th class="r">Miles</th><th class="r">Climb ft</th><th>Leg ratings</th><th>Difficulty</th><th>Toughest assignment</th></tr></thead>
<tbody id="plantbody">{rows}</tbody></table></div>
<p class="tiny" style="margin:.6em 0 0">Sorted hardest → easiest. Difficulty = equal parts total miles, total climb, and summed leg ratings (Easy 1 → Very Hard 4, team rating where it differs), scaled so the hardest slot = 100. Rating dots are in leg order<span class="web-only"> — hover for the leg</span>.</p>'''

def watch_panel(legs_href="index.html", inner=False):
    head = '' if inner else '<h2>Get your legs on your Garmin watch</h2>'
    open_div = '<div>' if inner else '<div class="panel" id="watch">'
    return f'''{open_div}
  {head}
  <p class="tiny" style="margin:.2em 0 .6em">Cell signal is spotty on the course — load your legs as courses <b>before race weekend</b> so the watch can guide you (route line, off-course alerts, climb profile) with no phone needed.</p>
  <ol class="steps">
    <li><b>Link Strava to Garmin (one-time).</b> Garmin Connect app → <i>Settings → Connected Apps → Strava</i> → sign in and enable the <b>Courses</b> permission.</li>
    <li><b>Save each of your legs on Strava.</b> Open the leg's Strava route from its card on the <a href="{legs_href}">Legs page</a> and tap the ☆ <b>star / save</b> icon so it lights up.</li>
    <li><b>Sync your watch</b> with the Garmin Connect app. Starred Strava routes are pushed to the watch automatically and land in <i>Courses</i>.</li>
    <li><b>Race day:</b> start a Run activity → hold <b>UP/MENU</b> → <i>Navigation → Courses</i> → pick your leg → <i>Do Course</i>. (Menu names vary slightly by model.)</li>
  </ol>
  <p class="tiny">Apple Watch has no native course-following — the WorkOutDoors app can import the same routes (export GPX from Strava), or use the map links on each leg card and run from the phone.</p>
</div>'''

def index_table(legs_href="index.html"):
    rows = ""
    max_d = max(l["dist"] for l in LEGS)
    max_g = max(l["gain"] for l in LEGS)
    max_v = max(ftpmi(l) for l in LEGS)
    def barcell(val, mx, text):
        return f'<td class="r bar" style="--p:{val/mx*100:.0f}%">{text}</td>'
    for l in LEGS:
        n = l["n"]
        team = f' → {l["team"]}' if l["team"] else ""
        surf = " / ".join(f"{k[0].upper()}{v}%" for v, k in zip(l["surface"], ("pav", "grav", "trail")) if v > 0)
        rows += (f'<tr data-slot="{(n - 1) % N_RUNNERS + 1}" data-n="{n}"><td class="c">{n}</td><td><a href="{legs_href}#leg-{n}">{esc(NAMES[n])}</a></td>'
                 + barcell(l["dist"], max_d, fmt_mi(l["dist"]))
                 + barcell(l["gain"], max_g, f'+{l["gain"]:,}')
                 + barcell(ftpmi(l), max_v, f'{ftpmi(l):.0f}')
                 + f'<td>{surf}</td>'
                 f'<td><span class="dotc" style="background:{DIFF[l["rating"]]}"></span>{l["rating"]}{team}</td>'
                 f'<td class="r">{fmt_mi(l["start_mi"])}</td>'
                 f'<td class="nowrap">{est_start_html(l)}</td></tr>')
        if n in EXCHANGES:
            rows += f'<tr class="exrow"><td colspan="9">🚩 {esc(EXCHANGES[n]["name"])} — mile {fmt_mi(l["end_mi"])}</td></tr>'
    return f'''<div class="tscroll"><table class="tbl small">
<thead><tr><th>#</th><th>Leg</th><th class="r">Mi</th><th class="r">Gain</th><th class="r">ft/mi</th><th>Surface</th><th>Rating (official → team)</th><th class="r">Starts @ mi</th><th>Est start</th></tr></thead>
<tbody>{rows}</tbody></table></div>'''

# ---------------- shared css ----------------
def css():
    base = '''
:root { color-scheme: light;
  --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10); --card:#ffffff; --accent:#2a78d6;
  --nightshade:rgba(38,52,110,.13) }
@media (prefers-color-scheme: dark) {
  :root:not([data-print]) { color-scheme: dark;
    --surface:#1a1a19; --page:#0d0d0d; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.12); --card:#232322; --accent:#3987e5;
    --nightshade:rgba(140,160,255,.18) } }
* { box-sizing:border-box }
:root { --mono: ui-monospace, SFMono-Regular, Menlo, monospace }
html { scroll-behavior:smooth }
body { margin:0; background:var(--page); color:var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", "Liberation Sans", "DejaVu Sans", sans-serif;
  font-size:14px; line-height:1.45; -webkit-print-color-adjust:exact; print-color-adjust:exact }
.wrap { max-width:860px; margin:0 auto; padding:0 16px 48px }
a { color:var(--accent) }
a, button { -webkit-tap-highlight-color: transparent }
h1,h2,h3 { line-height:1.15; margin:0 }
nav.top { position:sticky; top:0; z-index:9; background:var(--page); border-bottom:1px solid var(--grid); padding:8px 12px 0 }
.navrow { display:flex; gap:4px; overflow-x:auto; font-size:12.5px; white-space:nowrap; padding-bottom:8px; align-items:center }
.navrow a, .navrow button { text-decoration:none; color:var(--ink2); padding:5px 10px; border-radius:99px;
  border:1px solid var(--grid); background:none; font:inherit; font-size:12.5px; cursor:pointer;
  -webkit-appearance:none; appearance:none }
.navrow a:hover, .navrow button:hover { background:var(--card) }
.navrow .brand { font-weight:800; color:var(--ink); border:none; padding-left:0 }
.navrow .active { background:var(--ink); color:var(--page); border-color:var(--ink) }
.navrow .rowlabel { font-size:10px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); flex:none }
.navtabs a { font-weight:700 }
.jumprow { display:flex; gap:3px; overflow-x:auto; padding-bottom:8px }
.jumprow a { flex:none; position:relative; width:30px; height:34px; display:flex; align-items:center; justify-content:center;
  padding-bottom:6px; font-size:11.5px; font-weight:700; text-decoration:none; color:var(--ink2);
  border:1px solid var(--grid); border-radius:8px }
.jumprow a .d { position:absolute; bottom:3px; left:50%; transform:translateX(-50%); width:5px; height:5px; border-radius:50% }
.jumprow a:hover, .jumprow a:active { background:var(--card) }
.jumprow a:visited, .navrow a:visited { color:var(--ink2) }
.navrow .active:visited { color:var(--page) }
.hero { padding:30px 0 8px }
.hero .kicker { font-weight:800; letter-spacing:.14em; color:var(--accent); font-size:13px }
.hero h1 { font-size:32px; font-weight:800; letter-spacing:-.01em; margin:2px 0 4px }
.hero .sub { color:var(--ink2); font-size:15px }
.statgrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:8px; margin:18px 0 }
.tile { background:var(--card); border:1px solid var(--ring); border-radius:10px; padding:10px 12px }
.tile b { display:block; font-size:22px }
.tile span { color:var(--muted); font-size:11.5px; text-transform:uppercase; letter-spacing:.06em }
.panel { background:var(--card); border:1px solid var(--ring); border-radius:12px; padding:14px 16px; margin:14px 0 }
.panel h2 { font-size:16px; margin-bottom:8px }
.legendrow { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-top:8px; font-size:12px; color:var(--ink2) }
.pill { display:inline-flex; align-items:center; gap:5px; border:1.5px solid var(--pc);
  background:color-mix(in srgb, var(--pc) 13%, transparent); color:var(--ink);
  border-radius:99px; padding:2px 9px 2px 7px; font-size:11.5px; white-space:nowrap }
.pill .dot { width:8px; height:8px; border-radius:50%; background:var(--pc); flex:none }
.pill .pl { color:var(--ink2); font-size:10px; text-transform:uppercase; letter-spacing:.05em }
.chip { display:inline-block; border-radius:6px; padding:2px 7px; font-size:11px; margin:2px 3px 0 0;
  border:1px solid var(--ring); background:var(--surface); color:var(--ink2) }
.chip.climb { border-color:color-mix(in srgb, var(--accent) 45%, transparent); color:var(--ink) }
.dotc { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; outline:1px solid rgba(0,0,0,.2) }
.secbanner { margin:34px 0 12px; padding:14px 16px; border-radius:12px; background:var(--ink); color:var(--page) }
.secbanner .secno { font-size:11px; letter-spacing:.18em; opacity:.7; font-weight:700 }
.secbanner h2 { font-size:19px; margin:2px 0 }
.secbanner .sectotals { font-size:13px; opacity:.85 }
.secex { display:flex; flex-wrap:wrap; gap:8px 12px; align-items:center; justify-content:space-between;
  margin-top:11px; padding-top:11px; border-top:1px solid color-mix(in srgb, currentColor 25%, transparent) }
.secex b { display:block; font-size:12.5px; letter-spacing:.05em }
.secex > div > span { font-size:11.5px; opacity:.75 }
.secex .mapwrap { display:flex; gap:7px; flex-wrap:wrap; align-items:center }
.secex .coords { color:inherit; opacity:.7 }
.bannerbtn { display:inline-block; text-decoration:none; font-weight:700; font-size:12px; color:inherit;
  border:1.5px solid color-mix(in srgb, currentColor 45%, transparent); border-radius:8px; padding:4px 11px }
.leg { background:var(--card); border:1px solid var(--ring); border-radius:12px; padding:13px 15px; margin:10px 0 }
.leg.hidden, .hiddenx { display:none !important }
.leghead { display:flex; gap:12px; align-items:flex-start }
.legnum { font-size:26px; font-weight:800; color:var(--accent); line-height:1; padding-top:2px }
.titleblock { flex:1; min-width:0 }
.titleblock h3 { font-size:17px }
.titleblock .meta { font-size:11.5px; color:var(--muted); margin-top:2px }
.badges { display:flex; flex-direction:column; gap:4px; align-items:flex-end }
.statrow { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; margin:10px 0 6px }
.stat { font-size:13px; color:var(--ink2) }
.stat b { font-size:17px; color:var(--ink) }
.meterwrap { display:flex; align-items:center; gap:7px }
.meter { width:70px; height:7px; border-radius:99px; background:var(--grid); overflow:hidden }
.meter .fill { height:100%; background:var(--accent); border-radius:99px }
.meter.zoned { background:linear-gradient(to right,
  var(--grid) 0 24.5%, var(--axis) 24.5% 25.5%, var(--grid) 25.5% 49.5%, var(--axis) 49.5% 50.5%,
  var(--grid) 50.5% 74.5%, var(--axis) 74.5% 75.5%, var(--grid) 75.5% 100%) }
.mval { font-size:11.5px; color:var(--ink2) }
.profile { margin:8px 0 2px; border:1px solid var(--grid); border-radius:8px; padding:6px 8px 4px; background:var(--surface) }
.proflabel { font-size:10.5px; color:var(--muted); margin-top:2px }
.surfrow { margin:7px 0 }
.surfbar { display:flex; gap:2px; height:15px; border-radius:5px; overflow:hidden }
.seg { color:#fff; font-size:9.5px; text-transform:uppercase; letter-spacing:.06em;
  display:flex; align-items:center; justify-content:center; min-width:8px }
.surftext { font-size:11px; color:var(--muted); margin-top:3px }
.beta { margin:8px 0 4px; font-size:13.5px }
.beta .src, .beta2 .src, .srcbadge { display:inline-block; font-size:9.5px; font-weight:800; letter-spacing:.08em; text-transform:uppercase;
  color:var(--accent); border:1px solid color-mix(in srgb, var(--accent) 40%, transparent);
  border-radius:4px; padding:1px 5px; margin-right:7px; vertical-align:1px }
.tiny { font-size:11px; color:var(--muted) }
.nowrap { white-space:nowrap }
.steps { margin:8px 0 4px 20px; font-size:13.5px }
.steps li { margin:7px 0 }
#map iframe { width:100% !important; max-width:none !important }
.wrap.wide { max-width:1240px }
td.bar { background:linear-gradient(90deg, color-mix(in srgb, var(--accent) 22%, transparent) var(--p), transparent var(--p)); background-repeat:no-repeat }
.pillrow { display:flex; flex-wrap:wrap; gap:6px; margin:4px 0 10px }
.pillbtn { border:1px solid var(--grid); background:none; color:var(--ink2); font:inherit; font-size:12.5px;
  padding:5px 10px; border-radius:99px; cursor:pointer; -webkit-appearance:none; appearance:none }
.pillbtn.active { background:var(--ink); color:var(--page); border-color:var(--ink) }
.skb.dim { opacity:.15 }
.planctl { margin-top:10px; font-size:12.5px; color:var(--ink2); display:flex; flex-wrap:wrap; gap:6px 8px; align-items:center }
.planctl input, .planctl select { font:inherit; font-size:12.5px; background:var(--surface); color:var(--ink);
  border:1px solid var(--grid); border-radius:6px; padding:3px 6px; max-width:100% }
.planctl #paceIn { width:52px; text-align:center }
.planctl .pillbtn { padding:3px 9px }
/* ---------- redesign: header ---------- */
.hdr { position:sticky; top:0; z-index:9; background:color-mix(in srgb, var(--page) 94%, transparent);
  backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); border-bottom:1px solid var(--grid); padding:9px 14px }
.hdr-in { max-width:1064px; margin:0 auto }
.hdr-row { display:flex; align-items:center; gap:8px }
.hdr-brand { font-weight:800; font-size:13px }
.hdr-meta { font:11px var(--mono); color:var(--muted) }
.hdr-nav { margin-left:auto; display:flex; gap:14px; align-items:center }
.hdr-nav a, .hdr-nav span { font:700 12px system-ui; color:var(--ink2); text-decoration:none }
.hdr-nav span { color:var(--ink); border-bottom:2px solid var(--accent); padding-bottom:1px }
.chiprow { display:flex; gap:6px; margin-top:9px; overflow-x:auto; scrollbar-width:none }
.chiprow::-webkit-scrollbar { display:none }
.chip2 { flex:none; border:1px solid var(--grid); background:transparent; color:var(--ink2);
  font:600 12px system-ui; padding:5px 11px; border-radius:99px; cursor:pointer;
  -webkit-appearance:none; appearance:none }
.chip2.on { background:var(--ink); border-color:var(--ink); color:var(--page) }
/* ---------- redesign: page shell ---------- */
.wrap.shellwrap { max-width:none; padding:0 }
.wrap.shellwrap > footer.colophon { max-width:1064px; margin-left:auto; margin-right:auto; padding:12px 14px 40px }
.shell { max-width:1064px; margin:0 auto; padding:16px 14px 40px }
.eyebrow { display:flex; align-items:baseline; gap:8px }
.eyebrow b { font:800 10px system-ui; letter-spacing:.14em; text-transform:uppercase; color:var(--accent) }
.eyebrow span { margin-left:auto; font:11px var(--mono); color:var(--muted) }
.kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; margin-top:7px }
.kpi { background:var(--card); border:1px solid var(--ring); border-radius:12px; padding:11px 11px 10px }
.kpi b { display:block; font-weight:700; font-size:22px; letter-spacing:-.03em; font-variant-numeric:tabular-nums }
.kpi span { display:block; font:600 9.5px system-ui; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-top:2px }
/* ---------- redesign: chart card ---------- */
.chartcard { background:var(--card); border:1px solid var(--ring); border-radius:14px; padding:13px 12px 12px; margin:16px 0 0 }
.chartcard h2 { font-size:14px; letter-spacing:-.01em; font-weight:700 }
.chartcard .sub { font-size:12px; color:var(--ink2); margin:2px 0 8px }
.skb.dim { opacity:.18 }
details.chartlegend { margin-top:8px }
details.chartlegend summary { cursor:pointer; font:600 11.5px system-ui; color:var(--ink2) }
.legendgrid { display:grid; grid-template-columns:auto 1fr; gap:8px 10px; align-items:center; margin-top:9px; font-size:12px; color:var(--ink2) }
/* ---------- redesign: my legs ---------- */
.mylabel { font:11px system-ui; color:var(--muted); margin:16px 0 7px }
.minigrid { display:grid; grid-template-columns:repeat(3,1fr); gap:6px }
.mini { background:var(--card); border:1px solid var(--ring); border-radius:10px; padding:8px 9px 9px;
  color:var(--ink); min-width:0; text-decoration:none; display:block }
.mini .r1 { display:flex; justify-content:space-between; font:700 11px var(--mono); color:var(--muted) }
.mini .nm, .mini .d { display:block }
.mini .r1 i { font-style:normal; font-weight:400; font-size:11px }
.mini .nm { font:600 12px system-ui; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin:2px 0 }
.mini .d { font:11.5px var(--mono); color:var(--ink2) }
.morebtn { grid-column:1/-1; border:1px dashed var(--axis); background:none; color:var(--ink2);
  font:600 11.5px system-ui; border-radius:10px; padding:8px; cursor:pointer; -webkit-appearance:none; appearance:none }
/* ---------- redesign: banners ---------- */
.bnr { display:flex; gap:9px; align-items:center; padding:11px 12px; border-radius:12px;
  border:1px solid var(--ring); margin:14px 0 6px }
.bnr.ex { border-left:3px solid var(--accent); background:color-mix(in srgb, var(--accent) 8%, transparent) }
.bnr.se { border-left:3px solid var(--ink2); background:var(--surface) }
.bnr .bnrmain { flex:1; min-width:0 }
.bnr .kick { display:flex; justify-content:space-between; font:800 9.5px system-ui; letter-spacing:.13em; text-transform:uppercase }
.bnr.ex .kick { color:var(--accent) } .bnr.se .kick { color:var(--ink2) }
.bnr .kick i { font:10.5px var(--mono); font-style:normal; color:var(--muted); letter-spacing:0; text-transform:none }
.bnr .bname { font-weight:700; font-size:14.5px; letter-spacing:-.015em }
.bnr .bsub { font:10.5px var(--mono); color:var(--muted) }
.bnr .bnav { text-align:right; flex:none }
.mapbtn2 { display:inline-block; background:var(--card); border:1px solid var(--grid); border-radius:9px;
  padding:7px 11px; font:700 12px system-ui; color:var(--ink); text-decoration:none; white-space:nowrap }
.mapalt { display:block; font:11px system-ui; color:var(--muted); text-decoration:none; margin-top:3px }
.mapalt:hover { color:var(--ink2) }
/* ---------- redesign: leg rows + expanded card ---------- */
.allhdr { display:flex; justify-content:space-between; align-items:baseline; margin:18px 0 2px }
.allhdr b { font:800 10px system-ui; letter-spacing:.14em; text-transform:uppercase; color:var(--muted) }
.allhdr span { font:11px system-ui; color:var(--muted) }
.lrow { display:flex; align-items:center; gap:9px; padding:9px 10px; margin:5px 0; border-radius:11px;
  cursor:pointer; border:1px solid transparent }
.lrow .rail { width:3px; height:26px; border-radius:2px; flex:none }
.lrow .num { font:700 12px var(--mono); color:var(--muted); width:20px; flex:none }
.lrow .lname { font:600 13.5px system-ui; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; min-width:0 }
.lrow .lstats { font:11.5px var(--mono); color:var(--ink2); font-variant-numeric:tabular-nums; white-space:nowrap }
.lrow .av { width:22px; height:22px; border-radius:50%; flex:none; display:flex; align-items:center; justify-content:center;
  font:700 10px system-ui; background:var(--surface); color:var(--ink2); border:1px solid var(--grid) }
.lrow.mine { background:color-mix(in srgb, var(--accent) 12%, transparent);
  border:1px solid color-mix(in srgb, var(--accent) 34%, transparent) }
.lrow.mine .av { background:var(--accent); color:#fff; border-color:var(--accent) }
.lrow.openrow { background:var(--card); border:1px solid var(--ring) }
.lrow .lsurf, .lrow .lrating, .lrow .lstart { display:none }
.lx { display:none; background:var(--card); border:1px solid var(--ring); border-radius:12px; overflow:hidden; margin:0 0 8px }
.lx.open { display:block }
.lx .band { display:flex; justify-content:space-between; padding:7px 13px; font:800 10px system-ui; letter-spacing:.12em; text-transform:uppercase }
.lx .band i { font:10px var(--mono); font-style:normal; color:var(--muted); letter-spacing:0; text-transform:none }
.lx .bandmeta { font:10px var(--mono); color:var(--muted); letter-spacing:0; text-transform:none; display:none }
.lx .xbody { padding:12px 13px 13px }
.lx .nums { display:flex; gap:18px; margin-bottom:10px }
.lx .nums b { font-weight:700; font-size:19px; letter-spacing:-.03em; font-variant-numeric:tabular-nums }
.lx .nums span { font-size:11px; color:var(--muted); margin-left:3px }
.lx .assign { display:flex; align-items:center; gap:8px; padding:8px 9px; border-radius:9px;
  background:color-mix(in srgb, var(--accent) 13%, transparent); margin-bottom:10px }
.lx .assign .av { width:21px; height:21px; border-radius:50%; background:var(--accent); color:#fff;
  display:flex; align-items:center; justify-content:center; font:700 10px system-ui; flex:none }
.lx .assign b { font:700 12.5px system-ui }
.lx .assign .when { margin-left:auto; font:11.5px var(--mono); color:var(--ink2); white-space:nowrap }
.lx .surfmeta { display:flex; justify-content:space-between; font:10.5px var(--mono); color:var(--muted); margin-top:3px }
.lx .beta2 { font-size:14px; line-height:1.5; color:var(--ink2); text-wrap:pretty; margin:10px 0 }
.lx .beta2 .src { margin-right:7px }
.lx .xgrid { display:block }
.lx .xbtns { display:flex; gap:8px; align-items:flex-start; flex-wrap:wrap; margin-top:10px }
/* ---------- redesign: desktop ---------- */
@media (min-width: 900px) {
  .hdr { padding:11px 14px }
  .hdr-brand { font-size:15px }
  .hdr-nav a, .hdr-nav span { font-size:13px }
  .shell { padding:22px 28px 48px }
  .pagegrid { display:grid; grid-template-columns:308px minmax(0,1fr); gap:30px; align-items:start }
  .wrap.shellwrap > footer.colophon { padding-left:28px; padding-right:28px }
  .rail { position:sticky; top:76px; display:flex; flex-direction:column; gap:16px }
  .minigrid { grid-template-columns:repeat(2,1fr) }
  .legendgrid { grid-template-columns:auto 1fr auto 1fr }
  .exjump { background:var(--card); border:1px solid var(--ring); border-radius:12px; padding:6px 4px }
  .exjump a { display:flex; gap:8px; align-items:baseline; padding:7px 9px; border-radius:8px; text-decoration:none; color:var(--ink); font-size:13px; white-space:nowrap; overflow:hidden }
.exjump a > :nth-child(2) { overflow:hidden; text-overflow:ellipsis }
  .exjump a:hover { background:var(--surface) }
  .exjump .k { font:700 10.5px var(--mono); color:var(--accent) }
  .exjump .m { margin-left:auto; font:10.5px var(--mono); color:var(--muted) }
  .lrow .lsurf { display:flex; width:78px; height:6px; border-radius:3px; overflow:hidden; gap:1px; flex:none }
  .lrow .lsurf i { height:100% }
  .lrow .lrating { display:block; width:96px; font:600 10.5px system-ui; flex:none }
  .lrow .lstart { display:block; width:104px; font:11px var(--mono); color:var(--ink2); text-align:right; flex:none }
  .lrow .lname { font-size:14.5px }
  .lx .bandmeta { display:inline }
}
@media (max-width: 899px) { .exjump { display:none } .rail-desktop-only { display:none } #myLegsBlock { display:none } }
@media (min-width: 900px) { #myLegsBlockPhone { display:none } }
/* ---------- redesign: overview ---------- */
.ovh1 { font-weight:800; font-size:24px; letter-spacing:-.028em; margin:4px 0 2px }
.ovh2 { font-weight:800; font-size:20px; letter-spacing:-.025em; margin:26px 0 2px }
.ovsub { font-size:12.5px; line-height:1.5; color:var(--ink2); margin:0 0 10px }
.loadcards { display:flex; flex-direction:column; gap:7px }
.loadcard { background:var(--card); border:1px solid var(--ring); border-radius:13px; overflow:hidden }
.loadcard .lchead { display:flex; align-items:center; gap:8px; padding:10px 12px 7px }
.loadcard .rk { width:20px; height:20px; border-radius:6px; display:flex; align-items:center; justify-content:center;
  font:700 11px var(--mono); background:var(--surface); color:var(--muted); border:1px solid var(--grid); flex:none }
.loadcard .lcname { font:700 15px system-ui }
.loadcard .lcidx { margin-left:auto; font:700 15px var(--mono) }
.loadcard .lcidx i { font:400 10.5px var(--mono); color:var(--muted); font-style:normal; margin-left:4px }
.loadcard .lcbar { height:5px; background:var(--surface) }
.loadcard .lcbar i { display:block; height:100% }
.loadcard .lcbody { display:grid; grid-template-columns:auto auto 1fr; gap:16px; padding:9px 12px 8px; align-items:start }
.loadcard .lcbody b { display:block; font-weight:700; font-size:17px; letter-spacing:-.02em; font-variant-numeric:tabular-nums; white-space:nowrap }
.loadcard .lcbody span { display:block; font:10.5px var(--mono); color:var(--muted); white-space:nowrap }
.loadcard .lcbody div:last-child span { white-space:normal }
.loadcard .lcbody .hi { color:#ec835a }
.loadcard .lclegs { display:flex; gap:3px; padding:0 12px }
.loadcard .lclegs i { flex:1; text-align:center; font:700 10.5px var(--mono); padding:3px 0 4px;
  border-radius:0 0 5px 5px; font-style:normal }
.loadcard .lctough { font:10.5px var(--mono); color:var(--muted); padding:6px 12px 10px }
.swimcard { background:var(--card); border:1px solid var(--ring); border-radius:14px; padding:12px; display:flex }
.swimnames { flex:none; width:66px; padding-top:22px }
.swimnames div { height:26px; display:flex; align-items:center; justify-content:flex-end; padding-right:8px;
  font:700 11px system-ui; color:var(--ink2); white-space:nowrap; overflow:hidden }
.swimscroll { overflow-x:auto; flex:1 }
.swimscroll svg { display:block }
.swimlegend { display:flex; gap:12px; flex-wrap:wrap; font-size:11.5px; color:var(--muted); margin-top:8px; align-items:center }
details.ovd { margin:10px 0 }
details.ovd > summary { cursor:pointer; background:var(--card); border:1px solid var(--ring); border-radius:12px;
  padding:12px 14px; font:700 14px system-ui; list-style:none }
details.ovd > summary::-webkit-details-marker { display:none }
details.ovd > summary:after { content:'▾'; float:right; color:var(--muted) }
details.ovd[open] > summary:after { content:'▴' }
details.ovd .ovdbody { padding:12px 2px 2px }
@media (min-width: 900px) {
  .loadcards { display:grid; grid-template-columns:repeat(3,1fr) }
  .swimnames { width:78px }
  .ovtwo { display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start }
}
.footnote { font-size:11.5px; color:var(--ink2); background:var(--surface); border:1px dashed var(--axis);
  border-radius:7px; padding:5px 9px; margin-top:6px }
.legfoot { margin-top:9px; display:flex; flex-wrap:wrap; gap:7px; align-items:center }
.stravabtn { display:inline-block; text-decoration:none; font-weight:700; font-size:12.5px;
  border:1.5px solid var(--accent); border-radius:8px; padding:5px 12px }
.mapbtn { border-color:var(--grid); color:var(--ink2) }
.coords { font-size:11px; color:var(--muted); font-variant-numeric:tabular-nums }
.qrbox { display:flex; align-items:center; gap:8px }
.qrbox img { width:62px; height:62px; image-rendering:pixelated }
.qrbox span { font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em }
.qrbox.big img { width:88px; height:88px }
.qrbox.big { flex-direction:column; text-align:center; gap:4px }
.exchange { display:flex; gap:10px; align-items:center; border:1.5px dashed var(--ink2); border-radius:12px;
  padding:10px 14px; margin:12px 0; background:var(--surface) }
.exchange .flag { font-size:20px }
.exchange b { display:block; font-size:13.5px; letter-spacing:.04em }
.exchange span { font-size:12px; color:var(--ink2) }
.exchange.finish { border-style:solid; border-color:var(--ink) }
.exchange .mapwrap { display:flex; gap:7px; flex-wrap:wrap; margin-top:8px }
.tscroll { overflow-x:auto; -webkit-overflow-scrolling:touch }
.tscroll .tbl { min-width:560px }
.tbl { width:100%; border-collapse:collapse; font-size:12.5px }
.tbl th { text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
  border-bottom:1.5px solid var(--axis); padding:5px 7px }
.tbl td { border-bottom:1px solid var(--grid); padding:5px 7px; vertical-align:top }
.tbl .r { text-align:right; font-variant-numeric:tabular-nums }
.tbl .c { text-align:center }
.tbl.small { font-size:11px }
.tbl.small td, .tbl.small th { padding:3.5px 5px }
.exrow td { background:var(--surface); font-weight:700; font-size:10.5px; letter-spacing:.05em }
.blankcell { min-width:110px; border-bottom:1px dotted var(--muted) !important }
.linkrow { display:flex; flex-wrap:wrap; gap:16px; margin-top:10px }
details.legend { margin:12px 0 }
details.legend summary { cursor:pointer; font-weight:700; font-size:13px; color:var(--ink2) }
footer.colophon { margin-top:36px; font-size:11.5px; color:var(--muted); border-top:1px solid var(--grid); padding-top:12px }
.print-only { display:none }
@page { size:letter; margin:0.45in }
@media print {
  :root { color-scheme:light;
    --surface:#fcfcfb; --page:#ffffff; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.14); --card:#ffffff; --accent:#2a78d6 }
  body { font-size:11.5px; background:#fff }
  nav.top, .web-only { display:none !important }
  .print-only { display:flex }
  .wrap { max-width:none; padding:0 }
  .hero { padding-top:4px }
  .hero h1 { font-size:30px }
  .leg, .panel, .exchange { break-inside:avoid }
  .secbanner { break-before:page; margin-top:0; background:#0b0b0b !important; color:#fff !important }
  .cover-end { break-after:page }
  .leg { padding:10px 12px; margin:8px 0 }
  .beta { font-size:11.5px }
  a { text-decoration:none; color:inherit }
  .idx-break { break-before:page }
}
'''
    if ACCENT:
        base = base.replace("--accent:#2a78d6", f"--accent:{ACCENT}").replace("--accent:#3987e5", f"--accent:{ACCENT}")
    return base

# ---------------- page shells ----------------
# RUNNERS: set names once assignments are decided; the filter buttons + card labels pick them up.
def slot_label(s):
    return f'{s}-{RUNNERS[s]}' if RUNNERS.get(s) else f'Slot {s}'

def plan_ctl():
    p = PLAN["pace_min_per_mi"]
    t = round(p * 60); pace = f'{t // 60}:{t % 60:02d}'
    return (f'<div class="planctl web-only">⏱ Est. schedule assumes team pace '
            f'<input id="paceIn" value="{pace}" size="4"> min/mi · wave start {RACE_DAYS[0]} '
            f'<input id="startIn" type="time" value="{PLAN["start_hhmm"]}"> '
            f'<button id="planReset" class="pillbtn">reset</button> '
            f'<span class="tiny">{esc(PLAN_NOTE)}</span></div>')

def runners_js():
    plan = dict(start=hm(PLAN["start_hhmm"]), pace=PLAN["pace_min_per_mi"],
                sr=hm(PLAN["sunrise"]), ss=hm(PLAN["sunset"]), total=TOTAL_MI)
    _, plot_h, segs, _ = sky_layout()
    legdata = [dict(n=l["n"], dist=l["dist"], gain=l["gain"], v=round(ftpmi(l), 1),
                    pts=RATING_PTS[l["team"] or l["rating"]], color=DIFF[l["team"] or l["rating"]],
                    lbl=(l["team"] or l["rating"]), name=NAMES[l["n"]]) for l in LEGS]
    return ("const RACE_DAYS_JS=" + json.dumps(RACE_DAYS) + ";const RACE_ID=" + json.dumps(RACE_ID) + ";const PLAN=" + json.dumps(plan)
            + ";const SEGS=" + json.dumps([{k: round(v, 3) for k, v in s.items()} for s in segs])
            + ";const GEO=" + json.dumps(dict(top=SKY["TOP"], ploth=plot_h))
            + ";const NR=" + str(N_RUNNERS)
            + ";const RMAP=" + json.dumps({str(k): v for k, v in RUNNERS.items()})
            + ";const LEGDATA=" + json.dumps(legdata)
            + ";const RMAP0=" + json.dumps({str(k): v for k, v in RUNNERS.items()})
            + ";const NR0=" + str(N_RUNNERS) + ";"
            + RUNNERS_JS)

# runner names come baked into the HTML from data.RUNNERS; JS handles filtering + plan recompute
RUNNERS_JS = '''
function filterSlot(s, btn) {
  document.querySelectorAll('.leg').forEach(el => {
    el.classList.toggle('hidden', s !== 0 && Number(el.dataset.slot) !== s);
  });
  document.querySelectorAll('.jumprow a').forEach(el => {
    el.classList.toggle('hiddenx', s !== 0 && Number(el.dataset.slot) !== s);
  });
  document.querySelectorAll('.skb').forEach(el => {
    el.classList.toggle('dim', s !== 0 && Number(el.dataset.slot) !== s);
  });
  document.querySelectorAll('.filterbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  window.scrollTo({top: 0});
}
document.querySelectorAll('.idxbtn').forEach(b => b.addEventListener('click', () => {
  const s = Number(b.dataset.slot);
  document.querySelectorAll('#index tbody tr').forEach(tr => {
    const match = tr.classList.contains('exrow') ? s === 0 : (s === 0 || Number(tr.dataset.slot) === s);
    tr.classList.toggle('hiddenx', !match);
  });
  document.querySelectorAll('.idxbtn').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
}));
document.querySelectorAll('.filterbtn').forEach(b => {
  b.addEventListener('click', () => filterSlot(Number(b.dataset.slot), b));
});
// ---- pace / timeline estimator ----
const DAYSJS = RACE_DAYS_JS;
function fmtClock(t) {
  const d = Math.min(Math.floor(t/1440), DAYSJS.length-1); const mm = Math.round(t%1440);
  const h = Math.floor(mm/60), m = mm%60;
  return DAYSJS[d]+' '+((h%12)||12)+':'+String(m).padStart(2,'0')+' '+(h<12?'AM':'PM');
}
function phaseEmoji(t) {
  const c = t%1440;
  if (c >= PLAN.sr-45 && c < PLAN.sr+45) return '🌅';
  if (c >= PLAN.ss-45 && c < PLAN.ss+45) return '🌆';
  if (c >= PLAN.sr+45 && c < PLAN.ss-45) return '☀️';
  return '🌙';
}
function mileX(mi) {
  for (const s of SEGS) { if (mi >= s.a-1e-9 && mi <= s.b+1e-9) return s.x0+(mi-s.a)/(s.b-s.a)*(s.x1-s.x0); }
  return mi < SEGS[0].a ? SEGS[0].x0 : SEGS[SEGS.length-1].x1;
}
function renderNight() {
  const g = document.getElementById('nightg'); if (!g) return;
  const start = tAt(0), t1 = tAt(PLAN.total); const parts = []; const regions = [];
  for (let d = 0; d < 3; d++) {
    const ns = d*1440+PLAN.ss, ne = (d+1)*1440+PLAN.sr;
    const a = Math.max(ns, start), b = Math.min(ne, t1);
    if (b > a) regions.push([mAt(a), mAt(b), ns >= start, ne <= t1]);
  }
  const dayspans = []; let cur = 0;
  for (const r of regions) { dayspans.push([cur, r[0]]); cur = r[1]; }
  dayspans.push([cur, PLAN.total]);
  for (const [ma, mb] of regions) {
    const xa = mileX(ma), xb = mileX(mb);
    parts.push(`<rect x="${xa}" y="${GEO.top}" width="${xb-xa}" height="${GEO.ploth}" fill="var(--nightshade)"/>`);
    parts.push(`<text x="${(xa+xb)/2}" y="${GEO.top+10}" text-anchor="middle" font-size="9" fill="var(--ink2)">🌙 night</text>`);
  }
  for (const [da, db] of dayspans) {
    if (db-da > 18) parts.push(`<text x="${(mileX(da)+mileX(db))/2}" y="${GEO.top+10}" text-anchor="middle" font-size="9" fill="var(--ink2)">☀️ day</text>`);
  }
  let tick = (Math.floor(start/360)+1)*360;
  while (tick < t1) {
    const x = mileX(mAt(tick));
    const d = Math.min(Math.floor(tick/1440), DAYSJS.length-1), h = Math.floor((tick%1440)/60);
    const lbl = DAYSJS[d]+' '+((h%12)||12)+' '+(h<12?'AM':'PM');
    parts.push(`<line x1="${x}" y1="${GEO.top+GEO.ploth}" x2="${x}" y2="${GEO.top+GEO.ploth+4}" stroke="var(--axis)" stroke-width="1"/>`);
    parts.push(`<text x="${x}" y="${GEO.top+GEO.ploth+22}" text-anchor="middle" font-size="9" fill="var(--muted)">${lbl}</text>`);
    tick += 360;
  }
  g.innerHTML = parts.join('');
}
let __plan = {pace: null, start: null};
function tAt(m) { return window.OTO_SCHED ? window.OTO_SCHED.timeAtMile(m) : __plan.start + __plan.pace * m; }
function mAt(t) { return window.OTO_SCHED ? window.OTO_SCHED.mileAtTime(t) : (t - __plan.start) / __plan.pace; }
function applyPlan(pace, start) {
  __plan = {pace: pace, start: start};
  if (window.OTO_SCHED) window.OTO_SCHED.start = start;
  document.querySelectorAll('.eststart').forEach(el => {
    const t = tAt(parseFloat(el.dataset.mi));
    el.textContent = fmtClock(t)+' '+phaseEmoji(t);
  });
  document.querySelectorAll('.estdur').forEach(el => {
    const m0 = parseFloat(el.dataset.mi), d = parseFloat(el.dataset.dist);
    const mins = Math.round(tAt(m0 + d) - tAt(m0));
    el.textContent = '~' + (mins >= 60 ? Math.floor(mins/60) + 'h ' : '') + String(mins % 60).padStart(2, '0') + 'm';
  });
  renderNight();
  if (window.GUIDE && GUIDE.renderAll) GUIDE.renderAll(); else if (window.GUIDE) GUIDE.renderSide();
}
function parsePace(v) { const m = v.trim().match(/^(\\d{1,2}):(\\d{2})$/); return m ? Number(m[1])+Number(m[2])/60 : null; }
function hmJS(v) { const p = v.split(':').map(Number); return p[0]*60+p[1]; }
function paceStr(p) { const t = Math.round(p*60); return Math.floor(t/60)+':'+String(t%60).padStart(2,'0'); }
__plan = {pace: PLAN.pace, start: PLAN.start};
// ---- race-day finish estimator ----
const rdLeg = document.getElementById('rdLeg');
if (rdLeg) {
  const rdTime = document.getElementById('rdTime'), rdPace = document.getElementById('rdPace'),
        rdOut = document.getElementById('rdOut');
  let rdAnchor = null;
  const RACE0 = new Date(2026, 9, 9);  // Fri Oct 9, 2026 00:00 local
  function raceMinToDate(t) { return new Date(RACE0.getTime() + t*60000); }
  function rdUpdate() {
    const opt = rdLeg.selectedOptions[0];
    const pl = parsePace(rdPace.value);
    if (!opt || !pl || !rdTime.value) return;
    const dist = parseFloat(opt.dataset.dist), mi = parseFloat(opt.dataset.mi);
    const clock = hmJS(rdTime.value), est = tAt(mi);
    let t = clock;
    for (const cand of [clock, clock+1440, clock+2880]) {
      if (Math.abs(cand-est) < Math.abs(t-est)) t = cand;
    }
    rdAnchor = {mi: mi, t: t};
    const eta = t + pl*dist;
    const finish = eta + (tAt(PLAN.total) - tAt(mi + dist));
    let count = '';
    const now = new Date(), real = raceMinToDate(eta);
    if (Math.abs(now - RACE0) < 4*86400000 && real > now) {
      const m = Math.round((real - now)/60000);
      count = ` · in ${m >= 60 ? Math.floor(m/60)+'h ' : ''}${m%60}m`;
    }
    rdOut.innerHTML = `<b>${opt.dataset.runner || 'Runner'}</b> reaches <b>${opt.dataset.to}</b> ~<b>${fmtClock(eta)}</b>${count}` +
      ` · projected race finish <b>${fmtClock(finish)}</b>`;
  }
  document.getElementById('rdNow').addEventListener('click', () => {
    const n = new Date();
    rdTime.value = String(n.getHours()).padStart(2,'0')+':'+String(n.getMinutes()).padStart(2,'0');
    rdUpdate();
  });
  [rdLeg, rdTime, rdPace].forEach(el => el.addEventListener('change', rdUpdate));
  document.getElementById('rdApply').addEventListener('click', () => {
    if (!rdAnchor) { rdUpdate(); if (!rdAnchor) return; }
    const s = ((rdAnchor.t - __plan.pace*rdAnchor.mi) % 1440 + 1440) % 1440;
    const startEl = document.getElementById('startIn');
    if (startEl) {
      startEl.value = String(Math.floor(s/60)).padStart(2,'0')+':'+String(Math.round(s%60)).padStart(2,'0');
      startEl.dispatchEvent(new Event('change'));
    }
    rdUpdate();
  });
}
const paceIn = document.getElementById('paceIn'), startIn = document.getElementById('startIn');
if (paceIn && startIn) {
  const sp = localStorage.getItem('oto_pace'), st = localStorage.getItem('oto_start');
  if (sp) paceIn.value = sp;
  if (st) startIn.value = st;
  const upd = () => {
    const p = parsePace(paceIn.value); const t = startIn.value ? hmJS(startIn.value) : PLAN.start;
    if (p) { localStorage.setItem('oto_pace', paceIn.value); localStorage.setItem('oto_start', startIn.value); applyPlan(p, t); }
  };
  paceIn.addEventListener('change', upd);
  startIn.addEventListener('change', upd);
  const rst = document.getElementById('planReset');
  if (rst) rst.addEventListener('click', () => {
    localStorage.removeItem('oto_pace'); localStorage.removeItem('oto_start');
    paceIn.value = paceStr(PLAN.pace);
    startIn.value = String(Math.floor(PLAN.start/60)).padStart(2,'0')+':'+String(PLAN.start%60).padStart(2,'0');
    applyPlan(PLAN.pace, PLAN.start);
  });
  if (sp || st) upd();
}
// ---- interactive runner planner (overview) ----
const nrSel = document.getElementById('nrSel');
if (nrSel) {
  function renderPlanner(N) {
    const slots = [];
    for (let s = 1; s <= N; s++) {
      const legs = LEGDATA.filter(l => (l.n - 1) % N + 1 === s);
      const mi = legs.reduce((a, l) => a + l.dist, 0), gain = legs.reduce((a, l) => a + l.gain, 0),
            pts = legs.reduce((a, l) => a + l.pts, 0);
      slots.push({s, legs, mi, gain, pts});
    }
    const am = slots.reduce((a, x) => a + x.mi, 0) / N, ag = slots.reduce((a, x) => a + x.gain, 0) / N,
          ap = slots.reduce((a, x) => a + x.pts, 0) / N;
    slots.forEach(x => x.score = x.mi/am + x.gain/ag + x.pts/ap);
    const top = Math.max(...slots.map(x => x.score));
    slots.sort((a, b) => b.score - a.score);
    const rows = slots.map((x, i) => {
      const idx = Math.round(100 * x.score / top);
      const hardest = x.legs.reduce((a, l) =>
        (l.pts > a.pts || (l.pts === a.pts && (l.gain > a.gain || (l.gain === a.gain && l.v > a.v)))) ? l : a);
      const dots = x.legs.map(l =>
        `<span class="dotc" style="background:${l.color}" title="Leg ${l.n} · ${l.name} · ${l.lbl}"></span>`).join('');
      const nm = (N === NR && RMAP[x.s]) ? `<b>${RMAP[x.s]}</b>`
               : '<span class="tiny">—</span>';
      return `<tr><td class="c"><b>${i+1}</b></td><td class="c"><b>${x.s}</b></td>`
        + `<td class="runner-name">${nm}</td>`
        + `<td>${x.legs.map(l => l.n).join(', ')}</td><td class="r">${x.mi.toFixed(1)}</td>`
        + `<td class="r">${x.gain.toLocaleString()}</td><td class="nowrap">${dots}</td>`
        + `<td><div class="meterwrap"><div class="meter"><div class="fill" style="width:${idx}%"></div></div>`
        + `<span class="mval">${idx}</span></div></td>`
        + `<td>Leg ${hardest.n} · ${hardest.name} (${hardest.lbl} · +${hardest.gain.toLocaleString()} ft)</td></tr>`;
    });
    const tb = document.getElementById('plantbody');
    if (tb) tb.innerHTML = rows.join('');
    const note = document.getElementById('planNote');
    if (note) note.innerHTML = `With ${N} runners, slot <i>s</i> runs legs <i>s, s+${N}, s+${2*N}, …</i>`;
  }
  nrSel.addEventListener('change', () => renderPlanner(Number(nrSel.value)));
}
// ---- redesign UI: selection, accordion, my-legs, platform maps ----
window.GUIDE = {
  N: NR0, names: Object.assign({}, RMAP0), paces: {}, slotOf: {}, selected: 0, showAll: false, openLeg: null,
  legSlot(n) { return this.slotOf[n] || ((n - 1) % this.N) + 1; },
  label(s) { return this.names[s] || 'Slot ' + s; },
  shortLabel(s) { const nm = this.names[s]; return nm ? nm.split(' ')[0] : 'Slot ' + s; },
  initials(s) {
    const firsts = {};
    for (let i = 1; i <= this.N; i++) { const f = (this.names[i] || 'S' + i)[0].toUpperCase(); firsts[f] = (firsts[f] || 0) + 1; }
    const nm = this.names[s] || 'S' + s, f = nm[0].toUpperCase();
    return firsts[f] > 1 ? nm.slice(0, 2) : f;
  },
  renderChips() {
    const row = document.getElementById('chipRow');
    if (!row) return;
    row.innerHTML = '<button class="chip2" data-slot="0">All</button>' +
      Array.from({length: this.N}, (_, i) => `<button class="chip2" data-slot="${i + 1}">${this.shortLabel(i + 1)}</button>`).join('');
    row.querySelectorAll('.chip2').forEach(b => {
      b.classList.toggle('on', Number(b.dataset.slot) === this.selected);
      b.addEventListener('click', () => { this.select(Number(b.dataset.slot)); });
    });
  },
  select(s) {
    this.selected = s; this.showAll = false;
    if (this.openLeg) this.toggleLeg(this.openLeg, false);
    document.querySelectorAll('#chipRow .chip2').forEach(b => b.classList.toggle('on', Number(b.dataset.slot) === s));
    document.querySelectorAll('.skb').forEach(el => el.classList.toggle('dim', s !== 0 && Number(el.dataset.slot) !== s));
    document.querySelectorAll('.lrow').forEach(el => el.classList.toggle('mine', s !== 0 && Number(el.dataset.slot) === s));
    this.renderSide();
  },
  legMeta(n) { return LEGDATA.find(l => l.n === n); },
  renderSide() {
    const s = this.selected;
    const mine = LEGDATA.filter(l => this.legSlot(l.n) === s);
    const kt = document.getElementById('kpiTitle');
    if (kt) {
      if (s === 0) {
        kt.textContent = 'The whole race';
        document.getElementById('kpiMi').textContent = PLAN.total ? LEGDATA.reduce((a, l) => a + l.dist, 0).toFixed(1) : '';
        document.getElementById('kpiLegs').textContent = LEGDATA.length;
        document.getElementById('kpiGain').textContent = (LEGDATA.reduce((a, l) => a + l.gain, 0) / 1000).toFixed(1) + 'k';
      } else {
        kt.textContent = this.shortLabel(s) + "'s race";
        document.getElementById('kpiMi').textContent = mine.reduce((a, l) => a + l.dist, 0).toFixed(1);
        document.getElementById('kpiLegs').textContent = mine.length;
        document.getElementById('kpiGain').textContent = (mine.reduce((a, l) => a + l.gain, 0) / 1000).toFixed(1) + 'k';
      }
    }
    const html = s === 0 ? '' : this.myLegsHtml(s, mine);
    const d = document.getElementById('myLegsBlock'), ph = document.getElementById('myLegsBlockPhone');
    if (d) d.innerHTML = html;
    if (ph) ph.innerHTML = html;
  },
  myLegsHtml(s, mine) {
    const list = this.showAll ? mine : mine.slice(0, 6);
    const cards = list.map(l => {
      const meta = LEGDATA.find(x => x.n === l.n);
      const t = tAt(this.startMi(l.n));
      return `<a class="mini" style="border-top:3px solid ${meta.color}" href="#lr-${l.n}">` +
        `<span class="r1"><span>${String(l.n).padStart(2, '0')}</span><i>${fmtClock(t).replace(':00 ', ' ')}</i></span>` +
        `<span class="nm">${meta.name}</span><span class="d">${meta.dist} mi</span></a>`;
    }).join('');
    const more = mine.length > 6
      ? `<button class="morebtn" onclick="GUIDE.showAll=!GUIDE.showAll;GUIDE.renderSide()">${this.showAll ? 'show fewer' : '+ ' + (mine.length - 6) + ' more legs'}</button>` : '';
    return `<div class="mylabel">${this.shortLabel(s)} runs these ${mine.length}</div><div class="minigrid">${cards}${more}</div>`;
  },
  startMi(n) {
    let m = 0;
    for (const l of LEGDATA) { if (l.n === n) break; m += l.dist; }
    return m;
  },
  toggleLeg(n, want) {
    const x = document.getElementById('leg-' + n), row = document.getElementById('lr-' + n);
    if (!x || !row) return;
    const open = want !== undefined ? want : !x.classList.contains('open');
    if (open && this.openLeg && this.openLeg !== n) this.toggleLeg(this.openLeg, false);
    x.classList.toggle('open', open);
    row.classList.toggle('openrow', open);
    row.setAttribute('aria-expanded', open);
    this.openLeg = open ? n : (this.openLeg === n ? null : this.openLeg);
  }
};
document.querySelectorAll('.lrow').forEach(row => {
  const go = () => GUIDE.toggleLeg(Number(row.dataset.n));
  row.addEventListener('click', go);
  row.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
});
// open a leg when arriving via #leg-N or #lr-N
if (/^#(leg|lr)-[0-9]+$/.test(location.hash)) GUIDE.toggleLeg(Number(location.hash.split('-').pop()), true);
document.querySelectorAll('.skb').forEach(a => a.addEventListener('click', (e) => {
  const n = Number((a.getAttribute('href') || '').split('#leg-').pop());
  if (!n) return;
  const row = document.getElementById('lr-' + n);
  if (!row) return; // chart lives on another page — let the link navigate
  e.preventDefault();
  GUIDE.toggleLeg(n, true);
  row.scrollIntoView({behavior: 'smooth', block: 'start'});
}));
// "X runs these N" mini-cards re-render on every chip change, so delegate
document.addEventListener('click', (e) => {
  const mini = e.target.closest ? e.target.closest('a.mini') : null;
  if (!mini) return;
  const n = Number((mini.getAttribute('href') || '').split('#lr-').pop());
  if (!n) return;
  const row = document.getElementById('lr-' + n);
  if (!row) return;
  e.preventDefault();
  GUIDE.toggleLeg(n, true);
  row.scrollIntoView({behavior: 'smooth', block: 'start'});
});
// platform-appropriate map primary
(function () {
  const apple = /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent) && !/Android/.test(navigator.userAgent);
  if (!apple) return;
  document.querySelectorAll('.mapnav').forEach(w => {
    const p = w.querySelector('.mapPrimary'), alt = w.querySelector('.mapAlt');
    if (!p || !alt) return;
    p.href = w.dataset.a; p.textContent = '📍 Apple Maps ↗';
    alt.href = w.dataset.g; alt.textContent = 'or Google ↗';
  });
})();
// desktop: chart legend open by default
if (matchMedia('(min-width: 900px)').matches) {
  const cl = document.getElementById('chartLegend');
  if (cl) cl.open = true;
}
GUIDE.idxColor = (v) => v >= 96 ? '#d03b3b' : v >= 90 ? '#ec835a' : v >= 84 ? '#fab219' : '#0ca30c';
GUIDE.fmtDur = (mins) => { mins = Math.round(mins); return (mins >= 60 ? Math.floor(mins/60) + 'h ' : '') + String(mins % 60).padStart(2, '0') + 'm'; };
GUIDE.slotStats = function () {
  const out = [];
  for (let s = 1; s <= this.N; s++) {
    const legs = LEGDATA.filter(l => this.legSlot(l.n) === s);
    out.push({ s, legs,
      mi: legs.reduce((a, l) => a + l.dist, 0),
      gain: legs.reduce((a, l) => a + l.gain, 0),
      pts: legs.reduce((a, l) => a + l.pts, 0) });
  }
  const am = out.reduce((a, x) => a + x.mi, 0) / this.N || 1, ag = out.reduce((a, x) => a + x.gain, 0) / this.N || 1,
        ap = out.reduce((a, x) => a + x.pts, 0) / this.N || 1;
  out.forEach(x => x.score = x.mi / am + x.gain / ag + x.pts / ap);
  const top = Math.max(...out.map(x => x.score)) || 1;
  out.forEach(x => { x.idx = Math.round(100 * x.score / top); x.dMi = x.mi - am; x.dGain = x.gain - ag; });
  return out.sort((a, b) => b.score - a.score);
};
GUIDE.renderLoadCards = function () {
  const box = document.getElementById('loadCards');
  if (!box) return;
  const stats = this.slotStats();
  box.innerHTML = stats.map((x, i) => {
    const c = this.idxColor(x.idx);
    let shortest = Infinity, after = null;
    for (let k = 0; k + 1 < x.legs.length; k++) {
      const endT = tAt(this.startMi(x.legs[k].n) + x.legs[k].dist);
      const nextT = tAt(this.startMi(x.legs[k + 1].n));
      const gap = nextT - endT;
      if (gap < shortest) { shortest = gap; after = x.legs[k].n; }
    }
    const hardest = x.legs.length ? x.legs.reduce((a, l) => (l.pts > a.pts || (l.pts === a.pts && l.gain > a.gain)) ? l : a) : null;
    const rk1 = i === 0 ? `style="background:${c};color:var(--page);border-color:${c}"` : '';
    return `<div class="loadcard">
      <div class="lchead"><span class="rk" ${rk1}>${i + 1}</span><span class="lcname">${this.label(x.s)}</span>
        <span class="lcidx" style="color:${c}">${x.idx}<i>index</i></span></div>
      <div class="lcbar"><i style="width:${x.idx}%;background:${c}"></i></div>
      <div class="lcbody">
        <div><b>${x.mi.toFixed(1)} mi</b><span class="${x.dMi > 0 ? 'hi' : ''}">${x.dMi >= 0 ? '+' : ''}${x.dMi.toFixed(1)} vs avg</span></div>
        <div><b>+${x.gain.toLocaleString()} ft</b><span class="${x.dGain > 0 ? 'hi' : ''}">${x.dGain >= 0 ? '+' : ''}${Math.round(x.dGain)} vs avg</span></div>
        <div><b>${after ? this.fmtDur(shortest) : '—'}</b><span>${after ? 'shortest break · after ' + after : 'runs once'}</span></div>
      </div>
      <div class="lclegs">${x.legs.map(l => `<i style="background:color-mix(in srgb, ${l.color} 24%, transparent);border-top:2px solid ${l.color}">${l.n}</i>`).join('')}</div>
      ${hardest ? `<div class="lctough">toughest — leg ${hardest.n} · ${hardest.name} (${hardest.lbl.toLowerCase()}, +${hardest.gain.toLocaleString()} ft)</div>` : ''}
    </div>`;
  }).join('');
};
GUIDE.renderSwimlane = function () {
  const svg = document.getElementById('swimSvg'), namesBox = document.getElementById('swimNames');
  if (!svg || !namesBox) return;
  const LBL = 6, PLOTW = 900 - 16, HEAD = 22, ROWH = 26;
  const t0 = tAt(0), tEnd = tAt(PLAN.total);
  const X = (t) => LBL + (t - t0) / (tEnd - t0) * PLOTW;
  const bottom = HEAD + this.N * ROWH + 4;
  // size the canvas to the roster — 12-runner rows would clip at the baked-in 200px
  const svgH = bottom + 20;
  svg.setAttribute('height', svgH);
  svg.setAttribute('viewBox', '0 0 900 ' + svgH);
  namesBox.innerHTML = Array.from({length: this.N}, (_, i) => `<div>${this.shortLabel(i + 1)}</div>`).join('');
  let parts = [];
  for (let d = 0; d < 3; d++) {
    const ns = d * 1440 + PLAN.ss, ne = (d + 1) * 1440 + PLAN.sr;
    const a = Math.max(ns, t0), b = Math.min(ne, tEnd);
    if (b > a) {
      parts.push(`<rect x="${X(a).toFixed(1)}" y="${HEAD}" width="${(X(b) - X(a)).toFixed(1)}" height="${bottom - HEAD}" fill="var(--nightshade)"/>`);
      parts.push(`<text x="${((X(a) + X(b)) / 2).toFixed(1)}" y="15" text-anchor="middle" font-size="9.5" fill="var(--ink2)">🌙 dark — vest + headlamp</text>`);
    }
  }
  for (let t = Math.ceil(t0 / 180) * 180; t < tEnd; t += 180) {
    const d = Math.floor(t / 1440), h = Math.floor((t % 1440) / 60), major = h === 0 || h === 12;
    const x = X(t).toFixed(1);
    parts.push(`<line x1="${x}" y1="${HEAD}" x2="${x}" y2="${bottom}" stroke="${major ? 'var(--axis)' : 'var(--grid)'}" stroke-width="1"/>`);
    const lbl = h === 0 ? RACE_DAYS_JS[Math.min(d, RACE_DAYS_JS.length - 1)] + ' 12a' : (h % 12 || 12) + (h < 12 ? 'a' : 'p');
    parts.push(`<text x="${x}" y="${bottom + 14}" text-anchor="middle" font-size="9.5" font-weight="${major ? 700 : 400}" fill="${major ? 'var(--ink2)' : 'var(--muted)'}">${lbl}</text>`);
  }
  LEGDATA.forEach(l => {
    const sSlot = this.legSlot(l.n);
    if (sSlot > this.N) return;
    const y = HEAD + (sSlot - 1) * ROWH + 6;
    const m0 = this.startMi(l.n);
    const x1 = X(tAt(m0)), w = Math.max(X(tAt(m0 + l.dist)) - x1, 5);
    parts.push(`<rect x="${x1.toFixed(1)}" y="${y}" width="${w.toFixed(1)}" height="15" rx="3" fill="${l.color}"/>`);
    if (w >= 12) parts.push(`<text x="${(x1 + w / 2).toFixed(1)}" y="${y + 11.5}" text-anchor="middle" font-size="8.5" font-weight="700" fill="rgba(0,0,0,.78)">${l.n}</text>`);
  });
  svg.innerHTML = parts.join('');
};
GUIDE.renderAll = function () { this.renderSide(); this.renderLoadCards(); this.renderSwimlane(); };
if (document.getElementById('chipRow')) { GUIDE.renderChips(); GUIDE.renderSide(); }
if (document.getElementById('loadCards')) GUIDE.renderAll();
if (matchMedia('(min-width: 900px)').matches) { const lt = document.getElementById('legTableD'); if (lt) lt.open = true; }
if (document.querySelector('.eststart') && !document.querySelector('.eststart').textContent) applyPlan(PLAN.pace, PLAN.start);
// keep anchor targets clear of the sticky nav
const topnav = document.querySelector('.hdr') || document.querySelector('nav.top');
function setScrollPad() {
  if (topnav) document.documentElement.style.scrollPaddingTop = (topnav.offsetHeight + 10) + 'px';
}
setScrollPad();
addEventListener('resize', setScrollPad);
if (topnav && window.ResizeObserver) new ResizeObserver(setScrollPad).observe(topnav);
// re-align a hash-opened leg now that scroll padding is known
if (/^#(leg|lr)-[0-9]+$/.test(location.hash)) {
  const row = document.getElementById('lr-' + location.hash.split('-').pop());
  if (row) setTimeout(() => row.scrollIntoView({block: 'start'}), 0);
}
'''

def dot_legend():
    return " · ".join(f'<span class="dotc" style="background:{c}"></span>{k}' for k, c in DIFF.items())

def diff_legend():
    return "".join(f'<span class="pill" style="--pc:{c}"><span class="dot"></span><b>{k}</b></span>' for k, c in DIFF.items())

def race_day_panel(inner=False):
    opts = ""
    for l in LEGS:
        n = l["n"]
        slot = (n - 1) % N_RUNNERS + 1
        to = ("the FINISH 🏁" if n == 36
              else f'Exchange {n} · {EXCHANGES[n]["name"]}' if n in EXCHANGES
              else f'Exchange zone {n}')
        opts += (f'<option value="{n}" data-dist="{l["dist"]}" data-mi="{l["start_mi"]}" data-to="{esc(to)}" '
                 f'data-runner="{esc(RUNNERS.get(slot, ""))}">'
                 f'Leg {n} · {esc(NAMES[n])} — {esc(RUNNERS.get(slot) or f"slot {slot}")}</option>')
    p = PLAN["pace_min_per_mi"]
    t = round(p * 60); pace = f'{t // 60}:{t % 60:02d}'
    core = f'''<div id="raceday">
    <div class="planctl"><select id="rdLeg">{opts}</select></div>
    <div class="planctl">left the exchange at <input id="rdTime" type="time">
      <button id="rdNow" class="pillbtn">now</button> · running about
      <input id="rdPace" value="{pace}" size="4"> min/mi</div>
    <p id="rdOut" class="beta" style="margin:.6em 0">Pick the leg, tap <b>now</b> at the handoff (or type the time), and the ETA shows here.</p>
    <div class="planctl"><button id="rdApply" class="pillbtn">↻ re-time the whole schedule from this handoff</button>
      <span class="tiny">shifts every est. start on this page (and the overview) so this leg's start matches reality — reset with the ⏱ control's reset</span></div>
  </div>'''
    if inner:
        return core
    return f'<details class="legend" id="racedayWrap"><summary>🏁 Race day — who finishes when?</summary><div class="panel" style="margin-top:8px">{core}</div></details>'

def how_to_read(compact=False, inner=False):
    body = f'''
  <p style="margin:.3em 0"><span class="srcbadge">team beta</span>
  Beta boxes, difficulty ratings, surface breakdowns and commentary are from <b>your team's own experience</b> (fill in <code>builder/data.py</code>).
  Distances, gain, mile markers and climb grades are from public Strava data.</p>
  <p style="margin:.3em 0">🌐 <b>From online:</b> official leg names, Strava routes, exchange stations, dates and night rules
  come from the official race site and 2025 race guide.</p>
  <p style="margin:.3em 0" class="tiny">⚠ Distances/gain on the cards are our 2025 numbers. The elevation profile charts come straight
  from the current 2026 Strava routes (pulled July 2026). Four legs changed for 2026 — <b>1, 8, 30 and 31</b> — those cards carry a
  🔄 route-update flag. When in doubt, the Strava link wins.</p>
  <div class="legendrow">Difficulty: {diff_legend()} · Surface: <span class="dotc" style="background:{SURF["pavement"]}"></span>pavement
  <span class="dotc" style="background:{SURF["gravel"]}"></span>gravel <span class="dotc" style="background:{SURF["trail"]}"></span>trail</div>'''
    if inner:
        return body
    if compact:
        return f'<details class="legend"><summary>How to read this guide (sources + legend)</summary><div class="panel" style="margin-top:8px">{body}</div></details>'
    return f'<div class="panel"><h2>How to read this guide</h2>{body}</div>'

def sec_overview_rows(legs_href="index.html"):
    out = ""
    for i, sec in enumerate(SECTIONS):
        a, b = sec["legs"]
        legs = [l for l in LEGS if a <= l["n"] <= b]
        mi = sum(l["dist"] for l in legs); gain = sum(l["gain"] for l in legs)
        out += (f'<tr><td class="c"><a href="{legs_href}#sec{i+1}">{i+1}</a></td><td>{a}–{b}</td>'
                f'<td>{esc(sec["dest"])}</td><td class="r">{mi:.1f}</td>'
                f'<td class="r">+{gain:,}</td><td class="r">{fmt_mi(legs[-1]["end_mi"])}</td></tr>')
    return out

def hero(sub=True):
    lo, hi = len(LEGS) // N_RUNNERS, -(-len(LEGS) // N_RUNNERS)
    legs_each = str(lo) if lo == hi else f"{lo}\u2013{hi}"
    tiles = f'''
  <div class="statgrid">
    <div class="tile"><b>{TOTAL_MI:,.1f}</b><span>miles</span></div>
    <div class="tile"><b>{len(LEGS)}</b><span>legs</span></div>
    <div class="tile"><b>{TOTAL_GAIN:,}</b><span>ft of climbing</span></div>
    <div class="tile"><b>{N_RUNNERS}</b><span>runners · {legs_each} legs each</span></div>
    <div class="tile"><b>{len(EXCHANGES)}</b><span>major exchanges</span></div>
  </div>''' if sub else ""
    return f'''
<header class="hero">
  <div class="kicker">{esc(TEAM_NAME.upper())} · RACE GUIDE</div>
  <h1>{esc(RACE["title"])} · {esc(RACE["subtitle"].split(" · ")[0])}</h1>
  <div class="sub">{esc(RACE["dates"])} · {esc(RACE["start"])} → {esc(RACE["finish"])}</div>
  {tiles}
</header>'''

def rules_panel(with_qr, inner=False):
    L = RACE["links"]
    qrs = "".join(
        f'<div class="qrbox big"><img src="{qr_datauri(u)}" alt="QR {t}"><span>{t}</span></div>'
        for t, u in [("Official course map", L["course_map"]), ("2025 race guide PDF", L["guide_pdf"]),
                     ("Exchange zones (Google Maps)", L["exchanges_map"])]) if with_qr else ""
    head = '' if inner else '<h2>Night rules &amp; official links <span class="tiny">(🌐 from the official 2025 race guide)</span></h2>'
    open_div = '<div>' if inner else '<div class="panel" id="rules">'
    return f'''
{open_div}
  {head}
  <p style="margin:.3em 0">🦺 <b>Nighttime hours = 1 hour before sunset through 1 hour after dawn:</b> reflective vest for anyone
  out of the van, headlamp + rear flashing tail light for runners. In-ear headphones are banned (open-ear audio OK).
  Course is marked with black arrows on bright-yellow signs at each turn, plus yellow flags and reflective tags.</p>
  <p style="margin:.3em 0" class="web-only">
    <a href="{L["course_map"]}" target="_blank" rel="noopener">Official course map + Strava routes ↗</a> ·
    <a href="{L["guide_pdf"]}" target="_blank" rel="noopener">2025 race guide PDF ↗</a> ·
    <a href="{L["exchanges_map"]}" target="_blank" rel="noopener">Exchange zones map ↗</a> ·
    <a href="{L["full_route_map"]}" target="_blank" rel="noopener">Full route map ↗</a>
  </p>
  <div class="linkrow print-only">{qrs}</div>
</div>'''

COLOPHON = f'''<footer class="colophon">Built for {TEAM_NAME} · leg beta by your team ·
names, routes &amp; rules from outbackintheozarks.com · not an official race document. Go get it. 🤙</footer>'''

def page(title, nav_html, body, script="", wide=False):
    # shell pages (redesign) do their own centering; the legacy .wrap must not clamp them
    shellwrap = " shellwrap" if 'class="shell"' in body else ""
    return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">%F0%9F%8F%83%F0%9F%8F%BB</text></svg>'>
<title>{esc(title)}</title>
<style>{css()}</style></head>
<body>
{nav_html}
<div class="wrap{" wide" if wide else ""}{shellwrap}" id="top">
{body}
{COLOPHON}
</div>
{f'<script>{script}</script><script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script><script src="{JS_PREFIX}config.js"></script><script src="{JS_PREFIX}team.js"></script>' if script else ""}
</body></html>'''

def nav_tabs(active):
    legs_cls = ' class="active"' if active == "legs" else ""
    over_cls = ' class="active"' if active == "overview" else ""
    return (f'<div class="navrow navtabs"><a class="brand" href="index.html">{esc(TEAM_NAME)}</a>'
            f'<a href="index.html"{legs_cls}>Legs</a><a href="overview.html"{over_cls}>Overview</a></div>')


# ---------------- redesign components ----------------
def fmt_pace_str(v):
    t = round(v * 60); return f"{t // 60}:{t % 60:02d}"

def short_dates():
    """'Friday Oct 9 – Saturday Oct 10, 2026' -> 'Oct 9–10, 2026'; one-day races pass through."""
    d = RACE["dates"]
    for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"):
        d = d.replace(day + " ", "")
    return re.sub(r"([A-Za-z]+) ([0-9]+) – \1 ([0-9]+)", r"\1 \2–\3", d)

def header_nav(active, with_chips=False):
    """Two-row sticky header. Row 1 byte-identical across pages except the active item."""
    items = ""
    for key, label, href in (("legs", "Legs", "index.html"), ("overview", "Overview", "overview.html"), ("settings", "Settings", "settings.html")):
        if key == active:
            items += f'<span>{label}</span>'
        else:
            href2 = ("../" if JS_PREFIX.startswith("..") and key == "settings" else "") + href
            items += f'<a class="hnav" data-page="{key}" href="{href2}">{label}</a>'
    chips = ""
    if with_chips:
        chips = ('<div class="chiprow" id="chipRow"><button class="chip2 on" data-slot="0">All</button>'
                 + "".join(f'<button class="chip2" data-slot="{s2}">{esc((RUNNERS.get(s2) or f"Slot {s2}").split(" ")[0] if RUNNERS.get(s2) else f"Slot {s2}")}</button>' for s2 in range(1, N_RUNNERS + 1))
                 + '</div>')
    return f'''<div class="hdr"><div class="hdr-in">
  <div class="hdr-row"><span class="hdr-brand brand">{esc(TEAM_NAME)}</span>
    <span class="hdr-meta">OTO {RACE_ID} · {esc(short_dates())}</span>
    <nav class="hdr-nav">{items}</nav></div>
  {chips}
</div></div>'''

def kpi_band():
    return f'''<div class="eyebrow" style="margin-top:2px"><b id="kpiTitle">The whole race</b><span>Outback in the Ozarks 2026</span></div>
<div class="kpis">
  <div class="kpi"><b id="kpiMi">{TOTAL_MI:,.1f}</b><span>miles</span></div>
  <div class="kpi"><b id="kpiLegs">{len(LEGS)}</b><span>legs</span></div>
  <div class="kpi"><b id="kpiGain">{TOTAL_GAIN/1000:.1f}k</b><span>ft climb</span></div>
</div>'''

def chart_legend_details():
    g = lambda inner: f'<svg viewBox="0 0 26 18" width="26" height="18">{inner}</svg>'
    rows = [
        (g('<rect x="3" y="4" width="7" height="12" rx="1.5" fill="var(--axis)"/><rect x="14" y="9" width="7" height="7" rx="1.5" fill="var(--grid)"/>'),
         "<b>Taller</b> = longer leg (miles)"),
        (g('<rect x="2" y="5" width="12" height="11" rx="1.5" fill="var(--axis)"/><rect x="17" y="5" width="5" height="11" rx="1.5" fill="var(--grid)"/>'),
         "<b>Wider</b> = steeper (ft of climb per mile)"),
        (g(''.join(f'<rect x="{2+i*6}" y="6" width="4.5" height="10" rx="1" fill="{c}"/>' for i, c in enumerate(DIFF.values()))),
         "<b>Colour</b> = easy → very hard, team rating where it differs"),
        (g('<rect x="2" y="3" width="22" height="13" rx="2" fill="var(--nightshade)"/>'),
         "<b>Shaded band</b> = running in the dark"),
        (g('<line x1="13" y1="2" x2="13" y2="16" stroke="var(--ink2)" stroke-width="1.4" stroke-dasharray="3 3"/>'),
         "<b>Dashed</b> = major exchange / van swap"),
    ]
    body = "".join(f'<div>{a}</div><div>{b}</div>' for a, b in rows)
    return (f'<details class="chartlegend" id="chartLegend"><summary>What am I looking at? — how to read this chart</summary>'
            f'<div class="legendgrid">{body}</div></details>')

def _platform_maps(key, cls=""):
    st = STARTS.get(str(key))
    if not st: return ""
    ll = f'{st["lat"]:.6f},{st["lng"]:.6f}'
    g = f'https://www.google.com/maps/dir/?api=1&amp;destination={ll}'
    a = f'https://maps.apple.com/?daddr={ll}'
    return (f'<span class="mapnav web-only {cls}" data-g="{g}" data-a="{a}">'
            f'<a class="mapbtn2 mapPrimary" href="{g}" target="_blank" rel="noopener">📍 Google Maps ↗</a>'
            f'<a class="mapalt mapAlt" href="{a}" target="_blank" rel="noopener">or Apple ↗</a></span>'
            f'<span class="coords print-only">📍 {ll}</span>')

def race_banner(kind, kicker, name, mi_label, sub, coords_key):
    cls = "ex" if kind == "exchange" else "se"
    return (f'<div class="bnr {cls}" id="{kicker.lower().replace(" ", "-")}">'
            f'<div class="bnrmain"><div class="kick">{esc(kicker)}<i>{mi_label}</i></div>'
            f'<div class="bname">{esc(name)}</div><div class="bsub">{esc(sub)}</div></div>'
            f'<div class="bnav">{_platform_maps(coords_key)}</div></div>')

def initials_map():
    firsts = {}
    out = {}
    for s2 in range(1, N_RUNNERS + 1):
        nm = RUNNERS.get(s2) or f"S{s2}"
        f0 = nm[0].upper()
        firsts.setdefault(f0, []).append(s2)
    for s2 in range(1, N_RUNNERS + 1):
        nm = RUNNERS.get(s2) or f"S{s2}"
        f0 = nm[0].upper()
        out[s2] = nm[:2].capitalize() if len(firsts[f0]) > 1 else f0
    return out

def leg_row(l):
    n = l["n"]
    slot = (n - 1) % N_RUNNERS + 1
    rating = l["team"] or l["rating"]
    inits = initials_map()
    surf = "".join(f'<i style="flex:{v};background:{SURF[k]}"></i>'
                   for v, k in zip(l["surface"], ("pavement", "gravel", "trail")) if v > 0)
    team_txt = f'{l["rating"]} → {l["team"]}' if l["team"] else l["rating"]
    return (f'<div class="lrow" id="lr-{n}" data-n="{n}" data-slot="{slot}" role="button" tabindex="0" aria-expanded="false">'
            f'<span class="rail" style="background:{DIFF[rating]}"></span>'
            f'<span class="num">{n:02d}</span>'
            f'<span class="lname">{esc(NAMES[n])}</span>'
            f'<span class="lsurf">{surf}</span>'
            f'<span class="lstats">{fmt_mi(l["dist"])} mi · +{l["gain"]:,}</span>'
            f'<span class="lrating" style="color:{DIFF[rating]}">{esc(team_txt)}</span>'
            f'<span class="lstart eststart" data-mi="{l["start_mi"]}"></span>'
            f'<span class="av avslot" data-slot="{slot}">{esc(inits[slot])}</span>'
            f'</div>')

def leg_expanded(l):
    n = l["n"]
    slot = (n - 1) % N_RUNNERS + 1
    rating = l["team"] or l["rating"]
    c = DIFF[rating]
    band_txt = f'{l["rating"]} → {l["team"]}' if l["team"] else l["rating"]
    inits = initials_map()
    m = ELEV_META.get(n)
    foot = ""
    if m and abs(m["mi"] - l["dist"]) > 0.15:
        foot = (f'<div class="footnote">🔄 <b>2026 route update:</b> Strava now measures this leg at ~{m["mi"]:.1f} mi '
                f'(our 2025 data: {fmt_mi(l["dist"])} mi / +{l["gain"]:,} ft). The profile is the current route.</div>')
    tags = "".join(f'<span class="chip warn">⚠ {esc(t)}</span>' for t in l["tags"])
    url = strava_url(n)
    surfmeta = (f'<div class="surfmeta"><span>{esc(l["surface_text"])}</span>'
                f'<span>mi {fmt_mi(l["start_mi"])} → {fmt_mi(l["end_mi"])}</span></div>')
    left = (profile_svg(n) + surface_bar(l).replace('<div class="surftext">' + esc(l["surface_text"]) + '</div>', '') + surfmeta)
    right = (f'<p class="beta2"><span class="src">team beta</span>{esc(l["beta"])}</p>'
             f'<div class="tagrow">{tags}</div>{foot}'
             f'<div class="xbtns"><a class="stravabtn web-only" href="{url}" target="_blank" rel="noopener">View route on Strava ↗</a>'
             f'{_platform_maps(n - 1)}'
             f'<div class="qrbox print-only"><img src="{qr_datauri(url)}" alt="QR: Strava route leg {n}"><span>Strava route</span></div></div>')
    return (f'<div class="lx" id="leg-{n}" data-n="{n}" data-slot="{slot}">'
            f'<div class="band" style="background:color-mix(in srgb, {c} 22%, transparent);border-bottom:1px solid color-mix(in srgb, {c} 40%, transparent)">'
            f'<span style="color:{c}">{esc(band_txt)}</span>'
            f'<span class="bandmeta">mi {fmt_mi(l["start_mi"])} → {fmt_mi(l["end_mi"])}</span><i>difficulty</i></div>'
            f'<div class="xbody">'
            f'<div class="nums"><div><b>{fmt_mi(l["dist"])}</b><span>mi</span></div>'
            f'<div><b>+{l["gain"]:,}</b><span>ft</span></div>'
            f'<div><b>{ftpmi(l):.0f}</b><span>ft/mi</span></div></div>'
            f'<div class="assign"><span class="av avslot" data-slot="{slot}">{esc(inits[slot])}</span>'
            f'<b class="runner-name" data-slot="{slot}">{esc(RUNNERS.get(slot) or f"Slot {slot}")}</b>'
            f'<span class="when"><span class="eststart" data-mi="{l["start_mi"]}"></span>'
            f' · <span class="estdur" data-mi="{l["start_mi"]}" data-dist="{l["dist"]}"></span></span></div>'
            f'<div class="xgrid"><div>{left}</div><div class="xright">{right}</div></div>'
            f'</div></div>')

def legs_stream():
    out = [race_banner("start", "Start line", START_LABEL.title() if START_LABEL.isupper() else START_LABEL,
                       "mi 0", RACE["start"].split(",", 1)[-1].strip() if "," in RACE["start"] else "", START_KEY)]
    done_mi = LEGS[0]["start_mi"]
    for i, sec in enumerate(SECTIONS):
        a, b = sec["legs"]
        for l in LEGS:
            if a <= l["n"] <= b:
                out.append(leg_row(l))
                out.append(leg_expanded(l))
        last = [x for x in LEGS if x["n"] == b][0]
        secmi = sum(x["dist"] for x in LEGS if a <= x["n"] <= b)
        secgain = sum(x["gain"] for x in LEGS if a <= x["n"] <= b)
        sub = f'legs {a}–{b} done · {secmi:.1f} mi · +{secgain:,} ft'
        if b in EXCHANGES:
            out.append(race_banner("exchange", f"Major exchange {i + 1}", EXCHANGES[b]["name"],
                                   f'mi {fmt_mi(last["end_mi"])}', sub, b))
        else:
            out.append(race_banner("finish", "Finish line", RACE["finish"].split(",")[0],
                                   f'mi {fmt_mi(TOTAL_MI)}', sub, 36 if RACE_ID == "205" else 36))
    return "".join(out)

def exchange_jump():
    rows = ['<div class="exjump rail-desktop-only"><div class="mylabel" style="margin:6px 9px 2px">Jump to an exchange</div>']
    for i, sec in enumerate(SECTIONS):
        a, b = sec["legs"]
        last = [x for x in LEGS if x["n"] == b][0]
        if b in EXCHANGES:
            rows.append(f'<a href="#major-exchange-{i+1}"><span class="k">Ex {i+1}</span> {esc(EXCHANGES[b]["name"].split("—")[0].strip())}<span class="m">mi {fmt_mi(last["end_mi"])}</span></a>')
    rows.append(f'<a href="#finish-line"><span class="k">Finish</span> {esc(RACE["finish"].split(",")[0])}<span class="m">mi {fmt_mi(TOTAL_MI)}</span></a></div>')
    return "".join(rows)

def build_index():
    nav = header_nav("legs", with_chips=True)
    body = f'''
<div class="shell"><div class="pagegrid">
<div class="rail">
  <div>{kpi_band()}</div>
  <div id="myLegsBlock"></div>
  {exchange_jump()}
</div>
<div class="maincol">
<div class="chartcard" id="course">
  <h2>The whole course at a glance</h2>
  <div class="sub">{len(LEGS)} legs in race order — tap one to jump.</div>
  {skyline_svg("")}
  {chart_legend_details()}
  {plan_ctl()}
</div>
<div id="myLegsBlockPhone"></div>
<div class="allhdr"><b>All {len(LEGS)} legs</b><span>tap a leg to open it</span></div>
{legs_stream()}
<details class="legend" style="margin-top:20px"><summary>🏁 Race day — who finishes when?</summary>
  <div class="panel" style="margin-top:8px">{race_day_panel(inner=True)}</div>
</details>
</div>
</div></div>'''
    return page(f"{TEAM_NAME} — Legs", nav, body, runners_js())

def build_overview():
    nav = header_nav("overview", with_chips=False)
    body = f'''
<div class="shell">
<h1 class="ovh1">Who's carrying what</h1>
<p class="ovsub">Heaviest load first. The index weighs miles, climb and leg ratings equally, scaled so the toughest slot is 100. Change who runs what in <a href="settings.html">Settings</a>.</p>
<div class="loadcards" id="loadCards"></div>

<h2 class="ovh2">When does everyone run?</h2>
<p class="ovsub">One row per runner, left to right across the whole race. The shaded stretch is after dark — swipe the timeline to read the clock.</p>
<div class="swimcard"><div class="swimnames" id="swimNames"></div>
  <div class="swimscroll"><svg id="swimSvg" width="900" height="200" viewBox="0 0 900 200"></svg></div></div>
<div class="swimlegend"><span>bar = one leg · width = time on course · number = leg</span>{dot_legend()}</div>

<h2 class="ovh2">The whole course</h2>
<div class="chartcard" id="map" style="margin-top:8px">
  <div class="strava-embed-placeholder" data-embed-type="route" data-embed-id="3386113643310609494" data-style="standard" data-map-hash="7.42/36.048/-93.997" data-club-id="1634354" data-from-embed="true"></div>
  <script src="https://strava-embeds.com/embed.js"></script>
  <p class="tiny" style="margin:.5em 0 0"><a href="https://www.strava.com/routes/3386113643310609494" target="_blank" rel="noopener">Open the full route on Strava ↗</a></p>
</div>

<details class="ovd" id="legTableD"><summary>Every leg on one page <span class="tiny">table view</span></summary>
  <div class="ovdbody" style="overflow-x:auto">{index_table()}</div>
</details>

<h2 class="ovh2">Before you go</h2>
<div class="ovtwo">
<details class="ovd"><summary>⌚ Get your legs on your Garmin watch</summary><div class="ovdbody">{watch_panel(inner=True)}</div></details>
<details class="ovd"><summary>🦺 Night rules &amp; official links</summary><div class="ovdbody">{rules_panel(with_qr=False, inner=True)}</div></details>
</div>
</div>'''
    return page(f"{TEAM_NAME} — Overview", nav, body, runners_js(), wide=True)

def build_print():
    sections_html = "".join(section_block(i, s) for i, s in enumerate(SECTIONS))
    body = f'''
{hero()}
<div class="panel">
  <h2>The whole course at a glance</h2>
  {skyline_svg("")}
  <div class="legendrow">Bar height = leg distance (mi) · bar width = steepness (ft/mi)</div>
  <div class="legendrow">Color = difficulty, team-adjusted: {dot_legend()}</div>
</div>
<div class="panel">
  <h2>Race in six sections</h2>
  <div class="tscroll"><table class="tbl">
    <thead><tr><th>Sec</th><th>Legs</th><th>Runs to</th><th class="r">Miles</th><th class="r">Climb</th><th class="r">Race mi at exchange</th></tr></thead>
    <tbody>{sec_overview_rows("#")}</tbody></table></div>
</div>
{how_to_read()}
<div class="panel" id="plan">
  <h2>Runner planner — who takes which rotation slot?</h2>
  {planner_table()}
</div>
<div class="cover-end"></div>
{sections_html}
<div class="panel idx-break" id="index">
  <h2>Every leg on one page</h2>
  {index_table("#")}
</div>
{watch_panel("#")}
{rules_panel(with_qr=True)}'''
    return page(f"{TEAM_NAME} — Race Guide (print)", "", body)

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, doc in [("index.html", build_index()), ("overview.html", build_overview()), ("print.html", build_print())]:
        with open(f"{OUT_DIR}/{name}", "w") as f:
            f.write(doc)
        print(f"wrote {OUT_DIR}/{name} ({len(doc)/1024:.0f} KB)")
    print("elev profiles:", len(ELEV), "legs")
