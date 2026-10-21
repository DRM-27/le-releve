"""Faits de la semaine (lundi → dimanche, heure de Paris), à partir des tableaux quotidiens data/jours/.

Lancé à chaque passage : il calcule la dernière semaine complète si ses 7 jours existent et si le fichier n'existe pas encore.
Écrit facts/AAAA-MM-JJ-sem.json (date du dimanche). Les articles l'appellent avec {{AAAA-MM-JJ-sem:clé}} ou « jour: AAAA-MM-JJ-sem ».
"""
import json
import sys
from datetime import timedelta
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, FACTS, TZ, fr_date, fr_int, fr_pct, fr_rank, iso, read_csv, utc_now, write_csv


def main():
    today = utc_now().astimezone(TZ).date()
    sunday = today - timedelta(days=today.weekday() + 1)
    days = [sunday - timedelta(days=k) for k in range(6, -1, -1)]
    prev = [d - timedelta(days=7) for d in days]
    fid = f"{sunday.isoformat()}-sem"
    out = FACTS / f"{fid}.json"
    if out.exists():
        print("Semaine déjà calculée.")
        return
    tables = [read_csv(DATA / "jours" / f"{d.isoformat()}.csv") for d in days]
    if not all(tables):
        print("Semaine incomplète : pas de faits hebdomadaires.")
        return
    ptables = [read_csv(DATA / "jours" / f"{d.isoformat()}.csv") for d in prev]
    agg, pagg, names = {}, {}, {}
    for t in tables:
        for r in t:
            agg.setdefault(r["universe_id"], []).append(int(r["moyenne"]))
            names[r["universe_id"]] = r["nom"]
    for t in ptables:
        for r in t:
            pagg.setdefault(r["universe_id"], []).append(int(r["moyenne"]))
    week = {u: mean(v) for u, v in agg.items() if len(v) >= 5}
    ranked = sorted(week, key=lambda u: -week[u])
    src = f"data/jours/{sunday.isoformat()}.csv"
    F = {}

    def add(k, v, d, l):
        F[k] = {"v": v, "d": d, "l": l, "src": src}

    add("semaine.debut", days[0].isoformat(), fr_date(days[0], weekday=False), "Premier jour de la semaine")
    add("semaine.fin", sunday.isoformat(), fr_date(sunday, weekday=False), "Dernier jour de la semaine")
    add("n.top", 10, "10", "Taille du classement")
    rows = []
    for i, u in enumerate(ranked[:100], 1):
        p = mean(pagg[u]) if len(pagg.get(u, [])) >= 5 else None
        rows.append({"rang": i, "universe_id": u, "nom": names[u], "moyenne_semaine": round(week[u]),
                     "moyenne_semaine_precedente": round(p) if p else "", "variation": round(week[u] / p - 1, 4) if p else ""})
        if i <= 10:
            add(f"top.{i}.nom", names[u], names[u], f"N° {i} de la semaine : nom")
            add(f"top.{i}.moy", round(week[u]), fr_int(week[u]), f"N° {i} de la semaine : moyenne de joueurs")
            if p:
                add(f"top.{i}.var", week[u] / p - 1, fr_pct(week[u] / p - 1), f"N° {i} : variation par rapport à la semaine précédente")
    movers = [r for r in rows if r["variation"] != "" and max(r["moyenne_semaine"], r["moyenne_semaine_precedente"] or 0) >= 1000]
    for name, lst in (("hausse", sorted(movers, key=lambda r: -r["variation"])[:5]), ("baisse", sorted(movers, key=lambda r: r["variation"])[:5])):
        for i, r in enumerate(lst, 1):
            add(f"{name}.{i}.nom", r["nom"], r["nom"], f"{name.capitalize()} n° {i} : nom")
            add(f"{name}.{i}.var", r["variation"], fr_pct(r["variation"]), f"{name.capitalize()} n° {i} : variation hebdomadaire")
            add(f"{name}.{i}.moy", r["moyenne_semaine"], fr_int(r["moyenne_semaine"]), f"{name.capitalize()} n° {i} : moyenne de la semaine")
    write_csv(DATA / "semaines" / f"{sunday.isoformat()}.csv", list(rows[0].keys()), rows)
    for k in F:
        F[k]["src"] = f"data/semaines/{sunday.isoformat()}.csv"
    out.write_text(json.dumps({"jour": fid, "genere": iso(utc_now()), "couverture": {"releves": 7, "attendus": 7, "instantane": True},
                               "faits": F, "graphiques": {"top10": {"titre": "Moyenne de joueurs de la semaine, top 10", "unite": "joueurs",
                               "rows": [{"nom": r["nom"], "valeur": r["moyenne_semaine"]} for r in rows[:10]], "csv": f"data/semaines/{sunday.isoformat()}.csv"}}},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(fid, len(F), "faits")


if __name__ == "__main__":
    main()
