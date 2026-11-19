"""Écrit le quotidien de la veille, en 4 langues, avec un angle choisi par les chiffres.

À lancer après tools/facts.py. Ne fait rien si la journée compte moins de MIN_RELEVES relevés,
ou si le quotidien du jour existe déjà (publié ou en brouillon).

Le titre et le chapô ne sont plus fixes : le script retient le fait le plus fort du jour, dans cet ordre
(sans reprendre l'angle de la veille quand un autre est disponible) :
  nouveau_n1  le n° 1 a changé (toujours retenu)
  entree      un jeu entre dans le top 50 directement dans le top 20
  hausse      une hausse d'au moins +50 % sur une semaine (10 000 joueurs moyens ou plus), ou +30 % (20 000 ou plus)
  baisse      une baisse d'au moins −40 % sur une semaine, pour un jeu qui en avait 20 000 ou plus
  top         sinon : le n° 1 qui garde la tête et le poids du genre dominant
Le corps de l'article (n° 1, poursuivants, pic, genres) reste le même pour garder des repères au lecteur.

Publication : si config.json > quotidien.autoPublish vaut true, l'article et ses traductions vont directement
dans content/ (après tools/verify.py). Sinon, le français va dans drafts/ pour validation.
Usage : python tools/quotidien.py [AAAA-MM-JJ]   (par défaut : les 3 derniers jours jusqu'à hier, heure de Paris)
"""
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG, FACTS, ROOT, TZ, slugify, utc_now

MODELES = {"fr": ROOT / "tools" / "modeles" / "quotidien.md"}
for _l in ("en", "es", "pt-br"):
    MODELES[_l] = ROOT / "tools" / "modeles" / "i18n" / _l / "quotidien.md"
MIN_RELEVES = 12   # relevés minimum sur la journée ; GitHub saute des heures planifiées, l'article cite celles qui manquent

