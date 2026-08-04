# Outback in the Ozarks 205 — merged leg dataset
# Sources:
#   NOTE  = 2025 team Apple Note (first-hand beta from last year's runner)
#   SHEET = Luke's Google Sheet (Strava-scraped 2025: distances, gain, cumulative miles, climb sections)
#   WEB   = official outbackintheozarks.com course map (leg names, Strava route links, exchange names)

STRAVA = {
    1: "3379992613740062728", 2: "3379993009756757000", 3: "3384280323494893970",
    4: "3384309193583745802", 5: "3384309737164274076", 6: "3384310043525698972",
    7: "3386085387673391190", 8: "3386095246258470460", 9: "3386095841125979708",
    10: "3386096094381966438", 11: "3386096336748878934", 12: "3386097114352695398",
    13: "3386097533788029014", 14: "3386098082441573948", 15: "3386098515190436412",
    16: "3386098701498648662", 17: "3386099115846651452", 18: "3386102217590042710",
    19: "3386102804902513750", 20: "3386103842125470806", 21: "3386104079323906150",
    22: "3386104596854165590", 23: "3386104875912717884", 24: "3386105352317011046",
    25: "3386105554728989782", 26: "3386105849832191250", 27: "3386106246970734140",
    28: "3386106474653939798", 29: "3386106720653876796", 30: "3386107651228095036",
    31: "3386108031698157654", 32: "3386108373130219794", 33: "3386109824209567830",
    34: "3386110156892772626", 35: "3386112051238968892", 36: "3386112837113508412",
}

NAMES = {
    1: "Didgeridoo Dash", 2: "Rockhouse Roll", 3: "Koala Holler", 4: "Hot Diggity!",
    5: "Wobble to Cobble", 6: "Hobb Nob", 7: "Little Clifty", 8: "War Eagle",
    9: "Up and At 'em!", 10: "Dingos with Banjos", 11: "The Roamin' Forum",
    12: "Walkabout to Withrow", 13: "Lolligaggin'", 14: "Bandicoot", 15: "I Ain't Skeerd!",
    16: "Playin' Possum", 17: "Rip Snorter", 18: "Buncha Fun!", 19: "Tasmanian Devil",
    20: "No Worries!", 21: "Wallaby", 22: "Plumb Tuckered", 23: "Greased Lightnin'",
    24: "Bushwalker", 25: "Tester to Chester", 26: "Gumption", 27: "Chuck a Wobbly",
    28: "Boondocks", 29: "Backwoods Boomerang", 30: "Holy Hedgehog!",
    31: "Running from the Devil", 32: "Ridgy Didge", 33: "Platypus Plod",
    34: "Gravel, Grit & Bridge Biz", 35: "The Holy Roller", 36: "Finish Line",
}

