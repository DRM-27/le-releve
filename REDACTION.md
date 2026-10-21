# Charte de la rédaction

Ce fichier fait autorité pour tous les agents qui écrivent ou relisent un article. Le site s’adresse aux professionnels de Roblox : développeurs, studios, marques, investisseurs. Ton : précis, sobre, factuel, sans superlatifs ni emojis. On écrit en français, au présent ou au passé composé.

## La règle d’or : aucun chiffre tapé à la main

- Tous les chiffres viennent du fichier de faits du jour (`facts/AAAA-MM-JJ.md` pour la liste lisible, `.json` pour le détail).
- On les écrit avec leur jeton : `{{top.1.pic}}`. Pour un autre jour : `{{2026-10-19:top.1.pic}}`.
- Le titre et le chapô suivent la même règle.
- Seules exceptions tolérées : années, dates en toutes lettres (« 20 octobre »), et les repères de méthode « top 10 », « 7 jours », « 24 h ».
- Pas de nombres en lettres pour contourner la règle (« trois jeux », « deux fois plus »). Si un calcul manque, on ne l’écrit pas : on le note dans le rapport pour qu’il soit ajouté au programme.
- Un fait absent du fichier n’existe pas. On ne complète jamais avec sa mémoire ou une recherche web, sauf pour les chiffres officiels de Roblox Corporation, qui passent par `data/official/` avec leur lien (voir plus bas).

## Ce qu’un chiffre veut dire

- **Pic** : le plus haut des relevés horaires, pas le pic exact. On écrit « un pic relevé de… ».
- **Moyenne** : moyenne des relevés de la journée (heure de Paris).
- **Total des jeux suivis** (`cumul.*`) : ce n’est jamais « les joueurs de Roblox ». On écrit « sur les jeux que nous suivons ».
- **Variation** : toujours dire la référence (« par rapport à la veille », « par rapport aux 7 jours précédents » : jeton `{{mouv.reference}}`).
- **Rang** : rang au pic du jour parmi les jeux suivis.
- Corrélation n’est pas cause. On n’explique une hausse par une mise à jour, un événement ou une vidéo que si une source datée le montre, citée avec un lien. Sinon on décrit le mouvement sans l’expliquer.
- Journée incomplète (moins de 18 relevés) : on le dit dans le texte.

## Formats

| Type | Quand | Contenu |
|---|---|---|
| `quotidien` | chaque matin, sur la veille | 250 à 400 mots. Le n° 1, une ou deux hausses, une baisse, un fait de structure (genres, concentration, jeux récents). Graphiques `top10` et `variations`. |
| `hebdo` | le lundi, sur la semaine écoulée | 600 à 900 mots. Compare les jours avec des jetons datés. Une tendance de fond, expliquée prudemment. |
| `mensuel` | le 1er du mois | Rapport complet du mois. |
| `trimestriel` | après chaque publication de résultats de Roblox Corporation | Décryptage des chiffres officiels. |
| `analyse` | quand un mouvement le justifie | Un sujet, un angle, sourcé. |

## Structure d’un fichier

```
---
titre: {{top.1.nom}} creuse l'écart, {{hausse.1.nom}} bondit de {{hausse.1.var}}
chapo: Une phrase qui dit l'essentiel, avec ses jetons.
jour: 2026-10-20
type: quotidien
publie: 2026-10-21T08:30
---
Texte en Markdown. Intertitres en `##`. Graphiques sur une ligne seule : {{graphique:top10}}
```

Nom du fichier : `AAAA-MM-JJ-mots-cles.md`, la date étant celle des données.

## Titres

Un fait précis, pas une question, pas de point d’exclamation, pas de « choc » ni « incroyable ». Le titre doit être vrai même lu seul.

## Chiffres officiels de Roblox Corporation

Pour les articles trimestriels : saisir chaque chiffre dans `data/official/roblox-trimestriel.csv` (colonnes `trimestre,indicateur,valeur,unite,source_url,date_publication`), depuis le communiqué officiel (ir.roblox.com) uniquement, puis lancer `python tools/official.py` pour produire les jetons `officiel.*`.

## Relecture (agent vérificateur)

1. `python tools/verify.py drafts/<fichier>.md` doit répondre OK. Sinon, corriger et relancer.
2. Relire chaque phrase contre `facts/AAAA-MM-JJ.md` : le sens est-il exact ? « Reste en tête » suppose `rang_veille` = 1er ; « grimpe » suppose une variation positive ; « record » est interdit sans historique qui le prouve.
3. Vérifier qu’aucune phrase n’attribue une cause sans source.
4. Vérifier qu’aucune formulation ne laisse croire à un lien officiel avec Roblox.
5. Si l’éditeur a un lien avec un jeu cité, l’article le dit.
6. Signaler toute alerte du vérificateur (« nombre en lettres ») et la régler.

## Diffusion

- **X** : un post de 280 caractères au plus par article, dans `social/x/AAAA-MM-JJ-mots-cles.txt`, écrit lui aussi avec des jetons. Le fait principal, puis le lien de l’article. Un hashtag au plus. `python tools/render.py AAAA-MM-JJ social/x/<fichier>.txt` vérifie le post et donne le texte final à publier.
- **Newsletter** : alimentée par le flux RSS du site.
- **Vidéos courtes** : selon la méthode fournie par l’éditeur (à venir).
