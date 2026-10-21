"""Construit le site statique dans _site/. Refuse de construire si un article publié ne passe pas le vérificateur.

Usage : python tools/build.py [--drafts]   (--drafts : construit aussi les brouillons dans /brouillons/, pour relecture locale)
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parent))
import charts
import explore
from common import (CONFIG, DATA, FACTS, ROOT, TZ, UTC, fr_date, fr_hour, fr_int, fr_pct, github_blob, github_tree, load_games,
                    parse_iso, read_csv, snap_path, utc_now)
from facts import GENRES_FR
from verify import GRAPH, TOKEN, fact_for, load_facts, parse, verify

OUT = Path(os.environ.get("MEDIA_SITE_DIR", ROOT / "_site"))
CONTENT = Path(os.environ.get("MEDIA_CONTENT_DIR", ROOT / "content"))
esc = html.escape
NAME = CONFIG["name"]
BASE_URL = (CONFIG.get("baseUrl") or "").rstrip("/")
BASE = (urlparse(BASE_URL).path.rstrip("/") + "/") if BASE_URL else "/"
TYPES = {"quotidien": "Relevé quotidien", "hebdo": "La semaine", "mensuel": "Le mois", "trimestriel": "Résultats trimestriels",
         "analyse": "Analyse", "dossier": "Dossier"}


def url(path=""):
    return BASE + path.lstrip("/")


def abs_url(path=""):
    return (BASE_URL or "") + "/" + path.lstrip("/")


# ---------------------------------------------------------------- gabarit
def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"


ORG = {"@type": "NewsMediaOrganization", "name": NAME, "url": (BASE_URL or "") + "/", "logo": (BASE_URL or "") + "/assets/icon.svg",
       "description": CONFIG["description"], "publishingPrinciples": (BASE_URL or "") + "/methode/",
       "correctionsPolicy": (BASE_URL or "") + "/corrections/"}


def page(title, body, desc="", path="", extra_head="", og_type="website", ld=None):
    full = f"{title} | {NAME}" if title != NAME else NAME
    canon = f'<link rel="canonical" href="{esc(abs_url(path))}">' if BASE_URL else ""
    nav = [("", "Articles"), ("classement/", "Classement en direct"), ("alertes/", "Alertes"), ("comparer/", "Comparer"), ("methode/", "Méthode")]
    v = CONFIG.get("verification", {})
    verif = "".join(f'<meta name="{n}" content="{esc(v[k])}">' for k, n in (("google", "google-site-verification"), ("bing", "msvalidate.01")) if v.get(k))
    an = CONFIG.get("analytics", {})
    beacon = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\'{{"token": "{esc(an["cloudflareToken"])}"}}\'></script>'
              if an.get("cloudflareToken") else "")
    links = "".join(f'<a href="{url(p)}"{" aria-current=page" if path == p else ""}>{t}</a>' for p, t in nav)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full)}</title>
<meta name="description" content="{esc(desc or CONFIG['description'])}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc or CONFIG['description'])}">
<meta property="og:site_name" content="{esc(NAME)}">
<meta property="og:locale" content="fr_FR">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{esc(abs_url(path))}">
<meta name="twitter:card" content="summary">
{verif}
{jsonld(ld or {"@context": "https://schema.org", **ORG})}
{canon}
<link rel="alternate" type="application/rss+xml" title="{esc(NAME)}" href="{url('feed.xml')}">
<link rel="preload" href="{url('assets/fonts/schibsted-grotesk-latin-wght-normal.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{url('assets/style.css')}">
<link rel="icon" href="{url('assets/icon.svg')}" type="image/svg+xml">
{extra_head}
</head>
<body>
<a class="skip" href="#contenu">Aller au contenu</a>
<header class="site-head">
  <a class="wordmark" href="{url()}"><span class="mark" aria-hidden="true"></span>{esc(NAME)}</a>
  <nav aria-label="Navigation principale">{links}<a class="bell" href="{url('alertes/#recevoir')}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>Recevoir les alertes</a></nav>
</header>
{TICKER}
<main id="contenu">
{body}
</main>
<footer class="site-foot">
  <p><strong>{esc(NAME)}</strong> : {esc(CONFIG['tagline'])}.</p>
  <p>Média indépendant, non affilié à Roblox Corporation. Roblox est une marque de Roblox Corporation.</p>
  <p>Articles rédigés automatiquement à partir de données publiques, chiffres vérifiés par programme.
  <a href="{url('methode/')}">Méthode</a>, <a href="{url('corrections/')}">corrections</a>, <a href="{url('mentions-legales/')}">mentions légales</a>, <a href="{url('feed.xml')}">flux RSS</a>, <a href="{url('donnees/')}">données ouvertes et API</a>, <a href="{url('partenaires/')}">partenaires</a>.</p>
  <p>Mesure d’audience anonyme, sans cookie.</p>
  {STATUS_HTML}
</footer>
<script src="{url('assets/app.js')}" defer></script>
{beacon}
</body>
</html>
"""


