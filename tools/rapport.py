"""Rapport mensuel « État de Roblox » en PDF.

Usage : python tools/rapport.py [--mois AAAA-MM] [--out dossier]
Par défaut : le mois du dernier relevé. Écrit <out>/etat-de-roblox-AAAA-MM.pdf (et le .html source).

Chaque chiffre du rapport est calculé ici à partir des fichiers du dépôt (relevés horaires, games.csv,
game passes, faits officiels et externes) et renvoie, par un lien, au fichier ou à la page d'où il vient.
Les sections « du mois » (heures de pointe, record, progressions) n'apparaissent qu'avec au moins 7 jours de relevés.
"""
import argparse
import base64
import glob
import html
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CONFIG, DATA, FACTS, ROOT, TZ, fr_big, fr_date, fr_dec, fr_hour, fr_int, fr_pct, fr_share, github_blob,
                    github_tree, load_games, parse_iso, read_csv)
from facts import GENRES_FR

esc = html.escape
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MIN_DAYS = 7


# ------------------------------------------------------------------ données
def rel(p):
    p = Path(p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def month_files(y, m):
    return sorted(glob.glob(str(DATA / "snapshots" / f"{y:04d}" / f"{m:02d}" / "*" / "*.csv")))


def load_facts(name):
    p = FACTS / f"{name}.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    return d.get("faits", d)


def icon_uri(url, size=64):
    try:
        import og
        im = og.get_icon(url, size)
    except Exception:
        im = None
    if im is None:
        return ""
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def collect(y, m):
    files = month_files(y, m)
    if not files:
        raise SystemExit(f"Aucun relevé pour {y}-{m:02d}.")
    last = files[-1]
    rows = read_csv(Path(last))
    line = {r["universe_id"]: i + 2 for i, r in enumerate(rows)}
    rows.sort(key=lambda r: -int(r["playing"] or 0))
    games = load_games()
    ts = parse_iso(rows[0]["ts_utc"])
    src = rel(last)
    top = rows[:100]
    tot = sum(int(r["playing"]) for r in top) or 1

    def g(u):
        return games.get(u, {})

    def link_row(u):
        return github_blob(src) + f"#L{line[u]}"

    D = {"y": y, "m": m, "ts": ts, "src": src, "src_url": github_blob(src), "tot": tot, "n_suivis": len(rows), "games_url": github_blob("data/games.csv")}
    D["top"] = []
    for i, r in enumerate(top, 1):
        u = r["universe_id"]
        gg = g(u)
        D["top"].append({"rang": i, "uid": u, "nom": gg.get("name", u), "studio": gg.get("creator_name", ""), "genre": GENRES_FR.get(gg.get("genre_l1", ""), gg.get("genre_l1", "")),
                         "joueurs": int(r["playing"]), "part": int(r["playing"]) / tot, "visites": int(r["visits"] or 0), "cree": gg.get("created", "")[:10],
                         "icon": gg.get("icon", ""), "url": link_row(u)})
    t10 = sum(x["joueurs"] for x in D["top"][:10])
    D["part_top1"], D["part_top10"] = D["top"][0]["part"], t10 / tot

    # genres
    by, cnt = Counter(), Counter()
    for x in D["top"]:
        by[x["genre"] or "Non classé"] += x["joueurs"]
        cnt[x["genre"] or "Non classé"] += 1
    D["genres"] = [{"nom": k, "joueurs": v, "part": v / tot, "jeux": cnt[k]} for k, v in by.most_common(8)]

    # studios
    st = defaultdict(list)
    for x in D["top"]:
        if x["studio"]:
            st[x["studio"]].append(x)
    D["studios"] = sorted(({"nom": k, "jeux": len(v), "joueurs": sum(z["joueurs"] for z in v), "part": sum(z["joueurs"] for z in v) / tot,
                            "phare": max(v, key=lambda z: z["joueurs"])["nom"]} for k, v in st.items()), key=lambda s: -s["joueurs"])
    D["n_studios"] = len(st)
    D["multi"] = [s for s in D["studios"] if s["jeux"] >= 2]
    t5s = sum(s["joueurs"] for s in D["studios"][:5])
    D["part_top5_studios"] = t5s / tot

    # âge
    today = ts.astimezone(TZ).date()
    coh = [("Avant 2020", None, 2019), ("2020 à 2024", 2020, 2024), (str(today.year - 1), today.year - 1, today.year - 1), (str(today.year), today.year, today.year)]
    D["cohortes"] = []
    for lab, lo, hi in coh:
        sel = [x for x in D["top"] if x["cree"][:4].isdigit() and (lo is None or int(x["cree"][:4]) >= lo) and int(x["cree"][:4]) <= hi]
        D["cohortes"].append({"nom": lab, "jeux": len(sel), "part": sum(x["joueurs"] for x in sel) / tot})
    rec90 = [x for x in D["top"] if x["cree"] and (today - date.fromisoformat(x["cree"])).days <= 90]
    D["recents"] = {"jeux": len(rec90), "part": sum(x["joueurs"] for x in rec90) / tot, "liste": rec90[:5]}
    D["doyens"] = sorted([x for x in D["top"] if x["cree"]], key=lambda x: x["cree"])[:5]
    for x in D["doyens"]:
        x["age"] = (today - date.fromisoformat(x["cree"])).days // 365

    # game passes (dernier relevé du mois)
    pf = sorted(p for p in glob.glob(str(DATA / "passes" / f"{y:04d}-{m:02d}-*.csv")))
    D["passes"] = None
    if pf:
        prow = read_csv(Path(pf[-1]))
        prices = [int(p["prix"]) for p in prow if p["en_vente"] == "1" and p["prix"]]
        if prices:
            per = defaultdict(list)
            for p in prow:
                if p["en_vente"] == "1" and p["prix"]:
                    per[p["universe_id"]].append(int(p["prix"]))
            ranks = {x["uid"]: x for x in D["top"]}
            gm = sorted(([ranks[u], len(v), median(v)] for u, v in per.items() if u in ranks), key=lambda z: z[0]["rang"])
            bands = [(0, 99, "Moins de 100"), (100, 499, "100 à 499"), (500, 999, "500 à 999"), (1000, 4999, "1 000 à 4 999"), (5000, 10 ** 9, "5 000 et plus")]
            D["passes"] = {"src": rel(pf[-1]), "url": github_blob(rel(pf[-1])), "n": len(prices), "total": len(prow), "jeux": len(per), "mediane": median(prices),
                           "max": max(prices), "bands": [{"nom": lab, "part": sum(1 for p in prices if lo <= p <= hi) / len(prices)} for lo, hi, lab in bands],
                           "plus": sorted(gm, key=lambda z: -z[1])[:6], "jour": date.fromisoformat(prow[0]["date"])}

    # sections du mois
    days = sorted({Path(f).parent.name for f in files})
    D["jours"] = len(days)
    D["mois_ok"] = len(days) >= MIN_DAYS
    D["n_releves"] = len(files)
    if D["mois_ok"]:
        hours = defaultdict(list)
        best = (0, None, None)
        per_day = defaultdict(lambda: defaultdict(list))
        for f in files:
            rr = read_csv(Path(f))
            if not rr:
                continue
            t = parse_iso(rr[0]["ts_utc"])
            vals = sorted((int(r["playing"] or 0) for r in rr), reverse=True)
            hours[t.astimezone(TZ).hour].append(sum(vals[:100]))
            day = t.astimezone(TZ).date()
            for r in rr:
                v = int(r["playing"] or 0)
                per_day[r["universe_id"]][day].append(v)
                if v > best[0]:
                    best = (v, r["universe_id"], t)
        prof = {h: mean(v) for h, v in hours.items()}
        D["heures"] = [{"h": h, "v": prof.get(h)} for h in range(24)]
        hp = max(prof, key=prof.get)
        hc = min(prof, key=prof.get)
        D["pointe"] = {"h": hp, "v": prof[hp], "creux_h": hc, "creux_v": prof[hc], "ecart": prof[hp] / prof[hc] - 1 if prof[hc] else 0}
        D["record_mois"] = {"v": best[0], "nom": g(best[1]).get("name", best[1]), "ts": best[2]}
        dl = sorted({d for byd in per_day.values() for d in byd if d.month == m})
        first, lastd = dl[:3], dl[-3:]
        moves = []
        for u, byd in per_day.items():
            a = [mean(byd[d]) for d in first if d in byd]
            b = [mean(byd[d]) for d in lastd if d in byd]
            if len(a) >= 2 and len(b) >= 2 and mean(b) >= 5000 and mean(a) > 0:
                moves.append({"nom": g(u).get("name", u), "avant": mean(a), "apres": mean(b), "var": mean(b) / mean(a) - 1})
        moves.sort(key=lambda z: -z["var"])
        D["hausses"] = moves[:5]
        D["baisses"] = sorted(moves, key=lambda z: z["var"])[:5]
        D["mois_url"] = github_tree(f"data/snapshots/{y:04d}/{m:02d}")
        D["periode"] = (dl[0], dl[-1])

    D["off"] = load_facts("officiel")
    D["ext"] = load_facts("externe")
    return D


# ------------------------------------------------------------------ rendu
def a(v, url):
    return f'<a class="n" href="{esc(url)}">{v}</a>'


def bars(rows, key="part", fmt=fr_share, label="nom", color="var(--blue)"):
    vmax = max((r[key] for r in rows), default=1) or 1
    return '<div class="bars">' + "".join(
        f'<div class="bar-row"><span class="bl">{esc(str(r[label]))}</span><span class="bt"><span class="bb" style="width:{r[key] / vmax * 100:.1f}%;background:{color}"></span>'
        f'<span class="bv">{fmt(r[key])}</span></span></div>' for r in rows) + "</div>"


def off(D, key, fallback="—"):
    f = D["off"].get(key)
    return a(esc(f["d"]), f["src"] if f["src"].startswith("http") else github_blob(f["src"].split("#")[0])) if f else fallback


def ext(D, key):
    f = D["ext"].get(key)
    return a(esc(f["d"]), f["src"]) if f else "—"


def page(n, total, D, body, cls=""):
    mois = f"{MOIS[D['m'] - 1]} {D['y']}"
    return (f'<section class="page {cls}">{body}<footer class="pf"><span><b>PlayLedger</b> · État de Roblox, {mois}</span>'
            f'<span>{n} / {total}</span></footer></section>')


def render(D):
    mois_cap = f"{MOIS[D['m'] - 1].capitalize()} {D['y']}"
    when = D["ts"]
    when_txt = f"{fr_date(when.astimezone(TZ).date(), weekday=False)} à {fr_hour(when)}"
    T = D["top"]
    n1, n2 = T[0], T[1]
    pages = []

    # 1. couverture
    kpi = [(a(fr_big(D["tot"]), D["src_url"]), "joueurs en ligne sur les 100 jeux les plus joués"),
           (a(fr_share(D["part_top10"]), D["src_url"]), "des joueurs du top 100 sont sur les 10 premiers jeux"),
           (off(D, "officiel.t2-2026.dau"), "d’utilisateurs actifs chaque jour (T2 2026, Roblox Corporation)"),
           (a(fr_share(D["recents"]["part"]), D["games_url"]), "des joueurs du top 100 sur des jeux créés il y a moins de 90 jours")]
    pages.append(("cover", f'''<div class="cv-top"><span class="logo"><i></i><i></i><i></i></span><span class="brand">PlayLedger</span><span class="cv-tag">Baromètre mensuel</span></div>
<div class="cv-main"><p class="cv-kicker">Rapport · {esc(mois_cap)}</p><h1>État de Roblox</h1>
<p class="cv-sub">Ce que jouent vraiment les joueurs, qui capte l’audience et comment les jeux se monétisent. Chaque chiffre de ce rapport est relié à sa source.</p></div>
<div class="cv-kpis">{"".join(f'<div class="cv-k"><b>{v}</b><span>{esc(l)}</span></div>' for v, l in kpi)}</div>
<p class="cv-foot">Relevé de référence : {esc(when_txt)} (heure de Paris), {fr_int(D["n_suivis"])} jeux suivis. Données publiques de Roblox, rapport généré automatiquement le {esc(fr_date(datetime.now(TZ).date(), weekday=False))}.</p>'''))

    # 2. l'essentiel
    g1 = D["genres"][0]
    s1 = D["studios"][0]
    oldest = D["doyens"][0] if D["doyens"] else None
    pts = [
        f'<b>{esc(n1["nom"])}</b> domine Roblox : {a(fr_int(n1["joueurs"]), n1["url"])} joueurs en ligne au relevé de référence, soit {a(fr_share(n1["part"]), D["src_url"])} des joueurs du top 100, devant {esc(n2["nom"])} ({a(fr_int(n2["joueurs"]), n2["url"])}).',
        f'L’audience est concentrée : les 10 premiers jeux réunissent {a(fr_share(D["part_top10"]), D["src_url"])} des joueurs du top 100, et les 5 premiers studios {a(fr_share(D["part_top5_studios"]), D["src_url"])}.',
        f'Le genre le plus joué est <b>{esc(g1["nom"])}</b> : {a(fr_share(g1["part"]), D["src_url"])} des joueurs du top 100, répartis sur {a(fr_int(g1["jeux"]), D["games_url"])} jeux.',
        f'Le renouvellement est rapide : {a(fr_int(D["recents"]["jeux"]), D["games_url"])} jeux du top 100 ont moins de 90 jours et captent {a(fr_share(D["recents"]["part"]), D["games_url"])} des joueurs.'
        + (f' Le doyen, {esc(oldest["nom"])}, a été créé en {esc(oldest["cree"][:4])}.' if oldest else ""),
    ]
    if D["passes"]:
        P = D["passes"]
        pts.append(f'Sur {a(fr_int(P["n"]), P["url"])} game passes en vente dans le top 100, le prix médian est de {a(fr_int(P["mediane"]), P["url"])} Robux.')
    if D["off"]:
        pts.append(f'Côté entreprise, Roblox a publié pour le T2 2026 un chiffre d’affaires de {off(D, "officiel.t2-2026.revenus")} ({off(D, "officiel.t2-2026.revenus_croissance")} sur un an) et {off(D, "officiel.t2-2026.dau")} d’utilisateurs actifs quotidiens.')
    if D["mois_ok"]:
        pts.append(f'Sur le mois, la plateforme est la plus fréquentée vers {D["pointe"]["h"]}{chr(8239)}h (heure de Paris), avec {a(fr_pct(D["pointe"]["ecart"], signed=False, nd=0), D["mois_url"])} de joueurs en plus qu’au creux de {D["pointe"]["creux_h"]}{chr(8239)}h.')
    toc = ["Roblox Corporation", "Le top 100", "Genres et studios", "L’âge des jeux", "Monétisation"] + (["Le mois en relevés"] if D["mois_ok"] else []) + ["Records historiques", "Méthode et sources"]
    pages.append(("", f'''<p class="kicker">L’essentiel</p><h2>Ce qu’il faut retenir</h2>
<ol class="key">{"".join(f"<li>{p}</li>" for p in pts)}</ol>
<div class="toc"><p class="kicker">Sommaire</p><ol>{"".join(f"<li>{esc(t)}</li>" for t in toc)}</ol></div>
<p class="note">Les chiffres soulignés sont des liens : ils ouvrent le fichier de données ou la publication d’où ils viennent.</p>'''))

    # 3. Roblox Corporation
    if D["off"]:
        k = [("Chiffre d’affaires", "revenus"), ("Bookings", "bookings"), ("Utilisateurs actifs / jour", "dau"), ("Heures d’engagement", "heures"),
             ("Payeurs uniques / mois", "payeurs_mensuels"), ("Reversé aux créateurs (DevEx)", "devex")]
        cards = "".join(f'<div class="kc"><span>{esc(l)}</span><b>{off(D, "officiel.t2-2026." + c)}</b><em>{off(D, "officiel.t2-2026." + c.replace("_mensuels", "") + "_croissance", "")} sur un an</em></div>' for l, c in k)
        reg = [{"nom": "Japon", "k": "dau_japon_croissance"}, {"nom": "Inde", "k": "dau_inde_croissance"}, {"nom": "États-Unis et Canada", "k": "dau_usa_canada_croissance"}]
        for r in reg:
            r["v"] = (D["off"].get("officiel.t2-2026." + r["k"]) or {}).get("v", 0) or 0
        pages.append(("", f'''<p class="kicker">1 · L’entreprise</p><h2>Roblox Corporation au deuxième trimestre 2026</h2>
<p class="lede">Les derniers résultats publiés par Roblox (communiqué du 30 juillet 2026). Les résultats du troisième trimestre seront intégrés à l’édition suivant leur publication.</p>
<div class="kgrid">{cards}</div>
<div class="two"><div><h3>Croissance des utilisateurs actifs par région</h3>{bars(reg, "v", lambda v: fr_pct(v, nd=0), color="var(--green)")}</div>
<div><h3>Prévisions de Roblox pour le T3 2026</h3><p>Bookings attendus entre {off(D, "officiel.t3-2026.prevision_bookings_bas")} et {off(D, "officiel.t3-2026.prevision_bookings_haut")}, chiffre d’affaires entre {off(D, "officiel.t3-2026.prevision_revenus_bas")} et {off(D, "officiel.t3-2026.prevision_revenus_haut")}.</p>
<p>Perte nette du trimestre : {off(D, "officiel.t2-2026.perte_nette")}, contre {off(D, "officiel.t2-2025.perte_nette")} un an plus tôt. Flux de trésorerie disponible : {off(D, "officiel.t2-2026.flux_tresorerie_libre")}.</p></div></div>
<p class="src">Source : communiqué de résultats de Roblox Corporation (formulaire 8-K déposé à la SEC), saisi dans <a href="{esc(github_blob("data/official/roblox-trimestriel.csv"))}">data/official/roblox-trimestriel.csv</a>.</p>'''))

    # 4. top 100
    icons = {x["uid"]: icon_uri(x["icon"]) for x in T[:10]}
    trs = "".join(f'<tr><td class="r">{x["rang"]}</td><td class="g">' + (f'<img src="{icons[x["uid"]]}" alt="">' if icons.get(x["uid"]) else '<i class="ph"></i>')
                  + f'<span><b>{esc(x["nom"][:46])}</b><small>{esc(x["studio"][:40])}</small></span></td><td>{esc(x["genre"])}</td>'
                  f'<td class="num">{a(fr_int(x["joueurs"]), x["url"])}</td><td class="num">{fr_share(x["part"])}</td></tr>' for x in T[:12])
    pages.append(("", f'''<p class="kicker">2 · L’audience</p><h2>Le top 100 au relevé de référence</h2>
<p class="lede">{a(fr_int(D["tot"]), D["src_url"])} joueurs étaient en ligne sur les 100 jeux les plus joués le {esc(when_txt)}. Le premier jeu en concentre {a(fr_share(D["part_top1"]), D["src_url"])}, les dix premiers {a(fr_share(D["part_top10"]), D["src_url"])}.</p>
<table class="t"><thead><tr><th class="r">#</th><th>Jeu et studio</th><th>Genre</th><th class="num">Joueurs</th><th class="num">Part du top 100</th></tr></thead><tbody>{trs}</tbody></table>
<p class="src">Source : <a href="{esc(D["src_url"])}">{esc(D["src"])}</a> (un relevé horaire de l’API publique de Roblox) et <a href="{esc(D["games_url"])}">data/games.csv</a>.</p>'''))

    # 5. genres et studios
    srows = "".join(f'<tr><td class="r">{i}</td><td><b>{esc(s["nom"][:36])}</b><small>{esc(s["phare"][:44])}</small></td><td class="num">{s["jeux"]}</td>'
                    f'<td class="num">{a(fr_int(s["joueurs"]), D["src_url"])}</td><td class="num">{fr_share(s["part"])}</td></tr>' for i, s in enumerate(D["studios"][:10], 1))
    multi = ", ".join(f'{esc(s["nom"])} ({s["jeux"]} jeux)' for s in D["multi"][:4])
    pages.append(("", f'''<p class="kicker">3 · Le marché</p><h2>Genres et studios</h2>
<div class="two"><div><h3>Part des joueurs du top 100 par genre</h3>{bars(D["genres"])}<p class="small">Genres tels que déclarés par les créateurs sur Roblox.</p></div>
<div><h3>Ce qu’il faut lire</h3><p>Le genre <b>{esc(D["genres"][0]["nom"])}</b> arrive en tête avec {a(fr_share(D["genres"][0]["part"]), D["src_url"])} des joueurs, devant {esc(D["genres"][1]["nom"])} ({a(fr_share(D["genres"][1]["part"]), D["src_url"])}) et {esc(D["genres"][2]["nom"])} ({a(fr_share(D["genres"][2]["part"]), D["src_url"])}).</p>
<p>{a(fr_int(D["n_studios"]), D["games_url"])} studios se partagent le top 100. Les cinq premiers captent {a(fr_share(D["part_top5_studios"]), D["src_url"])} des joueurs.{(" Studios présents avec plusieurs jeux : " + multi + ".") if multi else ""}</p></div></div>
<h3>Les 10 studios qui réunissent le plus de joueurs</h3>
<table class="t"><thead><tr><th class="r">#</th><th>Studio et jeu phare</th><th class="num">Jeux (top 100)</th><th class="num">Joueurs</th><th class="num">Part</th></tr></thead><tbody>{srows}</tbody></table>
<p class="src">Sources : <a href="{esc(D["src_url"])}">{esc(D["src"])}</a>, <a href="{esc(D["games_url"])}">data/games.csv</a> (créateur et genre déclarés sur Roblox).</p>'''))

    # 6. âge
    drows = "".join(f'<tr><td><b>{esc(x["nom"][:44])}</b><small>{esc(x["studio"][:40])}</small></td><td class="num">{esc(fr_date(date.fromisoformat(x["cree"]), weekday=False))}</td>'
                    f'<td class="num">{x["age"]} ans</td><td class="num">{x["rang"]}<sup>e</sup></td></tr>' for x in D["doyens"])
    rl = ", ".join(f'{esc(x["nom"])} ({x["rang"]}<sup>e</sup>)' for x in D["recents"]["liste"][:4])
    pages.append(("", f'''<p class="kicker">4 · Le renouvellement</p><h2>L’âge des jeux qui comptent</h2>
<div class="two"><div><h3>Part des joueurs du top 100 selon l’année de création</h3>{bars(D["cohortes"])}</div>
<div><h3>Jeunes et anciens</h3><p>{a(fr_int(D["recents"]["jeux"]), D["games_url"])} jeux du top 100 ont été créés il y a 90 jours ou moins. Ensemble, ils réunissent {a(fr_share(D["recents"]["part"]), D["games_url"])} des joueurs.{(" Parmi eux : " + rl + ".") if rl else ""}</p>
<p>À l’autre bout, des jeux de plus de dix ans tiennent toujours leur place : les doyens du top 100 sont listés ci-dessous.</p></div></div>
<h3>Les doyens du top 100</h3>
<table class="t"><thead><tr><th>Jeu et studio</th><th class="num">Créé le</th><th class="num">Âge</th><th class="num">Rang</th></tr></thead><tbody>{drows}</tbody></table>
<p class="src">Source : date de création déclarée par Roblox, <a href="{esc(D["games_url"])}">data/games.csv</a>.</p>'''))

    # 7. monétisation
    if D["passes"]:
        P = D["passes"]
        prow = "".join(f'<tr><td><b>{esc(r["nom"][:44])}</b></td><td class="num">{r["rang"]}<sup>e</sup></td><td class="num">{a(fr_int(n), P["url"])}</td><td class="num">{fr_int(med)} R$</td></tr>'
                       for r, n, med in P["plus"])
        pages.append(("", f'''<p class="kicker">5 · L’argent</p><h2>Combien coûtent les game passes</h2>
<p class="lede">Relevé du {esc(fr_date(P["jour"], weekday=False))} : {a(fr_int(P["n"]), P["url"])} game passes en vente sur {a(fr_int(P["jeux"]), P["url"])} jeux du top 100. Prix médian : {a(fr_int(P["mediane"]), P["url"])} Robux ; le plus cher atteint {a(fr_int(P["max"]), P["url"])} Robux.</p>
<div class="two"><div><h3>Répartition des prix (en Robux)</h3>{bars(P["bands"], color="var(--amber)")}</div>
<div><h3>Les jeux qui vendent le plus de passes</h3><table class="t compact"><thead><tr><th>Jeu</th><th class="num">Rang</th><th class="num">Passes</th><th class="num">Médiane</th></tr></thead><tbody>{prow}</tbody></table></div></div>
<p class="small">Les passes retirés de la vente ne sont pas comptés dans les prix. Les Robux ne sont pas convertis en euros : le taux dépend du canal d’achat.</p>
<p class="src">Source : API publique des game passes de Roblox, relevé quotidien <a href="{esc(P["url"])}">{esc(P["src"])}</a>.</p>'''))

    # 8. le mois
    if D["mois_ok"]:
        hv = [h for h in D["heures"] if h["v"]]
        vmax = max(h["v"] for h in hv)
        cols = "".join(f'<div class="hc{" pk" if h["h"] == D["pointe"]["h"] else ""}"><span style="height:{(h["v"] or 0) / vmax * 100:.1f}%"></span><em>{h["h"]}</em></div>' for h in D["heures"])
        mv = lambda L: "".join(f'<tr><td><b>{esc(z["nom"][:44])}</b></td><td class="num">{fr_int(round(z["avant"]))}</td><td class="num">{fr_int(round(z["apres"]))}</td><td class="num {"up" if z["var"] >= 0 else "down"}">{fr_pct(z["var"], nd=0)}</td></tr>' for z in L)
        p0, p1 = D["periode"]
        pages.append(("", f'''<p class="kicker">6 · Le mois en relevés</p><h2>{esc(MOIS[D["m"] - 1].capitalize())}, heure par heure</h2>
<p class="lede">{a(fr_int(D["n_releves"]), D["mois_url"])} relevés horaires du {esc(fr_date(p0, weekday=False))} au {esc(fr_date(p1, weekday=False))}. Plus haut relevé du mois pour un seul jeu : {a(fr_int(D["record_mois"]["v"]), D["mois_url"])} joueurs sur {esc(D["record_mois"]["nom"])}, le {esc(fr_date(D["record_mois"]["ts"].astimezone(TZ).date(), weekday=False))}.</p>
<h3>Joueurs en ligne sur le top 100, en moyenne selon l’heure (Paris)</h3><div class="hours">{cols}</div>
<p class="small">Pointe vers {D["pointe"]["h"]} h ({fr_big(round(D["pointe"]["v"]))} joueurs en moyenne), creux vers {D["pointe"]["creux_h"]} h ({fr_big(round(D["pointe"]["creux_v"]))}).</p>
<div class="two"><div><h3>Plus fortes hausses</h3><table class="t compact"><thead><tr><th>Jeu</th><th class="num">Début</th><th class="num">Fin</th><th class="num">Évol.</th></tr></thead><tbody>{mv(D["hausses"])}</tbody></table></div>
<div><h3>Plus fortes baisses</h3><table class="t compact"><thead><tr><th>Jeu</th><th class="num">Début</th><th class="num">Fin</th><th class="num">Évol.</th></tr></thead><tbody>{mv(D["baisses"])}</tbody></table></div></div>
<p class="small">Moyenne des trois premiers jours de relevés comparée à celle des trois derniers, pour les jeux à 5 000 joueurs ou plus en fin de période.</p>
<p class="src">Source : relevés horaires du mois, <a href="{esc(D["mois_url"])}">data/snapshots/{D["y"]}/{D["m"]:02d}</a>.</p>'''))

    # 9. records
    if D["ext"]:
        recs = [("Roblox, toute la plateforme", "ext.roblox.ccu_aout25", "23 août 2025"), ("Roblox, record précédent", "ext.roblox.ccu_juil25", "juillet 2025"),
                ("Steal a Brainrot", "ext.sab.ccu_record", "octobre 2025"), ("Grow a Garden", "ext.gag.ccu_aout", "23 août 2025"),
                ("Steal An Egg (d’après Rolimon’s)", "ext.egg.record_rolimons", "2026")]
        rr = "".join(f'<tr><td><b>{esc(n)}</b></td><td class="num">{ext(D, k)}</td><td class="num">{esc(w)}</td></tr>' for n, k, w in recs if D["ext"].get(k))
        srcs = sorted({(D["ext"][k]["l"].split("(source : ")[-1].rstrip(")"), D["ext"][k]["src"]) for _, k, _ in recs if D["ext"].get(k)})
        pages.append(("", f'''<p class="kicker">7 · Repères</p><h2>Les records historiques</h2>
<p class="lede">Pour situer les chiffres du mois : les plus hauts nombres de joueurs simultanés publiés pour Roblox et pour ses jeux phares. Ces records précèdent notre suivi et viennent de sources de presse, citées une à une.</p>
<table class="t"><thead><tr><th>Jeu ou plateforme</th><th class="num">Joueurs simultanés</th><th class="num">Date</th></tr></thead><tbody>{rr}</tbody></table>
<p>Grow a Garden a atteint un milliard de visites en {ext(D, "ext.gag.jours_milliard")} jours, et dépassait {ext(D, "ext.gag.visites_mai26")} de visites en mai 2026.</p>
<p class="src">Sources : {"; ".join(f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in srcs)}.</p>'''))

    # 10. méthode
    pages.append(("", f'''<p class="kicker">Méthode</p><h2>Comment ce rapport est fait</h2>
<div class="two"><div><h3>Les données</h3><p>PlayLedger interroge chaque heure les API publiques de Roblox : nombre de joueurs en ligne, visites et votes de {fr_int(D["n_suivis"])} jeux (les classements mis en avant par Roblox et les jeux qui y sont passés). Les game passes du top 100 sont relevés une fois par jour.</p>
<p>Les résultats de Roblox Corporation viennent de ses communiqués officiels. Les records antérieurs à notre suivi viennent de sources de presse, citées à chaque fois.</p></div>
<div><h3>Les vérifications</h3><p>Aucun chiffre n’est saisi à la main dans le texte : chacun est calculé par programme à partir des fichiers publiés, et renvoie par un lien à sa source exacte.</p>
<p>Toutes les données sont ouvertes (CSV et JSON) et réutilisables en citant PlayLedger. Une erreur ? Elle est corrigée et la correction est publiée.</p></div></div>
<div class="end"><p class="kicker">PlayLedger</p><p class="big">L’économie de Roblox, en chiffres vérifiables.</p>
<p>Classement en direct, alertes, analyses et données ouvertes : <a href="{esc(CONFIG.get("baseUrl", ""))}">{esc(CONFIG.get("baseUrl", "").replace("https://", ""))}</a></p>
<p class="small">Média indépendant, non affilié à Roblox Corporation. Roblox est une marque de Roblox Corporation. Méthode détaillée : <a href="{esc(CONFIG.get("baseUrl", "") + "/methode/")}">page Méthode</a>.</p></div>'''))

    total = len(pages)
    body = "".join(page(i + 1, total, D, b, cls) for i, (cls, b) in enumerate(pages))
    font = (ROOT / "assets" / "fonts" / "schibsted-grotesk-latin-wght-normal.woff2").as_uri()
    font2 = (ROOT / "assets" / "fonts" / "schibsted-grotesk-latin-ext-wght-normal.woff2").as_uri()
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>État de Roblox, {esc(MOIS[D['m'] - 1])} {D['y']} | PlayLedger</title>
<style>
@font-face {{ font-family: "Schibsted"; src: url("{font}") format("woff2"); font-weight: 400 900; }}
@font-face {{ font-family: "Schibsted"; src: url("{font2}") format("woff2"); font-weight: 400 900; unicode-range: U+0100-024F, U+1E00-1EFF; }}
{CSS}
</style></head><body>{body}</body></html>"""


CSS = """
@page { size: A4; margin: 0; }
:root { --ink: #0f172a; --ink2: #334155; --muted: #64748b; --rule: #e2e8f0; --soft: #f1f5f9; --blue: #2563eb; --green: #10b981; --red: #ef4444; --amber: #f59e0b; --bg: #0b0e14; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Schibsted", system-ui, sans-serif; color: var(--ink); font-size: 10.5pt; line-height: 1.5; word-spacing: .03em; }
.page { width: 210mm; height: 297mm; padding: 18mm 17mm 20mm; position: relative; overflow: hidden; page-break-after: always; break-after: page; background: #fff; }
.page:last-child { page-break-after: auto; }
.pf { position: absolute; left: 17mm; right: 17mm; bottom: 10mm; display: flex; justify-content: space-between; font-size: 8pt; color: var(--muted); border-top: 1px solid var(--rule); padding-top: 3mm; }
a { color: inherit; }
a.n { color: var(--blue); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px; font-weight: 650; }
.kicker { font-size: 8pt; text-transform: uppercase; letter-spacing: .14em; color: var(--blue); font-weight: 700; margin-bottom: 2mm; }
h2 { font-size: 22pt; line-height: 1.12; letter-spacing: -.02em; font-weight: 800; margin-bottom: 5mm; }
h3 { font-size: 10.5pt; font-weight: 750; margin: 6mm 0 2.5mm; }
p { margin-bottom: 2.5mm; }
.lede { font-size: 11.5pt; color: var(--ink2); margin-bottom: 4mm; }
.small { font-size: 8.5pt; color: var(--muted); }
.note { font-size: 9pt; color: var(--muted); margin-top: 6mm; }
.src { font-size: 8pt; color: var(--muted); border-top: 1px solid var(--rule); padding-top: 2.5mm; margin-top: 6mm; }
.src a { color: var(--muted); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 9mm; }
.two h3:first-child { margin-top: 2mm; }
sup { font-size: .65em; }
small { display: block; color: var(--muted); font-size: 8pt; font-weight: 400; }

/* couverture */
.cover { background: var(--bg); color: #f8fafc; display: flex; flex-direction: column;
  background-image: radial-gradient(circle at 85% 12%, rgba(37,99,235,.35), transparent 45%), radial-gradient(circle at 10% 95%, rgba(16,185,129,.18), transparent 40%),
  linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
  background-size: auto, auto, 10mm 10mm, 10mm 10mm; }
.cover .pf { display: none; }
.cv-top { display: flex; align-items: center; gap: 3mm; }
.logo { display: inline-flex; align-items: flex-end; gap: 1.2mm; height: 6mm; }
.logo i { width: 1.6mm; background: #3b82f6; border-radius: .4mm; display: block; }
.logo i:nth-child(1) { height: 2.6mm; } .logo i:nth-child(2) { height: 6mm; } .logo i:nth-child(3) { height: 4.2mm; }
.brand { font-weight: 800; font-size: 14pt; }
.cv-tag { margin-left: auto; font-size: 8pt; text-transform: uppercase; letter-spacing: .14em; color: #94a3b8; border: 1px solid rgba(255,255,255,.2); border-radius: 99px; padding: 1mm 3mm; }
.cv-main { margin-top: 48mm; }
.cv-kicker { font-size: 10pt; text-transform: uppercase; letter-spacing: .18em; color: #60a5fa; font-weight: 700; margin-bottom: 4mm; }
.cover h1 { font-size: 54pt; line-height: 1; letter-spacing: -.035em; font-weight: 900; margin-bottom: 7mm; }
.cv-sub { font-size: 13pt; color: #cbd5e1; max-width: 140mm; line-height: 1.45; }
.cv-kpis { margin-top: auto; display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
.cv-k { border: 1px solid rgba(255,255,255,.12); background: rgba(255,255,255,.04); border-radius: 3mm; padding: 5mm; }
.cv-k b { display: block; font-size: 22pt; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; margin-bottom: 1.5mm; }
.cv-k b a.n { color: #fff; text-decoration-color: rgba(255,255,255,.35); }
.cv-k span { font-size: 9pt; color: #94a3b8; line-height: 1.35; display: block; }
.cv-foot { margin-top: 7mm; font-size: 8pt; color: #64748b; }

/* essentiel */
ol.key { list-style: none; counter-reset: k; margin-top: 2mm; }
ol.key li { counter-increment: k; position: relative; padding: 3.2mm 0 3.2mm 12mm; border-top: 1px solid var(--rule); font-size: 11pt; }
ol.key li::before { content: counter(k); position: absolute; left: 0; top: 3mm; width: 7mm; height: 7mm; border-radius: 50%; background: var(--soft); color: var(--blue); font-weight: 800; font-size: 9.5pt; display: flex; align-items: center; justify-content: center; }
.toc { margin-top: 8mm; background: var(--soft); border-radius: 3mm; padding: 5mm 6mm; }
.toc ol { columns: 2; padding-left: 5mm; font-weight: 600; }
.toc li { margin: 1mm 0; }

/* chiffres clés */
.kgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; margin: 4mm 0 2mm; }
.kc { border: 1px solid var(--rule); border-radius: 2.5mm; padding: 4mm; }
.kc span { font-size: 8.5pt; color: var(--muted); display: block; }
.kc b { display: block; font-size: 15pt; font-weight: 800; letter-spacing: -.01em; margin: 1mm 0; line-height: 1.15; }
.kc em { font-style: normal; font-size: 8.5pt; color: var(--green); font-weight: 650; }

/* barres */
.bars { display: grid; gap: 2.2mm; }
.bar-row { display: grid; grid-template-columns: 34mm 1fr; align-items: center; gap: 3mm; font-size: 9pt; }
.bl { color: var(--ink2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bt { display: flex; align-items: center; gap: 2mm; }
.bb { height: 4.2mm; border-radius: 0 1mm 1mm 0; min-width: .6mm; display: block; }
.bv { font-weight: 700; white-space: nowrap; font-size: 9pt; }

/* tableaux */
table.t { width: 100%; border-collapse: collapse; font-size: 9.2pt; margin-top: 2mm; }
.t th { text-align: left; font-size: 7.5pt; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 700; padding: 2mm 2mm; border-bottom: 1.5px solid var(--ink); }
.t td { padding: 2mm; border-bottom: 1px solid var(--rule); vertical-align: middle; }
.t .num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.t .r { width: 8mm; color: var(--muted); font-weight: 700; }
.t td.g { display: flex; align-items: center; gap: 3mm; }
.t td.g img, .t td.g .ph { width: 8mm; height: 8mm; border-radius: 1.6mm; flex: none; background: var(--soft); display: block; }
.t.compact td, .t.compact th { padding: 1.5mm; }
.t td.up { color: #059669; font-weight: 700; } .t td.down { color: #dc2626; font-weight: 700; }

/* heures */
.hours { display: grid; grid-template-columns: repeat(24, 1fr); gap: 1mm; height: 38mm; align-items: end; margin-top: 3mm; }
.hc { height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; }
.hc span { width: 100%; background: #bfdbfe; border-radius: .8mm .8mm 0 0; display: block; }
.hc.pk span { background: var(--blue); }
.hc em { font-style: normal; font-size: 6.5pt; color: var(--muted); margin-top: 1mm; }

/* fin */
.end { margin-top: 14mm; background: var(--bg); color: #f8fafc; border-radius: 4mm; padding: 8mm; }
.end .kicker { color: #60a5fa; }
.end .big { font-size: 17pt; font-weight: 800; letter-spacing: -.01em; margin-bottom: 3mm; }
.end a { color: #93c5fd; }
.end .small { color: #94a3b8; margin-top: 4mm; }
"""


def find_chrome():
    for c in (os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "/opt/pw-browsers/chromium/chrome-linux/chrome"):
        if c and (shutil.which(c) or Path(c).exists()):
            return shutil.which(c) or c
    for c in glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"):
        return c
    return None


def to_pdf(html_path, pdf_path):
    chrome = find_chrome()
    if not chrome:
        raise SystemExit("Chrome introuvable : impossible de produire le PDF (le HTML est écrit).")
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-data-dir={prof}", "--no-pdf-header-footer",
                        "--allow-file-access-from-files", "--virtual-time-budget=4000", f"--print-to-pdf={pdf_path}", Path(html_path).resolve().as_uri()],
                       check=True, capture_output=True, timeout=120)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mois", help="AAAA-MM (par défaut : mois du dernier relevé)")
    ap.add_argument("--out", default=str(ROOT / "out" / "rapport"))
    ap.add_argument("--html-only", action="store_true")
    args = ap.parse_args()
    if args.mois:
        y, m = map(int, args.mois.split("-"))
    else:
        last = sorted(glob.glob(str(DATA / "snapshots" / "*" / "*" / "*" / "*.csv")))[-1]
        parts = Path(last).parts
        y, m = int(parts[-4]), int(parts[-3])
    D = collect(y, m)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"etat-de-roblox-{y:04d}-{m:02d}"
    hp = out / f"{name}.html"
    hp.write_text(render(D), encoding="utf-8")
    if not args.html_only:
        to_pdf(hp, out / f"{name}.pdf")
        print(out / f"{name}.pdf")
    else:
        print(hp)


if __name__ == "__main__":
    main()
