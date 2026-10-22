"""Construit le site statique dans _site/. Refuse de construire si un article publié ne passe pas le vérificateur.

Le site existe en plusieurs langues : le français à la racine, les autres sous /en/, /es/, /pt-br/ (voir i18n.py).
Les pages de données sont générées dans chaque langue ; un article n'existe dans une langue que si sa traduction
est présente dans content/i18n/<langue>/articles/.

Usage : python tools/build.py [--drafts]   (--drafts : construit aussi les brouillons dans /brouillons/, pour relecture locale)
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parent))
import charts
import explore
import i18n
import og
import pages2
from common import (CONFIG, DATA, ROOT, TZ, UTC, fr_big, fr_date, fr_hour, fr_int, fr_pct, fr_rank, fr_share, github_blob, github_tree,
                    load_games, parse_iso, read_csv, snap_path, utc_now)
from facts import GENRES_FR
from i18n import LANGS, META, t
from verify import GRAPH, TOKEN, fact_for, load_facts, verify

OUT = Path(os.environ.get("MEDIA_SITE_DIR", ROOT / "_site"))
CONTENT = Path(os.environ.get("MEDIA_CONTENT_DIR", ROOT / "content"))
esc = html.escape
NAME = CONFIG["name"]
BASE_URL = (CONFIG.get("baseUrl") or "").rstrip("/")
BASE = (urlparse(BASE_URL).path.rstrip("/") + "/") if BASE_URL else "/"
SHARED = ("assets/", "api/", "badge/", "og/", "cartes/", "brouillons/", "rapport/")
TYPES = {"quotidien": "Relevé quotidien", "hebdo": "La semaine", "mensuel": "Le mois", "trimestriel": "Résultats trimestriels",
         "analyse": "Analyse", "dossier": "Dossier"}
BADGES = {"quotidien": "Quotidien", "hebdo": "Hebdo", "mensuel": "Mensuel", "trimestriel": "Résultats", "analyse": "Analyse", "dossier": "Dossier"}


def lpath(path, lang=None):
    path = path.lstrip("/")
    return path if path.startswith(SHARED) else i18n.prefix(lang) + path


def url(path=""):
    return BASE + lpath(path)


def abs_url(path="", lang=None):
    return (BASE_URL or "") + "/" + lpath(path, lang)


def tagline():
    return t(CONFIG["tagline"])


def description():
    return t(CONFIG["description"])


# ---------------------------------------------------------------- gabarit
def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def org():
    return {"@type": "NewsMediaOrganization", "name": NAME, "url": abs_url(""), "logo": abs_url("assets/icon.svg"),
            "description": description(), "publishingPrinciples": abs_url("methode/"), "correctionsPolicy": abs_url("corrections/")}


BELL = ('<svg class="nav-bell" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>')
GLOBE = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">'
         '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>')


def page(title, body, desc="", path="", extra_head="", og_type="website", ld=None, og_image="og/site.png", alts=None):
    """alts : langues dans lesquelles cette page existe (toutes par défaut)."""
    alts = [l for l in (alts or LANGS)]
    lang = i18n.CUR
    full = f"{title} | {NAME}" if title != NAME else NAME
    canon = f'<link rel="canonical" href="{esc(abs_url(path))}">' if BASE_URL else ""
    hreflang = "".join(f'<link rel="alternate" hreflang="{META[l]["html"]}" href="{esc(abs_url(path, l))}">' for l in alts) + (
        f'<link rel="alternate" hreflang="x-default" href="{esc(abs_url(path, "fr"))}">' if "fr" in alts and len(alts) > 1 else "")
    nav = [("", t("Articles")), ("classement/", t("Classement")), ("explorer/", t("Explorer")), ("alertes/", t("Alertes"))]
    v = CONFIG.get("verification", {})
    verif = "".join(f'<meta name="{n}" content="{esc(v[k])}">' for k, n in (("google", "google-site-verification"), ("bing", "msvalidate.01")) if v.get(k))
    an = CONFIG.get("analytics", {})
    beacon = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\'{{"token": "{esc(an["cloudflareToken"])}"}}\'></script>'
              if an.get("cloudflareToken") else "")
    cur = {"articles/": ""}.get(path, path)
    explore_kids = {"tendances/", "heures-de-pointe/", "mises-a-jour/", "records/", "comparer/", "studios/", "genres/", "monetisation/", "methode/",
                    "donnees/", "widget/", "actus-officielles/"}
    if path in explore_kids or path.startswith("genres/") or path.startswith("studios/"):
        cur = "explorer/"
    elif path.startswith("articles/"):
        cur = ""
    elif path.startswith("jeux/"):
        cur = "classement/"
    foot_cols = "".join(f'<div><h2>{esc(t(title_))}</h2><ul>' + "".join(f'<li><a href="{url(p_)}">{esc(t(n))}</a></li>' for p_, n, _ in items) + '</ul></div>'
                        for _, title_, _, items in pages2.EXPLORER_GROUPS) + (
        f'<div><h2>{t("Le média")}</h2><ul><li><a href="{url("articles/")}">{t("Tous les articles")}</a></li><li><a href="{url("classement/")}">{t("Classement en direct")}</a></li>'
        f'<li><a href="{url("alertes/")}">{t("Alertes")}</a></li><li><a href="{url("corrections/")}">{t("Corrections")}</a></li>'
        f'<li><a href="{url("partenaires/")}">{t("Partenaires")}</a></li><li><a href="{url("mentions-legales/")}">{t("Mentions légales")}</a></li>'
        f'<li><a href="{url("confidentialite/")}">{t("Confidentialité")}</a></li></ul></div>')
    links = "".join(f'<a href="{url(p)}"{" aria-current=page" if cur == p else ""}{" class=nav-alerts" if p == "alertes/" else ""}>{BELL if p == "alertes/" else ""}{n}</a>'
                    for p, n in nav)
    langs = "".join(f'<a href="{esc(BASE + lpath(path, l))}" hreflang="{META[l]["html"]}" lang="{META[l]["html"]}"'
                    f'{" aria-current=true" if l == lang else ""}>{META[l]["label"]}<span class="sr"> · {META[l]["name"]}</span></a>' for l in alts)
    switch = (f'<div class="lang" role="group" aria-label="{t("Langue")}">{GLOBE}{langs}</div>' if len(alts) > 1 else "")
    return f"""<!doctype html>
