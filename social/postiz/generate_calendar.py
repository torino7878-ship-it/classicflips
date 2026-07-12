#!/usr/bin/env python3
"""
Generates the 90-day / 270-post Classic Flips social calendar and writes it
to calendar.json. Pure offline generation -- no network calls.

Run:
    python3 generate_calendar.py

Regenerate any time the pillar copy, date range, or slot times change.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

START_DATE = "2026-07-08"
END_DATE = "2026-10-05"
TIMEZONE = "America/Los_Angeles"  # PT (handles PDT/PST automatically)
SLOT_TIMES = [(8, 0, "morning"), (12, 0, "midday"), (18, 0, "evening")]
OUTPUT_PATH = Path(__file__).parent / "calendar.json"

# Each post in a slot is cross-posted to both channels in a single Postiz
# API call (Postiz's /posts endpoint accepts multiple integration targets
# per post). 90 days x 3 slots = 270 scheduled posts.
PLATFORMS = ["tiktok", "instagram"]

PILLARS = [
    {
        "key": "supra",
        "name": "Toyota Supra (Mk4/A80)",
        "hook": "the 2JZ-GTE that launched a thousand builds",
        "facts": [
            "the legendary 2JZ-GTE twin-turbo straight-six built to handle power well past its factory rating",
            "a chassis that went from Japanese showroom to Hollywood icon in one movie franchise",
            "clean, unmodified Mk4s that are quietly becoming some of the hardest cars to find at any price",
            "a design so far ahead of its time it still turns heads parked next to modern sports cars",
        ],
        "hashtags": ["#ToyotaSupra", "#Mk4Supra", "#2JZ", "#JDM", "#SupraNation"],
    },
    {
        "key": "nsx",
        "name": "Honda/Acura NSX",
        "hook": "the everyday supercar Ayrton Senna helped tune",
        "facts": [
            "an all-aluminum body that put Ferrari on notice for build quality and daily drivability",
            "mid-engine balance dialed in with direct input from a three-time F1 world champion",
            "a reliability record that still embarrasses exotics costing three times as much",
            "one of the cleanest, most honest driver's cars Japan has ever exported",
        ],
        "hashtags": ["#HondaNSX", "#AcuraNSX", "#NSX", "#JDM", "#SennaTuned"],
    },
    {
        "key": "mustang",
        "name": "Ford Mustang",
        "hook": "the pony car that never stopped evolving",
        "facts": [
            "six decades of American performance history in one continuous bloodline",
            "Fox Body, SN95, and Terminator Cobra variants each with their own cult following",
            "a Boss 302 or Shelby GT500 pedigree that collectors are re-discovering right now",
            "a V8 soundtrack that defined a generation of American muscle",
        ],
        "hashtags": ["#FordMustang", "#Mustang", "#AmericanMuscle", "#ClassicMustang", "#PonyCar"],
    },
    {
        "key": "rx7",
        "name": "Mazda RX-7 (FD3S)",
        "hook": "the rotary that redefined the drift scene",
        "facts": [
            "the sequential twin-turbo 13B rotary that revs like nothing else on the road",
            "pop-up headlights and a silhouette that still looks futuristic decades later",
            "a chassis balance that made it the weapon of choice for an entire generation of drifters",
            "shrinking supply as clean, unmolested examples get harder to find every year",
        ],
        "hashtags": ["#MazdaRX7", "#RX7", "#FD3S", "#RotaryPower", "#JDM"],
    },
    {
        "key": "porsche911",
        "name": "Porsche 911",
        "hook": "the air-cooled icon that never left the blueprint",
        "facts": [
            "an air-cooled flat-six lineage that collectors treat as investment-grade rolling art",
            "a silhouette so consistent you can trace fifty years of the same idea, perfected",
            "964 and 993 examples that have quietly outpaced most blue-chip assets over the last decade",
            "a driving experience purists say still hasn't been matched by anything newer",
        ],
        "hashtags": ["#Porsche911", "#AirCooled", "#Porsche", "#911", "#GermanEngineering"],
    },
    {
        "key": "m3",
        "name": "BMW M3",
        "hook": "the touring-car pedigree built for the street",
        "facts": [
            "S14, S50, and S54 engines engineered from BMW's own touring car program",
            "E30, E36, and E46 generations each considered a benchmark driver's car in its era",
            "a motorsport DNA you can feel through the wheel on every single drive",
            "values on early E30 M3s that have climbed faster than almost anything else from the '80s",
        ],
        "hashtags": ["#BMWM3", "#M3", "#E30M3", "#E46M3", "#BMWMotorsport"],
    },
    {
        "key": "camaro",
        "name": "Chevrolet Camaro",
        "hook": "Detroit's answer that became a legend of its own",
        "facts": [
            "Z/28, SS, and IROC-Z trims that each wrote their own chapter of muscle car history",
            "a rivalry with the Mustang that pushed both nameplates to their best eras",
            "big-block and small-block variants that collectors are actively hunting right now",
            "a silhouette instantly recognizable at any cruise night in the country",
        ],
        "hashtags": ["#ChevyCamaro", "#Camaro", "#AmericanMuscle", "#IROCZ", "#Z28"],
    },
    {
        "key": "r34",
        "name": "Nissan Skyline GT-R (R34)",
        "hook": "the car America wasn't allowed to have for 25 years",
        "facts": [
            "the RB26DETT and ATTESA E-TS all-wheel-drive system that earned it the name 'Godzilla'",
            "grey-market import status that's only made clean examples more coveted stateside",
            "a Nurburgring resume that out-punched cars costing multiples of its price",
            "prices that have climbed harder than almost any other JDM legend on this list",
        ],
        "hashtags": ["#SkylineGTR", "#R34", "#GodzillaGTR", "#NissanSkyline", "#JDMLegends"],
    },
]

SLOT_ANGLES = {
    "morning": {
        "label": "Morning Spotlight",
        "opener": "Morning Spotlight: {name}.",
        "cta": "Swipe to see why the {name} keeps climbing collector watchlists. Full listings and AI Flip Score on ClassicFlips.com.",
    },
    "midday": {
        "label": "Midday Market Check",
        "opener": "Midday Market Check -- {name}.",
        "cta": "Curious what your {name} (or dream {name}) is really worth? Get an instant AI Flip Score at ClassicFlips.com.",
    },
    "evening": {
        "label": "Evening Feature",
        "opener": "Evening Feature: {name}.",
        "cta": "Auction-ready {name} builds are live now on ClassicFlips.com -- list from 38 countries, 4% fee only on sale.",
    },
}


def daterange(start: str, end: str):
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    d = d0
    while d <= d1:
        yield d
        d += timedelta(days=1)


def build_caption(pillar: dict, slot_key: str, post_index: int) -> str:
    angle = SLOT_ANGLES[slot_key]
    fact = pillar["facts"][post_index % len(pillar["facts"])]
    hashtags = " ".join(pillar["hashtags"])
    opener = angle["opener"].format(name=pillar["name"])
    cta = angle["cta"].format(name=pillar["name"])
    hook = pillar["hook"]
    hook_sentence = hook[0].upper() + hook[1:]
    return (
        f"{opener} {hook_sentence}.\n\n"
        f"What makes it a Classic Flips pillar car: {fact}.\n\n"
        f"{cta}\n\n"
        f"{hashtags} #ClassicFlips #CollectorCars"
    )


def main():
    tz = ZoneInfo(TIMEZONE)
    dates = list(daterange(START_DATE, END_DATE))
    posts = []
    post_index = 0

    for day_index, day in enumerate(dates):
        for slot_index, (hour, minute, slot_key) in enumerate(SLOT_TIMES):
            pillar = PILLARS[post_index % len(PILLARS)]
            scheduled_dt = datetime(
                day.year, day.month, day.day, hour, minute, tzinfo=tz
            )
            caption = build_caption(pillar, slot_key, post_index)

            posts.append(
                {
                    "post_id": f"cf-{day.isoformat()}-{slot_key}",
                    "date": day.isoformat(),
                    "slot": slot_key,
                    "scheduled_at_pt": scheduled_dt.isoformat(),
                    "scheduled_at_utc": scheduled_dt.astimezone(ZoneInfo("UTC")).isoformat(),
                    "pillar": pillar["key"],
                    "pillar_name": pillar["name"],
                    "platforms": PLATFORMS,
                    "caption": caption,
                }
            )
            post_index += 1

    assert len(dates) == 90, f"expected 90 days, got {len(dates)}"
    assert len(posts) == 270, f"expected 270 posts, got {len(posts)}"

    payload = {
        "meta": {
            "start_date": START_DATE,
            "end_date": END_DATE,
            "timezone": TIMEZONE,
            "days": len(dates),
            "slots_per_day": len(SLOT_TIMES),
            "total_posts": len(posts),
            "pillars": [p["key"] for p in PILLARS],
            "platforms": PLATFORMS,
            "generated_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        },
        "posts": posts,
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {len(posts)} posts across {len(dates)} days to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