# ---------------------------------------------------------------- articles
GAME_PAGES = {g.get("name", u): explore.game_slug(u, g.get("name", u)) for u, g in load_games().items() if g.get("name")}


def render_tokens(text, day, linked=True, used=None):
    def sub(m):
        d, key = m.group(1) or day, m.group(2)
        f = fact_for(d, key)
        numeric = isinstance(f["v"], (int, float)) and not isinstance(f["v"], bool)
        if linked and not numeric and str(f["d"]) in GAME_PAGES:
            return f'<a class="jeu" href="{url("jeux/" + GAME_PAGES[str(f["d"])] + "/")}">{esc(f["d"])}</a>'
        if not linked or not numeric:
            return esc(f["d"]) if linked else f["d"]
        if used is not None:
            used.add((d, key))
        src = f.get("src", "")
        line = src.split("#L")[1] if "#L" in src else ""
        where = f"ligne {line} de {src.split('#')[0]}" if line else src
        href = src if src.startswith("http") else github_blob(src)
        return (f'<a class="fait" href="{esc(href)}" data-fact="{esc(f["l"])}" data-where="{esc(where)}">'
                f'{esc(f["d"])}</a>')
    return TOKEN.sub(sub, text)


def load_articles(folder, strict=True):
    arts = []
    for p in sorted(folder.glob("*.md")):
        errors, warnings, meta, body = verify(p)
        if errors:
            msg = f"Article bloqué par le vérificateur : {p.name}\n  " + "\n  ".join(errors)
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
            return charts.render(gid, load_facts(d)["graphiques"][gid])
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


