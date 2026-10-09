#!/usr/bin/env python3
"""Push leg content from data.py into the Supabase legs table. The live site shows the
database row for each leg, not the static text, so a data.py edit is not live until it
is pushed. Writes need an admin login (the anon key can only read), so set either
    OTO_ADMIN_EMAIL + OTO_ADMIN_PASSWORD   an admin.html user: signs in, then writes
    SUPABASE_SERVICE_ROLE_KEY              bypasses row security; never commit it anywhere
Project URL + anon key are read from ../js/config.js.

    cd builder && ../.venv/bin/python push_legs.py 2 3 4   # those legs
    ../.venv/bin/python push_legs.py --all                 # every leg, same rows as seed_legs.sql
Each named leg's whole row (beta, tags, team_rating, surface_text) is replaced from
data.py, including anything edited in admin.html since. Reads the rows back to verify.
"""
import json, os, re, sys, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data

cfg = open(os.path.join(HERE, "..", "js", "config.js"), encoding="utf-8").read()
URL = re.search(r'url:\s*"([^"]+)"', cfg).group(1).rstrip("/")
ANON = re.search(r'anonKey:\s*"([^"]+)"', cfg).group(1)
YEAR = int(re.search(r"20[0-9][0-9]", data.RACE["dates"]).group(0))


def request(path, headers, method="GET", body=None):
    req = urllib.request.Request(URL + path, method=method, headers={"Content-Type": "application/json", **headers},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")
    except urllib.error.URLError as e:
        sys.exit(f"cannot reach {URL}: {e.reason}\n(from a cloud session: allow this host under the environment's network settings)")


def token():
    email, pw = os.environ.get("OTO_ADMIN_EMAIL"), os.environ.get("OTO_ADMIN_PASSWORD")
    if email and pw:
        return request("/auth/v1/token?grant_type=password", {"apikey": ANON}, "POST",
                       {"email": email, "password": pw})["access_token"]
    if os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        return os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sys.exit("set OTO_ADMIN_EMAIL + OTO_ADMIN_PASSWORD (or SUPABASE_SERVICE_ROLE_KEY) in the environment")


args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
want = None if args == ["--all"] else {int(a) for a in args}
legs = [l for l in data.LEGS if want is None or l["n"] in want]
if want is not None and len(legs) != len(want):
    sys.exit(f"unknown leg numbers: {sorted(want - {l['n'] for l in legs})}")

auth = {"apikey": ANON, "Authorization": f"Bearer {token()}"}
seasons = request(f"/rest/v1/seasons?select=id,year&year=eq.{YEAR}", auth)
if not seasons:
    sys.exit(f"no season {YEAR} in the database")
sid = seasons[0]["id"]
rows = [dict(season_id=sid, n=l["n"], beta=l["beta"], tags=l["tags"], team_rating=l["team"],
             surface_text=l["surface_text"]) for l in legs]
request("/rest/v1/legs", {**auth, "Prefer": "resolution=merge-duplicates,return=minimal"}, "POST", rows)
back = request(f"/rest/v1/legs?select=n,beta&season_id=eq.{sid}&n=in.({','.join(str(l['n']) for l in legs)})", auth)
live = {r["n"]: r["beta"] for r in back}
bad = 0
for l in legs:
    ok = live.get(l["n"]) == l["beta"]
    bad += not ok
    print(f"leg {l['n']:2d}: {'ok      ' if ok else 'MISMATCH'} {l['beta'][:70]}")
sys.exit(1 if bad else 0)
