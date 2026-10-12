# Handoff — recap of the "OutbackInTheOzarks sync and deploy" session (Aug–Oct 2026)

Written 2026-10-12 so a new session (desktop or cloud) can continue from here. Read `CLAUDE.md` first; this is the narrative behind it.

## Where things live
- Working repo: `~/Developer/Other/oto-guide` → live at https://teamguide.outbackintheozarks.com (GitHub Pages; push to `main` = deploy in ~1–3 min). The `OutbackInTheOzarks` repo is retired (run1.fun redirect + an old PDF) — leave it alone.
- Build: `python3 -m venv .venv && .venv/bin/pip install qrcode pillow`; `cd builder`; `../.venv/bin/python build.py`; `OTO_DATA=data65 OTO_OUT=out65 ../.venv/bin/python build.py`; `cp out/*.html .. && cp out65/*.html ../65/`. **`git pull --ff-only` first** — cloud sessions push straight to `main`.
- Luke runs any SQL himself in the Supabase SQL editor. Writes to the `legs` table need his admin login (`builder/push_legs.py`, or a SQL block like `supabase/update_legs_2026-10-12.sql`). Reads are public via the anon key in `js/config.js`.

## What shipped (all on `main`, all live)
1. **Phone-first redesign of Legs + Overview** (from `page_redesign.zip`): sticky two-row header (nav + runner chips; "TeamName  OTO 205 · Oct 9–10, 2026"), runner-aware KPIs, accordion leg rows, platform-aware map buttons, desktop 308px rail. Overview = "Who's carrying what" load cards (index, ±vs avg, *shortest break · after N*, "runs once" for single-leg runners) + "When does everyone run?" swimlane (svg sized to the roster — 12-runner teams were clipped before). `settings.html` got the same ribbon.
2. **Leg card**: big-numbers row; route line `Start @ 13.9 ●────● End @ 20.7` with the bathroom status under each end (🚻 Bathroom / 🚽 Porta-potty / 🚫 No bathroom; "nearby" shows Bathroom plus a note chip "🚻 Bathroom at start/end is nearby" on both legs touching the zone); runner avatar + first name + est. start + time-of-day emoji + duration sit in the difficulty bar (the blue runner strip is gone); elevation/surface/beta stack in one column at every width; chips = ⚠ warnings from the DB + baked `.chip.note` chips that `team.js` preserves when it swaps in DB tags.
3. **Course facts in `builder/data.py`, baked at build, no admin UI** (Luke's rule: if JT won't edit it, don't build UI for it): `ZONE_BATHROOMS` for all 37 zones (JT's handwritten list; zone 0 = yes, 11 = no, 23 = no per Luke; 1 and 7 = "nearby"); `ZONE_EXTRAS` season-gated (2026: The Ol' Cabin breakfast at zone 29 → "🍳 Breakfast available" chip + footnote on legs 29 and 30; disappears when `RACE["dates"]` rolls to 2027).
4. **Admin**: "Exchange windows" board (one row per physical location: first/last projected arrival, team count, first/last team, 65 teams tagged; Print button) computed from wave + per-runner paces × assigned legs. Race totals and exchange miles come from `js/legdata.js`, which the 205 build emits (commit it). A bathroom admin UI and a `zones` table were tried and removed; `supabase/migrations.sql` records the cleanup (Luke ran it).
5. **Keep-alive**: `.github/workflows/keepalive.yml` pings Supabase daily (an Oct 5 GitHub Actions outage cancelled a Mon/Thu run; "job was not acquired by Runner" = GitHub outage, not us).
6. **Leg content**: the Oct 9 cloud session set legs 1/8/30/31 to the current Strava distances/gains (2025 figures in the footnote) and added `builder/gen_seed.py` + `push_legs.py`. On Oct 12 the Run1 group-chat notes and Luke's own notes were folded into 22 legs (2,3,4,7,9,10,11,12,13,14,15,16,19,20,21,22,24,25,26,27,28,29): *add to the beta, never replace*, except leg 24, which was wrong (≈4 mi rough loose gravel, not 100% pavement; surface bar/text/chip changed) and leg 21 (the uneven bridge was rebuilt; now "a few bridge crossings", hard-packed dirt). Leg 15 surface = 3 mi gravel · 4 mi pavement + "Loose gravel" chip; leg 26 team rating → Hard; leg 27 opens "Easily a hard rating" + "Shaded"; turn warnings as chips on 16 ("Turn left at 197 / 6041") and 19 ("Veer left early, GPS is wrong"). Where a watch read ≥25% more climb than listed (2, 7, 10, 11, 12, 29) the beta says "2026 watches read ~N ft of climb, more than the figure listed"; listed numbers stay the Strava route. Luke ran `supabase/update_legs_2026-10-12.sql`; verified all 36 live rows == `data.py`.

## Open items
- Legs 31–36 have no 2026 notes (Run1 DNF'd). Sebastian's legs 5, 11, 17, 23, 29 have 2026 numbers but no description. When the team sends more: same add-don't-replace rule, then `gen_seed.py`, rebuild, and give Luke the SQL/push for the live rows.
- Watch-vs-Strava distance disagreements were flagged, not written in: 13 (5.6 vs 6.09), 29 (6.98 vs 6.27), 30 (6.57 vs 7.27), 7 (5.15 vs 4.87). Luke chose to leave the listed numbers.
- 2027 rollover checklist is in `CLAUDE.md` (`RACE["dates"]` in `data.py`, `RACE_DATES` in `settings.html`, confirm `ZONE_BATHROOMS` with JT, admin "new season" copies leg rows forward).

## How Luke likes to work
- Brainstorm layouts with a quick visual of 3–4 options and a recommendation before building; he picks, then build → deploy → verify live → report in short plain sentences. Label anything open as DECISION NEEDED / NO ACTION, parked / LATER.
- Keep the UI emoji-light and uncluttered. He reviews on his iPhone; his screenshots are ground truth.
- Watches are less accurate than the Strava route; never change listed distances from watch data.
- He doesn't want to read scripts: show the diff/plan in chat and give him one thing to paste or run.

## Gotchas
- The desktop Browser pane can't animate smooth scrolling and blacks out after programmatic scrolls; verify geometry with JS, or use a tall viewport so the target is in view without scrolling.
- The scratchpad venv gets wiped between days; recreate it (qrcode, pillow) before building.
- Luke's iMessage attachments under `~/Library/Messages` are unreadable (TCC); ask him to paste the image into chat.
- `admin.html` can't be signed into from a harness; to exercise its table code, fetch `admin.html`, run its IIFE body with `new Function(body + 'window.__t={loadSeasons,loadTeams}')()` and call those (reads are public).
