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
from common import (CONFIG, DATA, FACTS, ROOT, TZ, UTC, fr_date, fr_hour, fr_int, github_blob, github_tree, load_games,
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
         "analyse": "Analyse"}


def url(path=""):
    return BASE + path.lstrip("/")


def abs_url(path=""):
    return (BASE_URL or "") + "/" + path.lstrip("/")


# ---------------------------------------------------------------- gabarit
def page(title, body, desc="", path="", extra_head=""):
    full = f"{title} | {NAME}" if title != NAME else NAME
    canon = f'<link rel="canonical" href="{esc(abs_url(path))}">' if BASE_URL else ""
    nav = [("", "Articles"), ("classement/", "Classement en direct"), ("methode/", "Méthode")]
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
  <nav aria-label="Navigation principale">{links}</nav>
</header>
<main id="contenu">
{body}
</main>
<footer class="site-foot">
  <p><strong>{esc(NAME)}</strong> : {esc(CONFIG['tagline'])}.</p>
  <p>Média indépendant, non affilié à Roblox Corporation. Roblox est une marque de Roblox Corporation.</p>
  <p>Articles rédigés automatiquement à partir de données publiques, chiffres vérifiés par programme.
  <a href="{url('methode/')}">Méthode</a>, <a href="{url('corrections/')}">corrections</a>, <a href="{url('mentions-legales/')}">mentions légales</a>, <a href="{url('feed.xml')}">flux RSS</a>, <a href="{esc(github_tree('data'))}">données ouvertes</a>.</p>
</footer>
<script src="{url('assets/app.js')}" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------- articles
def render_tokens(text, day, linked=True, used=None):
    def sub(m):
        d, key = m.group(1) or day, m.group(2)
        f = fact_for(d, key)
        numeric = isinstance(f["v"], (int, float)) and not isinstance(f["v"], bool)
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
        pub = meta.get("publie") or f"{day}T08:00"
        try:
            pub_dt = datetime.fromisoformat(pub).replace(tzinfo=TZ) if "Z" not in pub else parse_iso(pub)
        except ValueError:
            pub_dt = datetime.fromisoformat(day).replace(tzinfo=TZ)
        arts.append({"slug": slug, "meta": meta, "day": day, "pub": pub_dt, "html": body_html, "used": used,
                     "title": render_tokens(meta["titre"], day, linked=False),
                     "chapo": render_tokens(meta["chapo"], day, linked=False),
                     "chapo_html": render_tokens(meta["chapo"], day, used=used), "warnings": warnings})
    arts.sort(key=lambda a: a["pub"], reverse=True)
    return arts


def article_page(a, prefix="articles"):
    f = load_facts(a["day"])
    cov = f["couverture"]
    sources = sorted({fact_for(d, k).get("src", "").split("#")[0] for d, k in a["used"]} - {""})
    src_list = "".join(f'<li><a href="{esc(s if s.startswith("http") else github_blob(s) if s.endswith(".csv") else github_tree(s))}">{esc(s)}</a></li>' for s in sources)
    d = datetime.fromisoformat(a["day"]).date()
    kind = TYPES.get(a["meta"]["type"], "Article")
    body = f"""<article class="article">
<header class="article-head">
  <h1>{esc(a['title'])}</h1>
  <p class="chapo">{a['chapo_html']}</p>
  <p class="dateline">{esc(kind)}, données du {esc(fr_date(d))}. Publié le {esc(fr_date(a['pub'].date(), weekday=False))} à {esc(fr_hour(a['pub']))}.</p>
</header>
<div class="prose">
{a['html']}
</div>
<aside class="provenance" aria-labelledby="prov-{esc(a['slug'])}">
  <h2 id="prov-{esc(a['slug'])}">D’où viennent ces chiffres</h2>
  <p class="checked"><span class="check" aria-hidden="true"></span>{len(a['used'])} chiffres dans cet article, tous calculés par programme et reliés à leur source. Cliquez sur un chiffre souligné pour ouvrir la ligne exacte du fichier de données.</p>
  <p>Journée couverte par {cov['releves']} relevés horaires sur {cov['attendus']}. Le texte a été rédigé par une IA à partir de ces chiffres, puis contrôlé avant publication. <a href="{url('methode/')}">Comment nous travaillons</a>.</p>
  <ul class="files">{src_list}</ul>
  <p>Une erreur ? <a href="{url('corrections/')}">Signalez-la</a> : chaque correction est publiée.</p>
</aside>
</article>"""
    return page(a["title"], body, a["chapo"], f"{prefix}/{a['slug']}/")


