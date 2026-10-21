"""Données FICTIVES pour tester la chaîne en local. Ne jamais écrire dans data/ : utiliser MEDIA_DATA_DIR."""
import math
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

assert os.environ.get("MEDIA_DATA_DIR"), "MEDIA_DATA_DIR doit pointer vers un dossier de test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from common import DATA, GAME_FIELDS, SNAP_FIELDS, SORT_FIELDS, TZ, UTC, iso, snap_path, write_csv  # noqa

random.seed(7)
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 9
GENRES = [("Action", "Combat"), ("Simulation", "Incremental Simulator"), ("Roleplay & Avatar Sim", "Life"),
          ("Obby & Platformer", "Classic Obby"), ("Survival", "Horror"), ("Adventure", "Action RPG"),
          ("Sports & Racing", "Racing"), ("Shooter", "Battlegrounds"), ("Party & Casual", "Minigame")]
syl = ["Blox", "Pet", "Tower", "Brain", "Garden", "Rival", "Doors", "Fruit", "Steal", "Grow", "Murder", "Mystery",
       "Tycoon", "Rush", "Island", "Sim", "Legends", "Arena", "Ninja", "Forest"]
games = []
for i in range(300):
    base = 400_000 * (i + 1) ** -1.25 + random.uniform(50, 400)
    trend = random.choice([0] * 8 + [0.12, -0.10, 0.25, -0.2])
    g1, g2 = random.choice(GENRES)
    games.append({"universe_id": str(1_000_000 + i * 7919), "root_place_id": str(9_000_000 + i * 104729),
                  "name": f"FICTIF {random.choice(syl)} {random.choice(syl)} {i}", "creator_name": f"Studio Test {i % 40}",
                  "creator_type": "Group", "creator_verified": int(i < 60), "genre_l1": g1, "genre_l2": g2,
                  "created": "2023-05-01T00:00:00Z", "updated": "2026-10-01T00:00:00Z", "max_players": 12,
                  "first_seen": "", "last_in_sort": "", "_base": base, "_trend": trend,
                  "_visits": base * 30000, "_fav": base * 900, "_up": base * 40, "_down": base * 8})

now = datetime.now(UTC).replace(minute=7, second=0, microsecond=0)
start = now - timedelta(days=DAYS)
t = start
while t <= now:
    day_index = (t - start).total_seconds() / 86400
    local = t.astimezone(TZ)
    cycle = 0.55 + 0.45 * math.sin((local.hour - 14) / 24 * 2 * math.pi) ** 2 * (1 if 12 <= local.hour <= 23 else 0.5)
    weekend = 1.25 if local.weekday() >= 5 else 1.0
    ts = iso(t)
    rows = []
    for g in games:
        playing = g["_base"] * cycle * weekend * (1 + g["_trend"]) ** day_index * random.uniform(0.93, 1.07)
        g["_visits"] += playing * 0.9
        g["_fav"] += playing * 0.004
        g["_up"] += playing * 0.0009
        g["_down"] += playing * 0.0002
        rows.append({"ts_utc": ts, "universe_id": g["universe_id"], "playing": int(playing), "visits": int(g["_visits"]),
                     "favorites": int(g["_fav"]), "up_votes": int(g["_up"]), "down_votes": int(g["_down"])})
        if not g["first_seen"]:
            g["first_seen"] = ts
        g["last_in_sort"] = ts
    rows.sort(key=lambda r: -r["playing"])
    if random.random() > 0.03:  # quelques relevés manquants, comme en vrai
        write_csv(snap_path("snapshots", t), SNAP_FIELDS, rows)
        write_csv(snap_path("sorts", t), SORT_FIELDS,
                  [{"ts_utc": ts, "sort_id": "top-playing-now", "position": k + 1, "universe_id": r["universe_id"],
                    "player_count": r["playing"], "is_sponsored": 0} for k, r in enumerate(rows[:100])])
    t += timedelta(hours=1)

write_csv(DATA / "games.csv", GAME_FIELDS, games)
print("fictif:", DATA, DAYS, "jours")
