"""Données des vidéos courtes, tirées des fichiers du dépôt (aucun chiffre saisi à la main).

  python tools/social/video/prep.py choisir JOUR            formats possibles ce jour-là, avec la raison (JSON)
  python tools/social/video/prep.py FORMAT JOUR SORTIE.json  données d'un format (duel, decollage, chute, course, nouveaux, genres)
  python tools/social/video/prep.py icones DONNEES.json      universe_id dont la vidéo a besoin (pour le workflow des icônes)

Les chiffres viennent des jetons de facts/JOUR.json quand ils existent, sinon d'un calcul fait ici sur data/ (écarts, séries,
totaux par genre) : le même calcul à chaque fois, documenté dans README.md.
"""
import csv
import glob
import json
import os
import sys
import datetime as dt
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
from common import load_day_snapshots  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
D = dt.date.fromisoformat
GAMES = {r["universe_id"]: r for r in csv.DictReader(open("data/games.csv"))}
GENRES = {  # nom Roblox -> libellés français (bandeau, titre, « jeux … », question)
    "Survival": ("SURVIE", "La survie", "de survie", "de la survie"),
    "RPG": ("RPG", "Les RPG", "RPG", "du RPG"),
    "Simulation": ("SIMULATION", "La simulation", "de simulation", "de la simulation"),
    "Action": ("ACTION", "L’action", "d’action", "de l’action"),
    "Roleplay & Avatar Sim": ("JEU DE RÔLE", "Le jeu de rôle", "de jeu de rôle", "du jeu de rôle"),
    "Sports & Racing": ("SPORT", "Le sport", "de sport et de course", "du sport"),
    "Strategy": ("STRATÉGIE", "La stratégie", "de stratégie", "de la stratégie"),
    "Shooter": ("TIR", "Le tir", "de tir", "du tir"),
    "Adventure": ("AVENTURE", "L’aventure", "d’aventure", "de l’aventure"),
    "Obby & Platformer": ("OBBY", "Les obbys", "d’obby", "de l’obby"),
    "Party & Casual": ("PARTY", "Les jeux party", "party", "du jeu party"),
    "Shopping": ("SHOPPING", "Le shopping", "de shopping", "du shopping"),
    "Puzzle": ("RÉFLEXION", "La réflexion", "de réflexion", "de la réflexion"),
}


def facts(day):
    p = f"facts/{day}.json"
    return json.load(open(p))["faits"] if os.path.exists(p) else None


def rows(day):
    p = f"data/jours/{day}.csv"
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


def disp(f):
    return {k: v["d"] for k, v in f.items()}


def raw(f):
    return {k: v["v"] for k, v in f.items()}


def uid_of(day, nom):
    return next(r["universe_id"] for r in rows(day) if r["nom"] == nom)


def mesures(fin, nmax):
    """jours mesurés consécutifs (faits + données) se terminant à fin, au plus nmax"""
    out = [fin]
    while len(out) < nmax:
        prev = (D(out[0]) - dt.timedelta(days=1)).isoformat()
        if not (os.path.exists(f"facts/{prev}.json") and os.path.exists(f"data/jours/{prev}.csv")):
            break
        out.insert(0, prev)
    return out


def classement_moy(day):
    rs = sorted([r for r in rows(day) if r.get("complet") == "1"], key=lambda r: -int(r["moyenne"]))
    return [(r["universe_id"], int(r["moyenne"])) for r in rs]


def hourly(uid, d0, d1):
    pts, days, d = [], [], d0
    while d <= d1:
        days.append({"i": len(pts), "iso": d.isoformat()})
        for ts, r in load_day_snapshots(d):
            if uid in r:
                loc = ts.astimezone(PARIS)
                pts.append({"t": ts.isoformat(), "h": f"{loc.hour} h {loc.minute:02d}", "day": d.isoformat(), "v": int(r[uid]["playing"])})
        d += dt.timedelta(days=1)
    return pts, days


