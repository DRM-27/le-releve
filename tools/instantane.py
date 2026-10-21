"""Faits figés d'un relevé horaire précis (« instantané »), pour les articles d'analyse.

Usage : python tools/instantane.py [data/snapshots/AAAA/MM/JJ/HH.csv]   (par défaut : le dernier relevé)
Écrit facts/AAAA-MM-JJ-HHh.json et .md. Ces faits ne changent plus : un article peut les citer durablement
avec des jetons {{AAAA-MM-JJ-HHh:clé}} ou en mettant « jour: AAAA-MM-JJ-HHh » dans son en-tête.
"""
import glob
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, FACTS, ROOT, TZ, fr_big, fr_date, fr_hour, fr_int, fr_rank, fr_share, iso, load_games, parse_iso,
                    read_csv, utc_now, write_csv)
from facts import GENRES_FR, summary_md

THEMES = {
    "oeufs": (r"\begg|œuf|oeuf|🥚", "Jeux dont le nom évoque les œufs"),
    "halloween": (r"🎃|halloween|hlwn|fright", "Jeux affichant Halloween dans leur nom (🎃, Halloween, HLWN)"),
}
COHORTS = [("avant2020", "Créés avant 2020", None, 2019), ("2020_2024", "Créés entre 2020 et 2024", 2020, 2024),
           ("2025", "Créés en 2025", 2025, 2025), ("2026", "Créés en 2026", 2026, 2026)]


