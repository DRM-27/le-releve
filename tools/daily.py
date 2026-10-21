"""Relevés quotidiens (une fois par jour) : game passes du top 100, annonces officielles Roblox, documents SEC.

Lancé à chaque passage horaire, il ne travaille que si le dernier passage a plus de 20 heures.
Écrit :
  data/passes/AAAA-MM-JJ.csv           un passe par ligne : prix en Robux, en vente ou non
  data/officiel/annonces.csv           annonces du forum développeurs (catégorie Announcements) : titre, date, lien
  data/officiel/sec.csv                documents déposés par Roblox Corporation (8-K, 10-Q, 10-K) : date, type, lien
  data/daily_status.json
"""
import json
import sys
import time
import urllib.request
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG, DATA, TZ, iso, parse_iso, read_csv, snap_path, utc_now, write_csv
import glob

UA = "LeReleveBot/1.0 (media de donnees; https://github.com/DRM-27/le-releve)"
STATUS = DATA / "daily_status.json"


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == 2:
                print(f"Échec {url[:90]} : {e}")
                return None
            time.sleep(2 * (i + 1))


def passes(today):
    files = sorted(glob.glob(str(DATA / "snapshots/*/*/*/*.csv")))
    if not files:
        return 0
    top = read_csv(Path(files[-1]))[:100]
    rows = []
    for r in top:
        uid = r["universe_id"]
        token, n = "", 0
        while n < 5:
            q = f"https://apis.roblox.com/game-passes/v1/universes/{uid}/game-passes?passView=Full&pageSize=100" + (f"&pageToken={token}" if token else "")
            d = get_json(q)
            if not d:
                break
            for p in d.get("gamePasses") or []:
                rows.append({"date": today, "universe_id": uid, "pass_id": p.get("id", ""), "nom": p.get("displayName") or p.get("name", ""),
                             "prix": p.get("price") if p.get("isForSale") else "", "en_vente": int(bool(p.get("isForSale"))),
                             "cree": (p.get("created") or "")[:10]})
            token = d.get("nextPageToken") or ""
            n += 1
            if not token:
                break
        time.sleep(0.3)
    if rows:
        write_csv(DATA / "passes" / f"{today}.csv", ["date", "universe_id", "pass_id", "nom", "prix", "en_vente", "cree"], rows)
    return len(rows)


def announcements():
    d = get_json("https://devforum.roblox.com/c/updates/announcements/36.json")
    if not d:
        return 0
    path = DATA / "officiel" / "annonces.csv"
    known = {r["id"]: r for r in read_csv(path)}
    for t in d.get("topic_list", {}).get("topics", []):
        if t.get("slug") == "about-the-announcements-category":
            continue
        known[str(t["id"])] = {"id": t["id"], "titre": t.get("title", ""), "date": t.get("created_at", "")[:19] + "Z",
                               "lien": f"https://devforum.roblox.com/t/{t.get('slug', '')}/{t['id']}"}
    rows = sorted(known.values(), key=lambda r: r["date"], reverse=True)[:200]
    write_csv(path, ["id", "titre", "date", "lien"], rows)
    return len(rows)


def sec():
    contact = CONFIG.get("contact")
    if not contact:
        print("SEC : adresse de contact requise dans config.json (règle d'accès de la SEC).")
        return 0
    d = get_json("https://data.sec.gov/submissions/CIK0001315098.json", {"User-Agent": f"Le Releve {contact}"})
    if not d:
        return 0
    rec = d.get("filings", {}).get("recent", {})
    keep = {"8-K": "Communiqué (8-K)", "10-Q": "Rapport trimestriel (10-Q)", "10-K": "Rapport annuel (10-K)"}
    rows = []
    for i, form in enumerate(rec.get("form", [])):
        if form not in keep:
            continue
        acc = rec["accessionNumber"][i]
        doc = rec.get("primaryDocument", [""] * (i + 1))[i]
        rows.append({"date": rec["filingDate"][i], "type": keep[form], "description": rec.get("primaryDocDescription", [""] * (i + 1))[i],
                     "lien": f"https://www.sec.gov/Archives/edgar/data/1315098/{acc.replace('-', '')}/{doc}"})
        if len(rows) >= 40:
            break
    if rows:
        write_csv(DATA / "officiel" / "sec.csv", ["date", "type", "description", "lien"], rows)
    return len(rows)


def main(force=False):
    now = utc_now()
    st = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    if not force and st.get("lastRunAt") and now - parse_iso(st["lastRunAt"]) < timedelta(hours=20):
        print("Relevé quotidien déjà fait.")
        return
    today = now.astimezone(TZ).date().isoformat()
    res = {"passes": passes(today), "annonces": announcements(), "sec": sec()}
    STATUS.write_text(json.dumps({"lastRunAt": iso(now), **res}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(res)


if __name__ == "__main__":
    main(force="--force" in sys.argv)
