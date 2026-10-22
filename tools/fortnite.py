"""Collecte Fortnite (îles créées par les joueurs) via l'API publique d'Epic : https://api.fortnite.com/ecosystem/v1

L'API ne garde que 7 jours : tout ce qui n'est pas archivé ici est perdu. Rien n'est publié sur le site pour l'instant.

À chaque passage horaire :
  - joueurs simultanés de tout Fortnite, par heure        -> data/fortnite/ecosysteme.csv (dédoublonné)
  - classement des 50 premières îles de chaque genre     -> data/fortnite/classements/AAAA/MM/JJ/HH.csv
    (rattrape les heures manquantes des dernières 48 h grâce au paramètre at=)
  - fiche des îles nouvellement classées                    -> data/fortnite/iles.csv
Une fois par jour (premier passage après minuit UTC), pour chaque île classée :
  - métriques quotidiennes (joueurs uniques, parties, minutes, rétention J1/J7...) -> data/fortnite/jours/AAAA-MM-JJ.csv
  - pic de joueurs simultanés heure par heure                                      -> data/fortnite/heures/AAAA-MM-JJ.csv
  (rattrape les jours manquants dans la fenêtre de 7 jours)
État : data/fortnite/status.json
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, read_csv, write_csv

BASE = "https://api.fortnite.com/ecosystem/v1"
UA = "PlayLedgerBot/1.0 (media de donnees; https://github.com/DRM-27/le-releve)"
FN = DATA / "fortnite"
TOP_PER_GENRE = 50
WORKERS = 6
ERRORS = []

DAY_FIELDS = ["date", "code", "unique_players", "plays", "minutes_played", "avg_minutes_per_player", "peak_ccu", "favorites", "recommendations",
              "retention_d1", "retention_d7"]
API_DAY = {"uniquePlayers": "unique_players", "plays": "plays", "minutesPlayed": "minutes_played", "averageMinutesPerPlayer": "avg_minutes_per_player",
           "peakCCU": "peak_ccu", "favorites": "favorites", "recommendations": "recommendations"}
ISLAND_FIELDS = ["code", "titre", "createur", "cree_dans", "categorie", "tags", "premiere_vue"]


def ts(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def get(path, params=None, tries=5):
    q = urllib.parse.urlencode(params or {}, doseq=True, safe=":")
    url = BASE + path + ("?" + q if q else "")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                ra = e.headers.get("Retry-After")
                time.sleep(min(float(ra) if ra and ra.isdigit() else 2 ** i, 60))
                continue
            ERRORS.append(f"{e.code} {path}")
            return None
        except Exception as e:
            if i < tries - 1:
                time.sleep(2 ** i)
                continue
            ERRORS.append(f"réseau {path}: {e}")
            return None


def series(payload, key):
    """Les réponses mettent une série soit directement sous la clé, soit sous {intervals: [...]}."""
    if not payload:
        return []
    v = payload.get(key, payload.get("intervals")) if isinstance(payload, dict) else None
    if isinstance(v, dict):
        v = v.get("intervals")
    return v or []


# ------------------------------------------------------------------ toutes les heures
def ecosystem(now):
    p = FN / "ecosysteme.csv"
    rows = {r["ts_utc"]: r for r in read_csv(p)}
    d = get("/metrics/hour", {"from": ts(now - timedelta(hours=48)), "to": ts(now)})
    added = 0
    if d:
        im = {x["timestamp"]: x.get("value") for x in series(d, "inMatchPeakCCU")}
        ic = {x["timestamp"]: x.get("value") for x in series(d, "inClientPeakCCU")}
        for t in sorted(set(im) | set(ic)):
            r = {"ts_utc": t, "in_match_peak_ccu": im.get(t) if im.get(t) is not None else "", "in_client_peak_ccu": ic.get(t) if ic.get(t) is not None else ""}
            if rows.get(t) != r:
                added += t not in rows
                rows[t] = r
    write_csv(p, ["ts_utc", "in_match_peak_ccu", "in_client_peak_ccu"], [rows[k] for k in sorted(rows)])
    return added


def genres():
    d = get("/genres")
    return [g["slug"] for g in (d or {}).get("data", [])]


def ranking_path(snap):
    return FN / "classements" / f"{snap:%Y}" / f"{snap:%m}" / f"{snap:%d}" / f"{snap:%H}.csv"


def rankings(now, slugs):
    """Classement de l'heure (et rattrapage des heures manquantes sur 48 h)."""
    done = 0
    codes = set()
    hours = [now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=k) for k in range(0, 48)]
    todo = [h for h in hours if not ranking_path(h).exists()][:12]
    for h in todo:
        rows = []
        for slug in slugs:
            params = {"size": TOP_PER_GENRE}
            if h != hours[0]:
                params["at"] = ts(h)
            d = get(f"/genres/{slug}/rankings", params)
            if not d or not d.get("meta", {}).get("snapshotAvailable", True):
                continue
            snap = d.get("meta", {}).get("snapshot", ts(h))
            for it in d.get("data", []):
                rows.append({"snapshot": snap, "genre": slug, "rang": it.get("rank"), "code": it.get("islandCode"),
                             "total_genre": d.get("meta", {}).get("total", "") if it.get("rank") == 1 else ""})
        if rows:
            snap = datetime.strptime(rows[0]["snapshot"][:13], "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
            write_csv(ranking_path(snap), ["genre", "rang", "code", "total_genre"], rows)
            codes |= {r["code"] for r in rows}
            done += 1
    return done, codes


def islands_meta(codes, now):
    p = FN / "iles.csv"
    known = {r["code"]: r for r in read_csv(p)}
    new = [c for c in codes if c and c not in known]

    def one(c):
        d = get(f"/islands/{c}")
        if not d:
            return None
        d = d.get("data", d)
        return {"code": c, "titre": d.get("title", ""), "createur": d.get("creatorCode", "") or d.get("displayName", ""),
                "cree_dans": d.get("createdIn", ""), "categorie": d.get("category", ""), "tags": "|".join(d.get("tags") or []),
                "premiere_vue": now.strftime("%Y-%m-%dT%H:%MZ")}

    with ThreadPoolExecutor(WORKERS) as ex:
        for r in ex.map(one, new):
            if r:
                known[r["code"]] = r
    write_csv(p, ISLAND_FIELDS, [known[k] for k in sorted(known)])
    return len(new)


# ------------------------------------------------------------------ une fois par jour
def tracked_codes():
    files = sorted(FN.glob("classements/*/*/*/*.csv"))
    return sorted({r["code"] for r in read_csv(files[-1])} if files else set())


def daily(now):
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = [today - timedelta(days=k) for k in range(1, 7)]
    missing = [d for d in days if not (FN / "jours" / f"{d:%Y-%m-%d}.csv").exists()]
    if not missing:
        return None
    start = min(missing) if min(missing) > now - timedelta(days=7) else today - timedelta(days=6)
    codes = tracked_codes()
    per_day = {d.strftime("%Y-%m-%d"): [] for d in missing}
    per_hour = {d.strftime("%Y-%m-%d"): [] for d in missing}

    def one(code):
        out_d, out_h = [], []
        dd = get(f"/islands/{code}/metrics/day", {"from": ts(start), "to": ts(today)})
        if dd:
            byday = {}
            for k, f in API_DAY.items():
                for x in series(dd, k):
                    byday.setdefault(x["timestamp"][:10], {})[f] = "" if x.get("value") is None else x["value"]
            for x in series(dd, "retention"):
                r = byday.setdefault(x["timestamp"][:10], {})
                r["retention_d1"] = "" if x.get("d1") is None else x["d1"]
                r["retention_d7"] = "" if x.get("d7") is None else x["d7"]
            for day, r in byday.items():
                out_d.append({"date": day, "code": code, **{f: r.get(f, "") for f in DAY_FIELDS[2:]}})
        hh = get(f"/islands/{code}/metrics/hour/peak-ccu", {"from": ts(start), "to": ts(today)})
        for x in series(hh, "peakCCU"):
            if x.get("value") is not None:
                out_h.append({"date": x["timestamp"][:10], "heure": x["timestamp"][11:13], "code": code, "peak_ccu": x["value"]})
        return out_d, out_h

    with ThreadPoolExecutor(WORKERS) as ex:
        for out_d, out_h in ex.map(one, codes):
            for r in out_d:
                if r["date"] in per_day:
                    per_day[r["date"]].append(r)
            for r in out_h:
                if r["date"] in per_hour:
                    per_hour[r["date"]].append(r)
    written = 0
    for day, rows in per_day.items():
        if rows:
            write_csv(FN / "jours" / f"{day}.csv", DAY_FIELDS, sorted(rows, key=lambda r: r["code"]))
            written += 1
        if per_hour[day]:
            write_csv(FN / "heures" / f"{day}.csv", ["date", "heure", "code", "peak_ccu"], sorted(per_hour[day], key=lambda r: (r["code"], r["heure"])))
    return written


def main():
    now = datetime.now(timezone.utc)
    st_path = FN / "status.json"
    st = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {}
    res = {}
    res["ecosysteme_nouvelles_heures"] = ecosystem(now)
    slugs = genres()
    res["genres"] = len(slugs)
    n, codes = rankings(now, slugs) if slugs else (0, set())
    res["classements_ecrits"] = n
    res["nouvelles_iles"] = islands_meta(codes, now)
    if not st.get("dailyAt") or st["dailyAt"][:10] != now.strftime("%Y-%m-%d"):
        w = daily(now)
        res["jours_ecrits"] = w or 0
        if w is None or w > 0:
            st["dailyAt"] = now.strftime("%Y-%m-%dT%H:%MZ")
    st.update({"lastRunAt": now.strftime("%Y-%m-%dT%H:%MZ"), "dernier": res, "erreurs": ERRORS[:20], "nbErreurs": len(ERRORS),
               "ilesSuivies": len(read_csv(FN / "iles.csv"))})
    st_path.parent.mkdir(parents=True, exist_ok=True)
    st_path.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(st, ensure_ascii=False))


if __name__ == "__main__":
    main()