def facteur(v, signe):
    s = f"{v:.1f}".replace(".", ",")
    return signe + (s[:-2] if s.endswith(",0") else s)


# ---------------------------------------------------------------- formats
def duel(day):
    """un jeu du top 5 (à la moyenne du jour) vient d'en dépasser un autre ; l'écart sur 8 jours mesurés"""
    jours = mesures(day, 8)
    if len(jours) < 4:
        return None, "moins de 4 jours mesurés consécutifs"
    auj, hier = classement_moy(day), classement_moy(jours[-2])
    ra, rh = {u: i for i, (u, _) in enumerate(auj)}, {u: i for i, (u, _) in enumerate(hier)}
    paires = [(ra[a], a, b) for a, _ in auj[:5] for b, _ in auj[:5] if ra[a] < ra[b] and a in rh and b in rh and rh[a] > rh[b]]
    if not paires:
        return None, "aucun dépassement dans le top 5 à la moyenne du jour"
    _, a, b = min(paires)
    f = facts(day)
    out = {"day": day, "days": jours, "facts": disp(f), "raw": raw(f)}
    for key, u in (("a", a), ("b", b)):
        moy = []
        for d in jours:
            tok = (facts(d) or {}).get(f"g.{u}.moy")
            if not tok:
                return None, f"moyenne manquante pour {u} le {d}"
            moy.append({"v": tok["v"], "d": tok["d"]})
        out[key] = {"uid": u, "nom": f[f"g.{u}.nom"]["d"], "moy": moy}
    return out, f"{out['a']['nom']} passe devant {out['b']['nom']}"


def decollage(day):
    f = facts(day)
    k = next((i for i in range(1, 6) if f.get(f"hausse.{i}.var") and ((f[f"hausse.{i}.var"]["v"] >= .5 and f[f"hausse.{i}.moy"]["v"] >= 10000)
              or (f[f"hausse.{i}.var"]["v"] >= .3 and f[f"hausse.{i}.moy"]["v"] >= 20000))), None)
    if not k:
        return None, "aucune hausse d'au moins +50 % (10 000 joueurs) ou +30 % (20 000 joueurs)"
    uid = uid_of(day, f[f"hausse.{k}.nom"]["v"])
    pts, days = hourly(uid, D(day) - dt.timedelta(days=7), D(day))
    if len(pts) < 48:
        return None, "série horaire trop courte"
    _, ij = max((pts[i + 1]["v"] - pts[i]["v"], i) for i in range(len(pts) - 1))
    tj = dt.datetime.fromisoformat(pts[ij + 1]["t"])
    maj = None   # événement daté : une mise à jour publiée dans les 6 h avant le saut
    if os.path.exists("data/mises-a-jour.csv"):
        for r in csv.DictReader(open("data/mises-a-jour.csv")):
            if r["universe_id"] != uid:
                continue
            a = dt.datetime.fromisoformat(r["apres"].replace("Z", "+00:00"))
            if a <= tj and (tj - a).total_seconds() <= 6 * 3600 and (maj is None or a > dt.datetime.fromisoformat(maj["t"])):
                loc = a.astimezone(PARIS)
                maj = {"t": a.isoformat(), "iso": loc.date().isoformat(), "h": f"{loc.hour} h {loc.minute:02d}"}
    tok = f.get(f"hausse.{k}.mult")
    m = tok["v"] if tok else f[f"hausse.{k}.moy"]["v"] / f[f"hausse.{k}.moy_avant"]["v"]
    cree = GAMES.get(uid, {}).get("created", "")[:10]
    age = (D(day) - D(cree)).days if cree else None
    return ({"day": day, "k": k, "uid": uid, "facts": disp(f), "raw": raw(f), "pts": pts, "days": days, "jump": ij, "maj": maj,
             "mult": {"v": m, "d": tok["d"] if tok else facteur(m, "×")}, "age": age},
            f"{f[f'hausse.{k}.nom']['v']} {f[f'hausse.{k}.var']['d']}" + (" après une mise à jour" if maj else " (sans mise à jour datée)"))


