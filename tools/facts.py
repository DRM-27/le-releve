"""Calcule les faits d'une journée (heure de Paris) à partir des relevés horaires.

Seul ce script produit des chiffres. Les articles ne font que les citer avec des jetons {{clé}}.

Usage : python tools/facts.py [AAAA-MM-JJ]   (par défaut : hier)
Écrit :
  data/jours/AAAA-MM-JJ.csv         une ligne par jeu (pic, moyenne, variations…) : la source citée par les articles
  facts/AAAA-MM-JJ.json             tous les faits, avec valeur, affichage, libellé et source
  facts/AAAA-MM-JJ.md               la liste lisible des jetons, pour la rédaction
"""
import json
import sys
from datetime import date, timedelta
from statistics import mean

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import (CONFIG, DATA, FACTS, NNBSP, TZ, fr_big, fr_date, fr_hour, fr_int, fr_pct, fr_rank, fr_share,
                    github_blob, hours_of_day, iso, load_day_snapshots, load_games, parse_iso, read_csv, utc_now,
                    write_csv)

MIN_COVER = 18          # relevés horaires minimum pour qu'une journée serve de référence
MIN_PRESENCE = 0.5      # un jeu doit être présent dans la moitié des relevés du jour pour être classé
GENRES_FR = {"Action": "Action", "Adventure": "Aventure", "Simulation": "Simulation", "Roleplay & Avatar Sim": "Jeu de rôle et avatar",
             "Obby & Platformer": "Obby et plateforme", "Survival": "Survie", "Sports & Racing": "Sport et course",
             "Shooter": "Tir", "Party & Casual": "Party games", "RPG": "RPG", "Strategy": "Stratégie", "Puzzle": "Réflexion",
             "Social": "Social", "Entertainment": "Divertissement", "Shopping": "Shopping", "Education": "Éducation",
             "Utility & Other": "Utilitaires et autres", "": "Non classé"}


def day_stats(d):
    """Statistiques par jeu pour une journée. Retourne (stats, nb_relevés, relevés)."""
    snaps = load_day_snapshots(d)
    stats = {}
    for ts, rows in snaps:
        for uid, r in rows.items():
            s = stats.setdefault(uid, {"vals": [], "first": None, "last": None})
            s["vals"].append((ts, int(r["playing"] or 0)))
            s["first"] = s["first"] or r
            s["last"] = r
    n = len(snaps)
    for uid, s in stats.items():
        vals = [v for _, v in s["vals"]]
        s["n"] = len(vals)
        s["peak"] = max(vals)
        s["peak_ts"] = max(s["vals"], key=lambda x: x[1])[0]
        s["avg"] = mean(vals)
        s["ok"] = n > 0 and len(vals) >= MIN_PRESENCE * n
    return stats, n, snaps


