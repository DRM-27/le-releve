"""Vérifie puis affiche en texte brut un post (X, script vidéo) écrit avec des jetons.

Usage : python tools/render.py AAAA-MM-JJ social/x/fichier.txt
Le jour sert de référence pour les jetons sans date. Refuse si un chiffre est tapé à la main ou si un jeton est inconnu.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify import TOKEN, fact_for, verify_text

day, path = sys.argv[1], Path(sys.argv[2])
text = path.read_text(encoding="utf-8").strip()
errors, warnings = [], []
verify_text(text, day, path.name, errors, warnings)
if errors:
    sys.exit("BLOQUÉ\n  " + "\n  ".join(errors))
out = TOKEN.sub(lambda m: fact_for(m.group(1) or day, m.group(2))["d"], text)
for w in warnings:
    print("⚠", w, file=sys.stderr)
print(out)
if len(out) > 280 and "/x/" in str(path):
    sys.exit(f"Trop long pour X : {len(out)} caractères (280 au plus).")
