"""Prépare le brouillon du quotidien à partir du modèle tools/modeles/quotidien.md.

À lancer après tools/facts.py. Ne fait rien si la journée est incomplète, si le brouillon existe déjà
ou si l'article est déjà publié. Le brouillon est vérifié par tools/verify.py ; s'il échoue, il est supprimé.

Usage : python tools/quotidien.py [AAAA-MM-JJ]   (par défaut : hier, heure de Paris)
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FACTS, ROOT, TZ, slugify, utc_now

MODELE = ROOT / "tools" / "modeles" / "quotidien.md"


def main():
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else (utc_now().astimezone(TZ).date() - timedelta(days=1))
    f = FACTS / f"{d.isoformat()}.json"
    if not f.exists():
        print(f"Pas de faits pour {d} : rien à faire.")
        return 0
    faits = json.loads(f.read_text(encoding="utf-8"))
    cov = faits.get("couverture", {})
    if not cov or cov.get("releves", 0) < cov.get("attendus", 24):
        print(f"Journée incomplète ({cov.get('releves')}/{cov.get('attendus')}) : rien à faire.")
        return 0
    top = faits["faits"].get("top.1.nom", {}).get("v")
    if not top:
        print("Pas de n° 1 dans les faits : rien à faire.")
        return 0
    nom = f"{d.isoformat()}-{slugify(top)}-quotidien.md"
    cible = ROOT / "drafts" / nom
    if cible.exists() or list((ROOT / "content" / "articles").glob(f"{d.isoformat()}-*-quotidien.md")):
        print("Quotidien déjà présent : rien à faire.")
        return 0
    publie = (utc_now().astimezone(TZ) + timedelta(days=0)).strftime("%Y-%m-%dT%H:%M")
    cible.parent.mkdir(exist_ok=True)
    cible.write_text(MODELE.read_text(encoding="utf-8").replace("@JOUR@", d.isoformat()).replace("@PUBLIE@", publie), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "verify.py"), str(cible)], capture_output=True, text=True)
    print(r.stdout + r.stderr)
    if r.returncode != 0:
        cible.unlink()
        print("Vérification échouée : brouillon supprimé.")
        return 1
    print(f"Brouillon créé : {cible.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