# rating: official rating from the note (caps). team: adjusted read from the beta, if different.
# surface: (pavement %, gravel/dirt %, trail %) approximated from the note text; surface_text = literal.
# climbs: notable climb sections from the sheet (avg grade, elevation ft, distance mi).
# dist/gain: sheet values (Strava-scraped 2025). Leg 30 & 36 ratings come from the sheet (missing in note).
LEGS = [
 dict(n=1, dist=6.35, gain=755, rating="Hard", team="Very Hard",
      surface=(33, 33, 34), surface_text="Trail / pavement / gravel",
      beta="Trail has switchbacks with loose gravel and tree roots — be careful, saw several people fall. Steep climb going into Eureka, potential to walk some of it. Easy downhill through town, followed by a tough gravel climb to the finish. Could see this leg rated very hard.",
      climbs=[(2.8, 330, 2.2), (2.2, 274, 2.3)], tags=["Loose gravel + roots", "Steep climb"]),
 dict(n=2, dist=7.53, gain=561, rating="Moderate", team="Hard",
      surface=(100, 0, 0), surface_text="All pavement",
      beta="A lot of climbs on this one. Moderate, but arguably hard. Pay attention to turn signs and dogs.",
      climbs=[(1.8, 497, 5.3)], tags=["Dogs", "Watch the turns"]),
 dict(n=3, dist=6.81, gain=609, rating="Hard", team=None,
      surface=(25, 38, 37), surface_text="75% gravel/trail · 25% pavement",
      beta="Hard for sure. Super rocky path — even the vans can't follow it. You run across a dry river bed and finish up a steep, narrow hiking trail to the highway. Many had to walk a little.",
      climbs=[(1.4, 223, 3.0)], tags=["No van access", "Rocky"]),
 dict(n=4, dist=5.33, gain=126, rating="Moderate", team="Easy",
      surface=(50, 50, 0), surface_text="Pavement / gravel",
      beta="Starts on paved highway with moderate traffic. Mostly flat. Finishes with a descent on a rocky dirt road. Closer to easy.",
      climbs=[], tags=["Traffic"]),
 dict(n=5, dist=6.49, gain=896, rating="Very Hard", team=None,
      surface=(0, 100, 0), surface_text="100% gravel",
      beta="Very steep climbs with some hard descents — and beautiful views. You'll have hills where you have to walk, followed by steep descents where you can run fast, but not too fast or you might fall. Pay attention to footing. Very challenging leg.",
      climbs=[(3.4, 315, 1.8), (2.2, 252, 2.1)], tags=["Footing", "Walk the steeps", "Views"]),
 dict(n=6, dist=5.04, gain=193, rating="Moderate", team="Easy",
      surface=(95, 5, 0), surface_text="¼ mile dirt, then all pavement",
      beta="Easy paved highway. Rated moderate, but I would rate it easy. Nice rolling flats on pavement.",
      climbs=[], tags=[]),
 dict(n=7, dist=4.87, gain=379, rating="Hard", team=None,
      surface=(0, 0, 100), surface_text="100% trail",
      beta="Rolling hills with two big inclines. Easy to go fast on the downhill. A lot of good shade.",
      climbs=[], tags=["Shaded"]),
 dict(n=8, dist=6.08, gain=376, rating="Hard", team=None,
      surface=(16, 0, 84), surface_text="Mostly trail · last mile pavement",
      beta="Anticipate loose rocks, exposed roots and heavy leaf coverage. Several descents and moderate climbs. Finishes with a transition to paved road leading directly to War Eagle. GPS navigation recommended for the trail (sorry Benny).",
      climbs=[], tags=["GPS recommended", "Rocks + roots + leaves"]),
 dict(n=9, dist=8.13, gain=557, rating="Hard", team="Moderate",
      surface=(60, 40, 0), surface_text="60% pavement · 40% gravel",
      beta="Lightly hilly countryside with a few medium-sized hills along the way. Seems moderate.",
      climbs=[(2.1, 226, 2.1)], tags=[]),
 dict(n=10, dist=8.73, gain=722, rating="Hard", team=None,
      surface=(17, 83, 0), surface_text="½ mi pavement · 7 mi gravel · 1 mi pavement",
      beta="You go up a gnarly hill when you reach gravel — the rock was chunky and challenging for road shoes. Back onto the highway, then gravel again. Both my favorite and least favorite leg. Rated hard, and I definitely agree.",
      climbs=[(2.9, 229, 1.5)], tags=["Chunky rock", "Shoe choice matters"]),
 dict(n=11, dist=7.13, gain=327, rating="Moderate", team=None,
      surface=(67, 33, 0), surface_text="⅓ gravel · ⅔ pavement",
      beta="Easy downhill to start. Rolling hills with a couple decent climbs. Gravel was in good shape. Turns onto Hwy 23, which is flat — but be on the lookout for traffic.",
      climbs=[], tags=["Traffic on Hwy 23"]),
 dict(n=12, dist=3.86, gain=183, rating="Easy", team=None,
      surface=(42, 58, 0), surface_text="Mostly gravel / pavement · last ½ mi gravel",
      beta="Big decline at the pavement portion. The last half mile is trail and the toughest part — the stairs on the trail are slippery.",
      climbs=[], tags=["Slippery stairs"]),
 dict(n=13, dist=6.09, gain=459, rating="Moderate", team=None,
      surface=(33, 67, 0), surface_text="⅓ pavement · ⅔ gravel",
      beta="Cross the street to the dirt road — if you go over the second bridge, you went too far. Pavement leads to a ferry pickup to cross Hwy 412, then finish with a half-mile run after.",
      climbs=[(0.5, 162, 6.1)], tags=["Navigation", "Hwy 412 ferry crossing"]),
 dict(n=14, dist=4.89, gain=542, rating="Moderate", team=None,
      surface=(0, 100, 0), surface_text="100% gravel",
      beta="Several turns, and some of the signs were removed or hard to see. Pay attention — have the van stick with the runner on this one.",
      climbs=[(1.1, 130, 2.3)], tags=["Navigation!", "Van should shadow runner"]),
 dict(n=15, dist=6.95, gain=287, rating="Hard", team="Moderate",
      surface=(71, 29, 0), surface_text="2 mi gravel · 5 mi pavement",
      beta="Pitch black. Some little rollers with one mild climb. I would rate it moderate.",
      climbs=[], tags=["Pitch black — lights!"]),
 dict(n=16, dist=4.85, gain=280, rating="Moderate", team="Easy",
      surface=(40, 60, 0), surface_text="40% pavement · 60% gravel",
      beta="Spooky as hell, but if you can get past that, a quiet and peaceful run. Rated moderate, but I would rate it easy.",
      climbs=[], tags=["Dark + spooky"]),
 dict(n=17, dist=4.74, gain=630, rating="Moderate", team=None,
      surface=(25, 75, 0), surface_text="75% gravel · 25% pavement",
      beta="Appropriately moderate. The hills were nasty getting up, but you end on pavement with a consistent decline — you make up a ton of time on the downhill. Push hard on the uphill, because you can catch your breath at the end.",
      climbs=[], tags=["Nasty ups, fast finish"]),
 dict(n=18, dist=4.75, gain=156, rating="Moderate", team="Easy",
      surface=(50, 50, 0), surface_text="Pavement / gravel / pavement · about half and half",
      beta="You can definitely run faster on this leg. Pay attention to turns and traffic on the final mile. Overall a flat and nice leg — more towards easy.",
      climbs=[], tags=["Turns + traffic, final mile"]),
 dict(n=19, dist=5.72, gain=429, rating="Hard", team="Moderate",
      surface=(100, 0, 0), surface_text="100% pavement",
      beta="Leaves the city and heads out onto a paved road. Very dark. Mostly flat with some light-to-medium rolling hills. More moderate.",
      climbs=[], tags=["Very dark"]),
 dict(n=20, dist=4.36, gain=187, rating="Easy", team=None,
      surface=(100, 0, 0), surface_text="100% pavement",
      beta="Easy breezy! A few hills.",
      climbs=[], tags=[]),
 dict(n=21, dist=4.23, gain=211, rating="Easy", team=None,
      surface=(0, 100, 0), surface_text="100% gravel",
      beta="Very easy run — smooth road and flat. The only lookout worth noting is an uneven bridge, which can pose a challenge running at night.",
      climbs=[], tags=["Uneven bridge at night"]),
 dict(n=22, dist=4.84, gain=944, rating="Moderate", team="Hard",
      surface=(50, 50, 0), surface_text="Gravel / pavement · close to half and half",
      beta="One steady climb the whole way — very gradual, but steep at times. It just keeps going! Hard to hold the heart rate down. Be ready to climb and go slow on this one. Leans towards hard.",
      climbs=[(3.0, 765, 4.8)], tags=["Sustained climb"]),
 dict(n=23, dist=8.17, gain=156, rating="Moderate", team=None,
      surface=(0, 100, 0), surface_text="100% gravel",
      beta="Starts off flat and smooth, but gets very rough and rugged about 3 miles in and stays that way until the end.",
      climbs=[], tags=["Rugged after mile 3"]),
 dict(n=24, dist=4.66, gain=453, rating="Hard", team=None,
      surface=(100, 0, 0), surface_text="100% pavement",
      beta="Even though it's pavement, it was in very bad shape at times — pay attention. A lot of hills and very desolate. You will walk some. It felt good to get to Lake Fort Smith and be done with this one.",
      climbs=[(3.7, 310, 1.6)], tags=["Broken pavement", "Desolate"]),
 dict(n=25, dist=8.41, gain=845, rating="Hard", team=None,
      surface=(100, 0, 0), surface_text="100% pavement",
      beta="All uphill for 1.7 miles before a constant downhill to Chester. The downhill felt like it went on forever. Rated hard, and I definitely agree.",
      climbs=[(5.3, 595, 2.1)], tags=["1.7 mi opening climb", "Endless downhill"]),
 dict(n=26, dist=5.47, gain=958, rating="Moderate", team=None,
      surface=(100, 0, 0), surface_text="100% pavement",
      beta="Take a left onto the main road out of the parking lot, immediately beginning a substantial climb. Once you reach the summit, bear left to transition to a dirt road for your exchange.",
      climbs=[(3.0, 851, 5.5)], tags=["Climbs right off the start"]),
 dict(n=27, dist=7.67, gain=818, rating="Moderate", team="Hard",
      surface=(0, 100, 0), surface_text="100% gravel",
      beta="Arguably a hard rating. The hills were a beast and the terrain was difficult. There's a huge hill between miles 5 and 6 — you will likely walk some. Save yourself on the initial hills, because the last one is painful.",
      climbs=[(2.3, 357, 3.0)], tags=["Beast hills", "Big hill mi 5–6"]),
 dict(n=28, dist=5.15, gain=415, rating="Moderate", team=None,
      surface=(50, 50, 0), surface_text="Half pavement · half gravel",
      beta="Smooth sailing! Nice paved road, beautiful views. Some substantial uphill, but still moderate overall.",
      climbs=[(2.5, 153, 1.1)], tags=["Views"]),
 dict(n=29, dist=6.27, gain=281, rating="Moderate", team=None,
      surface=(100, 0, 0), surface_text="100% pavement",
      beta="Lots of rolling hills with three big climbs — every downhill was met with a climb. Windy road with very little shoulder. Would recommend a flagger.",
      climbs=[], tags=["Flagger recommended", "No shoulder"]),
 dict(n=30, dist=7.56, gain=364, rating="Hard", team=None, rating_src="sheet",
      surface=(100, 0, 0), surface_text="100% pavement",
      beta="A lot of gradual climbs for the first 4–5 miles. Take your time — you'll need it for the brutal descent into Devil's Den: switchbacks and high traffic, with over 800 ft of descent in the last couple of miles. Highly recommend a flagger.",
      climbs=[], tags=["Flagger recommended", "Brutal descent", "Switchbacks + traffic"]),
 dict(n=31, dist=6.27, gain=929, rating="Very Hard", team=None,
      surface=(56, 36, 8), surface_text="½ mi trail · 3.5 mi pavement · rest gravel",
      beta="Short trail coming out of the park with uneven terrain. Once you reach Hwy 16 it's flat until 2.3 miles in — then you climb!! Climb the rest of the way. Walked a few stretches to keep the heart rate down.",
      climbs=[(2.3, 750, 6.3)], tags=["Climb from mile 2.3 on"]),
 dict(n=32, dist=4.62, gain=317, rating="Easy", team=None,
      surface=(50, 50, 0), surface_text="50% pavement · 50% gravel",
      beta="Transition is about halfway, where you'll make a left. Rolling hills throughout, followed by a short climb to the finish.",
      climbs=[], tags=[]),
 dict(n=33, dist=3.60, gain=99, rating="Easy", team=None,
      surface=(50, 50, 0), surface_text="Pavement / gravel",
      beta="A lot of curves in the road towards the end and no shoulder to retreat to — be careful! Recommend a flagger.",
      climbs=[], tags=["Flagger recommended", "Blind curves"]),
 dict(n=34, dist=3.62, gain=136, rating="Easy", team=None,
      surface=(0, 100, 0), surface_text="100% gravel",
      beta="Nice easy leg with a lot of descents. If you have anything left, you can make good time on this one.",
      climbs=[], tags=["Fast descents"]),
 dict(n=35, dist=3.03, gain=212, rating="Easy", team=None,
      surface=(50, 50, 0), surface_text="½ gravel · ½ pavement",
      beta="Start on dirt with a steady incline, finish on pavement with a decline. Next to a busy road — stay alert!",
      climbs=[], tags=["Busy road"]),
 dict(n=36, dist=4.89, gain=259, rating="Moderate", team=None, rating_src="sheet",
      surface=(80, 20, 0), surface_text="Pavement · 1 mi gravel · pavement",
      beta="Light rolling hills. Ferry at the Hwy 62 intersection — park your car on the same side as the runner and ferry across the street. Ends at the finish line at Prairie Grove Battlefield Park!",
      climbs=[], tags=["Hwy 62 ferry crossing", "FINISH!"]),
]