def chute(day):
    f = facts(day)
    connus = set()
    for d in mesures(day, 7):
        connus |= {r["universe_id"] for r in rows(d) if r.get("rang_moy") and int(r["rang_moy"]) <= 50}
    for i in range(1, 6):
        if not f.get(f"baisse.{i}.nom"):
            break
        uid = uid_of(day, f[f"baisse.{i}.nom"]["v"])
        div = f[f"baisse.{i}.moy_avant"]["v"] / f[f"baisse.{i}.moy"]["v"]
        if uid in connus and div >= 1.5:
            pts, days = hourly(uid, D(day) - dt.timedelta(days=7), D(day))
            return ({"day": day, "k": i, "uid": uid, "facts": disp(f), "raw": raw(f), "pts": pts, "days": days},
                    f"{f[f'baisse.{i}.nom']['v']} {f[f'baisse.{i}.var']['d']}")
    return None, "aucune baisse d'au moins un tiers sur un jeu du top 50 de la semaine"


def course(day):
    jours = mesures(day, 30)
    if len(jours) < 14:
        return None, "moins de 14 jours mesurés consécutifs"
    classe = {d: classement_moy(d)[:8] for d in jours}
    n1 = sorted({classe[d][0][0] for d in jours})
    if len(n1) != 1:
        return None, "le n° 1 a changé : la course pour la 2e place n'a pas de sens"
    deuxieme = [classe[d][1][0] for d in jours]
    chg = sum(1 for j in range(1, len(jours)) if deuxieme[j] != deuxieme[j - 1])
    if chg < 3:
        return None, f"seulement {chg} changement(s) de 2e place"
    cast = set()
    for d in jours:
        cast |= {u for u, _ in classe[d][1:7]}
    noms = {u: next(r["nom"] for d in reversed(jours) for r in rows(d) if r["universe_id"] == u) for u in cast | set(n1)}
    serie = {u: [] for u in cast}
    for d in jours:
        ff = facts(d)
        for u in cast:
            tok = ff.get(f"g.{u}.moy")
            serie[u].append({"v": tok["v"] if tok else 0, "d": tok["d"] if tok else ""})
    return ({"jours": jours, "n1": n1, "noms": noms, "serie": serie, "deuxieme": deuxieme, "n1_tous_les_jours": True,
             "facts": disp(facts(day))}, f"{chg} changements de 2e place en {len(jours)} jours")


def nouveaux(day):
    f = facts(day)
    lim = f["n.recents_jours"]["v"]
    def age(u):
        c = GAMES.get(u, {}).get("created", "")[:10]
        return (D(day) - D(c)).days if c else None
    top = sorted(rows(day), key=lambda r: int(r["rang"]))
    top10 = [{"uid": r["universe_id"], "nom": r["nom"], "rang": int(r["rang"]), "age": age(r["universe_id"]),
              "nouveau": age(r["universe_id"]) is not None and age(r["universe_id"]) <= lim} for r in top[:10]]
    part = f["recents.nb"]["v"] / f["n.top100"]["v"]
    nb10 = sum(r["nouveau"] for r in top10)
    if part < .25 or nb10 < 2:
        return None, f"{f['recents.nb']['d']} jeux récents dans le top 100 et {nb10} dans le top 10 (il en faut 25 et 2)"
    return ({"day": day, "facts": disp(f), "raw": raw(f), "top10": top10,
             "top100": [age(r["universe_id"]) is not None and age(r["universe_id"]) <= lim for r in top[:100]]},
            f"{f['recents.nb']['d']} jeux récents dans le top 100, {nb10} dans le top 10")