def main(path=None):
    path = Path(path) if path else Path(sorted(glob.glob(str(DATA / "snapshots/*/*/*/*.csv")))[-1])
    rows = read_csv(path)
    ts = parse_iso(rows[0]["ts_utc"])
    local = ts.astimezone(TZ)
    fid = f"{local:%Y-%m-%d}-{local:%H}h"
    games = load_games()
    src = str(path.resolve().relative_to(ROOT)) if str(path.resolve()).startswith(str(ROOT)) else str(path)
    rows.sort(key=lambda r: -int(r["playing"] or 0))
    top = rows[:100]
    line = {r["universe_id"]: i + 2 for i, r in enumerate(rows)}
    tot = sum(int(r["playing"]) for r in top) or 1
    F = {}

    def add(k, v, d, l, s=None):
        F[k] = {"v": v, "d": d, "l": l, "src": s or src}

    def sl(u):
        return f"{src}#L{line[u]}"

    add("jour.date", local.date().isoformat(), fr_date(local.date()), "Jour du relevé (heure de Paris)")
    add("releve.date", local.date().isoformat(), fr_date(local.date(), weekday=False), "Jour du relevé (heure de Paris)")
    add("releve.heure", iso(ts), fr_hour(ts), "Heure du relevé (Paris)")
    add("n.top", 10, "10", "Taille du classement principal")
    add("n.top100", 100, "100", "Taille du classement élargi")
    add("top100.joueurs", tot, fr_int(tot), "Total des joueurs en ligne sur les 100 premiers jeux")
    add("top100.joueurs_arrondi", tot, fr_big(tot), "Total des joueurs en ligne sur les 100 premiers jeux (arrondi)")
    add("concentration.top1", int(top[0]["playing"]) / tot, fr_share(int(top[0]["playing"]) / tot), "Part du n° 1 dans les joueurs du top 100")
    t10 = sum(int(r["playing"]) for r in top[:10])
    add("concentration.top10", t10 / tot, fr_share(t10 / tot), "Part du top 10 dans les joueurs du top 100")

    def gfacts(prefix, i, r, lab):
        u, g = r["universe_id"], games.get(r["universe_id"], {})
        s = sl(u)
        add(f"{prefix}.nom", g.get("name", u), g.get("name", u), f"{lab} : nom", s)
        add(f"{prefix}.rang", i, fr_rank(i), f"{lab} : rang au relevé", s)
        add(f"{prefix}.joueurs", int(r["playing"]), fr_int(int(r["playing"])), f"{lab} : joueurs en ligne au relevé", s)
        add(f"{prefix}.part", int(r["playing"]) / tot, fr_share(int(r["playing"]) / tot), f"{lab} : part des joueurs du top 100", s)
        if r.get("visits"):
            add(f"{prefix}.visites", int(r["visits"]), fr_big(int(r["visits"])), f"{lab} : visites cumulées", s)
        if g.get("created"):
            c = date.fromisoformat(g["created"][:10])
            add(f"{prefix}.cree", c.isoformat(), fr_date(c, weekday=False), f"{lab} : date de création (Roblox)", "data/games.csv")
            add(f"{prefix}.annee", c.year, str(c.year), f"{lab} : année de création", "data/games.csv")
            add(f"{prefix}.age_jours", (local.date() - c).days, fr_int((local.date() - c).days), f"{lab} : âge en jours au relevé", "data/games.csv")
            add(f"{prefix}.age_ans", (local.date() - c).days // 365, fr_int((local.date() - c).days // 365), f"{lab} : âge en années révolues", "data/games.csv")
        if g.get("genre_l1"):
            add(f"{prefix}.genre", g["genre_l1"], GENRES_FR.get(g["genre_l1"], g["genre_l1"]), f"{lab} : genre", "data/games.csv")
        if g.get("creator_name"):
            add(f"{prefix}.createur", g["creator_name"], g["creator_name"], f"{lab} : créateur", "data/games.csv")

    for i, r in enumerate(top, 1):
        if i <= 10:
            gfacts(f"top.{i}", i, r, f"N° {i} au relevé")
        gfacts(f"g.{r['universe_id']}", i, r, games.get(r["universe_id"], {}).get("name", r["universe_id"]))

    graphs = {"top10": {"titre": f"Joueurs en ligne, top 10 au relevé de {fr_hour(ts)}", "unite": "joueurs",
                        "rows": [{"nom": games.get(r["universe_id"], {}).get("name", ""), "valeur": int(r["playing"])} for r in top[:10]]}}

    # thèmes
    for key, (pat, lab) in THEMES.items():
        m = [(i, r) for i, r in enumerate(top, 1) if re.search(pat, games.get(r["universe_id"], {}).get("name", ""), re.I)]
        j = sum(int(r["playing"]) for _, r in m)
        add(f"theme.{key}.nb", len(m), fr_int(len(m)), f"{lab} : nombre dans le top 100")
        add(f"theme.{key}.joueurs", j, fr_int(j), f"{lab} : joueurs en ligne cumulés")
        add(f"theme.{key}.part", j / tot, fr_share(j / tot), f"{lab} : part des joueurs du top 100")
        for k, (i, r) in enumerate(m[:8], 1):
            gfacts(f"theme.{key}.{k}", i, r, f"{lab}, n° {k}")
        graphs[key] = {"titre": f"{lab} : joueurs en ligne au relevé de {fr_hour(ts)}", "unite": "joueurs",
                       "rows": [{"nom": games.get(r["universe_id"], {}).get("name", ""), "valeur": int(r["playing"])} for _, r in m[:12]]}

    # âge des jeux
    years = {}
    for i, r in enumerate(top, 1):
        c = games.get(r["universe_id"], {}).get("created", "")[:4]
        if c.isdigit():
            years.setdefault(int(c), []).append(int(r["playing"]))
    cohort_rows = []
    for key, lab, lo, hi in COHORTS:
        vals = [v for y, vs in years.items() for v in vs if (lo is None or y >= lo) and y <= hi]
        add(f"age.{key}.nb", len(vals), fr_int(len(vals)), f"{lab} : nombre de jeux dans le top 100")
        add(f"age.{key}.part", sum(vals) / tot, fr_share(sum(vals) / tot), f"{lab} : part des joueurs du top 100")
        cohort_rows.append({"nom": lab, "valeur": round(sum(vals) / tot, 4)})
    recent = [(i, r) for i, r in enumerate(top, 1) if games.get(r["universe_id"], {}).get("created")
              and (local.date() - date.fromisoformat(games[r["universe_id"]]["created"][:10])).days <= 90]
    add("age.recents90.nb", len(recent), fr_int(len(recent)), "Jeux du top 100 créés il y a 90 jours ou moins")
    add("age.recents90.part", sum(int(r["playing"]) for _, r in recent) / tot, fr_share(sum(int(r["playing"]) for _, r in recent) / tot),
        "Part des joueurs du top 100 sur ces jeux récents")
    add("n.jours90", 90, "90", "Seuil des jeux récents (jours)")
    oldest = sorted([(games[r["universe_id"]]["created"], i, r) for i, r in enumerate(top, 1) if games.get(r["universe_id"], {}).get("created")])
    for k, (_, i, r) in enumerate(oldest[:5], 1):
        gfacts(f"doyen.{k}", i, r, f"Doyen n° {k} du top 100")
    graphs["cohortes"] = {"titre": "Part des joueurs du top 100 selon l’année de création du jeu", "unite": "%", "rows": cohort_rows}

    # genres
    by = Counter()
    cnt = Counter()
    for r in top:
        gk = games.get(r["universe_id"], {}).get("genre_l1", "")
        by[gk] += int(r["playing"])
        cnt[gk] += 1
    for k, (gk, v) in enumerate(by.most_common(5), 1):
        add(f"genre.{k}.nom", gk, GENRES_FR.get(gk, gk), f"Genre n° {k} du top 100 (en joueurs)")
        add(f"genre.{k}.part", v / tot, fr_share(v / tot), f"Genre n° {k} : part des joueurs du top 100")
        add(f"genre.{k}.jeux", cnt[gk], fr_int(cnt[gk]), f"Genre n° {k} : nombre de jeux dans le top 100")
    graphs["genres"] = {"titre": "Part des joueurs du top 100 par genre", "unite": "%",
                        "rows": [{"nom": GENRES_FR.get(gk, gk), "valeur": round(v / tot, 4)} for gk, v in by.most_common(8)]}

    for gid, g in graphs.items():
        p = FACTS / "graphiques" / fid / f"{gid}.csv"
        write_csv(p, ["nom", "valeur"], g["rows"])
        g["csv"] = f"facts/graphiques/{fid}/{gid}.csv"
    out = {"jour": fid, "genere": iso(utc_now()), "couverture": {"releves": 1, "attendus": 1, "instantane": True},
           "source_jour": src, "faits": F, "graphiques": graphs}
    (FACTS / f"{fid}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (FACTS / f"{fid}.md").write_text(summary_md(out).replace("Relevés : 1 sur 1.", f"Instantané du relevé de {fr_hour(ts)}."), encoding="utf-8")
    print(fid, len(F), "faits")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