<html lang="{META[lang]["html"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full)}</title>
<meta name="description" content="{esc(desc or description())}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc or description())}">
<meta property="og:site_name" content="{esc(NAME)}">
<meta property="og:locale" content="{META[lang]["og"]}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{esc(abs_url(path))}">
<meta property="og:image" content="{esc(abs_url(og_image))}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{esc(abs_url(og_image))}">
{verif}
{jsonld(ld or {"@context": "https://schema.org", **org()})}
{canon}
{hreflang}
<link rel="alternate" type="application/rss+xml" title="{esc(NAME)}" href="{url('feed.xml')}">
<link rel="preload" href="{url('assets/fonts/schibsted-grotesk-latin-wght-normal.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{url('assets/style.css')}">
<link rel="icon" href="{url('assets/icon.svg')}" type="image/svg+xml">
{extra_head}
</head>
<body>
<a class="skip" href="#contenu">{t("Aller au contenu")}</a>
<header class="site-head">
  <a class="wordmark" href="{url()}"><span class="mark" aria-hidden="true"></span>{esc(NAME)}</a>
  <button class="menu-btn" type="button" aria-expanded="false" aria-controls="nav-main" aria-label="{t("Ouvrir le menu")}" data-close="{t("Fermer le menu")}"><span></span><span></span><span></span></button>
  <nav id="nav-main" aria-label="{t("Navigation principale")}">{links}<div class="search" data-index="{url('api/jeux/index.json')}" data-base="{url('jeux/')}"><label class="sr" for="q">{t("Rechercher un jeu")}</label><input id="q" type="search" placeholder="{t("Rechercher un jeu")}" autocomplete="off"><kbd class="kbd" aria-hidden="true">Ctrl K</kbd><ul class="search-res" hidden></ul></div>{switch}</nav>
</header>
{TICKER}
<main id="contenu">
{body}
</main>
<footer class="site-foot">
  <div class="foot-grid">
    <div class="foot-about">
      <a class="wordmark" href="{url()}"><span class="mark" aria-hidden="true"></span>{esc(NAME)}</a>
      <p>{esc(tagline())}.</p>
      <p class="foot-small">{t("Média indépendant, non affilié à Roblox Corporation. Roblox est une marque de Roblox Corporation. Articles rédigés automatiquement à partir de données publiques, chiffres vérifiés par programme. Mesure d’audience anonyme, sans cookie.")}</p>
    </div>
    {foot_cols}
  </div>
  <div class="foot-bar">{STATUS_HTML}<p class="foot-small">© {datetime.now().year} {esc(NAME)}</p></div>
</footer>
{'' if 'id="toast"' in body else '<div class="toast" id="toast" role="status" aria-live="polite"></div>'}
<script src="{url('assets/app.js')}" defer></script>
{beacon}
</body>
</html>
"""


# ---------------------------------------------------------------- articles
GAME_PAGES = {g.get("name", u): explore.game_slug(u, g.get("name", u)) for u, g in load_games().items() if g.get("name")}


def money(v):
    m = v / 1e6
    L = i18n.CUR
    if L == "en":
        return f"${fr_int(m)} million"
    if L == "es":
        return f"{fr_int(m)} millones de dólares"
    if L == "pt-br":
        return f"US$ {fr_int(m)} milhões"
    return f"{fr_int(m)} millions de dollars"


def loc_fact(key, f):
    """Affichage d'un fait dans la langue courante (le texte stocké, f["d"], est en français)."""
    v, d = f["v"], str(f["d"])
    if i18n.CUR == "fr":
        return d
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "%" in d:
            nd = 1 if "," in d else 0
            return fr_pct(v, nd=nd) if d[:1] in "+−-" else fr_share(v, nd=nd)
        if "de dollars" in d:
            return money(v)
        if "heures" in d:
            return fr_big(v) + {"en": " hours", "es": " de horas", "pt-br": " de horas"}[i18n.CUR]
        if key.endswith(".rang"):
            return fr_rank(int(v))
        if "million" in d or "milliard" in d:
            return fr_big(v)
        if key.endswith(".annee") or (isinstance(v, int) and v < 10000 and " " not in d and " " not in d and " " not in d):
            return str(v) if key.endswith(".annee") else fr_int(v)
        return fr_int(v) if float(v).is_integer() else d
    if isinstance(v, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            dd = date.fromisoformat(v)
            weekday = not d[:1].isdigit()
            return fr_date(dd, weekday=weekday)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", v) and key.endswith("heure"):
            return fr_hour(parse_iso(v))
        if key.endswith(".genre") or (key.startswith("genre.") and key.endswith(".nom")):
            return t(d)
    return d


def render_tokens(text, day, linked=True, used=None):
    def sub(m):
        d, key = m.group(1) or day, m.group(2)
        f = fact_for(d, key)
        shown = loc_fact(key, f)
        numeric = isinstance(f["v"], (int, float)) and not isinstance(f["v"], bool)
        if linked and not numeric and str(f["d"]) in GAME_PAGES:
            return f'<a class="jeu" href="{url("jeux/" + GAME_PAGES[str(f["d"])] + "/")}">{esc(shown)}</a>'
        if not linked or not numeric:
            return esc(shown) if linked else shown
        if used is not None:
            used.add((d, key))
        src = f.get("src", "")
        line = src.split("#L")[1] if "#L" in src else ""
        where = t("ligne {line} de {fichier}", line=line, fichier=src.split("#")[0]) if line else src
        href = src if src.startswith("http") else github_blob(src)
        return (f'<a class="fait" href="{esc(href)}" data-fact="{esc(f["l"])}" data-where="{esc(where)}">'
                f'{esc(shown)}</a>')
    return TOKEN.sub(sub, text)


def article_folder(lang, drafts=False):
    if lang == "fr":
        return ROOT / "drafts" if drafts else CONTENT / "articles"
    return (ROOT / "drafts" / "i18n" / lang) if drafts else (CONTENT / "i18n" / lang / "articles")


def load_articles(folder, strict=True):
    arts = []
    if not folder.exists():
        return arts
    for p in sorted(folder.glob("*.md")):
        errors, warnings, meta, body = verify(p)
        if errors:
            msg = f"Article bloqué par le vérificateur : {p}\n  " + "\n  ".join(errors)
            if strict:
                raise SystemExit(msg)
            print(msg)
            continue
        day = meta["jour"]
        slug = p.stem
        used = set()
        body_html = markdown.markdown(render_tokens(body, day, used=used), extensions=["extra", "sane_lists"])

        def graph(m):
            d, gid = m.group(1) or day, m.group(2)
            g = dict(load_facts(d)["graphiques"][gid])
            m_h = re.match(r"^(.*) au relevé de (\d{1,2})\s*h\s*(\d{2})$", g["titre"])
            if m_h and i18n.CUR != "fr":
                hh = datetime(2000, 1, 1, int(m_h.group(2)), int(m_h.group(3)), tzinfo=TZ)
                g["titre"] = t("{titre} au relevé de {heure}", titre=t(m_h.group(1)), heure=fr_hour(hh))
            else:
                g["titre"] = t(g["titre"])
            g["unite"] = t(g.get("unite", ""))
            if g.get("rows") and g.get("unite") == "%":      # catégories (genres, années) ; les noms de jeux ne se traduisent pas
                g["rows"] = [{**r, "nom": t(r["nom"])} for r in g["rows"]]
            return charts.render(gid, g)
        body_html = re.sub(r"<p>\s*(\{\{\s*graphique:[^}]+\}\})\s*</p>", lambda m: GRAPH.sub(graph, m.group(1)), body_html)
        body_html = GRAPH.sub(graph, body_html)
        pub = meta.get("publie") or f"{day[:10]}T08:00"
        try:
            pub_dt = datetime.fromisoformat(pub).replace(tzinfo=TZ) if "Z" not in pub else parse_iso(pub)
        except ValueError:
            pub_dt = datetime.fromisoformat(day[:10]).replace(tzinfo=TZ)
        arts.append({"slug": slug, "meta": meta, "day": day, "pub": pub_dt, "html": body_html, "used": used,
                     "title": render_tokens(meta["titre"], day, linked=False),
                     "chapo": render_tokens(meta["chapo"], day, linked=False),
                     "chapo_html": render_tokens(meta["chapo"], day, used=used), "warnings": warnings})
    arts.sort(key=lambda a: a["pub"], reverse=True)
    return arts


ARTICLE_LANGS = {}


def article_page(a, prefix="articles", related=()):
    f = load_facts(a["day"])
    cov = f["couverture"] if f else None
    sources = sorted({fact_for(d, k).get("src", "").split("#")[0] for d, k in a["used"]} - {""})
    src_list = "".join(f'<li><a href="{esc(s if s.startswith("http") else github_blob(s) if s.endswith(".csv") else github_tree(s))}">{esc(s)}</a></li>' for s in sources)
    d = datetime.fromisoformat(a["day"][:10]).date()
    kind = t(TYPES.get(a["meta"]["type"], "Article"))
    if f and f["couverture"].get("instantane"):
        when = t(", relevé du {date} à {heure}", date=fr_date(d), heure=fr_hour(parse_iso(f["faits"]["releve.heure"]["v"])))
    elif f:
        when = t(", données du {date}", date=fr_date(d))
    else:
        when = ""
    pub = t("Publié le {date} à {heure}.", date=fr_date(a["pub"].date(), weekday=False), heure=fr_hour(a["pub"]))
    cover_txt = (t("Journée couverte par {n} relevés horaires sur {total}. ", n=cov["releves"], total=cov["attendus"])
                 if cov and not cov.get("instantane") else "")
    body = f"""<article class="article">
<header class="article-head">
  <h1>{esc(a['title'])}</h1>
  <p class="chapo">{a['chapo_html']}</p>
  {byline(a)}
  <p class="dateline">{esc((kind + when + ". " + pub).replace(".. ", ". ").replace("..", "."))}</p>
</header>
<div class="prose">
{a['html']}
</div>
{share_bar(a, prefix)}
{newsletter_box('article') if prefix == 'articles' else ''}
<aside class="provenance" aria-labelledby="prov-{esc(a['slug'])}">
  <h2 id="prov-{esc(a['slug'])}">{t("D’où viennent ces chiffres")}</h2>
  <p class="checked"><span class="check" aria-hidden="true"></span>{t("{n} chiffres dans cet article, tous reliés à leur source. Cliquez sur un chiffre souligné pour ouvrir le document ou la ligne exacte du fichier de données d’où il vient.", n=len(a['used']))}</p>
  <p>{esc(cover_txt)}{t("Le texte a été rédigé par une IA à partir de ces chiffres, puis contrôlé avant publication.")}{"" if i18n.CUR == "fr" else " " + t("Cette version est une traduction de l’article original en français.")} <a href="{url('methode/')}">{t("Comment nous travaillons")}</a>.</p>
  <ul class="files">{src_list}</ul>
  <p>{t("Une erreur ?")} <a href="{url('corrections/')}">{t("Signalez-la")}</a>{t(" : chaque correction est publiée.")}</p>
</aside>
</article>{related_html(related)}"""
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": a["title"], "description": a["chapo"],
          "datePublished": a["pub"].isoformat(), "inLanguage": META[i18n.CUR]["html"], "isAccessibleForFree": True,
          "mainEntityOfPage": abs_url(f"{prefix}/{a['slug']}/"), "author": org(), "publisher": org(),
          "isBasedOn": [s if s.startswith("http") else github_blob(s) for s in sources][:20]}
    alts = ["fr"] if prefix == "brouillons" else ARTICLE_LANGS.get(a["slug"], [i18n.CUR])
    return page(a["title"], body, a["chapo"], f"{prefix}/{a['slug']}/", og_type="article", ld=ld, og_image=f"og/articles/{a['slug']}.png",
                extra_head=f'<meta property="article:published_time" content="{a["pub"].isoformat()}">'
                           + ('<meta name="robots" content="noindex">' if prefix == "brouillons" else ""), alts=alts)


