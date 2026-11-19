"""Tests des correctifs de l'audit du 19/11/2026, sur des données FICTIVES (jamais data/ ni facts/ du dépôt).

Lancer : python tests/test_correctifs.py   (ou pytest tests/test_correctifs.py)
Vérifie :
  1. collect.py refait les lots perdus (HTTP 429) et liste les jeux non mesurés ;
  2. facts.py : un jeu absent la veille n'est pas une entrée (c'est un retour) ; une vraie entrée a son rang de la veille ;
     une mesure partielle n'a pas de variation ; un pic d'une heure est marqué ponctuel, avec le rang à la moyenne ;
  3. verify.py bloque : journée incomplète non dite, « reste en tête » sans n° 1 la veille, « en une semaine »,
     « entre dans le top 50 » sans entrée établie, pic ponctuel non signalé ;
  4. quotidien.py écrit les phrases obligatoires et passe le vérificateur.
"""
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="releve-test-"))
os.environ["MEDIA_DATA_DIR"] = str(TMP / "data")
os.environ["MEDIA_FACTS_DIR"] = str(TMP / "facts")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import common  # noqa: E402
from common import GAME_FIELDS, SNAP_FIELDS, TZ, UTC, iso, snap_path, write_csv  # noqa: E402

JOUR = date(2026, 11, 18)
N_JEUX = 80


def uid(i):
    return str(5_000_000 + i)


def ecrire_releves():
    """9 jours de relevés. Jeu 0 : n° 1. Jeu 60 : absent la veille (mais dans le top 50 avant) puis très joué.
    Jeu 61 : vraie entrée (mesuré la veille, hors top 50). Jeu 62 : mesuré 12 h sur 24 le jour J.
    Jeu 1 : pic d'une heure le jour J."""
    games = [{"universe_id": uid(i), "root_place_id": "1", "name": f"FICTIF Jeu {i}", "creator_name": "Studio Test",
              "creator_type": "Group", "creator_verified": 0, "genre_l1": ("Simulation", "Survival", "Action")[i % 3], "genre_l2": "",
              "created": "2026-11-01T00:00:00Z", "updated": "", "max_players": 10, "first_seen": "", "last_in_sort": "", "icon": ""}
             for i in range(N_JEUX)]
    write_csv(common.DATA / "games.csv", GAME_FIELDS, games)
    debut = datetime(JOUR.year, JOUR.month, JOUR.day, tzinfo=TZ) - timedelta(days=8)
    for h in range(9 * 24):
        t = (debut + timedelta(hours=h)).astimezone(UTC)
        jour_local = t.astimezone(TZ).date()
        heure = t.astimezone(TZ).hour
        rows = []
        for i in range(N_JEUX):
            v = 100_000 // (i + 1) + 500
            if i == 60:
                if jour_local == JOUR - timedelta(days=1):
                    continue                      # absent toute la veille
                v = 60_000 if jour_local in (JOUR, JOUR - timedelta(days=4)) else 900
            if i == 61:
                v = 40_000 if jour_local == JOUR else 2_000
            if i == 62 and jour_local == JOUR and heure < 12:
                continue                          # mesuré 12 h sur 24
            if i == 1 and jour_local == JOUR and heure == 20:
                v = 400_000                       # pic d'une heure
            rows.append({"ts_utc": iso(t), "universe_id": uid(i), "playing": v, "visits": 10_000 + h, "favorites": 1,
                         "up_votes": 90, "down_votes": 10})
        write_csv(snap_path("snapshots", t), SNAP_FIELDS, rows)


def faits():
    import facts
    return facts.build(JOUR)["faits"]


def test_facts():
    F = faits()
    noms_entrees = [F[k]["v"] for k in F if k.startswith("entree.") and k.endswith(".nom")]
    noms_retours = [F[k]["v"] for k in F if k.startswith("retour.") and k.endswith(".nom")]
    assert "FICTIF Jeu 60" not in noms_entrees, "un jeu absent la veille ne doit pas être une entrée"
    assert "FICTIF Jeu 60" in noms_retours, "un jeu absent la veille, dans le top 50 avant, est un retour"
    assert "FICTIF Jeu 61" in noms_entrees, "un jeu mesuré la veille hors du top 50 est une entrée"
    k = next(k for k in F if k.startswith("entree.") and k.endswith(".nom") and F[k]["v"] == "FICTIF Jeu 61")[:-4]
    assert F[k + ".rang_veille"]["v"] > 50
    g62 = f"g.{uid(62)}"
    assert f"{g62}.nom" in F and f"{g62}.var_7j" not in F and f"{g62}.var_veille" not in F, "mesure partielle : pas de variation"
    g1 = f"g.{uid(1)}"
    assert F[f"{g1}.pic_isole"]["v"] is True and F[f"{g1}.rang_moy"]["v"] == 2
    assert F["top.1.nom"]["v"] == "FICTIF Jeu 1", "le pic d'une heure place le jeu 1er au pic"
    assert F[f"g.{uid(0)}.pic_isole"]["v"] is False
    return F