def article_page(a, prefix="articles"):
    f = load_facts(a["day"])
    cov = f["couverture"] if f else None
    sources = sorted({fact_for(d, k).get("src", "").split("#")[0] for d, k in a["used"]} - {""})
    src_list = "".join(f'<li><a href="{esc(s if s.startswith("http") else github_blob(s) if s.endswith(".csv") else github_tree(s))}">{esc(s)}</a></li>' for s in sources)
    d = datetime.fromisoformat(a["day"][:10]).date()
    kind = TYPES.get(a["meta"]["type"], "Article")
    body = f"""<article class="article">
<header class="article-head">
  <h1>{esc(a['title'])}</h1>
  <p class="chapo">{a['chapo_html']}</p>
  {byline(a)}
  <p class="dateline">{esc(kind)}{(", relevé du " + esc(fr_date(d)) + " à " + esc(f["faits"]["releve.heure"]["d"]) if f and f["couverture"].get("instantane") else (", données du " + esc(fr_date(d))) if f else "")}. Publié le {esc(fr_date(a['pub'].date(), weekday=False))} à {esc(fr_hour(a['pub']))}.</p>
</header>
<div class="prose">
{a['html']}
</div>
<aside class="provenance" aria-labelledby="prov-{esc(a['slug'])}">
  <h2 id="prov-{esc(a['slug'])}">D’où viennent ces chiffres</h2>
  <p class="checked"><span class="check" aria-hidden="true"></span>{len(a['used'])} chiffres dans cet article, tous reliés à leur source. Cliquez sur un chiffre souligné pour ouvrir le document ou la ligne exacte du fichier de données d’où il vient.</p>
  <p>{f"Journée couverte par {cov['releves']} relevés horaires sur {cov['attendus']}. " if cov and not cov.get("instantane") else ""}Le texte a été rédigé par une IA à partir de ces chiffres, puis contrôlé avant publication. <a href="{url('methode/')}">Comment nous travaillons</a>.</p>
  <ul class="files">{src_list}</ul>
  <p>Une erreur ? <a href="{url('corrections/')}">Signalez-la</a> : chaque correction est publiée.</p>
</aside>
</article>"""
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": a["title"], "description": a["chapo"],
          "datePublished": a["pub"].isoformat(), "inLanguage": "fr", "isAccessibleForFree": True,
          "mainEntityOfPage": abs_url(f"{prefix}/{a['slug']}/"), "author": ORG, "publisher": ORG,
          "isBasedOn": [s if s.startswith("http") else github_blob(s) for s in sources][:20]}
    return page(a["title"], body, a["chapo"], f"{prefix}/{a['slug']}/", og_type="article", ld=ld,
                extra_head=f'<meta property="article:published_time" content="{a["pub"].isoformat()}">'
                           + ('<meta name="robots" content="noindex">' if prefix == "brouillons" else ""))


BADGES = {"quotidien": "Quotidien", "hebdo": "Hebdo", "mensuel": "Mensuel", "trimestriel": "Résultats", "analyse": "Analyse", "dossier": "Dossier"}
ICONS_BY_SLUG = {}


def reading_time(a):
    words = len(re.sub(r"<[^>]+>", " ", a["html"]).split())
    return max(1, round(words / 220))


def byline(a):
    return (f'<span class="byline"><span class="rt"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
            f'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>{reading_time(a)} min de lecture</span>'
            f'<span class="auto">Rédaction automatisée, chiffres vérifiés par programme</span></span>')


def badge(a):
    return f'<span class="tag">{esc(BADGES.get(a["meta"]["type"], "Article"))}</span>'


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
    d = datetime.fromisoformat(a["day"][:10]).date()
    href = url("articles/" + a["slug"] + "/")
    if lead:
        return (f'<article class="hero-card"><a href="{href}">{cover(a)}<div class="hero-body">{badge(a)}<h2>{esc(a["title"])}</h2>'
                f'<p>{esc(a["chapo"])}</p><span class="meta">{esc(fr_date(a["pub"].date(), weekday=False))}</span>{byline(a)}</div></a></article>')
    return (f'<li class="card"><a href="{href}">{badge(a)}<h3>{esc(a["title"])}</h3>'
            f'<p>{esc(a["chapo"])}</p><span class="meta">{esc(fr_date(a["pub"].date(), weekday=False))}</span></a></li>')


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
    prev = next((sn for t, sn in reversed(snaps[:-1]) if 1800 <= (ts - t).total_seconds() <= 3 * 3600), None)
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
        return '<span class="mv new" title="Nouveau dans le top 100">nouveau</span>'
    d = r["rang_avant"] - r["rang"]
    if d > 0:
        return f'<span class="mv up" title="Gagne {d} place(s) en une heure">↑{d}</span>'
    if d < 0:
        return f'<span class="mv down" title="Perd {-d} place(s) en une heure">↓{-d}</span>'
    return ""