# @I@ = l'indice du jeu retenu (hausse.2, entree.1…). Aucun chiffre tapé : uniquement des jetons.
ANGLES = {
    "top": {
        "fr": ("{{top.1.nom}} reste en tête avec un pic de {{top.1.pic}} joueurs ; le genre {{genre.1.nom}} pèse {{genre.1.part}} du top 100",
               "Le {{jour.date_courte}}, le n° 1 garde sa place et réunit {{concentration.top1}} des joueurs moyens du top 100 ; le genre {{genre.1.nom}} en regroupe {{genre.1.part}}.",
               None),
        "en": ("{{top.1.nom}} stays on top with a peak of {{top.1.pic}} players; the {{genre.1.nom}} genre makes up {{genre.1.part}} of the top 100",
               "On {{jour.date_courte}}, the No. 1 game held its spot and drew {{concentration.top1}} of the top 100's average players; the {{genre.1.nom}} genre accounts for {{genre.1.part}}.",
               None),
        "es": ("{{top.1.nom}} sigue en cabeza con un pico de {{top.1.pic}} jugadores; el género {{genre.1.nom}} pesa {{genre.1.part}} del top 100",
               "El {{jour.date_courte}}, el n.º 1 conserva su puesto y reúne {{concentration.top1}} de los jugadores medios del top 100; el género {{genre.1.nom}} concentra {{genre.1.part}}.",
               None),
        "pt-br": ("{{top.1.nom}} segue na liderança com pico de {{top.1.pic}} jogadores; o gênero {{genre.1.nom}} pesa {{genre.1.part}} do top 100",
                  "Em {{jour.date_courte}}, o n.º 1 manteve o posto e reuniu {{concentration.top1}} dos jogadores médios do top 100; o gênero {{genre.1.nom}} concentra {{genre.1.part}}.",
                  None),
    },
    "nouveau_n1": {
        "fr": ("{{top.1.nom}} prend la tête de Roblox avec un pic de {{top.1.pic}} joueurs",
               "Le {{jour.date_courte}}, {{top.1.nom}} passe {{top.1.rang}} après avoir fini la veille {{top.1.rang_veille}}. Il réunit {{concentration.top1}} des joueurs moyens du top 100.",
               "**{{top.1.nom}}** était {{top.1.rang_veille}} la veille. Il passe en tête avec un pic relevé de {{top.1.pic}} joueurs à {{top.1.heure_pic}}, devant **{{top.2.nom}}** ({{top.2.pic}})."),
        "en": ("{{top.1.nom}} takes the top spot on Roblox with a peak of {{top.1.pic}} players",
               "On {{jour.date_courte}}, {{top.1.nom}} moved up to {{top.1.rang}} after finishing {{top.1.rang_veille}} the day before. It drew {{concentration.top1}} of the top 100's average players.",
               "**{{top.1.nom}}** was {{top.1.rang_veille}} the day before. It takes the lead with a recorded peak of {{top.1.pic}} players at {{top.1.heure_pic}}, ahead of **{{top.2.nom}}** ({{top.2.pic}})."),
        "es": ("{{top.1.nom}} toma la cabeza de Roblox con un pico de {{top.1.pic}} jugadores",
               "El {{jour.date_courte}}, {{top.1.nom}} pasa al puesto {{top.1.rang}} tras terminar el día anterior en el puesto {{top.1.rang_veille}}. Reúne {{concentration.top1}} de los jugadores medios del top 100.",
               "**{{top.1.nom}}** estaba en el puesto {{top.1.rang_veille}} el día anterior. Pasa a la cabeza con un pico registrado de {{top.1.pic}} jugadores a las {{top.1.heure_pic}}, por delante de **{{top.2.nom}}** ({{top.2.pic}})."),
        "pt-br": ("{{top.1.nom}} assume a liderança no Roblox com pico de {{top.1.pic}} jogadores",
                  "Em {{jour.date_courte}}, {{top.1.nom}} passou ao posto {{top.1.rang}} depois de terminar o dia anterior em {{top.1.rang_veille}}. Reúne {{concentration.top1}} dos jogadores médios do top 100.",
                  "**{{top.1.nom}}** estava em {{top.1.rang_veille}} no dia anterior. Assume a liderança com pico registrado de {{top.1.pic}} jogadores às {{top.1.heure_pic}}, à frente de **{{top.2.nom}}** ({{top.2.pic}})."),
    },
    "entree": {
        "fr": ("{{entree.@I@.nom}} entre dans le top 50 de Roblox, directement {{entree.@I@.rang}}",
               "Le {{jour.date_courte}}, {{entree.@I@.nom}} fait son entrée dans le top 50 avec un pic de {{entree.@I@.pic}} joueurs. @ENTREES@",
               "**{{entree.@I@.nom}}** était {{entree.@I@.rang_veille}} la veille, hors du top 50. Il arrive {{entree.@I@.rang}} avec un pic relevé de {{entree.@I@.pic}} joueurs."),
        "en": ("{{entree.@I@.nom}} enters Roblox's top 50, straight in at {{entree.@I@.rang}}",
               "On {{jour.date_courte}}, {{entree.@I@.nom}} entered the top 50 with a peak of {{entree.@I@.pic}} players. @ENTREES@",
               "**{{entree.@I@.nom}}** was {{entree.@I@.rang_veille}} the day before, outside the top 50. It comes in at {{entree.@I@.rang}} with a recorded peak of {{entree.@I@.pic}} players."),
        "es": ("{{entree.@I@.nom}} entra en el top 50 de Roblox, directamente en el puesto {{entree.@I@.rang}}",
               "El {{jour.date_courte}}, {{entree.@I@.nom}} entra en el top 50 con un pico de {{entree.@I@.pic}} jugadores. @ENTREES@",
               "**{{entree.@I@.nom}}** estaba en el puesto {{entree.@I@.rang_veille}} el día anterior, fuera del top 50. Llega al puesto {{entree.@I@.rang}} con un pico registrado de {{entree.@I@.pic}} jugadores."),
        "pt-br": ("{{entree.@I@.nom}} entra no top 50 do Roblox, direto no posto {{entree.@I@.rang}}",
                  "Em {{jour.date_courte}}, {{entree.@I@.nom}} entrou no top 50 com pico de {{entree.@I@.pic}} jogadores. @ENTREES@",
                  "**{{entree.@I@.nom}}** estava em {{entree.@I@.rang_veille}} no dia anterior, fora do top 50. Chega ao posto {{entree.@I@.rang}} com pico registrado de {{entree.@I@.pic}} jogadores."),
    },
    "hausse": {
        "fr": ("{{hausse.@I@.nom}} : {{hausse.@I@.var}} de joueurs sur Roblox par rapport aux 7 jours précédents",
               "Le {{jour.date_courte}}, {{hausse.@I@.nom}} a réuni {{hausse.@I@.moy}} joueurs en moyenne, contre {{hausse.@I@.moy_avant}} la semaine précédente : @PLUS@.",
               "**{{hausse.@I@.nom}}** passe de {{hausse.@I@.moy_avant}} à {{hausse.@I@.moy}} joueurs en moyenne ({{hausse.@I@.var}}) par rapport à la semaine précédente. Il se classe {{hausse.@I@.rang}} au pic du jour."),
        "en": ("{{hausse.@I@.nom}}: {{hausse.@I@.var}} players on Roblox compared with the previous 7 days",
               "On {{jour.date_courte}}, {{hausse.@I@.nom}} averaged {{hausse.@I@.moy}} players, against {{hausse.@I@.moy_avant}} the previous week: @PLUS@.",
               "**{{hausse.@I@.nom}}** went from {{hausse.@I@.moy_avant}} to {{hausse.@I@.moy}} average players ({{hausse.@I@.var}}) compared with the previous week. It ranks {{hausse.@I@.rang}} at the day's peak."),
        "es": ("{{hausse.@I@.nom}}: {{hausse.@I@.var}} de jugadores en Roblox respecto a los 7 días anteriores",
               "El {{jour.date_courte}}, {{hausse.@I@.nom}} reunió {{hausse.@I@.moy}} jugadores de media, frente a {{hausse.@I@.moy_avant}} la semana anterior: @PLUS@.",
               "**{{hausse.@I@.nom}}** pasa de {{hausse.@I@.moy_avant}} a {{hausse.@I@.moy}} jugadores de media ({{hausse.@I@.var}}) respecto a la semana anterior. Se sitúa en el puesto {{hausse.@I@.rang}} en el pico del día."),
        "pt-br": ("{{hausse.@I@.nom}}: {{hausse.@I@.var}} de jogadores no Roblox em relação aos 7 dias anteriores",
                  "Em {{jour.date_courte}}, {{hausse.@I@.nom}} reuniu {{hausse.@I@.moy}} jogadores em média, contra {{hausse.@I@.moy_avant}} na semana anterior: @PLUS@.",
                  "**{{hausse.@I@.nom}}** passa de {{hausse.@I@.moy_avant}} para {{hausse.@I@.moy}} jogadores em média ({{hausse.@I@.var}}) em relação à semana anterior. Fica no posto {{hausse.@I@.rang}} no pico do dia."),
    },
    "baisse": {
        "fr": ("Chute de {{baisse.@I@.var}} pour {{baisse.@I@.nom}} sur Roblox par rapport aux 7 jours précédents",
               "Le {{jour.date_courte}}, {{baisse.@I@.nom}} n'a plus réuni que {{baisse.@I@.moy}} joueurs en moyenne, contre {{baisse.@I@.moy_avant}} la semaine précédente.",
               "**{{baisse.@I@.nom}}** passe de {{baisse.@I@.moy_avant}} à {{baisse.@I@.moy}} joueurs en moyenne ({{baisse.@I@.var}}) par rapport à la semaine précédente. Nos relevés ne disent pas pourquoi."),
        "en": ("{{baisse.@I@.nom}} drops {{baisse.@I@.var}} on Roblox compared with the previous 7 days",
               "On {{jour.date_courte}}, {{baisse.@I@.nom}} averaged only {{baisse.@I@.moy}} players, against {{baisse.@I@.moy_avant}} the previous week.",
               "**{{baisse.@I@.nom}}** went from {{baisse.@I@.moy_avant}} to {{baisse.@I@.moy}} average players ({{baisse.@I@.var}}) compared with the previous week. Our readings do not say why."),
        "es": ("Caída de {{baisse.@I@.var}} para {{baisse.@I@.nom}} en Roblox respecto a los 7 días anteriores",
               "El {{jour.date_courte}}, {{baisse.@I@.nom}} solo reunió {{baisse.@I@.moy}} jugadores de media, frente a {{baisse.@I@.moy_avant}} la semana anterior.",
               "**{{baisse.@I@.nom}}** pasa de {{baisse.@I@.moy_avant}} a {{baisse.@I@.moy}} jugadores de media ({{baisse.@I@.var}}) respecto a la semana anterior. Nuestras lecturas no dicen por qué."),
        "pt-br": ("Queda de {{baisse.@I@.var}} para {{baisse.@I@.nom}} no Roblox em relação aos 7 dias anteriores",
                  "Em {{jour.date_courte}}, {{baisse.@I@.nom}} reuniu apenas {{baisse.@I@.moy}} jogadores em média, contra {{baisse.@I@.moy_avant}} na semana anterior.",
                  "**{{baisse.@I@.nom}}** passa de {{baisse.@I@.moy_avant}} para {{baisse.@I@.moy}} jogadores em média ({{baisse.@I@.var}}) em relação à semana anterior. Nossas leituras não dizem por quê."),
    },
}
ANGLES["en_tete"] = {   # angle « top » quand le rang de la veille n'est pas connu (veille incomplète) : pas de « reste en tête »
    "fr": ("{{top.1.nom}} en tête de Roblox avec un pic de {{top.1.pic}} joueurs ; le genre {{genre.1.nom}} pèse {{genre.1.part}} du top 100",
           "Le {{jour.date_courte}}, le n° 1 réunit {{concentration.top1}} des joueurs moyens du top 100 ; le genre {{genre.1.nom}} en regroupe {{genre.1.part}}.",
           None),
    "en": ("{{top.1.nom}} leads Roblox with a peak of {{top.1.pic}} players; the {{genre.1.nom}} genre makes up {{genre.1.part}} of the top 100",
           "On {{jour.date_courte}}, the No. 1 game drew {{concentration.top1}} of the top 100's average players; the {{genre.1.nom}} genre accounts for {{genre.1.part}}.",
           None),
    "es": ("{{top.1.nom}} lidera Roblox con un pico de {{top.1.pic}} jugadores; el género {{genre.1.nom}} pesa {{genre.1.part}} del top 100",
           "El {{jour.date_courte}}, el n.º 1 reúne {{concentration.top1}} de los jugadores medios del top 100; el género {{genre.1.nom}} concentra {{genre.1.part}}.",
           None),
    "pt-br": ("{{top.1.nom}} lidera o Roblox com pico de {{top.1.pic}} jogadores; o gênero {{genre.1.nom}} pesa {{genre.1.part}} do top 100",
              "Em {{jour.date_courte}}, o n.º 1 reuniu {{concentration.top1}} dos jogadores médios do top 100; o gênero {{genre.1.nom}} concentra {{genre.1.part}}.",
              None),
}
ANGLES["retour"] = {    # un jeu revient dans le top 50 après une absence de nos relevés : ce n'est pas une entrée
    "fr": ("{{retour.@I@.nom}} revient dans le top 50 de Roblox, {{retour.@I@.rang}}",
           "Le {{jour.date_courte}}, {{retour.@I@.nom}} retrouve le top 50 avec un pic relevé de {{retour.@I@.pic}} joueurs, après une absence de nos relevés.",
           "**{{retour.@I@.nom}}** n'avait pas pu être mesuré complètement la veille, alors qu'il figurait dans le top 50 au cours des 7 jours précédents. Il revient {{retour.@I@.rang}} avec un pic relevé de {{retour.@I@.pic}} joueurs : c'est un retour, pas une nouvelle entrée."),
    "en": ("{{retour.@I@.nom}} returns to Roblox's top 50 at {{retour.@I@.rang}}",
           "On {{jour.date_courte}}, {{retour.@I@.nom}} returned to the top 50 with a recorded peak of {{retour.@I@.pic}} players, after a gap in our readings.",
           "**{{retour.@I@.nom}}** could not be fully measured the day before, although it had been in the top 50 during the previous 7 days. It returns at {{retour.@I@.rang}} with a recorded peak of {{retour.@I@.pic}} players: a return, not a new entry."),
    "es": ("{{retour.@I@.nom}} vuelve al top 50 de Roblox, en el puesto {{retour.@I@.rang}}",
           "El {{jour.date_courte}}, {{retour.@I@.nom}} vuelve al top 50 con un pico registrado de {{retour.@I@.pic}} jugadores, tras una ausencia en nuestras lecturas.",
           "**{{retour.@I@.nom}}** no pudo medirse por completo el día anterior, aunque estuvo en el top 50 durante los 7 días anteriores. Vuelve al puesto {{retour.@I@.rang}} con un pico registrado de {{retour.@I@.pic}} jugadores: es un regreso, no una nueva entrada."),
    "pt-br": ("{{retour.@I@.nom}} volta ao top 50 do Roblox, no posto {{retour.@I@.rang}}",
              "Em {{jour.date_courte}}, {{retour.@I@.nom}} voltou ao top 50 com pico registrado de {{retour.@I@.pic}} jogadores, depois de uma ausência em nossas leituras.",
              "**{{retour.@I@.nom}}** não pôde ser medido por completo no dia anterior, embora estivesse no top 50 nos 7 dias anteriores. Volta ao posto {{retour.@I@.rang}} com pico registrado de {{retour.@I@.pic}} jogadores: é um retorno, não uma nova entrada."),
}
INCOMPLET = {   # phrase obligatoire quand la journée compte moins de 18 relevés
    "fr": "Journée incomplète : nos relevés ne couvrent que {{releves.nb}} heures sur {{releves.attendus}}. Les chiffres du jour sont à lire avec prudence.",
    "en": "Incomplete day: our readings cover only {{releves.nb}} of {{releves.attendus}} hours. Read the day's figures with caution.",
    "es": "Jornada incompleta: nuestras lecturas solo cubren {{releves.nb}} de {{releves.attendus}} horas. Las cifras del día deben leerse con prudencia.",
    "pt-br": "Dia incompleto: nossas leituras cobrem apenas {{releves.nb}} de {{releves.attendus}} horas. Leia os números do dia com cautela.",
}
PONCTUEL = {    # quand un pic cité dépasse 3 fois les relevés voisins
    "fr": ("Attention : le pic de {{@P@.nom}} est ponctuel, relevé à {{@P@.heure_pic}} ; à la moyenne du jour, il est {{@P@.rang_moy}}.",
           "Ce pic est ponctuel, relevé à {{@P@.heure_pic}}."),
    "en": ("Note: {{@P@.nom}}'s peak is a one-off, recorded at {{@P@.heure_pic}}; by daily average it ranks {{@P@.rang_moy}}.",
           "This peak is a one-off, recorded at {{@P@.heure_pic}}."),
    "es": ("Ojo: el pico de {{@P@.nom}} es puntual, registrado a las {{@P@.heure_pic}}; por la media del día, ocupa el puesto {{@P@.rang_moy}}.",
           "Este pico es puntual, registrado a las {{@P@.heure_pic}}."),
    "pt-br": ("Atenção: o pico de {{@P@.nom}} é pontual, registrado às {{@P@.heure_pic}}; pela média do dia, fica em {{@P@.rang_moy}}.",
              "Este pico é pontual, registrado às {{@P@.heure_pic}}."),
}
SEUIL_COMPLET = 18
FAIT = {"fr": "## Le fait du jour", "en": "## The day's standout", "es": "## El dato del día", "pt-br": "## O destaque do dia"}
ENTREES = {  # (une seule entrée, plusieurs)
    "fr": ("C'est la seule entrée par rapport à la veille.", "{{entrees.nb}} jeux y sont entrés par rapport à la veille."),
    "en": ("It is the only new entry compared with the day before.", "{{entrees.nb}} games entered it compared with the day before."),
    "es": ("Es la única entrada respecto al día anterior.", "{{entrees.nb}} juegos entraron respecto al día anterior."),
    "pt-br": ("É a única entrada em relação ao dia anterior.", "{{entrees.nb}} jogos entraram em relação ao dia anterior."),
}
PLUS = {  # (la plus forte, l'une des plus fortes)
    "fr": ("la plus forte hausse du jour", "l'une des plus fortes hausses du jour"),
    "en": ("the biggest rise of the day", "one of the biggest rises of the day"),
    "es": ("la mayor subida del día", "una de las mayores subidas del día"),
    "pt-br": ("a maior alta do dia", "uma das maiores altas do dia"),
}
SUJET = {"top": "top.1.nom", "nouveau_n1": "top.1.nom", "entree": "entree.@I@.nom", "retour": "retour.@I@.nom",
         "hausse": "hausse.@I@.nom", "baisse": "baisse.@I@.nom"}


