# PlayLedger

Média de données indépendant sur Roblox, en français. Chaque chiffre publié est calculé par programme à partir de relevés publics et relié à sa source.

Non affilié à Roblox Corporation.

## Comment ça marche

| Étape | Qui | Fichiers |
|---|---|---|
| Relevé toutes les heures (API web publiques de Roblox) | GitHub Actions, `tools/collect.py` | `data/snapshots/`, `data/sorts/`, `data/games.csv` |
| Calcul des faits de la veille | `tools/facts.py` | `data/jours/`, `facts/` |
| Rédaction d’un brouillon avec des jetons `{{clé}}` | agent rédacteur (CHAMAWN) | `drafts/` |
| Vérification : aucun chiffre sans source | `tools/verify.py` | |
| Publication | déplacement vers `content/articles/` | |
| Site, classement en direct, flux RSS | `tools/build.py`, GitHub Pages | `_site/` |

Règles de rédaction : [REDACTION.md](REDACTION.md). Méthode publique : [content/methode.md](content/methode.md).

## Commandes

```
python tools/facts.py 2026-10-20        # faits d'une journée
python tools/verify.py drafts/x.md      # vérifie un brouillon
python tools/render.py 2026-10-20 social/x/x.txt   # post X vérifié, en texte final
python tools/build.py --drafts          # construit le site (et les brouillons) dans _site/
```

## Données

Les relevés sont publiés sous licence [ODbL](https://opendatacommons.org/licenses/odbl/1-0/). Le code est sous licence MIT. La police Schibsted Grotesk est sous licence SIL OFL.