def var_html(r):
    v = r.get("var")
    if v is None:
        return ""
    cls = "up" if v >= 0.005 else ("down" if v <= -0.005 else "flat")
    return f'<span class="pill {cls}" title="Variation sur une heure">{esc(fr_pct(v))}</span>'


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
        trs.append(f'<tr data-href="{href}" data-genre="{esc(r["genre"])}"><td class="num rank">{r["rang"]}{move_html(r)}</td><td class="game"><div class="gcell">{icon_html(r)}<div>{name}<span class="sub">{esc(r["createur"])}</span></div></div></td>'
                   f'<td class="num{" hot" if (r.get("var") or 0) > 0.10 else ""}" data-v="{r["maintenant"]}">{fr_int(r["maintenant"])}{var_html(r)}</td>'
                   f'<td class="num hide-s" data-v="{r["pic24"]}">{fr_int(r["pic24"])}</td>'
                   f'<td class="spark-cell hide-s">{charts.sparkline(r["serie"], trend=trend_of(r))}</td>'
                   f'<td class="hide-m">{esc(r["genre"])}</td></tr>')
    counts = {}
    for r in rows:
        counts[r["genre"]] = counts.get(r["genre"], 0) + 1
    genres = [g for g, _ in sorted(counts.items(), key=lambda kv: -kv[1]) if g][:6]
    filt = ('<div class="filters" role="group" aria-label="Filtrer par genre"><button type="button" class="chip on" data-filter="">Tous</button>'
            + "".join(f'<button type="button" class="chip" data-filter="{esc(g)}">{esc(g)}</button>' for g in genres) + "</div>") if compact_rows is None else ""
    return (filt + '<div class="table-wrap"><table class="live sortable"><thead><tr><th scope="col" class="num" data-sort="num">Rang</th>'
            '<th scope="col">Jeu</th><th scope="col" class="num" data-sort="num">Joueurs en ligne</th>'
            '<th scope="col" class="num hide-s" data-sort="num">Pic sur 24 h</th><th scope="col" class="hide-s">24 dernières heures</th>'
            f'<th scope="col" class="hide-m">Genre</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')


def stamp(live):
    t = live["ts"]
    return f"Relevé du {fr_date(t.astimezone(TZ).date(), weekday=False)} à {fr_hour(t)}, heure de Paris"


TICKER = ""
STATUS_HTML = ""


def status_html(status):
    last = status.get("lastRunAt")
    if not last:
        return ""
    t = parse_iso(last)
    late = (utc_now() - t).total_seconds() > 2.5 * 3600
    ok = status.get("ok") and not late
    label = "Opérationnel" if ok else ("Retard" if late else "Incident")
    return (f'<p class="feed-status {"ok" if ok else "ko"}" data-last="{last}"><span class="fs-dot" aria-hidden="true"></span>'
            f'État des relevés Roblox : <strong>{label}</strong>. Dernier relevé à {esc(fr_hour(t))} '
            f'({fr_int(status.get("gamesMeasured", 0))} jeux)<span class="fs-next"></span>.</p>')


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
        items.append(f'<a class="tk-item tk-alert" href="{url("alertes/")}"><span class="tk-label">Alerte</span>{esc(a["nom"])}</a>')
    if not items:
        return ""
    row = "".join(items)
    return (f'<div class="ticker" role="region" aria-label="Fil d’actualité"><div class="tk-track">'
            f'<div class="tk-row">{row}</div><div class="tk-row" aria-hidden="true">{row}</div></div></div>')


def headline_pick(arts):
    pick, label = arts[0], "Dernier article"
    pop = DATA / "populaires.json"
    if pop.exists():
        try:
            paths = [x["path"] for x in json.loads(pop.read_text(encoding="utf-8")).get("pages", [])]
            by_path = {url("articles/" + a["slug"] + "/"): a for a in arts}
            for pth in paths:
                if pth in by_path:
                    return by_path[pth], "Le plus lu"
        except (ValueError, KeyError):
            pass
    return pick, label


