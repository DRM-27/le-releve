"""Chiffres publiés par des tiers (presse, fiches publiques) -> jetons ext.<clé>.

Source unique : data/sources/externes.csv, une ligne par chiffre avec le lien exact et la date de la source.
On ne saisit que des chiffres publiés tels quels ; « environ » ou « plus de » vont dans le libellé, que l'article doit respecter.
Écrit facts/externe.json et facts/externe.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, FACTS, fr_big, fr_int, iso, read_csv, utc_now

FMT = {"count": fr_big, "int": fr_int}
F = {}
for r in read_csv(DATA / "sources" / "externes.csv"):
    if not r["source_url"].startswith("https://"):
        sys.exit(f"Ligne sans lien source : {r}")
    v = float(r["valeur"])
    v = int(v) if v.is_integer() else v
    F[f"ext.{r['cle']}"] = {"v": v, "d": FMT.get(r["unite"], fr_big)(v), "l": f"{r['libelle']} (source : {r['source_nom']}, {r['date_source']})",
                           "src": r["source_url"]}
FACTS.mkdir(parents=True, exist_ok=True)
(FACTS / "externe.json").write_text(json.dumps({"jour": "externe", "genere": iso(utc_now()), "couverture": {"releves": 24, "attendus": 24},
                                                "faits": F, "graphiques": {}}, ensure_ascii=False, indent=1), encoding="utf-8")
(FACTS / "externe.md").write_text("# Chiffres de sources tierces\n\n| Jeton | Affichage | Signification |\n|---|---|---|\n" +
                                  "".join(f"| `{{{{{k}}}}}` | {f['d']} | {f['l']} |\n" for k, f in F.items()), encoding="utf-8")
print(f"{len(F)} chiffres externes")
