"""Vérificateur de chiffres. Bloque toute publication dont un chiffre ne vient pas des données.

Règles :
  1. Tout chiffre du titre, du chapô et du texte s'écrit avec un jeton {{clé}} (ou {{AAAA-MM-JJ:clé}} pour un autre jour).
     Seules exceptions : les années (2026), les dates écrites en toutes lettres (20 octobre) et quelques repères fixes
     de méthode (top 10, 7 jours, 24 h…).
  2. Chaque jeton doit exister dans le fichier de faits du jour indiqué.
  3. Chaque graphique {{graphique:id}} doit exister.
  4. Les nombres écrits en lettres (« trois jeux », « deux fois plus ») sont signalés pour relecture.
  5. Rien ne doit laisser croire à un lien officiel avec Roblox.

Usage : python tools/verify.py chemin/vers/article.md [...]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FACTS, ROOT

TOKEN = re.compile(r"\{\{\s*(?:(\d{4}-\d{2}-\d{2}(?:-\d{2}h|-sem)?):)?([a-z0-9_.\-]+)\s*\}\}")
GRAPH = re.compile(r"\{\{\s*graphique:(?:(\d{4}-\d{2}-\d{2}(?:-\d{2}h|-sem)?):)?([a-z0-9\-]+)\s*\}\}")
MOIS = ("janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre"
        # traductions (anglais, espagnol, portugais)
        "|january|february|march|april|may|june|july|august|september|october|november|december"
        "|enero|febrero|marzo|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
        "|janeiro|fevereiro|março|maio|junho|julho|setembro|outubro|novembro|dezembro")
ALLOWED = [
    re.compile(r"\bT[1-4]\b"),                                                # trimestres
    re.compile(r"\b\d{1,2}(?:er)?\s+(?:" + MOIS + r")(?:\s+20\d\d)?\b", re.I),  # 20 octobre (2026)
    re.compile(r"\b(?:" + MOIS + r")\s+20\d\d\b", re.I),                    # octobre 2026
    re.compile(r"\b(?:" + MOIS + r")\s+\d{1,2}(?:st|nd|rd|th)?\b", re.I),     # October 21
    re.compile(r"\b\d{1,2}\s+de\s+(?:" + MOIS + r")(?:\s+de\s+20\d\d)?\b", re.I),  # 21 de octubre (de 2026)
    re.compile(r"\b(?:7|14|30|90)\s(?:days|días|dias|last days)\b", re.I),
    re.compile(r"\b24\s?(?:hours|horas|hrs)\b", re.I),
    re.compile(r"\b(?:no\.|n\.º|nº|n\.o)\s?1\b", re.I),
    re.compile(r"\bQ[1-4]\b"),
    re.compile(r"(?<![\d,.])(?<!\d[   ])\b20\d\d\b(?![   ]?\d)(?!\s?%)(?!\s(?:joueurs|visites|jeux|joueur)\b)"),  # années
    re.compile(r"\btop\s(?:3|5|10|20|50|100)\b", re.I),
    re.compile(r"\b(?:7|14|30|90)\s(?:jours|derniers jours)\b"),
    re.compile(r"\b24\s?h\b"),
    re.compile(r"\bn°\s?1\b"),
]
WORDS = re.compile(r"\b(deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|quinze|vingt|trente|quarante|cinquante|"
                   r"soixante|cent|cents|mille|million|millions|milliard|milliards|moitié|double|triple|quadruple|"
                   r"doublé|triplé|tiers|quart)\b", re.I)
BANNED = [re.compile(p, re.I) for p in (r"partenaire (?:officiel )?de roblox", r"en partenariat avec roblox",
                                         r"média officiel", r"officiellement soutenu par roblox", r"approuvé par roblox")]
REQUIRED = ("titre", "chapo", "jour", "type")
TYPES = {"quotidien", "hebdo", "mensuel", "trimestriel", "analyse", "dossier"}


def parse(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def load_facts(day, cache={}):
    if day not in cache:
        p = FACTS / f"{day}.json"
        cache[day] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return cache[day]


def fact_for(day, key):
    """Le fait désigné par un jeton : faits du jour, ou chiffres officiels (officiel.*)."""
    src = "officiel" if key.startswith("officiel.") else ("externe" if key.startswith("ext.") else day)
    f = load_facts(src)
    return None if f is None else f["faits"].get(key)


def strip_for_digits(text):
    t = TOKEN.sub(" ", text)
    t = GRAPH.sub(" ", t)
    t = re.sub(r"\]\([^)]*\)", "]", t)          # adresses des liens
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    for rx in ALLOWED:
        t = rx.sub(" ", t)
    return t


def context(text, i, w=40):
    return text[max(0, i - w):i + w].replace("\n", " ").strip()


def verify_text(text, day, where, errors, warnings):
    for m in TOKEN.finditer(text):
        d, key = m.group(1) or day, m.group(2)
        src = "officiel" if key.startswith("officiel.") else ("externe" if key.startswith("ext.") else d)
        if load_facts(src) is None:
            errors.append(f"{where} : faits « {src} » introuvables (jeton {{{{{key}}}}})")
        elif fact_for(d, key) is None:
            errors.append(f"{where} : jeton inconnu {{{{{key}}}}} (faits « {src} »)")
    for m in GRAPH.finditer(text):
        d, gid = m.group(1) or day, m.group(2)
        f = load_facts(d)
        if f is None or gid not in f.get("graphiques", {}):
            errors.append(f"{where} : graphique inconnu « {gid} » (faits du {d})")
    stripped = strip_for_digits(text)
    for m in re.finditer(r"\d+(?:[   ,.]\d+)*", stripped):
        errors.append(f"{where} : chiffre tapé à la main « {m.group(0)} » … {context(stripped, m.start())} …")
    for m in WORDS.finditer(TOKEN.sub(" ", text)):
        warnings.append(f"{where} : nombre en lettres « {m.group(0)} » à vérifier … {context(text, m.start())} …")
    for rx in BANNED:
        for m in rx.finditer(text):
            errors.append(f"{where} : formulation interdite (lien officiel avec Roblox) « {m.group(0)} »")


def verify(path):
    path = Path(path)
    errors, warnings = [], []
    meta, body = parse(path.read_text(encoding="utf-8"))
    if meta is None:
        return ["En-tête manquant (bloc --- … --- en début de fichier)"], [], {}, ""
    for k in REQUIRED:
        if not meta.get(k):
            errors.append(f"En-tête : champ « {k} » manquant")
    if meta.get("type") and meta["type"] not in TYPES:
        errors.append(f"En-tête : type « {meta['type']} » inconnu ({', '.join(sorted(TYPES))})")
    day = meta.get("jour", "")
    f = load_facts(day) if day else None
    if day and f is None and meta.get("type") not in ("trimestriel", "dossier"):
        errors.append(f"Faits du {day} introuvables : lancer python tools/facts.py {day}")
    elif f:
        c = f["couverture"]
        if c["releves"] < 18 and not c.get("instantane"):
            warnings.append(f"Journée incomplète : {c['releves']} relevés sur {c['attendus']}. Le dire dans l'article.")
    for field in ("titre", "chapo"):
        verify_text(meta.get(field, ""), day, field.capitalize(), errors, warnings)
    verify_text(body, day, "Texte", errors, warnings)
    if len(body.split()) < 80:
        warnings.append("Texte très court (moins de 80 mots).")
    return errors, warnings, meta, body


def main(paths):
    bad = 0
    report = []
    for p in paths:
        e, w, meta, _ = verify(p)
        report.append({"fichier": str(p), "ok": not e, "erreurs": e, "alertes": w})
        status = "OK" if not e else "BLOQUÉ"
        print(f"[{status}] {p}")
        for x in e:
            print("  ✗", x)
        for x in w:
            print("  ⚠", x)
        bad += bool(e)
    return bad


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(1 if main(sys.argv[1:]) else 0)