def headline(arts):
    """Bannière « À la une » : l'article le plus lu des 7 derniers jours si la mesure d'audience est branchée, sinon le dernier."""
    if not arts:
        return ""
    pick, label = arts[0], "Dernier article"
    pop = DATA / "populaires.json"
    if pop.exists():
        try:
            paths = [x["path"] for x in json.loads(pop.read_text(encoding="utf-8")).get("pages", [])]
            by_path = {url("articles/" + a["slug"] + "/"): a for a in arts}
            for pth in paths:
                if pth in by_path:
                    pick, label = by_path[pth], "Le plus lu cette semaine"
                    break
        except (ValueError, KeyError):
            pass
    return (f'<a class="une" href="{url("articles/" + pick["slug"] + "/")}"><span class="une-label">{label}</span>'
            f'<span class="une-title">{esc(pick["title"])}</span></a>')


# ---------------------------------------------------------------- pages
def build(drafts=False):
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    arts = load_articles(CONTENT / "articles")
    live = live_data()
    status = json.loads((DATA / "status.json").read_text()) if (DATA / "status.json").exists() else {}
    global TICKER, STATUS_HTML
    STATUS_HTML = status_html(status)
    ICONS_BY_SLUG.update({explore.game_slug(u, g.get("name", u)): g.get("icon", "") for u, g in load_games().items()})
    TICKER = ticker_html(arts, live, list(reversed(read_csv(DATA / "alertes.csv"))))

    def write(path, content):
        p = OUT / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    for a in arts:
        write(f"articles/{a['slug']}/index.html", article_page(a))
    if drafts:
        for a in load_articles(ROOT / "drafts", strict=False):
            write(f"brouillons/{a['slug']}/index.html", article_page(a, "brouillons"))

    # accueil
    pulse = ""
    if live:
        top = live["rows"][:5]
        items = "".join(f'<li><span class="p-rank">{r["rang"]}{move_html(r)}</span><span class="p-id">{icon_html(r, 28)}<a class="p-name" href="{url("jeux/" + r["slug"] + "/")}">{esc(r["nom"])}</a></span>'
                        f'<span class="p-val">{fr_int(r["maintenant"])}{var_html(r)}</span>{charts.sparkline(r["serie"], 96, 24, trend_of(r))}</li>' for r in top)
        pulse = (f'<section class="pulse" aria-labelledby="pulse-h"><h2 id="pulse-h">En ce moment sur Roblox</h2>'
                 f'<p class="stamp">{esc(stamp(live))}. Joueurs en ligne par jeu.</p><ol>{items}</ol>'
                 f'<a class="cta-top" href="{url("classement/")}">Voir tout le top 100 <span aria-hidden="true">→</span></a></section>')
    if arts:
        lead, _ = headline_pick(arts)
        rest = [a for a in arts if a is not lead]
        feed = (card(lead, lead=True) + f'<ol class="cards grid2">{"".join(card(a) for a in rest[:4])}</ol>'
                + (f'<h2 class="sec-title">Plus d’articles</h2><ol class="cards list">{"".join(card(a) for a in rest[4:14])}</ol>' if len(rest) > 4 else "")
                + (f'<p class="more"><a href="{url("articles/")}">Tous les articles</a></p>' if len(rest) > 14 else ""))
    else:
        since = status.get("lastRunAt", "")
        skel = "".join('<li class="card skel" aria-hidden="true"><span class="sk sk-t"></span><span class="sk sk-t short"></span>'
                       '<span class="sk sk-p"></span><span class="sk sk-p"></span><span class="sk sk-m"></span></li>' for _ in range(3))
        feed = ('<div class="empty"><h2>Le premier relevé quotidien arrive vendredi matin</h2><p>Chaque matin, un article sur la veille, '
                'calculé à partir d’une journée complète de relevés. En attendant, le classement, les pages de jeux et les alertes se mettent à jour toutes les heures.</p>'
                f'<p class="empty-links"><a class="btn" href="{url("classement/")}">Voir le classement en direct</a> <a class="btn ghost" href="{url("comparer/")}">Comparer deux jeux</a></p></div>'
                f'<ol class="cards skel-list">{skel}</ol>')
    intro = f'<section class="intro"><h1>{esc(CONFIG["tagline"])}</h1><p>{esc(CONFIG["description"])}</p></section>'
    write("index.html", page(NAME, f'<div class="home"><div class="main-col">{intro}<section class="feed" aria-label="Derniers articles">{feed}</section></div><aside class="side-col">{pulse}</aside></div>', path=""))

    write("articles/index.html", page("Tous les articles", f'<div class="narrow"><h1>Tous les articles</h1><ol class="cards list">{"".join(card(a) for a in arts)}</ol></div>', path="articles/"))

    if live:
        body = (f'<div class="wide"><h1>Classement en direct</h1><p class="lede">Les 100 jeux Roblox qui comptent le plus de joueurs '
                f'en ligne. {esc(stamp(live))}, mis à jour toutes les heures.</p>{live_table(live)}'
                f'<p class="note">Source : API web publiques de Roblox, <a href="{esc(github_tree("data/snapshots"))}">relevés horaires archivés</a>. '
                f'Le pic sur 24 h est le plus haut des relevés horaires : le pic réel peut être un peu plus élevé. Jeux sponsorisés exclus des classements.</p></div>')
    else:
        body = '<div class="narrow"><h1>Classement en direct</h1><p>Le premier relevé n’a pas encore eu lieu.</p></div>'
    write("classement/index.html", page("Classement en direct des jeux Roblox", body,
                                        "Les 100 jeux Roblox les plus joués en ce moment, mis à jour toutes les heures.", "classement/"))

    # exploration : pages par jeu, comparateur, alertes, API
    recs, latest_ts = explore.build_records()
    indexable = []
    for rec in recs:
        html_, ok = explore.game_page(rec, page, url)
        write(f"jeux/{rec['slug']}/index.html", html_)
        if ok:
            indexable.append(f"jeux/{rec['slug']}/")
        write(f"widget/jeu/{rec['universe_id']}/index.html", explore.game_widget(rec, abs_url))
    if recs:
        write("comparer/index.html", explore.compare_page(recs, page, url))
    alerts = list(reversed(read_csv(DATA / "alertes.csv")))
    write("alertes/index.html", explore.alerts_page(alerts, page, url, live))
    write("alertes.xml", explore.alerts_feed(alerts, abs_url))
    write("donnees/index.html", explore.data_page(page, url))
    write("widget/index.html", explore.widget_page(live, url, abs_url))
    prev_ranks = {r["uid"]: {"var": round(r["var"], 4) if r.get("var") is not None else None, "rang": r.get("rang_avant")} for r in (live["rows"] if live else [])}
    for path_, content in explore.api_files(recs, latest_ts, alerts, prev_ranks).items():
        write(path_, content)

    for name, title, desc in (("methode", "Méthode", "Comment nous relevons, calculons et vérifions chaque chiffre."),
                              ("partenaires", "Partenaires", "Annoncer auprès des pros de Roblox, études et données sur mesure."),
                              ("corrections", "Corrections", "Les erreurs signalées et leur correction."),
                              ("mentions-legales", "Mentions légales", "Éditeur, hébergeur et données personnelles.")):
        src = CONTENT / f"{name}.md"
        text = src.read_text(encoding="utf-8") if src.exists() else ""
        text = text.replace("{{depot}}", github_tree("")).replace("{{donnees}}", github_tree("data")).replace("{{nom}}", NAME).replace(
            "{{contact}}", f"[{CONFIG['contact']}](mailto:{CONFIG['contact']})" if CONFIG.get("contact") else "L’adresse de contact arrive très bientôt.")
        write(f"{name}/index.html", page(title, f'<div class="narrow prose page">{markdown.markdown(text, extensions=["extra"])}</div>', desc, f"{name}/"))

    write("404.html", page("Page introuvable", f'<div class="narrow"><h1>Cette page n’existe pas</h1><p><a href="{url()}">Revenir à l’accueil</a>.</p></div>'))

    # flux RSS (sert aussi à la newsletter)
    items = "".join(
        f"<item><title>{esc(a['title'])}</title><link>{esc(abs_url('articles/' + a['slug'] + '/'))}</link>"
        f"<guid isPermaLink=\"true\">{esc(abs_url('articles/' + a['slug'] + '/'))}</guid>"
        f"<pubDate>{format_datetime(a['pub'].astimezone(UTC))}</pubDate><description>{esc(a['chapo'])}</description>"
        f"<content:encoded><![CDATA[<p><strong>{html.escape(a['chapo'])}</strong></p>{a['html']}]]></content:encoded></item>"
        for a in arts[:30])
    write("feed.xml", f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
                      f"<channel><title>{esc(NAME)}</title><link>{esc(abs_url())}</link><description>{esc(CONFIG['description'])}</description>"
                      f"<language>fr</language>{items}</channel></rss>")
    urls = ([abs_url(p) for p in ("", "classement/", "alertes/", "comparer/", "donnees/", "methode/", "articles/", "partenaires/")]
            + [abs_url("articles/" + a["slug"] + "/") for a in arts] + [abs_url(p) for p in indexable])
    write("sitemap.xml", '<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         + "".join(f"<url><loc>{esc(u)}</loc></url>" for u in urls) + "</urlset>")
    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "PerplexityBot", "Google-Extended", "Applebot-Extended", "Bingbot", "Googlebot"]
    write("robots.txt", "".join(f"User-agent: {b}\nAllow: /\nDisallow: /brouillons/\n\n" for b in bots)
          + f"User-agent: *\nAllow: /\nDisallow: /brouillons/\nDisallow: /widget/\n\nSitemap: {abs_url('sitemap.xml')}\n")
    top_games = [r for r in recs if r["rang"]][:20]
    write("llms.txt", f"# {NAME}\n\n> {CONFIG['description']} Média indépendant en français, non affilié à Roblox Corporation.\n\n"
          "Chaque chiffre publié est calculé par programme à partir de relevés horaires des API publiques de Roblox, "
          "et relié à la ligne exacte du fichier de données d’où il vient. Les données sont ouvertes (licence ODbL, citation obligatoire).\n\n"
          "## Pages clés\n\n"
          f"- [Classement en direct]({abs_url('classement/')}) : les 100 jeux Roblox les plus joués, mis à jour toutes les heures\n"
          f"- [Alertes]({abs_url('alertes/')}) : les jeux qui décollent, détectés à chaque relevé\n"
          f"- [Comparer deux jeux]({abs_url('comparer/')})\n"
          f"- [Méthode]({abs_url('methode/')}) : comment les chiffres sont relevés, calculés et vérifiés\n"
          f"- [Données ouvertes et API]({abs_url('donnees/')}) : JSON mis à jour toutes les heures\n\n"
          "## Articles\n\n" + "".join(f"- [{a['title']}]({abs_url('articles/' + a['slug'] + '/')}) : {a['chapo']}\n" for a in arts[:50])
          + "\n## Jeux les plus suivis\n\n" + "".join(f"- [{r['nom']}]({abs_url('jeux/' + r['slug'] + '/')})\n" for r in top_games)
          + f"\n## Données\n\n- [Classement JSON]({abs_url('api/classement.json')})\n- [Liste des jeux JSON]({abs_url('api/jeux/index.json')})\n")
    (OUT / ".nojekyll").write_text("")
    print(f"Site construit : {len(arts)} article(s), {len(recs)} pages de jeux ({len(indexable)} indexées), {len(alerts)} alerte(s), classement {'à jour' if live else 'vide'}.")
    for a in arts:
        for w in a["warnings"]:
            print(f"  ⚠ {a['slug']} : {w}")


if __name__ == "__main__":
    build(drafts="--drafts" in sys.argv)
