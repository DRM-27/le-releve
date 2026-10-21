"""Chiffres officiels de Roblox Corporation -> jetons officiel.<trimestre>.<indicateur>.

Source unique : data/official/roblox-trimestriel.csv, saisi depuis les communiqués de ir.roblox.com,
une ligne par chiffre avec son lien. Écrit facts/officiel.json et facts/officiel.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, FACTS, fr_big, fr_dec, fr_int, fr_pct, iso, read_csv, utc_now

UNITS = {"usd": lambda v: fr_big(v) + " de dollars", "pct": lambda v: fr_pct(v), "count": fr_big, "hours": lambda v: fr_big(v) + " d’heures",
         "usd_per_user": lambda v: fr_dec(v, 2) + " $"}
rows = read_csv(DATA / "official" / "roblox-trimestriel.csv")
F = {}
for r in rows:
    if not r.get("source_url", "").startswith("https://"):
        sys.exit(f"Ligne sans lien source : {r}")
    v = float(r["valeur"])
    key = f"officiel.{r['trimestre'].lower()}.{r['indicateur']}"
    fmt = UNITS.get(r["unite"], fr_big)
    F[key] = {"v": v, "d": fmt(v), "l": f"Roblox Corporation, {r['trimestre']} : {r['indicateur']} (publié le {r['date_publication']})",
              "src": r["source_url"]}
FACTS.mkdir(parents=True, exist_ok=True)
(FACTS / "officiel.json").write_text(json.dumps({"jour": "officiel", "genere": iso(utc_now()), "couverture": {"releves": 24, "attendus": 24},
                                                 "faits": F, "graphiques": {}}, ensure_ascii=False, indent=1), encoding="utf-8")
(FACTS / "officiel.md").write_text("# Chiffres officiels\n\n| Jeton | Affichage | Signification |\n|---|---|---|\n" +
                                   "".join(f"| `{{{{{k}}}}}` | {f['d']} | {f['l']} |\n" for k, f in F.items()), encoding="utf-8")
print(f"{len(F)} chiffres officiels")
