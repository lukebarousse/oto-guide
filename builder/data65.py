# 65-Mile Relay variant — legs 25-36 of the same course, official numbering kept.
# One-day event: starts Saturday morning at Lake Fort Smith, finishes Prairie Grove.
# Build with: OTO_DATA=data65 OTO_OUT=out65 python build.py
from data import *  # noqa: F401,F403 — start from the 205 dataset, then filter/rebase

RACE_ID = "65"
LEGS = [dict(l) for l in LEGS if l["n"] >= 25]
_OFF = LEGS[0]["start_mi"]
for _l in LEGS:
    _l["start_mi"] -= _OFF
    _l["end_mi"] -= _OFF
TOTAL_MI = LEGS[-1]["end_mi"]
TOTAL_GAIN = sum(l["gain"] for l in LEGS)

SECTIONS = [s for s in SECTIONS if s["legs"][0] >= 25]
EXCHANGES = {k: v for k, v in EXCHANGES.items() if k >= 25}

RACE = dict(
    RACE,
    subtitle="65-Mile Relay · Team Guide",
    dates="Saturday Oct 10, 2026",
    start="Lake Fort Smith State Park, Mountainburg, AR",
)

TEAM_NAME = "OTO 65"
N_RUNNERS = 6          # 65-mile teams are 4-6 runners
RUNNERS = {}

PLAN = dict(PLAN, start_hhmm="06:00")   # 6:00 AM Saturday, per the race director
RACE_DAYS = ["Sat", "Sun"]
PLAN_NOTE = "one-day event — confirm your start time with the race"
START_KEY = "24"       # leg 25 starts at exchange zone 24 (Lake Fort Smith)
START_LABEL = "LAKE FORT SMITH STATE PARK"
ACCENT = "#d97427"     # distinct look: Ozark-orange accent instead of the 205's blue
JS_PREFIX = "../js/"