def share_bar(a, prefix):
    link = abs_url(f"{prefix}/{a['slug']}/")
    x = f"https://twitter.com/intent/tweet?text={quote(a['title'])}&url={quote(link)}"
    li = f"https://www.linkedin.com/sharing/share-offsite/?url={quote(link)}"
    return (f'<div class="share-bar" aria-label="{t("Partager cet article")}"><span class="share-label">{t("Partager")}</span>'
            f'<a class="share x" href="{esc(x)}" target="_blank" rel="noopener">'
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.8 3h3.1l-6.8 7.7L22 21h-6.2l-4.9-6.4L5.3 21H2.2l7.2-8.3L1.8 3h6.4l4.4 5.8L17.8 3Zm-1.1 16.2h1.7L7.4 4.7H5.5l11.2 14.5Z"/></svg>X</a>'
            f'<a class="share li" href="{esc(li)}" target="_blank" rel="noopener">'
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9.5h4V21H3V9.5Zm6.5 0h3.8v1.6h.1c.5-1 1.8-2 3.8-2 4 0 4.8 2.6 4.8 6V21h-4v-5.2c0-1.2 0-2.9-1.8-2.9s-2 1.4-2 2.8V21h-4V9.5Z"/></svg>LinkedIn</a>'
            f'<button class="share copy" type="button" data-copy="{esc(link)}" data-copy-msg="{t("Lien copié !")}">'
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>'
            f'{t("Copier le lien")}</button></div>')


def related_html(related):
    if not related:
        return ""
    return (f'<section class="related" aria-labelledby="rel-h"><h2 id="rel-h" class="sec-title">{t("À lire aussi")}</h2>'
            f'<ol class="cards grid3">{"".join(card(r) for r in related)}</ol></section>')


def pick_related(a, arts, n=3):
    others = [x for x in arts if x["slug"] != a["slug"]]
    others.sort(key=lambda x: (x["meta"]["type"] != a["meta"]["type"], -x["pub"].timestamp()))
    return others[:n]


ICONS_BY_SLUG = {}


def reading_time(a):
    words = len(re.sub(r"<[^>]+>", " ", a["html"]).split())
    return max(1, round(words / 220))


