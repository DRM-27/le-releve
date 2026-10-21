"""Langues du site. Le français est la langue source ; les autres sont servies sous /en/, /es/, /pt-br/.

- t("texte français", **valeurs) renvoie la traduction de la langue courante (ou le français s'il n'y en a pas,
  en notant la chaîne manquante), puis applique .format(**valeurs).
- La mise en forme des nombres et des dates (common.fr_*) suit la langue courante.
"""
from traductions import TR

LANGS = ["fr", "en", "es", "pt-br"]
META = {
    "fr": {"html": "fr", "og": "fr_FR", "prefix": "", "intl": "fr-FR", "label": "FR", "name": "Français"},
    "en": {"html": "en", "og": "en_US", "prefix": "en/", "intl": "en-US", "label": "EN", "name": "English"},
    "es": {"html": "es", "og": "es_ES", "prefix": "es/", "intl": "es-ES", "label": "ES", "name": "Español"},
    "pt-br": {"html": "pt-BR", "og": "pt_BR", "prefix": "pt-br/", "intl": "pt-BR", "label": "PT", "name": "Português (BR)"},
}
IDX = {"en": 0, "es": 1, "pt-br": 2}
CUR = "fr"
MISSING = set()


def set_lang(lang):
    global CUR
    CUR = lang


def t(s, **kw):
    if CUR != "fr":
        tr = TR.get(s)
        if tr and tr[IDX[CUR]]:
            s = tr[IDX[CUR]]
        else:
            MISSING.add(s)
    return s.format(**kw) if kw else s


def prefix(lang=None):
    return META[lang or CUR]["prefix"]