def v(F, k):
    return (F.get(k) or {}).get("v")


def candidats(F):
    out = []
    if v(F, "top.1.rang_veille") not in (None, 1):
        out.append(("nouveau_n1", 1))
    for i in range(1, 4):
        if v(F, f"entree.{i}.nom") and (v(F, f"entree.{i}.rang") or 99) <= 20:
            out.append(("entree", i))
            break
    for i in range(1, 4):
        if v(F, f"retour.{i}.nom") and (v(F, f"retour.{i}.rang") or 99) <= 20:
            out.append(("retour", i))
            break
    sept_jours = v(F, "mouv.reference") == "var_7j"   # les titres disent « par rapport aux 7 jours précédents »
    for i in range(1, 6 if sept_jours else 1):
        var, moy = v(F, f"hausse.{i}.var") or 0, v(F, f"hausse.{i}.moy") or 0
        if (var >= 0.5 and moy >= 10000) or (var >= 0.3 and moy >= 20000):
            out.append(("hausse", i))
            break
    for i in range(1, 6 if sept_jours else 1):
        if (v(F, f"baisse.{i}.var") or 0) <= -0.4 and (v(F, f"baisse.{i}.moy_avant") or 0) >= 20000:
            out.append(("baisse", i))
            break
    out.append(("top", 1))
    return out


