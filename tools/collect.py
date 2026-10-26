"""Relevé horaire des jeux Roblox, à partir des API web publiques de Roblox.

Écrit :
  data/sorts/AAAA/MM/JJ/HH.csv      position de chaque jeu dans les classements de la page Découvrir
  data/snapshots/AAAA/MM/JJ/HH.csv  joueurs en ligne, visites, favoris, votes de chaque jeu suivi
  data/games.csv                    fiche de chaque jeu suivi (nom, créateur, genre, dates)
  data/status.json                  état du dernier relevé
Un jeu est suivi dès qu'il apparaît dans un classement, et le reste 14 jours après sa dernière apparition,
pour pouvoir mesurer aussi les baisses.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import (CONFIG, DATA, GAME_FIELDS, SNAP_FIELDS, SORT_FIELDS, iso, load_games, parse_iso,
                    read_csv, snap_path, utc_now, write_csv)

UA = "PlayLedgerBot/1.0 (media de donnees; releves horaires publics)"
EXPLORE = "https://apis.roblox.com/explore-api/v1"
GAMES = "https://games.roblox.com/v1/games"
ICONS = "https://thumbnails.roblox.com/v1/games/icons"
BATCH = 50
errors = []


def get_json(url, tries=4):
    delay = 2
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            errors.append(f"HTTP {e.code} {url[:120]}")
            return None
        except Exception as e:  # réseau, JSON
            if i < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            errors.append(f"{type(e).__name__} {url[:120]}")
            return None


def fetch_sorts(session):
    """Classements de la page Découvrir : top-playing-now, top-trending, up-and-coming…"""
    q = urllib.parse.urlencode({"sessionId": session, "device": "computer", "country": "all"})
    data = get_json(f"{EXPLORE}/get-sorts?{q}") or {}
    sorts = {}
    for s in data.get("sorts", []):
        if s.get("contentType") == "Games" and s.get("sortId"):
            sorts[s["sortId"]] = list(s.get("games") or [])
    # Contenu complet de chaque classement (jusqu'à 3 pages)
    for sort_id in list(sorts):
        games, token = [], ""
        for _ in range(3):
            params = {"sessionId": session, "sortId": sort_id, "device": "computer", "country": "all"}
            if token:
                params["pageToken"] = token
            page = get_json(f"{EXPLORE}/get-sort-content?{urllib.parse.urlencode(params)}")
            if not page:
                break
            games += page.get("games") or []
            token = page.get("nextPageToken") or ""
            if not token:
                break
            time.sleep(0.5)
        if len(games) > len(sorts[sort_id]):
            sorts[sort_id] = games
    return sorts


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    now = utc_now()
    ts = iso(now)
    session = str(uuid.uuid4())
    cfg = CONFIG.get("tracking", {})
    keep = timedelta(days=cfg.get("keepDaysAfterSort", 14))
    max_games = cfg.get("maxGames", 1500)

    games = load_games()
    sorts = fetch_sorts(session)

    sort_rows, in_sort = [], {}
    for sort_id, items in sorts.items():
        for pos, g in enumerate(items, 1):
            uid = str(g.get("universeId") or "")
            if not uid:
                continue
            sponsored = bool(g.get("isSponsored"))
            sort_rows.append({"ts_utc": ts, "sort_id": sort_id, "position": pos, "universe_id": uid,
                              "player_count": g.get("playerCount", ""), "is_sponsored": int(sponsored)})
            if not sponsored:
                in_sort.setdefault(uid, g)

    # Jeux à suivre : présents dans un classement maintenant, ou dans les 14 derniers jours
    for uid, g in in_sort.items():
        rec = games.setdefault(uid, {"universe_id": uid, "first_seen": ts})
        rec["last_in_sort"] = ts
        rec.setdefault("name", g.get("name", ""))
        rec.setdefault("root_place_id", g.get("rootPlaceId", ""))
    tracked = [uid for uid, r in games.items()
               if r.get("last_in_sort") and now - parse_iso(r["last_in_sort"]) <= keep]

    # Détail de chaque jeu suivi
    snap, details = {}, {}
    for part in chunks(tracked, BATCH):
        ids = ",".join(part)
        d = get_json(f"{GAMES}?universeIds={ids}") or {}
        for g in d.get("data") or []:
            details[str(g["id"])] = g
        v = get_json(f"{GAMES}/votes?universeIds={ids}") or {}
        for g in v.get("data") or []:
            snap.setdefault(str(g["id"]), {}).update(up_votes=g.get("upVotes", ""), down_votes=g.get("downVotes", ""))
        time.sleep(0.4)

    snap_rows, updates = [], []
    for uid, g in details.items():
        row = {"ts_utc": ts, "universe_id": uid, "playing": g.get("playing", 0), "visits": g.get("visits", ""),
               "favorites": g.get("favoritedCount", ""), **snap.get(uid, {})}
        snap_rows.append(row)
        rec = games[uid]
        old_upd = rec.get("updated", "")
        if old_upd and g.get("updated") and g["updated"] != old_upd:
            updates.append({"ts_utc": ts, "universe_id": uid, "nom": g.get("name", rec.get("name", "")), "avant": old_upd,
                            "apres": g["updated"], "joueurs": g.get("playing", 0)})
        creator = g.get("creator") or {}
        rec.update(root_place_id=g.get("rootPlaceId", rec.get("root_place_id", "")), name=g.get("name", rec.get("name", "")),
                   creator_name=creator.get("name", ""), creator_type=creator.get("type", ""),
                   creator_verified=int(bool(creator.get("hasVerifiedBadge"))),
                   genre_l1=g.get("genre_l1", ""), genre_l2=g.get("genre_l2", ""),
                   created=g.get("created", ""), updated=g.get("updated", ""), max_players=g.get("maxPlayers", ""))

    # Icône officielle de chaque jeu (adresse sur le CDN de Roblox)
    for part in chunks(list(details), BATCH):
        ic = get_json(f"{ICONS}?universeIds={','.join(part)}&returnPolicy=PlaceHolder&size=150x150&format=Png&isCircular=false") or {}
        for x in ic.get("data") or []:
            if x.get("state") == "Completed" and x.get("imageUrl", "").startswith("https://"):
                games[str(x["targetId"])]["icon"] = x["imageUrl"]
        time.sleep(0.3)

    # Limite de taille : on garde les jeux les plus joués si la liste déborde
    if len(games) > max_games:
        playing = {r["universe_id"]: int(r["playing"] or 0) for r in snap_rows}
        recent = sorted(games, key=lambda u: (games[u].get("last_in_sort", ""), playing.get(u, 0)), reverse=True)
        games = {u: games[u] for u in recent[:max_games]}

    snap_rows.sort(key=lambda r: -int(r["playing"] or 0))
    if sort_rows:
        write_csv(snap_path("sorts", now), SORT_FIELDS, sort_rows)
    if snap_rows:
        write_csv(snap_path("snapshots", now), SNAP_FIELDS, snap_rows)
    write_csv(DATA / "games.csv", GAME_FIELDS, sorted(games.values(), key=lambda r: int(r["universe_id"])))

    if updates:
        upath = DATA / "mises-a-jour.csv"
        old = read_csv(upath)
        write_csv(upath, ["ts_utc", "universe_id", "nom", "avant", "apres", "joueurs"], old + updates)
    prev_status = json.loads((DATA / "status.json").read_text(encoding="utf-8")) if (DATA / "status.json").exists() else {}
    fails = 0 if snap_rows else int(prev_status.get("echecsConsecutifs", 0)) + 1
    status = {"echecsConsecutifs": fails, "dernierSucces": ts if snap_rows else prev_status.get("dernierSucces", prev_status.get("lastRunAt")),
              "lastRunAt": ts, "ok": bool(snap_rows) and not errors, "sorts": {k: len(v) for k, v in sorts.items()},
              "gamesTracked": len(tracked), "gamesMeasured": len(snap_rows), "errors": errors[:20]}
    (DATA / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    if not snap_rows:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # on garde la trace dans status.json pour diagnostiquer l'échec depuis le dépôt
        import traceback
        tb = traceback.format_exc()
        print(tb)
        prev = json.loads((DATA / "status.json").read_text(encoding="utf-8")) if (DATA / "status.json").exists() else {}
        prev.update(ok=False, lastRunAt=iso(utc_now()), echecsConsecutifs=int(prev.get("echecsConsecutifs", 0)) + 1,
                    errors=(errors + tb.strip().splitlines()[-6:])[:20])
        (DATA / "status.json").write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
        sys.exit(1)
