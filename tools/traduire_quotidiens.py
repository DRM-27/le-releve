"""Écrit les traductions (en, es, pt-br) des quotidiens publiés à partir des modèles traduits.

Un quotidien n'est traduit automatiquement que si son texte français est exactement le modèle
tools/modeles/quotidien.md (seuls jour et publie changent) : les chiffres viennent des mêmes jetons,
donc la traduction dit la même chose. Un quotidien retouché à la main n'est pas traduit ici.
Une traduction déjà présente n'est jamais réécrite. Chaque fichier écrit passe tools/verify.py.

Usage : python tools/traduire_quotidiens.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELE = ROOT / "tools" / "modeles" / "quotidien.md"
LANGS = ["en", "es", "pt-br"]


def norm(text):
    text = re.sub(r"(?m)^jour: .*$", "jour: @JOUR@", text)
    return re.sub(r"(?m)^publie: .*$", "publie: @PUBLIE@", text).strip()


def field(text, name):
    m = re.search(rf"(?m)^{name}: (.*)$", text)
    return m.group(1).strip() if m else None


def main():
    modele = norm(MODELE.read_text(encoding="utf-8"))
    ecrits = 0
    for fr in sorted((ROOT / "content" / "articles").glob("*-quotidien.md")):
        texte = fr.read_text(encoding="utf-8")
        if norm(texte) != modele:
            continue
        jour, publie = field(texte, "jour"), field(texte, "publie")
        for lang in LANGS:
            cible = ROOT / "content" / "i18n" / lang / "articles" / fr.name
            src = ROOT / "tools" / "modeles" / "i18n" / lang / "quotidien.md"
            if cible.exists() or not src.exists():
                continue
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(src.read_text(encoding="utf-8").replace("@JOUR@", jour).replace("@PUBLIE@", publie), encoding="utf-8")
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "verify.py"), str(cible)], capture_output=True, text=True)
            if r.returncode != 0:
                print(r.stdout + r.stderr)
                cible.unlink()
                continue
            ecrits += 1
            print(f"Traduit : {cible.relative_to(ROOT)}")
    print(f"{ecrits} traduction(s) écrite(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