def card(a, lead=False):
    d = datetime.fromisoformat(a["day"]).date()
    cls = "card lead" if lead else "card"
    return (f'<li class="{cls}"><a href="{url("articles/" + a["slug"] + "/")}"><h2>{esc(a["title"])}</h2>'
            f'<p>{esc(a["chapo"])}</p><span class="meta">{esc(TYPES.get(a["meta"]["type"], "Article"))}, '
            f'{esc(fr_date(d))}</span></a></li>')


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
    window = [s for s in snaps if (ts - s[0]).total_seconds() <= 24 * 3600]
    ranked = sorted(last.values(), key=lambda r: -int(r["playing"] or 0))[:limit]
    rows = []
    for i, r in enumerate(ranked, 1):
        u = r["universe_id"]
        series = [int(s[1][u]["playing"] or 0) for s in window if u in s[1]]
        g = games.get(u, {})
        rows.append({"rang": i, "uid": u, "nom": g.get("name", u), "createur": g.get("creator_name", ""),
                     "genre": GENRES_FR.get(g.get("genre_l1", ""), g.get("genre_l1", "")), "place": g.get("root_place_id", ""),
                     "maintenant": int(r["playing"] or 0), "pic24": max(series) if series else 0, "serie": series})
    return {"ts": ts, "rows": rows, "file": str(snap_path("snapshots", ts).relative_to(DATA.parent)) if str(DATA).startswith(str(ROOT)) else "data/snapshots"}


def live_table(live, compact_rows=None):
    rows = live["rows"][:compact_rows] if compact_rows else live["rows"]
    trs = []
    for r in rows:
        link = f"https://www.roblox.com/games/{r['place']}" if r["place"] else ""
        name = f'<a href="{esc(link)}" rel="nofollow">{esc(r["nom"])}</a>' if link else esc(r["nom"])
        trs.append(f'<tr><td class="num rank">{r["rang"]}</td><td class="game">{name}<span class="sub">{esc(r["createur"])}</span></td>'
                   f'<td class="num" data-v="{r["maintenant"]}">{fr_int(r["maintenant"])}</td>'
                   f'<td class="num hide-s" data-v="{r["pic24"]}">{fr_int(r["pic24"])}</td>'
                   f'<td class="spark-cell hide-s">{charts.sparkline(r["serie"])}</td>'
                   f'<td class="hide-m">{esc(r["genre"])}</td></tr>')
    return ('<div class="table-wrap"><table class="live sortable"><thead><tr><th scope="col" class="num" data-sort="num">Rang</th>'
            '<th scope="col">Jeu</th><th scope="col" class="num" data-sort="num">Joueurs en ligne</th>'
            '<th scope="col" class="num hide-s" data-sort="num">Pic sur 24 h</th><th scope="col" class="hide-s">24 dernières heures</th>'
            f'<th scope="col" class="hide-m">Genre</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')


def stamp(live):
    t = live["ts"]
    return f"Relevé du {fr_date(t.astimezone(TZ).date(), weekday=False)} à {fr_hour(t)}, heure de Paris"


