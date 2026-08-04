#!/usr/bin/env python3
"""Build the OTO race guide site:
   out/index.html    — legs page (home): jump bar, runner/slot filter, leg cards by section
   out/overview.html — dashboard: skyline, sections, planner, all-legs table, rules
   out/print.html    — everything on one page, print CSS -> PDF
Elevation profiles: if out/elev.json exists ({"1": [[mi, ft], ...], ...}), native SVG
profiles are embedded in each leg card.
"""
import base64, importlib, io, json, os, html as H
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
SKY = dict(W=760, H=200, PADL=30, PADR=8, TOP=40, BOT=26)

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
        parts.append(f'<text x="{(xa+xb)/2:.1f}" y="{TOP+10}" text-anchor="middle" font-size="8" fill="var(--ink2)">🌙 night</text>')
    for da, db in day_spans:
        if db - da > 18:
            parts.append(f'<text x="{(mile_x(da,segs)+mile_x(db,segs))/2:.1f}" y="{SKY["TOP"]+10}" text-anchor="middle" font-size="8" fill="var(--ink2)">☀️ day</text>')
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
        parts.append(f'<text x="{x:.1f}" y="{TOP+plot_h+20}" text-anchor="middle" font-size="6.8" fill="var(--muted)">{lbl}</text>')
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
        parts.append(f'<text x="{PAD_L-4}" y="{y(gv)+3:.1f}" text-anchor="end" font-size="8" fill="var(--muted)">{gv}</text>')
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
                     + (f'<text x="{xx+w/2:.1f}" y="{TOP+plot_h+9}" text-anchor="middle" font-size="6.2" fill="var(--muted)">{l["n"]}</text>' if w >= 8.5 else "")
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
    parts.append(f'<text x="{PAD_L-22}" y="{TOP-2}" font-size="7.5" fill="var(--muted)">mi</text>')
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
        parts.append(f'<text x="{PL-4}" y="{Y(gv)+2.5:.1f}" text-anchor="end" font-size="7.5" fill="var(--muted)">{gv:,.0f}</text>')
        gv += step
    parts.append(f'<path d="{area}" fill="color-mix(in srgb, var(--accent) 22%, transparent)"/>')
    parts.append(f'<path d="{path}" fill="none" stroke="var(--accent)" stroke-width="1.6" stroke-linejoin="round"/>')
    # x ticks each mile
    m = 1
    while m < x1:
        parts.append(f'<text x="{X(m):.1f}" y="{PT+ph+11}" text-anchor="middle" font-size="7.5" fill="var(--muted)">{m} mi</text>')
        m += 1
    parts.append(f'<text x="{PL-4}" y="{PT+2}" text-anchor="end" font-size="7" fill="var(--muted)">ft</text>')
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