def article(nom, titre, corps, jour=JOUR.isoformat()):
    p = TMP / "articles" / nom
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitre: {titre}\nchapo: Le {{{{jour.date_courte}}}}, un fait.\njour: {jour}\ntype: analyse\npublie: 2026-11-19T08:00\n---\n"
                 + corps + "\n\n" + "Texte de remplissage pour la longueur. " * 20, encoding="utf-8")
    return p


def erreurs(p):
    import verify
    e, _, _, _ = verify.verify(p)
    return e


def test_verify():
    base = "{{top.2.nom}} est {{top.2.rang}} avec un pic de {{top.2.pic}} joueurs."
    assert not erreurs(article("ok.md", "{{top.1.nom}} en tête", base))
    assert any("en une semaine" in x for x in erreurs(article("sem.md", "{{hausse.1.nom}} : {{hausse.1.var}} en une semaine", base)))
    assert any("entre dans le top 50" in x for x in erreurs(article("ent.md", "Un jeu entre dans le top 50", base)))
    assert any("ponctuel" in x for x in erreurs(article("pic.md", "{{top.1.nom}} en tête", "{{top.1.nom}} : pic de {{top.1.pic}}.")))
    assert not erreurs(article("pic2.md", "{{top.1.nom}} en tête", "{{top.1.nom}} : pic ponctuel de {{top.1.pic}}."))


def test_quotidien():
    import quotidien
    F = json.loads((common.FACTS / f"{JOUR.isoformat()}.json").read_text(encoding="utf-8"))["faits"]
    for lang in quotidien.MODELES:
        txt = quotidien.ecrire(lang, "top", 1, F, JOUR.isoformat(), "2026-11-19T08:00")
        p = TMP / "q" / lang / f"{JOUR.isoformat()}-test-quotidien.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")
        assert not erreurs(p), (lang, erreurs(p))      # dont la mention du pic ponctuel du n° 1
    F2 = dict(F)
    F2.pop("top.1.rang_veille", None)
    assert "reste en tête" not in quotidien.ecrire("fr", "top", 1, F2, JOUR.isoformat(), "x")
    F3 = dict(F)
    F3["releves.nb"] = {"v": 15, "d": "15"}
    assert "Journée incomplète" in quotidien.ecrire("fr", "top", 1, F3, JOUR.isoformat(), "x")


def test_collect():
    """Un lot perdu (HTTP 429) est refait ; seuls les jeux jamais servis sont listés comme non mesurés."""
    import collect
    collect.time.sleep = lambda s: None
    appels = {}

    def faux_get_json(url, tries=6):
        if "get-sorts" in url or "thumbnails" in url or "icons" in url:
            return {}
        ids = url.split("universeIds=")[1].split("&")[0].split(",")
        cle = (url.split("?")[0], ids[0])
        appels[cle] = appels.get(cle, 0) + 1
        if "votes" in url:
            return {"data": [{"id": int(i), "upVotes": 1, "downVotes": 0} for i in ids]}
        if ids[0] == uid(0) and appels[cle] == 1:
            return None                       # premier essai du premier lot : HTTP 429
        if uid(79) in ids:
            ids = [i for i in ids if i != uid(79)]   # jeu indisponible : l'API ne le renvoie pas
        return {"data": [{"id": int(i), "playing": 10, "visits": 1, "favoritedCount": 1, "rootPlaceId": 1,
                          "creator": {"name": "x"}, "name": f"FICTIF Jeu {int(i) - 5_000_000}"} for i in ids]}
    collect.get_json = faux_get_json
    collect.fetch_sorts = lambda session: {"top-playing-now": [{"universeId": int(uid(i)), "name": "x"} for i in range(N_JEUX)]}
    collect.main()
    st = json.loads((common.DATA / "status.json").read_text(encoding="utf-8"))
    assert st["lotsRelances"] == 1, st
    assert st["jeuxNonMesures"]["nb"] == 0, st
    assert st["jeuxIndisponibles"]["ids"] == [uid(79)], st
    assert st["ok"] is True


if __name__ == "__main__":
    ecrire_releves()
    test_facts()
    test_verify()
    test_quotidien()
    test_collect()
    print("OK : tous les tests des correctifs passent.", TMP)
else:  # pytest
    ecrire_releves()