def byline(a):
    return (f'<span class="byline"><span class="rt"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
            f'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>{t("{n} min de lecture", n=reading_time(a))}</span>'
            f'<span class="auto">{t("Rédaction automatisée, chiffres vérifiés par programme")}</span></span>')


def badge(a):
    return f'<span class="tag">{esc(t(BADGES.get(a["meta"]["type"], "Article")))}</span>'


def cover(a):
    """Couverture 16:9 : l'image de l'en-tête si elle existe, sinon une composition des icônes des jeux cités."""
    if a["meta"].get("image"):
        return f'<div class="cover"><img src="{esc(a["meta"]["image"])}" alt="" loading="lazy"></div>'
    slugs = []
    for m in re.finditer(r'jeux/([^/"]+)/', a["html"]):
        if m.group(1) not in slugs and ICONS_BY_SLUG.get(m.group(1)):
            slugs.append(m.group(1))
    icons = "".join(f'<img src="{esc(ICONS_BY_SLUG[sl])}" alt="" loading="lazy">' for sl in slugs[:5])
    return (f'<div class="cover gen{" has-icons" if icons else ""}" aria-hidden="true"><span class="cover-grid"></span>'
            f'<span class="cover-icons">{icons}</span><span class="cover-mark"><span class="mark"></span>{esc(NAME)}</span></div>')


def card(a, lead=False):
    href = url("articles/" + a["slug"] + "/")
    if lead:
        return (f'<article class="hero-card"><a href="{href}">{cover(a)}<div class="hero-body">{badge(a)}<h2>{esc(a["title"])}</h2>'
                f'<p>{esc(a["chapo"])}</p><span class="meta">{esc(fr_date(a["pub"].date(), weekday=False))}</span>{byline(a)}</div></a></article>')
    return (f'<li class="card"><a href="{href}">{badge(a)}<h3>{esc(a["title"])}</h3>'
            f'<p>{esc(a["chapo"])}</p><span class="meta">{esc(fr_date(a["pub"].date(), weekday=False))} · {reading_time(a)} min</span></a></li>')


# ---------------------------------------------------------------- classement en direct
def latest_snapshots(hours=25):
    now = utc_now().replace(minute=0, second=0)
    out = []
    for k in range(0, 24 * 3):
        rows = read_csv(snap_path("snapshots", now - timedelta(hours=k)))
        if rows:
            out.append((parse_iso(rows[0]["ts_utc"]), {r["universe_id"]: r for r in rows}))
        if len(out) >= hours:
            break
    return list(reversed(out))


def live_data(limit=100):
    snaps = latest_snapshots()
    if not snaps:
        return None
    games = load_games()
    ts, last = snaps[-1]
    prev = next((sn for t_, sn in reversed(snaps[:-1]) if 1800 <= (ts - t_).total_seconds() <= 3 * 3600), None)
    prev_rank = {u: i + 1 for i, u in enumerate(sorted(prev, key=lambda u: -int(prev[u]["playing"] or 0)))} if prev else {}
    window = [s for s in snaps if (ts - s[0]).total_seconds() <= 24 * 3600]
    ranked = sorted(last.values(), key=lambda r: -int(r["playing"] or 0))[:limit]
    rows = []
    for i, r in enumerate(ranked, 1):
        u = r["universe_id"]
        series = [int(s[1][u]["playing"] or 0) for s in window if u in s[1]]
        g = games.get(u, {})
        rows.append({"rang": i, "uid": u, "nom": g.get("name", u), "createur": g.get("creator_name", ""),
                     "genre": GENRES_FR.get(g.get("genre_l1", ""), g.get("genre_l1", "")), "place": g.get("root_place_id", ""),
                     "maintenant": int(r["playing"] or 0), "pic24": max(series) if series else 0, "serie": series,
                     "slug": explore.game_slug(u, g.get("name", u)), "icon": g.get("icon", ""),
                     "var": (int(r["playing"] or 0) / int(prev[u]["playing"]) - 1) if prev and u in prev and int(prev[u]["playing"] or 0) > 0 else None,
                     "rang_avant": prev_rank.get(u) if prev else None, "has_prev": bool(prev)})
    return {"ts": ts, "rows": rows, "n": len(last), "file": str(snap_path("snapshots", ts).relative_to(DATA.parent)) if str(DATA).startswith(str(ROOT)) else "data/snapshots"}


def move_html(r):
    if not r.get("has_prev"):
        return ""
    if r["rang_avant"] is None or r["rang_avant"] > 100:
        return f'<span class="mv new" title="{t("Nouveau dans le top 100")}">{t("nouveau")}</span>'
    d = r["rang_avant"] - r["rang"]
    if d > 0:
        return f'<span class="mv up" title="{t("Gagne {n} place(s) en une heure", n=d)}">↑{d}</span>'
    if d < 0:
        return f'<span class="mv down" title="{t("Perd {n} place(s) en une heure", n=-d)}">↓{-d}</span>'
    return ""


def var_html(r):
    v = r.get("var")
    if v is None:
        return ""
    cls = "up" if v >= 0.005 else ("down" if v <= -0.005 else "flat")
    return f'<span class="pill {cls}" title="{t("Variation sur une heure")}">{esc(fr_pct(v))}</span>'


def trend_of(r):
    v = r.get("var")
    return None if v is None else ("down" if v < 0 else "up")


def icon_html(r, size=36):
    if not r.get("icon"):
        return f'<span class="gicon ph" style="width:{size}px;height:{size}px" aria-hidden="true"></span>'
    return f'<img class="gicon" src="{esc(r["icon"])}" alt="" width="{size}" height="{size}" loading="lazy" decoding="async">'


def live_table(live, compact_rows=None):
    rows = live["rows"][:compact_rows] if compact_rows else live["rows"]
    trs = []
    for r in rows:
        href = url("jeux/" + r["slug"] + "/")
        name = f'<a href="{href}">{esc(r["nom"])}</a>'
        g = t(r["genre"]) if r["genre"] else ""
        trs.append(f'<tr data-href="{href}" data-genre="{esc(g)}"><td class="num rank"><div class="rk">{r["rang"]}{move_html(r)}</div></td><td class="game"><div class="gcell">{icon_html(r)}<div>{name}<span class="sub">{esc(r["createur"])}</span></div></div></td>'
                   f'<td class="num{" hot" if (r.get("var") or 0) > 0.10 else ""}" data-v="{r["maintenant"]}">{fr_int(r["maintenant"])}{var_html(r)}</td>'
                   f'<td class="num hide-s" data-v="{r["pic24"]}">{fr_int(r["pic24"])}</td>'
                   f'<td class="spark-cell hide-s">{charts.sparkline(r["serie"], trend=trend_of(r))}</td>'
                   f'<td class="hide-m">{esc(g)}</td></tr>')
    counts = {}
    for r in rows:
        counts[r["genre"]] = counts.get(r["genre"], 0) + 1
    genres = [g for g, _ in sorted(counts.items(), key=lambda kv: -kv[1]) if g][:6]
    filt = (f'<div class="filters" role="group" aria-label="{t("Filtrer par genre")}"><button type="button" class="chip on" data-filter="">{t("Tous")}</button>'
            + "".join(f'<button type="button" class="chip" data-filter="{esc(t(g))}">{esc(t(g))}</button>' for g in genres) + "</div>") if compact_rows is None else ""
    return (filt + f'<div class="table-wrap sticky-head"><table class="live sortable"><thead><tr><th scope="col" class="num" data-sort="num">{t("Rang")}</th>'
            f'<th scope="col">{t("Jeu")}</th><th scope="col" class="num" data-sort="num">{t("Joueurs en ligne")}</th>'
            f'<th scope="col" class="num hide-s" data-sort="num">{t("Pic sur 24 h")}</th><th scope="col" class="hide-s">{t("24 dernières heures")}</th>'
            f'<th scope="col" class="hide-m">{t("Genre")}</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')