def build(d):
    games = load_games()
    today, n, snaps = day_stats(d)
    if n == 0:
        raise SystemExit(f"Aucun relevé pour le {d}.")
    prev, n_prev, prev_snaps = day_stats(d - timedelta(days=1))
    week = []
    for k in range(1, 8):
        st, nk, _ = day_stats(d - timedelta(days=k))
        if nk >= MIN_COVER:
            week.append(st)

    jour_csv = f"data/jours/{d.isoformat()}.csv"
    snaps_dir = f"data/snapshots/{d:%Y}/{d:%m}"
    F = {}

    def add(key, v, disp, label, src=jour_csv):
        F[key] = {"v": v, "d": disp, "l": label, "src": src}

    # --- tableau par jeu ---
    ranked = sorted([u for u, s in today.items() if s["ok"]], key=lambda u: -today[u]["peak"])
    rank_of = {u: i + 1 for i, u in enumerate(ranked)}
    prev_ranked = sorted([u for u, s in prev.items() if s["ok"]], key=lambda u: -prev[u]["peak"]) if n_prev >= MIN_COVER else []
    prev_rank = {u: i + 1 for i, u in enumerate(prev_ranked)}

    rows = []
    for u in ranked:
        s, g = today[u], games.get(u, {})
        row = {"rang": rank_of[u], "universe_id": u, "nom": g.get("name", u), "createur": g.get("creator_name", ""),
               "genre": g.get("genre_l1", ""), "pic": s["peak"], "heure_pic_paris": s["peak_ts"].astimezone(TZ).strftime("%H:%M"),
               "moyenne": round(s["avg"]), "releves": s["n"]}
        if n_prev >= MIN_COVER and u in prev and prev[u]["ok"] and prev[u]["avg"] > 0:
            row["moyenne_veille"] = round(prev[u]["avg"])
            row["var_veille"] = round(s["avg"] / prev[u]["avg"] - 1, 4)
        base = [w[u]["avg"] for w in week if u in w and w[u]["ok"]]
        if len(week) >= 5 and len(base) >= 5:
            row["moyenne_7j_avant"] = round(mean(base))
            row["var_7j"] = round(s["avg"] / mean(base) - 1, 4)
        # visites sur 24 h : dernier relevé du jour moins dernier relevé de la veille (écart de 23 à 25 h)
        if u in prev and prev[u]["last"] and s["last"]:
            t0, t1 = parse_iso(prev[u]["last"]["ts_utc"]), parse_iso(s["last"]["ts_utc"])
            if 23 * 3600 <= (t1 - t0).total_seconds() <= 25 * 3600 and s["last"]["visits"] and prev[u]["last"]["visits"]:
                row["visites_24h"] = int(s["last"]["visits"]) - int(prev[u]["last"]["visits"])
        up, down = s["last"].get("up_votes"), s["last"].get("down_votes")
        if up and down and int(up) + int(down) >= 100:
            row["note"] = round(int(up) / (int(up) + int(down)), 4)
        if s["last"].get("visits"):
            row["visites_total"] = int(s["last"]["visits"])
        row["rang_veille"] = prev_rank.get(u, "")
        rows.append(row)
    fields = ["rang", "universe_id", "nom", "createur", "genre", "pic", "heure_pic_paris", "moyenne", "releves", "moyenne_veille",
              "var_veille", "moyenne_7j_avant", "var_7j", "visites_24h", "visites_total", "note", "rang_veille"]
    write_csv(DATA / "jours" / f"{d.isoformat()}.csv", fields, rows)
    line = {r["universe_id"]: i + 2 for i, r in enumerate(rows)}  # n° de ligne dans le CSV (en-tête = 1)

    def src_line(u):
        return f"{jour_csv}#L{line[u]}"

    # --- faits généraux ---
    add("jour.date", d.isoformat(), fr_date(d), "Jour étudié (heure de Paris)")
    add("jour.date_courte", d.isoformat(), fr_date(d, weekday=False), "Jour étudié")
    add("releves.nb", n, fr_int(n), "Relevés horaires disponibles ce jour-là", snaps_dir)
    add("releves.attendus", 24, "24", "Relevés horaires attendus par jour", snaps_dir)
    add("jeux.nb", len(ranked), fr_int(len(ranked)), "Jeux suivis et classés ce jour-là")
    add("n.top", 10, "10", "Taille du classement principal")
    add("n.top100", 100, "100", "Taille du classement élargi")

    # total des joueurs sur les jeux suivis, relevé par relevé
    totals = [(ts, sum(int(r["playing"] or 0) for r in rows_.values())) for ts, rows_ in snaps]
    tpk = max(totals, key=lambda x: x[1])
    add("cumul.pic", tpk[1], fr_int(tpk[1]), "Total des joueurs en ligne sur les jeux suivis, au relevé le plus haut", snaps_dir)
    add("cumul.pic_heure", iso(tpk[0]), fr_hour(tpk[0]), "Heure (Paris) de ce relevé", snaps_dir)
    add("cumul.moy", round(mean(v for _, v in totals)), fr_int(mean(v for _, v in totals)),
        "Total moyen des joueurs en ligne sur les jeux suivis", snaps_dir)

    def game_facts(prefix, u, label_prefix):
        r = rows[rank_of[u] - 1]
        src = src_line(u)
        add(f"{prefix}.nom", r["nom"], r["nom"], f"{label_prefix} : nom", src)
        add(f"{prefix}.rang", r["rang"], fr_rank(r["rang"]), f"{label_prefix} : rang au pic du jour", src)
        add(f"{prefix}.pic", r["pic"], fr_int(r["pic"]), f"{label_prefix} : pic de joueurs simultanés relevé", src)
        add(f"{prefix}.heure_pic", r["heure_pic_paris"], fr_hour(today[u]["peak_ts"]),
            f"{label_prefix} : heure (Paris) du pic relevé", src)
        add(f"{prefix}.moy", r["moyenne"], fr_int(r["moyenne"]), f"{label_prefix} : moyenne des joueurs simultanés sur la journée", src)
        if r["createur"]:
            add(f"{prefix}.createur", r["createur"], r["createur"], f"{label_prefix} : créateur", src)
        if r["genre"]:
            add(f"{prefix}.genre", r["genre"], GENRES_FR.get(r["genre"], r["genre"]), f"{label_prefix} : genre", src)
        if "var_veille" in r:
            add(f"{prefix}.var_veille", r["var_veille"], fr_pct(r["var_veille"]), f"{label_prefix} : variation de la moyenne par rapport à la veille", src)
            add(f"{prefix}.moy_veille", r["moyenne_veille"], fr_int(r["moyenne_veille"]), f"{label_prefix} : moyenne de la veille", src)
        if "var_7j" in r:
            add(f"{prefix}.var_7j", r["var_7j"], fr_pct(r["var_7j"]), f"{label_prefix} : variation de la moyenne par rapport aux 7 jours précédents", src)
            add(f"{prefix}.moy_7j", r["moyenne_7j_avant"], fr_int(r["moyenne_7j_avant"]), f"{label_prefix} : moyenne des 7 jours précédents", src)
        if "visites_24h" in r:
            add(f"{prefix}.visites_24h", r["visites_24h"], fr_big(r["visites_24h"]), f"{label_prefix} : visites gagnées en 24 h", src)
        if "visites_total" in r:
            add(f"{prefix}.visites_total", r["visites_total"], fr_big(r["visites_total"]), f"{label_prefix} : visites cumulées depuis la création", src)
        if "note" in r:
            add(f"{prefix}.note", r["note"], fr_share(r["note"]), f"{label_prefix} : part de votes positifs", src)
        if r["rang_veille"]:
            add(f"{prefix}.rang_veille", r["rang_veille"], fr_rank(r["rang_veille"]), f"{label_prefix} : rang la veille", src)

    for i, u in enumerate(ranked[:10], 1):
        game_facts(f"top.{i}", u, f"N° {i} du jour")
    for u in ranked[:100]:
        game_facts(f"g.{u}", u, games.get(u, {}).get("name", u))

    # --- hausses et baisses (jeux assez joués pour que la variation ait un sens) ---
    min_avg = CONFIG.get("tracking", {}).get("moversMinAvg", 1000)
    key = "var_7j" if any("var_7j" in r for r in rows) else ("var_veille" if any("var_veille" in r for r in rows) else None)
    movers = {"up": [], "down": []}
    if key:
        base_key = "moyenne_7j_avant" if key == "var_7j" else "moyenne_veille"
        add("mouv.reference", key, "les 7 jours précédents" if key == "var_7j" else "la veille", "Période de comparaison des hausses et baisses")
        add("mouv.seuil", min_avg, fr_int(min_avg), "Moyenne minimale de joueurs pour figurer dans les hausses et baisses")
        cand = [r for r in rows if key in r and max(r["moyenne"], r[base_key]) >= min_avg]
        ups = sorted([r for r in cand if r[key] > 0], key=lambda r: -r[key])[:5]
        downs = sorted([r for r in cand if r[key] < 0], key=lambda r: r[key])[:5]
        for name, lst in (("hausse", ups), ("baisse", downs)):
            for i, r in enumerate(lst, 1):
                src = src_line(r["universe_id"])
                lab = f"{'Hausse' if name == 'hausse' else 'Baisse'} n° {i}"
                add(f"{name}.{i}.nom", r["nom"], r["nom"], f"{lab} : nom", src)
                add(f"{name}.{i}.var", r[key], fr_pct(r[key]), f"{lab} : variation de la moyenne de joueurs", src)
                add(f"{name}.{i}.moy", r["moyenne"], fr_int(r["moyenne"]), f"{lab} : moyenne du jour", src)
                add(f"{name}.{i}.moy_avant", r[base_key], fr_int(r[base_key]), f"{lab} : moyenne de référence", src)
                add(f"{name}.{i}.rang", r["rang"], fr_rank(r["rang"]), f"{lab} : rang au pic du jour", src)
            movers["up" if name == "hausse" else "down"] = lst

    # --- entrées dans le top 50 ---
    if prev_ranked:
        top50_prev = set(prev_ranked[:50])
        entrants = [u for u in ranked[:50] if u not in top50_prev]
        add("entrees.nb", len(entrants), fr_int(len(entrants)), "Jeux entrés dans le top 50 par rapport à la veille")
        for i, u in enumerate(entrants[:5], 1):
            r = rows[rank_of[u] - 1]
            add(f"entree.{i}.nom", r["nom"], r["nom"], f"Entrée n° {i} : nom", src_line(u))
            add(f"entree.{i}.rang", r["rang"], fr_rank(r["rang"]), f"Entrée n° {i} : rang", src_line(u))
            add(f"entree.{i}.pic", r["pic"], fr_int(r["pic"]), f"Entrée n° {i} : pic", src_line(u))

    # --- concentration et genres (top 100) ---
    top100 = rows[:100]
    tot100 = sum(r["moyenne"] for r in top100) or 1
    add("concentration.top10", sum(r["moyenne"] for r in top100[:10]) / tot100,
        fr_share(sum(r["moyenne"] for r in top100[:10]) / tot100), "Part du top 10 dans les joueurs moyens du top 100")
    add("concentration.top1", top100[0]["moyenne"] / tot100, fr_share(top100[0]["moyenne"] / tot100),
        "Part du n° 1 dans les joueurs moyens du top 100")
    by_genre = {}
    for r in top100:
        gk = r["genre"] or ""
        by_genre.setdefault(gk, [0, 0])
        by_genre[gk][0] += r["moyenne"]
        by_genre[gk][1] += 1
    genres = sorted(by_genre.items(), key=lambda kv: -kv[1][0])
    for i, (gk, (tot, cnt)) in enumerate(genres[:5], 1):
        add(f"genre.{i}.nom", gk, GENRES_FR.get(gk, gk), f"Genre n° {i} du top 100 (en joueurs moyens)")
        add(f"genre.{i}.part", tot / tot100, fr_share(tot / tot100), f"Genre n° {i} : part des joueurs moyens du top 100")
        add(f"genre.{i}.jeux", cnt, fr_int(cnt), f"Genre n° {i} : nombre de jeux dans le top 100")

    # --- jeux récents (créés il y a moins de 90 jours) dans le top 100 ---
    recent = []
    for r in top100:
        c = games.get(r["universe_id"], {}).get("created", "")
        if c:
            try:
                created = date.fromisoformat(c[:10])
            except ValueError:
                continue
            if (d - created).days <= 90:
                recent.append((r, created))
    add("recents.nb", len(recent), fr_int(len(recent)), "Jeux du top 100 créés il y a 90 jours ou moins")
    add("n.recents_jours", 90, "90", "Seuil d'ancienneté des jeux récents (jours)")
    if recent:
        r, created = recent[0]
        src = src_line(r["universe_id"])
        add("recent.1.nom", r["nom"], r["nom"], "Jeu récent le mieux classé : nom", src)
        add("recent.1.rang", r["rang"], fr_rank(r["rang"]), "Jeu récent le mieux classé : rang", src)
        add("recent.1.cree", created.isoformat(), fr_date(created, weekday=False), "Jeu récent le mieux classé : date de création", src)

    # --- données des graphiques ---
    graphs = {}
    graphs["top10"] = {"titre": "Pic de joueurs simultanés relevé, top 10", "unite": "joueurs",
                       "rows": [{"nom": r["nom"], "valeur": r["pic"]} for r in top100[:10]]}
    if movers["up"] or movers["down"]:
        graphs["variations"] = {"titre": "Plus fortes hausses et baisses de la moyenne de joueurs", "unite": "%",
                                "reference": F["mouv.reference"]["d"],
                                "rows": [{"nom": r["nom"], "valeur": r[key]} for r in movers["up"] + movers["down"][::-1]]}
    # courbes horaires sur 7 jours : total des jeux suivis et n° 1
    series_total, series_top = [], []
    lead = ranked[0]
    for k in range(6, -1, -1):
        dk = d - timedelta(days=k)
        for ts, rows_ in load_day_snapshots(dk):
            series_total.append([iso(ts), sum(int(r["playing"] or 0) for r in rows_.values())])
            if lead in rows_:
                series_top.append([iso(ts), int(rows_[lead]["playing"] or 0)])
    graphs["cumul"] = {"titre": "Total des joueurs en ligne sur les jeux suivis, relevés horaires", "unite": "joueurs", "points": series_total,
                       "note": "Le nombre de jeux suivis varie d'un jour à l'autre : ce total n'est pas le nombre de joueurs de toute la plateforme."}
    graphs["courbe-top1"] = {"titre": f"{rows[0]['nom']} : joueurs en ligne, relevés horaires", "unite": "joueurs", "points": series_top}
    for gid, g in graphs.items():
        path = FACTS / "graphiques" / d.isoformat() / f"{gid}.csv"
        if "rows" in g:
            write_csv(path, ["nom", "valeur"], g["rows"])
        else:
            write_csv(path, ["heure_utc", "valeur"], [{"heure_utc": a, "valeur": b} for a, b in g["points"]])
        g["csv"] = f"facts/graphiques/{d.isoformat()}/{gid}.csv"

    out = {"jour": d.isoformat(), "genere": iso(utc_now()), "couverture": {"releves": n, "attendus": len(list(hours_of_day(d)))},
           "source_jour": jour_csv, "source_releves": snaps_dir, "faits": F, "graphiques": graphs}
    FACTS.mkdir(parents=True, exist_ok=True)
    (FACTS / f"{d.isoformat()}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (FACTS / f"{d.isoformat()}.md").write_text(summary_md(out), encoding="utf-8")
    return out


def summary_md(out):
    """Liste lisible des jetons, pour la rédaction. Les jeux g.<id> sont regroupés en tableau."""
    F = out["faits"]
    lines = [f"# Faits du {F['jour.date']['d']}", "",
             f"Relevés : {out['couverture']['releves']} sur {out['couverture']['attendus']}. Source : `{out['source_jour']}`.", "",
             "Écris chaque chiffre avec son jeton, par exemple `{{top.1.pic}}`. Aucun chiffre tapé à la main.", "",
             "| Jeton | Affichage | Signification |", "|---|---|---|"]
    for k, f in F.items():
        if not k.startswith("g."):
            lines.append(f"| `{{{{{k}}}}}` | {f['d']} | {f['l']} |")
    lines += ["", "## Top 100 : jetons par jeu", "Préfixe `g.<id>` puis : nom, rang, pic, moy, var_veille, var_7j, visites_24h, note, genre, createur.", "",
              "| Rang | Jeu | Préfixe |", "|---|---|---|"]
    seen = set()
    for k, f in F.items():
        if k.startswith("g.") and k.endswith(".nom"):
            p = k[:-4]
            if p not in seen:
                seen.add(p)
                lines.append(f"| {F[p + '.rang']['d']} | {f['d']} | `{p}` |")
    lines += ["", "## Graphiques disponibles", ""] + [f"- `{{{{graphique:{gid}}}}}` : {g['titre']}" for gid, g in out["graphiques"].items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else (utc_now().astimezone(TZ).date() - timedelta(days=1))
    o = build(d)
    print(f"{d} : {len(o['faits'])} faits, {o['couverture']['releves']}/{o['couverture']['attendus']} relevés")