def angle_veille(d):
    for p in sorted((ROOT / "content" / "articles").glob("*-quotidien.md"), reverse=True):
        if p.name[:10] < d.isoformat():
            m = re.search(r"(?m)^angle: (\S+)", p.read_text(encoding="utf-8"))
            return m.group(1) if m else "top"
    return None


def choisir(F, d):
    c = candidats(F)
    if c[0][0] == "nouveau_n1":
        return c[0]
    hier = angle_veille(d)
    for a in c:
        if a[0] != hier:
            return a
    return c[0]


def ecrire(lang, angle, i, F, jour, publie):
    # « reste en tête » seulement si le rang de la veille est connu et vaut 1
    texte_angle = "en_tete" if angle == "top" and v(F, "top.1.rang_veille") != 1 else angle
    titre, chapo, fait = ANGLES[texte_angle][lang]
    rep = {"@I@": str(i),
           "@ENTREES@": ENTREES[lang][0 if (v(F, "entrees.nb") or 0) <= 1 else 1],
           "@PLUS@": PLUS[lang][0 if i == 1 else 1]}

    def sub(s):
        for a, b in rep.items():
            s = s.replace(a, b)
        return s
    texte = MODELES[lang].read_text(encoding="utf-8").replace("@JOUR@", jour).replace("@PUBLIE@", publie)
    texte = re.sub(r"(?m)^titre: .*$", lambda m: "titre: " + sub(titre), texte, count=1)
    texte = re.sub(r"(?m)^chapo: .*$", lambda m: "chapo: " + sub(chapo), texte, count=1)
    texte = texte.replace("type: quotidien\n", f"type: quotidien\nangle: {angle}\n", 1)
    if fait:  # le fait du jour, juste avant la première section
        texte = texte.replace("\n\n## ", f"\n\n{FAIT[lang]}\n\n{sub(fait)}\n\n## ", 1)
    return completer(texte, lang, F)