def watch_panel(legs_href="index.html"):
    return f'''<div class="panel" id="watch">
  <h2>Get your legs on your Garmin watch</h2>
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
.beta .src, .srcbadge { display:inline-block; font-size:9.5px; font-weight:800; letter-spacing:.08em; text-transform:uppercase;
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
    pace = f'{int(p)}:{round(p % 1 * 60):02d}'
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
            + ";const LEGDATA=" + json.dumps(legdata) + ";"
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
function renderNight(pace, start) {
  const g = document.getElementById('nightg'); if (!g) return;
  const t1 = start + pace*PLAN.total; const parts = []; const regions = [];
  for (let d = 0; d < 3; d++) {
    const ns = d*1440+PLAN.ss, ne = (d+1)*1440+PLAN.sr;
    const a = Math.max(ns, start), b = Math.min(ne, t1);
    if (b > a) regions.push([(a-start)/pace, (b-start)/pace, ns >= start, ne <= t1]);
  }
  const dayspans = []; let cur = 0;
  for (const r of regions) { dayspans.push([cur, r[0]]); cur = r[1]; }
  dayspans.push([cur, PLAN.total]);
  for (const [ma, mb] of regions) {
    const xa = mileX(ma), xb = mileX(mb);
    parts.push(`<rect x="${xa}" y="${GEO.top}" width="${xb-xa}" height="${GEO.ploth}" fill="var(--nightshade)"/>`);
    parts.push(`<text x="${(xa+xb)/2}" y="${GEO.top+10}" text-anchor="middle" font-size="8" fill="var(--ink2)">🌙 night</text>`);
  }
  for (const [da, db] of dayspans) {
    if (db-da > 18) parts.push(`<text x="${(mileX(da)+mileX(db))/2}" y="${GEO.top+10}" text-anchor="middle" font-size="8" fill="var(--ink2)">☀️ day</text>`);
  }
  let tick = (Math.floor(start/360)+1)*360;
  while (tick < t1) {
    const x = mileX((tick-start)/pace);
    const d = Math.min(Math.floor(tick/1440), DAYSJS.length-1), h = Math.floor((tick%1440)/60);
    const lbl = DAYSJS[d]+' '+((h%12)||12)+' '+(h<12?'AM':'PM');
    parts.push(`<line x1="${x}" y1="${GEO.top+GEO.ploth}" x2="${x}" y2="${GEO.top+GEO.ploth+4}" stroke="var(--axis)" stroke-width="1"/>`);
    parts.push(`<text x="${x}" y="${GEO.top+GEO.ploth+20}" text-anchor="middle" font-size="6.8" fill="var(--muted)">${lbl}</text>`);
    tick += 360;
  }
  g.innerHTML = parts.join('');
}
let __plan = {pace: null, start: null};
function applyPlan(pace, start) {
  __plan = {pace: pace, start: start};
  document.querySelectorAll('.eststart').forEach(el => {
    const t = start + pace*parseFloat(el.dataset.mi);
    el.textContent = fmtClock(t)+' '+phaseEmoji(t);
  });
  renderNight(pace, start);
}
function parsePace(v) { const m = v.trim().match(/^(\\d{1,2}):(\\d{2})$/); return m ? Number(m[1])+Number(m[2])/60 : null; }
function hmJS(v) { const p = v.split(':').map(Number); return p[0]*60+p[1]; }
function paceStr(p) { const mm = Math.floor(p), ss = Math.round((p-mm)*60); return mm+':'+String(ss).padStart(2,'0'); }
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
    const clock = hmJS(rdTime.value), est = __plan.start + __plan.pace*mi;
    let t = clock;
    for (const cand of [clock, clock+1440, clock+2880]) {
      if (Math.abs(cand-est) < Math.abs(t-est)) t = cand;
    }
    rdAnchor = {mi: mi, t: t};
    const eta = t + pl*dist;
    const finish = eta + __plan.pace*(PLAN.total - mi - dist);
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
// keep anchor targets clear of the sticky nav
const topnav = document.querySelector('nav.top');
function setScrollPad() {
  if (topnav) document.documentElement.style.scrollPaddingTop = (topnav.offsetHeight + 10) + 'px';
}
setScrollPad();
addEventListener('resize', setScrollPad);
'''

def diff_legend():
    return "".join(f'<span class="pill" style="--pc:{c}"><span class="dot"></span><b>{k}</b></span>' for k, c in DIFF.items())

def race_day_panel():
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
    pace = f'{int(p)}:{round(p % 1 * 60):02d}'
    return f'''<details class="legend" id="raceday">
  <summary>🏁 Race day — who finishes when?</summary>
  <div class="panel" style="margin-top:8px">
    <div class="planctl"><select id="rdLeg">{opts}</select></div>
    <div class="planctl">left the exchange at <input id="rdTime" type="time">
      <button id="rdNow" class="pillbtn">now</button> · running about
      <input id="rdPace" value="{pace}" size="4"> min/mi</div>
    <p id="rdOut" class="beta" style="margin:.6em 0">Pick the leg, tap <b>now</b> at the handoff (or type the time), and the ETA shows here.</p>
    <div class="planctl"><button id="rdApply" class="pillbtn">↻ re-time the whole schedule from this handoff</button>
      <span class="tiny">shifts every est. start on this page (and the overview) so this leg's start matches reality — reset with the ⏱ control's reset</span></div>
  </div>
</details>'''

def how_to_read(compact=False):
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

