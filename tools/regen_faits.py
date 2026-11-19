"""Recalcule les faits de jours passés avec les règles actuelles de tools/facts.py, sans changer l'histoire.

Les noms, créateurs et genres d'un jeu changent avec le temps (balises d'événement « [🎃] », recatégorisation).
Recalculer un vieux jour avec data/games.csv d'aujourd'hui afficherait les noms d'aujourd'hui. Ce script reprend
donc, pour chaque jour, les noms, créateurs et genres inscrits à l'époque dans data/jours/AAAA-MM-JJ.csv,
puis relance le calcul. Seuls changent les faits que les nouvelles règles corrigent.

Usage : python tools/regen_faits.py AAAA-MM-JJ [AAAA-MM-JJ ...]   (ou --tous : tous les jours de facts/)
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import facts   # noqa: E402

_load_games = common.load_games


def regen(d):
    old = {r["universe_id"]: r for r in common.read_csv(common.DATA / "jours" / f"{d.isoformat()}.csv")}

    def load_games_historique():
        games = _load_games()
        for uid, r in old.items():
            g = games.setdefault(uid, {"universe_id": uid})
            g["name"], g["creator_name"], g["genre_l1"] = r["nom"], r.get("createur", ""), r.get("genre", "")
        return games
    facts.load_games = load_games_historique
    try:
        return facts.build(d)
    finally:
        facts.load_games = _load_games


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--tous"]:
        args = sorted(p.stem for p in common.FACTS.glob("????-??-??.json"))
    for a in args:
        o = regen(date.fromisoformat(a))
        print(f"{a} : {len(o['faits'])} faits, {o['couverture']['releves']}/{o['couverture']['attendus']} relevés")