def completer(texte, lang, F):
    """Ajoute les phrases que les chiffres rendent obligatoires : journée incomplète, pics ponctuels."""
    tete, corps = texte.split("\n---\n", 1)
    if (v(F, "releves.nb") or 0) < SEUIL_COMPLET:   # après le paragraphe des relevés
        corps = corps.replace("\n\n", f"\n\n{INCOMPLET[lang]}\n\n", 1)
    for pref in sorted({m.group(1) for m in re.finditer(r"\{\{((?:top|entree|retour|hausse)\.\d+)\.pic\}\}", corps)}):
        if v(F, f"{pref}.pic_isole") is not True:
            continue
        note = PONCTUEL[lang][0 if (F.get(f"{pref}.rang_moy") and pref.startswith("top.")) else 1].replace("@P@", pref)
        k = corps.index("{{" + pref + ".pic}}")
        fin = corps.find("\n\n", k)
        fin = len(corps) if fin < 0 else fin
        corps = corps[:fin] + " " + note + corps[fin:]
    return tete + "\n---\n" + corps


def verifie(paths):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "verify.py"), *map(str, paths)], capture_output=True, text=True)
    print(r.stdout + r.stderr)
    return r.returncode == 0


def main():
    """Sans date : traite les 3 derniers jours, du plus ancien au plus récent (rattrape un jour manqué)."""
    if len(sys.argv) > 1:
        return un_jour(date.fromisoformat(sys.argv[1]))
    hier = utc_now().astimezone(TZ).date() - timedelta(days=1)
    return max(un_jour(hier - timedelta(days=k)) for k in (2, 1, 0))


