"""IndexNow : prévient Bing (et Yandex, Seznam, Naver…) dès qu'une page est publiée.
Bing alimente aussi la recherche de ChatGPT, Copilot et DuckDuckGo. Google n'utilise pas IndexNow.

  python tools/indexnow.py cle      -> écrit _site/<clé>.txt (preuve que le site nous appartient)
  python tools/indexnow.py envoyer  -> envoie les articles publiés depuis 2 h (toutes langues),
                                       plus les pages principales une fois par jour (relevé de 6 h UTC)
Ne fait rien tant que le site n'est pas sur son domaine (config.json › hebergeur = cloudflare)."""
import json, sys, re, urllib.request, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
KEY = CONFIG.get("indexnow", "")
LANGS = {"fr": "", "en": "en/", "es": "es/", "pt-br": "pt-br/"}
PARIS = ZoneInfo("Europe/Paris")


def actif():
    return KEY and CONFIG.get("hebergeur") == "cloudflare"


def base():
    return CONFIG["baseUrl"].rstrip("/")


def articles_recents(heures=2):
    maintenant = dt.datetime.now(PARIS)
    urls = []
    for f in sorted((ROOT / "content" / "articles").glob("*.md")):
        m = re.search(r"^publie:\s*(\S+)", f.read_text(encoding="utf-8"), re.M)
        if not m:
            continue
        try:
            quand = dt.datetime.fromisoformat(m.group(1)).replace(tzinfo=PARIS)
        except ValueError:
            continue
        if dt.timedelta(0) <= maintenant - quand <= dt.timedelta(hours=heures):
            for lang, pre in LANGS.items():
                if lang == "fr" or (ROOT / "content" / "i18n" / lang / "articles" / f.name).exists():
                    urls.append(f"{base()}/{pre}articles/{f.stem}/")
    return urls


def pages_principales():
    return [f"{base()}/{pre}{p}" for pre in LANGS.values() for p in ("", "classement/", "articles/", "tendances/")]


def main():
    if not actif():
        print("IndexNow : site pas encore sur son domaine, rien à faire.")
        return
    if sys.argv[1:] == ["cle"]:
        (ROOT / "_site" / f"{KEY}.txt").write_text(KEY, encoding="utf-8")
        print("IndexNow : fichier de clé écrit.")
        return
    urls = articles_recents()
    if dt.datetime.now(dt.timezone.utc).hour == 6:
        urls += pages_principales()
    urls = list(dict.fromkeys(urls))
    if not urls:
        print("IndexNow : aucune nouvelle page à signaler.")
        return
    host = base().split("://", 1)[1].split("/")[0]
    corps = json.dumps({"host": host, "key": KEY, "keyLocation": f"{base()}/{KEY}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/IndexNow", data=corps,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow : {len(urls)} adresse(s) envoyée(s), réponse {r.status}.")
    except Exception as e:  # jamais bloquant pour la publication
        print(f"::warning::IndexNow a refusé l'envoi ({e}).")
    for u in urls[:12]:
        print("  ", u)


if __name__ == "__main__":
    main()