def stamp(live):
    ts = live["ts"]
    return t("Relevé du {date} à {heure}, heure de Paris", date=fr_date(ts.astimezone(TZ).date(), weekday=False), heure=fr_hour(ts))


TICKER = ""
STATUS_HTML = ""

RAPPORT_SOMMAIRE = ["Ce qu’il faut retenir : les chiffres du mois en sept points", "Roblox Corporation : derniers résultats, utilisateurs, prévisions",
                    "Le top 100 : qui capte l’audience, et dans quelles proportions", "Genres et studios : la carte du marché",
                    "L’âge des jeux : renouvellement et doyens", "Monétisation : le prix des game passes",
                    "Le mois heure par heure : pointes, records, plus fortes hausses et baisses", "Les records historiques, sources à l’appui"]


def newsletter_box(variant="article"):
    """Formulaire d'inscription beehiiv, en iframe : aucun script tiers ni cookie déposé sur le site."""
    fid = CONFIG.get("newsletter", {}).get("beehiivFormId")
    if not fid:
        return ""
    title = {"article": t("Recevoir PlayLedger par e-mail"), "home": t("La newsletter"), "rapport": t("Recevoir le rapport")}[variant]
    text = {"article": t("Les chiffres clés de Roblox, une fois par semaine, et le rapport mensuel « État de Roblox » en PDF. Gratuit, désinscription en un clic."),
            "home": t("Les chiffres clés de la semaine et le rapport mensuel, dans votre boîte. Gratuit."),
            "rapport": t("Inscrivez-vous : vous recevrez chaque édition dès sa sortie, puis la newsletter hebdomadaire. Gratuit, désinscription en un clic.")}[variant]
    src = f"https://subscribe-forms.beehiiv.com/v3/forms/{fid}"
    return (f'<section class="nl-box nl-{variant}"><h2>{esc(title)}</h2><p>{esc(text)}</p>'
            f'<iframe class="nl-frame" src="{esc(src)}" title="{esc(t("Inscription à la newsletter"))}" loading="lazy"></iframe>'
            f'<p class="nl-legal">{t("Envoi par beehiiv. Vos données :")} <a href="{url("confidentialite/")}">{t("politique de confidentialité")}</a>.</p></section>')


def rapport_page():
    nl = CONFIG.get("newsletter", {})
    first = CONFIG.get("rapport", {}).get("premiereEdition", "")
    when = fr_date(datetime.fromisoformat(first).date(), weekday=False) if first else ""
    som = "".join(f"<li>{esc(x)}</li>" for x in RAPPORT_SOMMAIRE)
    if nl.get("beehiivFormId"):
        cta = (f'<div class="rp-form"><span class="tag">{esc("Première édition le " + when)}</span>' + newsletter_box("rapport") + '</div>')
        robots = ""
    else:
        cta = (f'<div class="rp-form soon-box"><span class="tag">Bientôt</span><h2>Première édition le {esc(when)}</h2>'
               f'<p>Le rapport sera envoyé gratuitement aux inscrits. L’inscription ouvre avec la première édition.</p>'
               f'<p><a class="btn" href="{url("alertes.xml")}">En attendant, suivre les alertes (RSS)</a></p></div>')
        robots = '<meta name="robots" content="noindex">'
    body = (f'<div class="wide rapport"><div class="rp-hero"><div><p class="kicker">Baromètre mensuel · gratuit</p><h1>État de Roblox</h1>'
            f'<p class="lede">Chaque mois, un rapport PDF d’une dizaine de pages sur l’économie de Roblox : ce que jouent vraiment les joueurs, qui capte l’audience, '
            f'comment les jeux se monétisent. Chaque chiffre est cliquable et renvoie à sa source.</p>'
            f'<ul class="rp-points"><li>Calculé sur des milliers de relevés horaires des API publiques de Roblox</li>'
            f'<li>Croisé avec les résultats officiels de Roblox Corporation</li><li>Pensé pour les studios, les marques et les investisseurs</li></ul></div>{cta}</div>'
            f'<h2 class="sec-title">Au sommaire</h2><ol class="rp-som">{som}</ol></div>')
    return page("Rapport « État de Roblox »", body, "Le baromètre mensuel gratuit de l’économie de Roblox, en PDF, chaque chiffre sourcé.", "rapport/",
                extra_head=robots, alts=["fr"])


def status_html(status):
    last = status.get("lastRunAt")
    if not last:
        return ""
    ts = parse_iso(last)
    late = (utc_now() - ts).total_seconds() > 2.5 * 3600
    ok = status.get("ok") and not late
    label = t("Opérationnel") if ok else (t("Retard") if late else t("Incident"))
    return (f'<p class="feed-status {"ok" if ok else "ko"}" data-last="{last}"><span class="fs-dot" aria-hidden="true"></span>'
            f'{t("État des relevés Roblox :")} <strong>{label}</strong> <span class="sep">•</span> '
            f'{t("Dernier relevé à {heure} ({n} jeux)", heure=fr_hour(ts), n=fr_int(status.get("gamesMeasured", 0)))}<span class="fs-next"></span></p>')


def ticker_html(arts, live, alerts):
    items = []
    if arts:
        pick, label = headline_pick(arts)
        items.append(f'<a class="tk-item tk-une" href="{url("articles/" + pick["slug"] + "/")}"><span class="tk-label">{label}</span>{esc(pick["title"])}</a>')
    if live:
        moves = [r for r in live["rows"][:50] if r.get("var") is not None]
        ups = sorted(moves, key=lambda r: -r["var"])[:3]
        downs = sorted(moves, key=lambda r: r["var"])[:2]
        for r in ups + downs:
            items.append(f'<a class="tk-item" href="{url("jeux/" + r["slug"] + "/")}">{esc(r["nom"])} <b>{fr_int(r["maintenant"])}</b>{var_html(r)}</a>')
    for a in alerts[:2]:
        items.append(f'<a class="tk-item tk-alert" href="{url("alertes/")}"><span class="tk-label">{t("Alerte")}</span>{esc(a["nom"])}</a>')
    if not items:
        return ""
    row = "".join(items)
    return (f'<div class="ticker" role="region" aria-label="{t("Fil d’actualité")}"><div class="tk-track">'
            f'<div class="tk-row">{row}</div><div class="tk-row" aria-hidden="true">{row}</div></div></div>')


