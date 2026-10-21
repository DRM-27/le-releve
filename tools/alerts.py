"""Détecte les mouvements forts d'une heure à l'autre et les archive dans data/alertes.csv.

Lancé après chaque relevé. Seuils volontairement prudents pour éviter le bruit :
  - forte hausse : au moins 2 000 joueurs maintenant et +50 % ou plus par rapport au relevé précédent ;
  - entrée dans le top 10 : dans le top 10 maintenant, hors du top 20 au relevé précédent.
Un même jeu ne déclenche pas deux fois la même alerte en moins de 6 heures.
"""
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, iso, load_games, parse_iso, read_csv, snap_path, utc_now, write_csv

FIELDS = ["ts_utc", "type", "universe_id", "nom", "avant", "maintenant", "variation", "rang", "rang_avant", "releve"]
MIN_PLAYERS = 2000
MIN_RISE = 0.5
COOLDOWN = timedelta(hours=6)


def last_two():
    now = utc_now().replace(minute=0, second=0)
    found = []
    for k in range(0, 6):
        p = snap_path("snapshots", now - timedelta(hours=k))
        rows = read_csv(p)
        if rows:
            found.append((parse_iso(rows[0]["ts_utc"]), {r["universe_id"]: r for r in rows}, p))
        if len(found) == 2:
            break
    return found


def main():
    pair = last_two()
    if len(pair) < 2:
        print("Pas assez de relevés pour comparer.")
        return
    (t1, cur, p1), (t0, prev, _) = pair
    gap = (t1 - t0).total_seconds()
    if not 1800 <= gap <= 3 * 3600:
        print(f"Écart entre relevés hors limites ({gap / 60:.0f} min) : pas d'alerte.")
        return
    games = load_games()
    rank_now = {u: i + 1 for i, u in enumerate(sorted(cur, key=lambda u: -int(cur[u]["playing"] or 0)))}
    rank_prev = {u: i + 1 for i, u in enumerate(sorted(prev, key=lambda u: -int(prev[u]["playing"] or 0)))}
    path = DATA / "alertes.csv"
    hist = read_csv(path)
    recent = {(r["type"], r["universe_id"]): parse_iso(r["ts_utc"]) for r in hist}
    new = []
    for u, r in cur.items():
        now_p = int(r["playing"] or 0)
        if u not in prev:
            continue
        before = int(prev[u]["playing"] or 0)
        cands = []
        if now_p >= MIN_PLAYERS and before > 0 and now_p / before - 1 >= MIN_RISE:
            cands.append("forte_hausse")
        if rank_now[u] <= 10 and rank_prev.get(u, 999) > 20:
            cands.append("entree_top10")
        for typ in cands:
            last = recent.get((typ, u))
            if last and t1 - last < COOLDOWN:
                continue
            new.append({"ts_utc": iso(t1), "type": typ, "universe_id": u, "nom": games.get(u, {}).get("name", u),
                        "avant": before, "maintenant": now_p, "variation": round(now_p / before - 1, 4) if before else "",
                        "rang": rank_now[u], "rang_avant": rank_prev.get(u, ""),
                        "releve": str(p1.relative_to(DATA.parent)) if str(p1).startswith(str(DATA.parent)) else ""})
    if new:
        write_csv(path, FIELDS, hist + new)
    print(f"{len(new)} alerte(s).")


if __name__ == "__main__":
    main()