def rules_panel(with_qr):
    L = RACE["links"]
    qrs = "".join(
        f'<div class="qrbox big"><img src="{qr_datauri(u)}" alt="QR {t}"><span>{t}</span></div>'
        for t, u in [("Official course map", L["course_map"]), ("2025 race guide PDF", L["guide_pdf"]),
                     ("Exchange zones (Google Maps)", L["exchanges_map"])]) if with_qr else ""
    return f'''
<div class="panel" id="rules">
  <h2>Night rules &amp; official links <span class="tiny">(🌐 from the official 2025 race guide)</span></h2>
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
    return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">%F0%9F%8F%83%F0%9F%8F%BB</text></svg>'>
<title>{esc(title)}</title>
<style>{css()}</style></head>
<body>
{nav_html}
<div class="wrap{" wide" if wide else ""}" id="top">
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

def build_index():
    jump = ""
    for l in LEGS:
        slot = (l["n"] - 1) % N_RUNNERS + 1
        jump += (f'<a href="#leg-{l["n"]}" data-slot="{slot}" title="{esc(NAMES[l["n"]])}">'
                 f'{l["n"]}<span class="d" style="background:{DIFF[l["rating"]]}"></span></a>')
    filters = '<button class="filterbtn active" data-slot="0">All runners</button>' + "".join(
        f'<button class="filterbtn" data-slot="{s}">{esc(slot_label(s))}</button>' for s in range(1, N_RUNNERS + 1))
    # the runner filter only appears once a roster is configured in data.py
    filter_row = f'<div class="navrow"><span class="rowlabel">Runner</span>{filters}</div>' if RUNNERS else ""
    nav = f'''<nav class="top">
  {nav_tabs("legs")}
  {filter_row}
  <div class="jumprow"><span class="rowlabel" style="align-self:center;margin-right:4px">Leg</span>{jump}</div>
</nav>'''
    sections_html = "".join(section_block(i, s) for i, s in enumerate(SECTIONS))
    body = f'''
{hero(sub=False)}
<div class="panel" id="course">
  <h2>The whole course at a glance</h2>
  {skyline_svg("")}
  <div class="legendrow">Bar height = leg distance (mi) · bar width = steepness (ft/mi) · color = difficulty, team-adjusted: {diff_legend()} · tap a bar to open that leg</div>
  {plan_ctl()}
</div>
{how_to_read(compact=True)}
{race_day_panel()}
{sections_html}'''
    return page(f"{TEAM_NAME} — Legs", nav, body, runners_js())

def build_overview():
    nr_options = "".join(f'<option value="{k}"{" selected" if k == N_RUNNERS else ""}>{k}</option>' for k in range(1, 13))
    nav = f'''<nav class="top">
  {nav_tabs("overview")}
  <div class="navrow"><span class="rowlabel">Jump to</span><a href="#index">All legs</a><a href="#map">Map</a><a href="#plan">Planner</a><a href="#watch">Watch</a><a href="#rules">Rules</a></div>
</nav>'''
    pills = ('<div class="pillrow web-only"><button class="pillbtn idxbtn active" data-slot="0">All legs</button>'
             + "".join(f'<button class="pillbtn idxbtn" data-slot="{s}">{esc(slot_label(s))}</button>' for s in range(1, N_RUNNERS + 1))
             + '</div>') if RUNNERS else ""
    body = f'''
{hero()}
<div class="panel" id="index">
  <h2>Every leg on one page</h2>
  {pills}
  {index_table()}
  {plan_ctl()}
</div>
<div class="panel" id="map">
  <h2>Full course map <span class="tiny">(the race's official all-legs Strava route)</span></h2>
  <div class="strava-embed-placeholder" data-embed-type="route" data-embed-id="3386113643310609494" data-style="standard" data-map-hash="7.42/36.048/-93.997" data-club-id="1634354" data-from-embed="true"></div>
  <script src="https://strava-embeds.com/embed.js"></script>
  <p class="tiny" style="margin:.5em 0 0">Embed not loading? <a href="https://www.strava.com/routes/3386113643310609494" target="_blank" rel="noopener">Open the all-legs route on Strava ↗</a></p>
</div>
<div class="panel" id="plan">
  <h2>Runner planner — who takes which rotation slot?</h2>
  <p class="tiny" style="margin:.2em 0 .6em" id="planNote">With {N_RUNNERS} runners, slot <i>s</i> runs legs <i>s, s+{N_RUNNERS}, s+{2*N_RUNNERS}, …</i></p>
  <div class="planctl web-only">Runners on your team: <select id="nrSel">{nr_options}</select>
    <span class="tiny">what-if only — it doesn't change any team's real setup</span></div>
  {planner_table()}
</div>
{watch_panel()}
{rules_panel(with_qr=False)}'''
    return page(f"{TEAM_NAME} — Overview", nav, body, runners_js(), wide=True)

def build_print():
    sections_html = "".join(section_block(i, s) for i, s in enumerate(SECTIONS))
    body = f'''
{hero()}
<div class="panel">
  <h2>The whole course at a glance</h2>
  {skyline_svg("")}
  <div class="legendrow">Bar height = leg distance (mi) · bar width = steepness (ft/mi) · color = difficulty, team-adjusted: {diff_legend()}</div>
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
