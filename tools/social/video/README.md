# Vidéos courtes (TikTok) : formats validés par le propriétaire le 20/11/2026

Six formats, un générateur, des contrôles automatiques. Une vidéo qui échoue à un contrôle n'est jamais publiée, et on ne
modifie jamais un contrôle pour le faire passer.

## Les formats et quand les produire

`python tools/social/video/prep.py choisir AAAA-MM-JJ` dit quels formats sont possibles ce jour-là, et pourquoi.

| Format | Ce que montre la vidéo | Condition (vérifiée par prep.py) | Quand |
|---|---|---|---|
| `duel` (rose) | Un jeu du top 5 à la moyenne du jour en dépasse un autre : courbe de l'écart sur 8 jours mesurés, zoom sur le passage du zéro, l'icône du gagnant saute en tête | dépassement dans le top 5 entre la veille et le jour | quotidien, priorité 1 |
| `decollage` (vert) | Courbe horaire sur 8 jours, plate puis explosion ; étiquette « mise à jour » au pied du pic si une mise à jour est datée dans les 6 h avant le saut ; ×N en géant | hausse ≥ +50 % (≥ 10 000 joueurs) ou ≥ +30 % (≥ 20 000) | quotidien, priorité 2 |
| `chute` (rouge) | Courbe horaire sur 8 jours avec dates ; la moyenne du jour tombe au ralenti sous celle de la semaine d'avant | baisse d'au moins un tiers d'un jeu du top 50 (à la moyenne) de la semaine | quotidien, priorité 3 |
| `course` (ambre) | Course à la 2e place, jour par jour : seule la 2e place glisse (ralenti), les places 3 à 6 basculent sur place | n° 1 inchangé sur 14 à 30 jours mesurés consécutifs, au moins 3 changements de 2e place | le lundi |
| `nouveaux` (violet) | Grille des 100 places (jeux récents allumés), puis top 10 où les nouveaux grimpent dans leur place vide | au moins 25 jeux de 90 jours ou moins dans le top 100, et 2 dans le top 10 | le mercredi |
| `genres` (turquoise) | Un genre qui monte, un genre ÷N « à cause d'un seul jeu » révélé à la fin | un genre ×1,5 face à un genre ÷1,5 en 4 semaines, et un seul jeu fait au moins 60 % de la baisse | le 1er du mois |

Au plus une vidéo quotidienne (duel, sinon décollage, sinon chute), plus la course le lundi, les nouveaux le mercredi et les
genres le 1er du mois. Jamais deux vidéos sur le même jeu deux jours de suite. Aucun angle hors de ces six formats sans
décision du propriétaire. Le carrousel « La semaine » viendra plus tard.

## Le gabarit commun (déjà codé dans socle.css et socle.js)

- 1080 × 1920, 30 images/s, 19 à 25 s. Zone sûre TikTok : x 72 → 900, y 230 → 1436 (le pied de page peut descendre plus bas).
- La première image est la couverture : lisible, avec les vrais chiffres. Quelque chose bouge dès 0,25 s, et l'image n'est jamais figée plus d'1 s.
- Le titre reste épinglé pendant que le visuel se dessine. Le moment fort passe au ralenti, avec un chiffre géant.
- La question arrive pendant le moment fort, reste 3 s et ne recouvre jamais le chiffre fort. La dernière seconde revient à la couverture : la vidéo boucle.
- Chaque format a sa signature : un mot en grand, une couleur, un son d'ouverture.
- Aucune carte ne répète un chiffre déjà vu. Les chiffres « tombent » directement à leur vraie valeur. Un chiffre attaché à un jeu (date, âge, moyenne) n'est jamais animé en compteur.
- Son : effets synthétisés par sons.py, sans musique (le son tendance s'ajoute dans l'appli).
- Icônes officielles des jeux en illustration de classement, comme sur le site, jamais versionnées en clair. Aucune autre image de jeu, aucun logo Roblox. Pied de page « non affilié à Roblox ».

## D'où viennent les chiffres

Jetons de `facts/JOUR.json` (`g.<id>.moy`, `hausse.k.*` dont `hausse.k.mult`, `baisse.k.*` dont `baisse.k.div`, `recents.*`,
`recent.k.age`), ou calcul fait par prep.py sur les fichiers de `data/`, toujours le même :
- écart du duel = moyenne du jour du premier jeu − celle du second ;
- ×N / ÷N = jeton `mult` / `div`, sinon rapport des deux moyennes (même formule) ;
- course = `g.<id>.moy` de chaque jour mesuré ;
- genres = somme des moyennes des jeux du top 100 mesurés en entier, par genre Roblox ; jeux absents au départ marqués « nouveaux » ;
- courbes et pic = relevés horaires de `data/` ; mise à jour = `data/mises-a-jour.csv`.

## Produire une vidéo

Depuis la racine du dépôt (Playwright avec Chromium, ffmpeg et numpy ; s'ils manquent :
`pip install playwright numpy && python -m playwright install chromium`).

```
J=AAAA-MM-JJ; F=duel; V=tools/social/video; O=social/video/$J-$F
python $V/prep.py choisir $J
python $V/prep.py $F $J $V/donnees/$F.json
bash $V/icones.sh $(python $V/prep.py icones $V/donnees/$F.json)      # icônes manquantes, via le workflow chiffré
python $V/filmer.py $V/$F.html $V/donnees/$F.json verif                # contrôles sur chaque image, sans filmer
python $V/filmer.py $V/$F.html $V/donnees/$F.json video $O/video.mp4   # filme, contrôle chaque image, ajoute le son
python $V/controle.py $O/video.mp4                                     # mouvement, durée, boucle : doit dire OK
```

`filmer.py` refuse la vidéo (fichier `.refusee.mp4`, code 1) si un contrôle échoue : question sur un chiffre fort, élément
hors zone sûre, chiffre attaché à un jeu qui n'est pas sa vraie valeur, jeu affiché deux fois (course). `controle.py` refuse
une vidéo figée plus d'1 s, hors de 19 à 25 s, ou dont la dernière image ne rejoint pas la première.

Regarder ensuite quelques images (`ffmpeg -i $O/video.mp4 -vf "fps=1/4,scale=270:480,tile=6x1" /tmp/apercu.png`), puis écrire
`$O/legende.md` : une phrase, la question de la vidéo, « Abonne-toi : le classement Roblox chaque jour, chiffres vérifiés. »,
la source (« API publiques de Roblox, PlayLedgers »), le lien du site et 3 à 5 mots-clés. Pousser `video.mp4` et `legende.md`.