def headline_pick(arts):
    pick, label = arts[0], t("Dernier article")
    pop = DATA / "populaires.json"
    if pop.exists():
        try:
            paths = [x["path"] for x in json.loads(pop.read_text(encoding="utf-8")).get("pages", [])]
            by_path = {url("articles/" + a["slug"] + "/"): a for a in arts}
            for pth in paths:
                if pth in by_path:
                    return by_path[pth], t("Le plus lu")
        except (ValueError, KeyError):
            pass
    return pick, label


# ---------------------------------------------------------------- pages
def static_page(name, lang):
    src = CONTENT / f"{name}.md" if lang == "fr" else CONTENT / "i18n" / lang / f"{name}.md"
    if not src.exists():
        src = CONTENT / f"{name}.md"
    text = src.read_text(encoding="utf-8") if src.exists() else ""
    contact = f"[{CONFIG['contact']}](mailto:{CONFIG['contact']})" if CONFIG.get("contact") else t("L’adresse de contact arrive très bientôt.")
    return (text.replace("{{depot}}", github_tree("")).replace("{{donnees}}", github_tree("data")).replace("{{nom}}", NAME)
            .replace("{{contact}}", contact))


def build(drafts=False):
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    live = live_data()
    status = json.loads((DATA / "status.json").read_text()) if (DATA / "status.json").exists() else {}
    ICONS_BY_SLUG.update({explore.game_slug(u, g.get("name", u)): g.get("icon", "") for u, g in load_games().items()})
    alerts = list(reversed(read_csv(DATA / "alertes.csv")))
    recs, latest_ts = explore.build_records()

    def write(path, content, shared=False):
        p = OUT / (path if shared else lpath(path))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # ---- éléments communs à toutes les langues (français)
    i18n.set_lang("fr")
    arts_by_lang = {}
    for l in LANGS:          # chaque langue charge ses articles avec ses propres formats (nombres, dates, liens)
        i18n.set_lang(l)
        arts_by_lang[l] = load_articles(article_folder(l))
    i18n.set_lang("fr")
    for l, arts_l in arts_by_lang.items():
        for a in arts_l:
            ARTICLE_LANGS.setdefault(a["slug"], []).append(l)
    (OUT / "og" / "articles").mkdir(parents=True, exist_ok=True)
    (OUT / "og" / "jeux").mkdir(parents=True, exist_ok=True)
    og.site_card(OUT / "og" / "site.png", CONFIG["tagline"])
    arts_fr = arts_by_lang["fr"]

    def og_article(a):
        slugs = [m.group(1) for m in re.finditer(r'jeux/([^/"]+)/', a["html"])]
        icons = [ICONS_BY_SLUG.get(sl) for sl in dict.fromkeys(slugs) if ICONS_BY_SLUG.get(sl)]
        og.article_card(OUT / "og" / "articles" / f"{a['slug']}.png", BADGES.get(a["meta"]["type"], "Article"), a["title"],
                        fr_date(a["pub"].date(), weekday=False), icons)

    for a in arts_fr:
        og_article(a)
    (OUT / "badge").mkdir(parents=True, exist_ok=True)
    for rec in recs:
        if rec["rang"] and rec["rang"] <= 100:
            og.game_card(OUT / "og" / "jeux" / f"{rec['universe_id']}.png", rec["nom"], rec["icon"], rec["joueurs"], rec["rang"],
                         [v for _, v in rec["serie"]], None)
        (OUT / "badge" / f"{rec['universe_id']}.svg").write_text(og.badge_svg(rec["rang"], rec["joueurs"], rec["nom"]), encoding="utf-8")
    prev_ranks = {r["uid"]: {"var": round(r["var"], 4) if r.get("var") is not None else None, "rang": r.get("rang_avant")} for r in (live["rows"] if live else [])}
    for path_, content in explore.api_files(recs, latest_ts, alerts, prev_ranks).items():
        write(path_, content, shared=True)

    global TICKER, STATUS_HTML
    sitemap = []
    for lang in LANGS:
        i18n.set_lang(lang)
        arts = arts_by_lang[lang]
        STATUS_HTML = status_html(status)
        TICKER = ticker_html(arts, live, alerts)

        for a in arts:
            if lang != "fr":
                og_path = OUT / "og" / "articles" / f"{a['slug']}.png"
                if not og_path.exists():
                    og_article(a)
            write(f"articles/{a['slug']}/index.html", article_page(a, related=pick_related(a, arts)))
        if drafts and lang == "fr":
            for a in load_articles(ROOT / "drafts", strict=False):
                og_article(a)
                write(f"brouillons/{a['slug']}/index.html", article_page(a, "brouillons"), shared=True)

        # accueil
        pulse = pulse_m = ""
        if live:
            top = live["rows"][:5]
            items = "".join(f'<li><span class="p-rank">{r["rang"]}{move_html(r)}</span><span class="p-id">{icon_html(r, 28)}<a class="p-name" href="{url("jeux/" + r["slug"] + "/")}">{esc(r["nom"])}</a></span>'
                            f'<span class="p-val">{fr_int(r["maintenant"])}{var_html(r)}</span>{charts.sparkline(r["serie"], 96, 24, trend_of(r))}</li>' for r in top)
            pulse = (f'<section class="pulse" aria-labelledby="pulse-h"><h2 id="pulse-h">{t("En ce moment sur Roblox")}</h2>'
                     f'<p class="stamp">{esc(stamp(live))}. {t("Joueurs en ligne par jeu.")}</p><ol>{items}</ol>'
                     f'<a class="cta-top" href="{url("classement/")}">{t("Voir tout le top 100")} <span aria-hidden="true">→</span></a></section>')
            items_m = "".join(f'<li><span class="p-rank">{r["rang"]}</span>{icon_html(r, 24)}<a class="p-name" href="{url("jeux/" + r["slug"] + "/")}">{esc(r["nom"])}</a>'
                              f'<span class="p-val">{fr_int(r["maintenant"])}</span></li>' for r in live["rows"][:3])
            pulse_m = (f'<section class="pulse-m mobile-only" aria-label="{t("En ce moment sur Roblox")}"><div class="pm-head"><span class="live-dot" aria-hidden="true"></span>{t("En ce moment")}'
                       f'<span class="pm-stamp">{esc(stamp(live))}</span></div><ol>{items_m}</ol>'
                       f'<a class="cta-top" href="{url("classement/")}">{t("Tout le top 100")} <span aria-hidden="true">→</span></a></section>')
        if arts:
            lead, _ = headline_pick(arts)
            rest = [a for a in arts if a is not lead]
            feed = (card(lead, lead=True) + pulse_m + f'<ol class="cards grid2">{"".join(card(a) for a in rest[:4])}</ol>'
                    + (f'<h2 class="sec-title">{t("Plus d’articles")}</h2><ol class="cards list">{"".join(card(a) for a in rest[4:14])}</ol>' if len(rest) > 4 else "")
                    + (f'<p class="more"><a href="{url("articles/")}">{t("Tous les articles")}</a></p>' if len(rest) > 14 else ""))
        else:
            feed = (pulse_m + f'<div class="empty"><h2>{t("Les analyses arrivent dans cette langue")}</h2><p>{t("Le classement, les pages de jeux et les alertes sont déjà disponibles et se mettent à jour toutes les heures.")}</p>'
                    f'<p class="empty-links"><a class="btn" href="{url("classement/")}">{t("Voir le classement en direct")}</a> <a class="btn ghost" href="{url("comparer/")}">{t("Comparer deux jeux")}</a></p></div>')
        intro = (f'<section class="intro"><h1>{esc(tagline())}</h1><p>{esc(description())}</p>'
                 f'<a class="trust" href="{url("methode/")}"><span class="check" aria-hidden="true"></span>{t("Chaque chiffre est sourcé")} <span class="trust-go">{t("Méthode")} <span aria-hidden="true">→</span></span></a></section>')
        write("index.html", page(NAME, f'<div class="home"><div class="main-col">{intro}<section class="feed" aria-label="{t("Derniers articles")}">{feed}</section></div><aside class="side-col">{pulse}{newsletter_box("home")}</aside></div>', path=""))
        write("articles/index.html", page(t("Tous les articles"), f'<div class="narrow"><h1>{t("Tous les articles")}</h1><ol class="cards list">{"".join(card(a) for a in arts)}</ol></div>', path="articles/"))

        if live:
            body = (f'<div class="wide"><h1>{t("Classement en direct")}</h1><p class="lede">{t("Les 100 jeux Roblox qui comptent le plus de joueurs en ligne.")} '
                    f'{esc(stamp(live))}{t(", mis à jour toutes les heures.")}</p>{live_table(live)}'
                    f'<p class="note">{t("Source : API web publiques de Roblox,")} <a href="{esc(github_tree("data/snapshots"))}">{t("relevés horaires archivés")}</a>. '
                    f'{t("Le pic sur 24 h est le plus haut des relevés horaires : le pic réel peut être un peu plus élevé. Jeux sponsorisés exclus des classements.")}</p></div>')
        else:
            body = f'<div class="narrow"><h1>{t("Classement en direct")}</h1><p>{t("Le premier relevé n’a pas encore eu lieu.")}</p></div>'
        write("classement/index.html", page(t("Classement en direct des jeux Roblox"), body,
                                            t("Les 100 jeux Roblox les plus joués en ce moment, mis à jour toutes les heures."), "classement/"))

        indexable = []
        for rec in recs:
            html_, ok = explore.game_page(rec, page, url, recs)
            write(f"jeux/{rec['slug']}/index.html", html_)
            if ok:
                indexable.append(f"jeux/{rec['slug']}/")
            write(f"widget/jeu/{rec['universe_id']}/index.html", explore.game_widget(rec, abs_url))
        if recs:
            write("comparer/index.html", explore.compare_page(recs, page, url))
        write("alertes/index.html", explore.alerts_page(alerts, page, url, live))
        write("alertes.xml", explore.alerts_feed(alerts, abs_url))
        write("donnees/index.html", explore.data_page(page, url))
        write("tendances/index.html", pages2.trends_page(recs, page, url))
        write("mises-a-jour/index.html", pages2.updates_page(recs, page, url))
        write("heures-de-pointe/index.html", pages2.peak_page(recs, page, url))
        write("records/index.html", pages2.records_page(recs, page, url))
        if recs:
            import resumes
            write("joueurs-roblox-en-ce-moment/index.html", resumes.players_now_page(page, url, recs, latest_ts, loc_fact, github_blob, charts))
            write("jeux-roblox-les-plus-joues/index.html", resumes.most_played_page(page, url, recs, latest_ts))
        st_pages, _ = pages2.studios_pages(recs, page, url)
        g_pages = pages2.genres_pages(recs, page, url)
        for path_, content in {**st_pages, **g_pages}.items():
            write(path_, content)
        write("explorer/index.html", pages2.explorer_page(page, url))
        write("monetisation/index.html", pages2.monetization_page(recs, page, url))
        write("actus-officielles/index.html", pages2.official_page(page, url))
        write("widget/index.html", explore.widget_page(live, url, abs_url))

        statics = (("methode", "Méthode", "Comment nous relevons, calculons et vérifions chaque chiffre."),
                   ("partenaires", "Partenaires", "Annoncer auprès des pros de Roblox, études et données sur mesure."),
                   ("corrections", "Corrections", "Les erreurs signalées et leur correction."),
                   ("mentions-legales", "Mentions légales", "Éditeur, hébergeur et données personnelles."),
                   ("confidentialite", "Politique de confidentialité", "Quelles données nous collectons, pourquoi, et comment exercer vos droits."))
        for name, title, desc in statics:
            text = static_page(name, lang)
            write(f"{name}/index.html", page(t(title), f'<div class="narrow prose page">{markdown.markdown(text, extensions=["extra"])}</div>', t(desc), f"{name}/"))

        write("404.html", page(t("Page introuvable"), f'<div class="narrow"><h1>{t("Cette page n’existe pas")}</h1><p><a href="{url()}">{t("Revenir à l’accueil")}</a>.</p></div>'))

        # flux RSS (sert aussi à la newsletter)
        items = "".join(
            f"<item><title>{esc(a['title'])}</title><link>{esc(abs_url('articles/' + a['slug'] + '/'))}</link>"
            f"<guid isPermaLink=\"true\">{esc(abs_url('articles/' + a['slug'] + '/'))}</guid>"
            f"<pubDate>{format_datetime(a['pub'].astimezone(UTC))}</pubDate><description>{esc(a['chapo'])}</description>"
            f"<content:encoded><![CDATA[<p><strong>{html.escape(a['chapo'])}</strong></p>{a['html']}]]></content:encoded></item>"
            for a in arts[:30])
        write("feed.xml", f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
                          f"<channel><title>{esc(NAME)}</title><link>{esc(abs_url())}</link><description>{esc(description())}</description>"
                          f"<language>{META[lang]['html']}</language>{items}</channel></rss>")

        extra = (["rapport/"] if CONFIG.get("newsletter", {}).get("beehiivFormId") and lang == "fr" else []) + ["joueurs-roblox-en-ce-moment/", "jeux-roblox-les-plus-joues/", "monetisation/", "actus-officielles/", "tendances/", "mises-a-jour/", "heures-de-pointe/", "records/", "studios/", "genres/", "explorer/"] + \
                [p.replace("index.html", "") for p in st_pages if '<meta name="robots"' not in st_pages[p] and p != "studios/index.html"] + \
                [p.replace("index.html", "") for p in g_pages if p != "genres/index.html"]
        paths = ["", "classement/", "alertes/", "comparer/", "donnees/", "methode/", "articles/", "partenaires/"] + indexable + extra
        sitemap += [(p, None) for p in paths] if lang == "fr" else []
        if lang == "fr":
            sitemap += [(f"articles/{a['slug']}/", ARTICLE_LANGS.get(a["slug"])) for a in arts]

        if lang == "fr":
            write("rapport/index.html", rapport_page(), shared=True)
            # PDF du rapport (généré par tools/rapport.py dans out/rapport/) : lien envoyé par e-mail, non listé ni indexé
            pdfs = sorted((ROOT / "out" / "rapport").glob("etat-de-roblox-*.pdf"))
            if pdfs:
                (OUT / "rapport" / "pdf").mkdir(parents=True, exist_ok=True)
                for p_ in pdfs:
                    shutil.copy(p_, OUT / "rapport" / "pdf" / p_.name)
                shutil.copy(pdfs[-1], OUT / "rapport" / "pdf" / "derniere-edition.pdf")
            else:   # avant la première édition : une page d'attente, pour que le lien de l'e-mail de bienvenue ne soit jamais cassé
                (OUT / "rapport" / "pdf").mkdir(parents=True, exist_ok=True)
                og.waiting_pdf(OUT / "rapport" / "pdf" / "derniere-edition.pdf", NAME,
                               fr_date(datetime.fromisoformat(CONFIG.get("rapport", {}).get("premiereEdition", "2026-11-01")).date(), weekday=False))
            try:
                import cartes
                import rapport as rapport_mod
                made = cartes.make(rapport_mod.collect(*cartes.latest_month()), OUT / "cartes")
                figs = "".join(f'<figure class="carte"><a href="{url("cartes/" + f)}" download><img src="{url("cartes/" + f)}" alt="{esc(x)}" loading="lazy" width="1080" height="1350"></a>'
                               f'<figcaption>{esc(x)} · <a href="{url("cartes/" + f)}" download>Télécharger</a></figcaption></figure>' for f, x in made)
                write("cartes/index.html", page("Cartes à partager", f'<div class="wide"><h1>Cartes à partager</h1><p class="lede">Les chiffres clés de Roblox en images (1080 × 1350), '
                                                f'régénérées à chaque relevé horaire. Libres de reprise en citant PlayLedger.</p><div class="cartes">{figs}</div></div>',
                                                "Les chiffres clés de Roblox en images à partager.", "cartes/", extra_head='<meta name="robots" content="noindex">', alts=["fr"]),
                      shared=True)
            except Exception as e:
                print("Cartes non générées :", e)

    # ---- fichiers communs
    i18n.set_lang("fr")
    urls = []
    for p, langs_ in sitemap:
        langs_ = langs_ or LANGS
        alt = "".join(f'<xhtml:link rel="alternate" hreflang="{META[l]["html"]}" href="{esc(abs_url(p, l))}"/>' for l in langs_)
        for l in langs_:
            urls.append(f"<url><loc>{esc(abs_url(p, l))}</loc>{alt}</url>")
    write("sitemap.xml", '<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
                         + "".join(urls) + "</urlset>", shared=True)
    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "PerplexityBot", "Google-Extended", "Applebot-Extended", "Bingbot", "Googlebot"]
    write("robots.txt", "".join(f"User-agent: {b}\nAllow: /\nDisallow: /brouillons/\n\n" for b in bots)
          + f"User-agent: *\nAllow: /\nDisallow: /brouillons/\nDisallow: /widget/\nDisallow: /rapport/pdf/\n\nSitemap: {abs_url('sitemap.xml')}\n", shared=True)
    top_games = [r for r in recs if r["rang"]][:20]
    write("llms.txt", f"# {NAME}\n\n> {CONFIG['description']} Média indépendant, non affilié à Roblox Corporation. "
          f"Disponible en français, en anglais ({abs_url('', 'en')}), en espagnol ({abs_url('', 'es')}) et en portugais du Brésil ({abs_url('', 'pt-br')}).\n\n"
          "Chaque chiffre publié est calculé par programme à partir de relevés horaires des API publiques de Roblox, "
          "et relié à la ligne exacte du fichier de données d’où il vient. Les données sont ouvertes (licence ODbL, citation obligatoire).\n\n"
          "## Pages clés\n\n"
          f"- [Classement en direct]({abs_url('classement/')}) : les 100 jeux Roblox les plus joués, mis à jour toutes les heures\n"
          f"- [Live ranking (English)]({abs_url('classement/', 'en')}) : the 100 most played Roblox games, updated hourly\n"
          f"- [Alertes]({abs_url('alertes/')}) : les jeux qui décollent, détectés à chaque relevé\n"
          f"- [Comparer deux jeux]({abs_url('comparer/')})\n"
          f"- [Méthode]({abs_url('methode/')}) : comment les chiffres sont relevés, calculés et vérifiés\n"
          f"- [Données ouvertes et API]({abs_url('donnees/')}) : JSON mis à jour toutes les heures\n\n"
          "## Articles\n\n" + "".join(f"- [{a['title']}]({abs_url('articles/' + a['slug'] + '/')}) : {a['chapo']}\n" for a in arts_fr[:50])
          + "\n## Jeux les plus suivis\n\n" + "".join(f"- [{r['nom']}]({abs_url('jeux/' + r['slug'] + '/')})\n" for r in top_games)
          + f"\n## Données\n\n- [Classement JSON]({abs_url('api/classement.json')})\n- [Liste des jeux JSON]({abs_url('api/jeux/index.json')})\n", shared=True)
    (OUT / ".nojekyll").write_text("")
    print(f"Site construit : {len(arts_fr)} article(s) en français, " + ", ".join(f"{len(arts_by_lang[l])} en {l}" for l in LANGS[1:])
          + f", {len(recs)} pages de jeux, {len(alerts)} alerte(s), classement {'à jour' if live else 'vide'}.")
    if i18n.MISSING:
        print(f"  {len(i18n.MISSING)} texte(s) d’interface sans traduction (affichés en français).")
        if "--missing" in sys.argv:
            for s in sorted(i18n.MISSING):
                print("   ·", s)
    for a in arts_fr:
        for w in a["warnings"]:
            print(f"  ⚠ {a['slug']} : {w}")


if __name__ == "__main__":
    build(drafts="--drafts" in sys.argv)