# ---------------------------------------------------------------- pages
def build(drafts=False):
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    arts = load_articles(CONTENT / "articles")
    live = live_data()
    status = json.loads((DATA / "status.json").read_text()) if (DATA / "status.json").exists() else {}

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
        items = "".join(f'<li><span class="p-rank">{r["rang"]}</span><span class="p-name">{esc(r["nom"])}</span>'
                        f'<span class="p-val">{fr_int(r["maintenant"])}</span>{charts.sparkline(r["serie"], 96, 24)}</li>' for r in top)
        pulse = (f'<section class="pulse" aria-labelledby="pulse-h"><h2 id="pulse-h">En ce moment sur Roblox</h2>'
                 f'<p class="stamp">{esc(stamp(live))}. Joueurs en ligne par jeu.</p><ol>{items}</ol>'
                 f'<a class="more" href="{url("classement/")}">Voir le classement des 100 premiers</a></section>')
    if arts:
        feed = (f'<ol class="cards">{card(arts[0], lead=True)}{"".join(card(a) for a in arts[1:12])}</ol>'
                + (f'<p class="more"><a href="{url("articles/")}">Tous les articles</a></p>' if len(arts) > 12 else ""))
    else:
        since = status.get("lastRunAt", "")
        feed = ('<div class="empty"><h2>Les premiers relevés sont en cours</h2><p>Un article paraît chaque matin dès qu’une '
                'journée complète de relevés est disponible. En attendant, le classement se met à jour toutes les heures.</p></div>')
    intro = (f'<section class="intro"><h1>{esc(CONFIG["tagline"])}</h1><p>{esc(CONFIG["description"])}</p></section>')
    write("index.html", page(NAME, f'<div class="home">{intro}{pulse}<section class="feed" aria-label="Derniers articles">{feed}</section></div>', path=""))

    write("articles/index.html", page("Tous les articles", f'<div class="narrow"><h1>Tous les articles</h1><ol class="cards">{"".join(card(a) for a in arts)}</ol></div>', path="articles/"))

    if live:
        body = (f'<div class="wide"><h1>Classement en direct</h1><p class="lede">Les 100 jeux Roblox qui comptent le plus de joueurs '
                f'en ligne. {esc(stamp(live))}, mis à jour toutes les heures.</p>{live_table(live)}'
                f'<p class="note">Source : API web publiques de Roblox, <a href="{esc(github_tree("data/snapshots"))}">relevés horaires archivés</a>. '
                f'Le pic sur 24 h est le plus haut des relevés horaires : le pic réel peut être un peu plus élevé. Jeux sponsorisés exclus des classements.</p></div>')
    else:
        body = '<div class="narrow"><h1>Classement en direct</h1><p>Le premier relevé n’a pas encore eu lieu.</p></div>'
    write("classement/index.html", page("Classement en direct des jeux Roblox", body,
                                        "Les 100 jeux Roblox les plus joués en ce moment, mis à jour toutes les heures.", "classement/"))

    for name, title, desc in (("methode", "Méthode", "Comment nous relevons, calculons et vérifions chaque chiffre."),
                              ("corrections", "Corrections", "Les erreurs signalées et leur correction."),
                              ("mentions-legales", "Mentions légales", "Éditeur, hébergeur et données personnelles.")):
        src = CONTENT / f"{name}.md"
        text = src.read_text(encoding="utf-8") if src.exists() else ""
        text = text.replace("{{depot}}", github_tree("")).replace("{{donnees}}", github_tree("data")).replace("{{nom}}", NAME)
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
    urls = [abs_url(p) for p in ("", "classement/", "methode/", "articles/")] + [abs_url("articles/" + a["slug"] + "/") for a in arts]
    write("sitemap.xml", '<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         + "".join(f"<url><loc>{esc(u)}</loc></url>" for u in urls) + "</urlset>")
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /brouillons/\nSitemap: {abs_url('sitemap.xml')}\n")
    (OUT / ".nojekyll").write_text("")
    print(f"Site construit : {len(arts)} article(s), classement {'à jour' if live else 'vide'}.")
    for a in arts:
        for w in a["warnings"]:
            print(f"  ⚠ {a['slug']} : {w}")


if __name__ == "__main__":
    build(drafts="--drafts" in sys.argv)
