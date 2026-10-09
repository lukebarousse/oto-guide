#!/usr/bin/env python3
"""Regenerate supabase/seed_legs.sql from data.py after editing leg content:
    cd builder && ../.venv/bin/python gen_seed.py          # writes ../supabase/seed_legs.sql
    ../.venv/bin/python gen_seed.py /some/other/path.sql   # writes elsewhere
The seed is an upsert: re-running the whole file in the Supabase SQL editor overwrites
every leg's beta/tags/team_rating/surface_text for that season with data.py's version,
including anything edited in admin.html since. To push one leg, run just its row.
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data

year = int(re.search(r"20[0-9][0-9]", data.RACE["dates"]).group(0))
def q(s): return "'" + s.replace("'", "''") + "'"
rows = [f"((select id from seasons where year={year}), {l['n']}, {q(l['beta'])}, "
        f"{q(json.dumps(l['tags']))}::jsonb, {q(l['team']) if l['team'] else 'null'}, {q(l['surface_text'])})"
        for l in data.LEGS]
sql = (f"-- Seed {year} leg content (run after schema.sql)\n"
       "insert into legs (season_id, n, beta, tags, team_rating, surface_text) values\n"
       + ",\n".join(rows) + "\n"
       "on conflict (season_id, n) do update set beta=excluded.beta, tags=excluded.tags, "
       "team_rating=excluded.team_rating, surface_text=excluded.surface_text;\n")
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "supabase", "seed_legs.sql")
with open(out, "w", encoding="utf-8") as f:
    f.write(sql)
print(f"wrote {os.path.normpath(out)} ({len(rows)} legs, season {year})")