def un_jour(d):
    f = FACTS / f"{d.isoformat()}.json"
    if not f.exists():
        print(f"Pas de faits pour {d} : rien à faire.")
        return 0
    faits = json.loads(f.read_text(encoding="utf-8"))
    cov, F = faits.get("couverture", {}), faits["faits"]
    if not cov or cov.get("releves", 0) < min(MIN_RELEVES, cov.get("attendus", 24)):
        print(f"Journée incomplète ({cov.get('releves')}/{cov.get('attendus')}) : rien à faire.")
        return 0
    if not v(F, "top.1.nom"):
        print("Pas de n° 1 dans les faits : rien à faire.")
        return 0
    deja = list((ROOT / "content" / "articles").glob(f"{d.isoformat()}-*-quotidien.md")) + list((ROOT / "drafts").glob(f"{d.isoformat()}-*-quotidien.md"))
    if deja:
        print(f"Quotidien déjà présent ({deja[0].name}) : rien à faire.")
        return 0
    angle, i = choisir(F, d)
    nom = f"{d.isoformat()}-{slugify(v(F, SUJET[angle].replace('@I@', str(i))))}-quotidien.md"
    publie = utc_now().astimezone(TZ).strftime("%Y-%m-%dT%H:%M")
    auto = bool((CONFIG.get("quotidien") or {}).get("autoPublish"))
    cibles = {}
    for lang in MODELES:
        if lang != "fr" and not auto:
            continue
        base = (ROOT / "content" / "articles") if lang == "fr" else (ROOT / "content" / "i18n" / lang / "articles")
        cibles[lang] = (base if auto else ROOT / "drafts") / nom
    for lang, p in cibles.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(ecrire(lang, angle, i, F, d.isoformat(), publie), encoding="utf-8")
    if not verifie(list(cibles.values())):
        for p in cibles.values():
            p.unlink(missing_ok=True)
        print("Vérification échouée : rien n'est publié.")
        return 1
    print(f"Angle « {angle} » ; {'publié' if auto else 'brouillon'} : {', '.join(str(p.relative_to(ROOT)) for p in cibles.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
