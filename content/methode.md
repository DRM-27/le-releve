# Méthode

{{nom}} publie des chiffres sur Roblox que chacun peut revérifier. Cette page explique d’où ils viennent, comment ils sont calculés et ce qu’ils ne disent pas.

## Ce que nous relevons

Toutes les heures, un programme interroge les API web publiques de Roblox, celles qu’utilise le site roblox.com lui-même :

- les classements de la page Découvrir (jeux les plus joués du moment, tendances, jeux en progression) ;
- pour chaque jeu apparu dans l’un de ces classements au cours des quatorze derniers jours : le nombre de joueurs en ligne, les visites cumulées, les favoris et les votes.

Un jeu reste suivi deux semaines après sa dernière apparition dans un classement, pour que nous puissions aussi mesurer les baisses. Les emplacements sponsorisés sont exclus des classements.

Chaque relevé est archivé tel quel, en fichiers CSV lisibles par tous, dans notre [dépôt de données ouvertes]({{donnees}}).

## Comment nous calculons

Tous les chiffres sont calculés par un programme, jamais à la main ni par une IA. Une journée va de minuit à minuit, heure de Paris.

- **Pic de joueurs** : le plus haut des relevés horaires de la journée. Comme nous relevons une fois par heure, le pic réel peut être un peu plus élevé.
- **Moyenne de joueurs** : la moyenne des relevés horaires de la journée.
- **Variations** : la moyenne du jour comparée à celle de la veille, ou à la moyenne des sept jours précédents quand nous avons assez d’historique. Ces comparaisons n’utilisent que des mesures complètes : le jeu doit avoir été mesuré dans au moins trois quarts des relevés de chaque journée comparée (18 heures sur 24).
- **Hausses et baisses** : seuls les jeux qui comptent au moins mille joueurs en moyenne sont retenus, pour éviter les pourcentages spectaculaires sur des jeux presque vides.
- **Pic ponctuel** : les jeux sont classés par leur pic du jour. Quand ce pic dépasse plus de trois fois les relevés voisins, souvent un événement d’une heure, l’article le signale comme ponctuel et donne aussi le rang du jeu à la moyenne du jour.
- **Entrées dans le top 50** : un jeu ne compte comme entrant que s’il a été mesuré complètement la veille, hors du top 50. Un jeu absent de nos relevés la veille (relevé perdu, jeu indisponible) qui figurait dans le top 50 au cours des sept jours précédents est un retour, pas une entrée.
- **Visites en 24 h** : l’écart entre deux relevés espacés de 23 à 25 heures. Sans paire de relevés valable, nous ne publions pas ce chiffre.

Un jeu n’est classé que s’il est présent dans au moins la moitié des relevés de la journée. Quand des relevés manquent, l’article l’indique ; en dessous de 18 relevés sur la journée, il précise que la journée est incomplète. Quand l’API de Roblox limite nos requêtes, le programme réessaie les jeux non mesurés avant d’enregistrer le relevé ; ceux qui restent non mesurés sont listés dans le fichier d’état du relevé.

## Alertes

À chaque relevé, un programme compare chaque jeu au relevé précédent. Il publie une alerte quand un jeu qui compte au moins 2 000 joueurs gagne 50 % ou plus en une heure, ou quand un jeu entre dans le top 10 depuis l’extérieur du top 20. Un même jeu ne déclenche pas deux fois la même alerte en moins de six heures.

## Pages par jeu et données ouvertes

Chaque jeu suivi a sa page, avec sa courbe horaire et ses chiffres clés. Une page n’est proposée aux moteurs de recherche qu’après sept jours d’historique. Toutes les données sont accessibles librement en JSON et en CSV (voir [Données ouvertes](../donnees/)).

## Ce que ces chiffres ne disent pas

- Roblox ne publie pas en temps réel le nombre total de joueurs connectés. Le total que nous affichons ne porte que sur les jeux que nous suivons.
- Les chiffres annuels et trimestriels de la plateforme (utilisateurs actifs, revenus, heures jouées) viennent des publications officielles de Roblox Corporation à ses investisseurs. Nous les citons avec un lien vers le document d’origine.
- Nous ne publions aucune estimation de revenus d’un jeu : aucune donnée publique ne permet de la vérifier.

## Comment les articles sont écrits

1. Le programme calcule les faits de la journée et les enregistre dans un fichier.
2. Le quotidien est écrit par un programme, à partir de modèles fixes ; les analyses sont rédigées par une IA. Ni l’un ni l’autre n’écrit de chiffre : les chiffres sont appelés depuis le fichier.
3. Un vérificateur automatique bloque la publication si un chiffre ne provient pas des données, si une formulation laisse croire à un lien officiel avec Roblox, ou si une formulation courante contredit les faits (journée incomplète non signalée, « reste en tête » sans être n° 1 la veille, entrée dans le top 50 non établie, pic ponctuel présenté comme durable).
4. Les analyses sont relues par un agent qui contrôle le sens des phrases. Le quotidien, qui suit des modèles fixes, est publié dès qu’il passe le vérificateur.
5. Les quotidiens en anglais, en espagnol et en portugais suivent des modèles traduits ; les autres articles sont traduits de l’original français par une IA. Les chiffres sont les mêmes, appelés depuis les mêmes fichiers.

Dans chaque article, les chiffres soulignés sont des liens : ils ouvrent la ligne exacte du fichier de données dont ils proviennent.

## Indépendance

{{nom}} n’est ni affilié à Roblox Corporation, ni soutenu par elle. Roblox est une marque de Roblox Corporation. Quand un article parle d’un jeu avec lequel l’éditeur a un lien, l’article le dit.

## Erreurs

Une erreur ? Signalez-la depuis la page [Corrections](../corrections/). Chaque correction est publiée.