# Exchange stations (after leg N). Names cross-checked: team note vs official 2025 race guide.
EXCHANGES = {
    6:  dict(name="Hobbs State Park", note="Major exchange 1 · official van-swap point"),
    12: dict(name="Withrow Springs State Park", note="Major exchange 2"),
    18: dict(name="Elkins — Bunch City Park", note="Major exchange 3 · team note says “Elkins”, official guide says “Bunch City Park” (same stop, in Elkins)"),
    24: dict(name="Lake Fort Smith State Park", note="Major exchange 4"),
    30: dict(name="Devil's Den State Park", note="Major exchange 5"),
}

START = dict(name="Lake Leatherwood City Ballpark, Eureka Springs", )
FINISH = dict(name="Prairie Grove Battlefield State Park", )

SECTIONS = [
    dict(legs=(1, 6),  dest="Hobbs State Park"),
    dict(legs=(7, 12), dest="Withrow Springs State Park"),
    dict(legs=(13, 18), dest="Elkins (Bunch City Park)"),
    dict(legs=(19, 24), dest="Lake Fort Smith State Park"),
    dict(legs=(25, 30), dest="Devil's Den State Park"),
    dict(legs=(31, 36), dest="FINISH — Prairie Grove Battlefield"),
]

RACE = dict(
    title="Outback in the Ozarks",
    subtitle="205-Mile Relay · Team Guide",
    dates="Friday Oct 9 – Saturday Oct 10, 2026",
    start="Lake Leatherwood City Ballpark, Eureka Springs, AR",
    finish="Prairie Grove Battlefield State Park, Prairie Grove, AR",
    links=dict(
        site="https://outbackintheozarks.com/",
        course_map="https://outbackintheozarks.com/course-map",
        guide_pdf="https://static1.squarespace.com/static/67b6279ccd5b44506e82f478/t/68488aee94be8934cad18ff3/1749584626134/OTO+2025+Race+Guide+.pdf",
        exchanges_map="https://maps.app.goo.gl/gRvJDNHpHR2z5R6q9",
        full_route_map="https://www.google.com/maps/d/edit?mid=1S3rWAD35CEJBqz6sRkXKpyRrL0PEO_w&usp=sharing",
    ),
)

# sanity: cumulative miles
def with_cumulative(legs):
    cum = 0.0
    out = []
    for l in legs:
        l = dict(l)
        l["start_mi"] = cum
        cum = round(cum + l["dist"], 2)
        l["end_mi"] = cum
        out.append(l)
    return out

LEGS = with_cumulative(LEGS)
TOTAL_MI = LEGS[-1]["end_mi"]
TOTAL_GAIN = sum(l["gain"] for l in LEGS)

TEAM_NAME = "OTO 205"    # overridden per-team at runtime from the database

# defaults for the generic (no-team) view; team pages override from the database
N_RUNNERS = 6
RUNNERS = {}

# timeline assumptions (2026) — update start_hhmm when wave assignments land (notified by Oct 6).
# Official: first wave 6:00 AM Friday, staggered 6:00-12:00 by team 10k pace (race FAQ).
# pace: generic default; team pages override from the database.
PLAN = dict(
    start_hhmm="06:00",
    pace_min_per_mi=10.0,
    sunrise="07:15", sunset="18:45",   # Eureka Springs/Fayetteville, Oct 9-10
)