def genres(day):
    jours = [os.path.basename(p)[:10] for p in glob.glob("data/jours/*.csv")]
    a = max((d for d in jours if d <= (D(day) - dt.timedelta(days=28)).isoformat()), default=None)
    if not a:
        return None, "pas de jour mesuré 4 semaines avant"
    def sel(d, g):
        return {r["universe_id"]: (r["nom"], int(r["moyenne"])) for r in rows(d) if int(r["rang"]) <= 100 and r["genre"] == g and r.get("complet") == "1"}
    tot = {}
    for g in GENRES:
        sa, sb = sel(a, g), sel(day, g)
        tot[g] = (sum(v for _, v in sa.values()), sum(v for _, v in sb.values()), sa, sb)
    up = max((g for g in tot if tot[g][0] >= 50000 and tot[g][1] >= 100000), key=lambda g: tot[g][1] / tot[g][0], default=None)
    dn = min((g for g in tot if tot[g][0] >= 100000 and tot[g][1] > 0), key=lambda g: tot[g][1] / tot[g][0], default=None)
    if not up or not dn or tot[up][1] / tot[up][0] < 1.5 or tot[dn][0] / tot[dn][1] < 1.5:
        return None, "aucun genre ×1,5 face à un genre ÷1,5 sur 4 semaines"
    out = {"a": a, "b": day, "genres": {}, "facts": disp(facts(day))}
    for role, g in (("up", up), ("down", dn)):
        ta, tb, sa, sb = tot[g]
        jeux = [{"uid": u, "nom": (sb.get(u) or sa.get(u))[0], "a": sa[u][1] if u in sa else None, "b": sb[u][1] if u in sb else None,
                 "nouveau": u not in sa, "sorti": u not in sb} for u in set(sa) | set(sb)]
        jeux.sort(key=lambda j: -max(j["a"] or 0, j["b"] or 0))
        lab, titre, de, q = GENRES[g]
        out["genres"][role] = {"g": g, "lab": lab, "titre": titre, "de": de, "q": q, "a": ta, "b": tb, "jeux": jeux}
    d = out["genres"]["down"]
    big = max((j for j in d["jeux"] if not j["nouveau"] and not j["sorti"]), key=lambda j: j["a"])
    part = (big["a"] - big["b"]) / (d["a"] - d["b"])
    if part < .6:
        return None, f"la baisse {d['de']} ne tient pas à un seul jeu ({part:.0%}) : histoire non validée"
    return out, f"{GENRES[up][1]} ×{tot[up][1] / tot[up][0]:.1f}, {GENRES[dn][1].lower()} ÷{tot[dn][0] / tot[dn][1]:.1f}, {big['nom']} = {part:.0%} de la baisse"


FORMATS = {"duel": duel, "decollage": decollage, "chute": chute, "course": course, "nouveaux": nouveaux, "genres": genres}


def ids(data):
    """universe_id nécessaires à une vidéo : champs uid, liste n1, clés de serie"""
    s = set()
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "uid" and isinstance(v, str):
                    s.add(v)
                elif k == "n1":
                    s.update(v)
                elif k == "serie":
                    s.update(v.keys())
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(data)
    return sorted(u for u in s if u.isdigit())


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "choisir":
        res = {}
        for name, fn in FORMATS.items():
            try:
                data, why = fn(sys.argv[2])
            except Exception as e:  # données absentes ce jour-là
                data, why = None, f"impossible : {e}"
            res[name] = {"possible": data is not None, "raison": why}
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif cmd == "icones":
        print(",".join(ids(json.load(open(sys.argv[2])))))
    else:
        data, why = FORMATS[cmd](sys.argv[2])
        if data is None:
            sys.exit(f"{cmd} impossible le {sys.argv[2]} : {why}")
        json.dump(data, open(sys.argv[3], "w"), ensure_ascii=False)
        print(f"{cmd} {sys.argv[2]} : {why} → {sys.argv[3]}")
