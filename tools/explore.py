"""Pages d'exploration : une page par jeu, comparateur, alertes, données ouvertes (API JSON).

Tout est calculé à partir des relevés archivés : aucune donnée tierce.
"""
import html
import json
from datetime import timedelta

import charts
from common import (CONFIG, DATA, TZ, fr_big, fr_date, fr_hour, fr_int, fr_pct, fr_share, github_tree, iso, load_games,
                    parse_iso, read_csv, slugify, snap_path, utc_now)
from facts import GENRES_FR

esc = html.escape
HISTORY_DAYS = 30
INDEX_AFTER_DAYS = 7  # une page de jeu n'est proposée à Google qu'avec 7 jours d'historique
LICENCE = "Données sous licence ODbL : réutilisation libre, y compris commerciale, en citant « Le Relevé » avec un lien."


def game_slug(uid, name):
    return f"{slugify(name)[:60]}-{uid}"


def load_history(days=HISTORY_DAYS):
    """{uid: [(ts, ligne)]} sur les N derniers jours, du plus ancien au plus récent."""
    now = utc_now().replace(minute=0, second=0)
    hist = {}
    for k in range(days * 24, -1, -1):
        rows = read_csv(snap_path("snapshots", now - timedelta(hours=k)))
        if not rows:
            continue
        ts = parse_iso(rows[0]["ts_utc"])
        for r in rows:
            hist.setdefault(r["universe_id"], []).append((ts, r))
    return hist


def game_record(uid, series, g, rank_now):
    ts_last, last = series[-1]
    pts = [(t, int(r["playing"] or 0)) for t, r in series]
    day = [v for t, v in pts if (ts_last - t).total_seconds() <= 24 * 3600]
    up, down = last.get("up_votes"), last.get("down_votes")
    note = int(up) / (int(up) + int(down)) if up and down and int(up) + int(down) >= 100 else None
    span_days = (ts_last - pts[0][0]).total_seconds() / 86400
    best = max(pts, key=lambda x: x[1])
    return {"universe_id": uid, "nom": g.get("name", uid), "slug": game_slug(uid, g.get("name", uid)),
            "createur": g.get("creator_name", ""), "createur_verifie": g.get("creator_verified") == "1",
            "genre": GENRES_FR.get(g.get("genre_l1", ""), g.get("genre_l1", "")), "sous_genre": g.get("genre_l2", ""),
            "place_id": g.get("root_place_id", ""), "cree": g.get("created", "")[:10], "mis_a_jour": g.get("updated", "")[:10],
            "joueurs": pts[-1][1], "rang": rank_now.get(uid), "releve": iso(ts_last),
            "pic_24h": max(day) if day else None, "moyenne_24h": round(sum(day) / len(day)) if day else None,
            "pic_suivi": best[1], "pic_suivi_date": iso(best[0]), "suivi_depuis": iso(pts[0][0]), "jours_suivis": round(span_days, 1),
            "visites": int(last["visits"]) if last.get("visits") else None,
            "favoris": int(last["favorites"]) if last.get("favorites") else None, "note": note,
            "serie": [[iso(t), v] for t, v in pts]}


def build_records():
    hist = load_history()
    if not hist:
        return [], None
    games = load_games()
    latest_ts = max(s[-1][0] for s in hist.values())
    current = {u: s for u, s in hist.items() if s[-1][0] == latest_ts}
    rank_now = {u: i + 1 for i, u in enumerate(sorted(current, key=lambda u: -int(current[u][-1][1]["playing"] or 0)))}
    recs = [game_record(u, s, games.get(u, {}), rank_now) for u, s in hist.items()]
    recs.sort(key=lambda r: (r["rang"] is None, r["rang"] or 0, -r["joueurs"]))
    return recs, latest_ts


def stat(label, value, note=""):
    return (f'<div class="stat"><span class="stat-label">{esc(label)}</span><span class="stat-value">{value}</span>'
            + (f'<span class="stat-note">{esc(note)}</span>' if note else "") + "</div>")


def game_page(rec, page, url):
    pts = {"titre": f"{rec['nom']} : joueurs en ligne, relevés horaires", "unite": "joueurs", "points": rec["serie"],
           "csv": f"data/snapshots", "note": f"Depuis le début de notre suivi, le {fr_date(parse_iso(rec['suivi_depuis']).astimezone(TZ).date(), weekday=False)}. Heure de Paris."}
    chart = charts.line("jeu", pts, height=280).replace(
        "Données du graphique (CSV)", "Relevés horaires (CSV)") if len(rec["serie"]) > 1 else \
        '<p class="note">La courbe apparaîtra dès le deuxième relevé.</p>'
    roblox = f"https://www.roblox.com/games/{rec['place_id']}" if rec["place_id"] else ""
    stats = [
        stat("Joueurs en ligne", fr_int(rec["joueurs"]), f"relevé de {fr_hour(parse_iso(rec['releve']))}"),
        stat("Rang", f"{rec['rang']}<small>e</small>" if rec["rang"] and rec["rang"] > 1 else ("1<small>er</small>" if rec["rang"] == 1 else "—"), "parmi les jeux suivis"),
        stat("Pic sur 24 h", fr_int(rec["pic_24h"]) if rec["pic_24h"] is not None else "—", "plus haut relevé horaire"),
        stat("Pic depuis le début du suivi", fr_int(rec["pic_suivi"]), fr_date(parse_iso(rec["pic_suivi_date"]).astimezone(TZ).date(), weekday=False)),
        stat("Visites cumulées", fr_big(rec["visites"]) if rec["visites"] else "—"),
        stat("Votes positifs", fr_share(rec["note"]) if rec["note"] is not None else "—"),
    ]
    facts = [("Créateur", esc(rec["createur"]) + (" (vérifié)" if rec["createur_verifie"] else "")), ("Genre", esc(" · ".join(x for x in (rec["genre"], rec["sous_genre"]) if x))),
             ("Créé le", esc(rec["cree"])), ("Dernière mise à jour", esc(rec["mis_a_jour"]))]
    dl = "".join(f"<dt>{k}</dt><dd>{v or '—'}</dd>" for k, v in facts)
    body = (f'<div class="wide game"><p class="crumbs"><a href="{url("classement/")}">Classement</a></p>'
            f'<h1>{esc(rec["nom"])}</h1><p class="lede">Joueurs en ligne, pics et visites, relevés toutes les heures depuis les API publiques de Roblox.</p>'
            f'<div class="stats">{"".join(stats)}</div>{chart}'
            f'<div class="game-meta"><dl>{dl}</dl><div class="game-links">'
            + (f'<a class="btn" href="{esc(roblox)}" rel="nofollow">Ouvrir sur Roblox</a>' if roblox else "")
            + f'<a class="btn" href="{url("comparer/?a=" + rec["universe_id"])}">Comparer avec un autre jeu</a>'
            f'<a class="btn ghost" href="{url("api/jeux/" + rec["universe_id"] + ".json")}">Données en JSON</a></div></div>'
            f'<p class="note">{esc(LICENCE)} Les visites et votes sont ceux affichés par Roblox au dernier relevé.</p></div>')
    noindex = rec["jours_suivis"] < INDEX_AFTER_DAYS
    head = '<meta name="robots" content="noindex">' if noindex else ""
    title = f"{rec['nom']} : joueurs en ligne et statistiques"
    desc = f"Combien de joueurs sur {rec['nom']} ? Joueurs en ligne, pic sur 24 h, visites et courbe horaire, mis à jour toutes les heures."
    return page(title, body, desc, f"jeux/{rec['slug']}/", extra_head=head), not noindex


def compare_page(recs, page, url):
    opts = "".join(f'<option value="{r["universe_id"]}">{esc(r["nom"])}</option>' for r in sorted(recs, key=lambda r: r["nom"].lower()))
    ranked = [r for r in recs if r["rang"]]
    da, db = (ranked[0]["universe_id"], ranked[1]["universe_id"]) if len(ranked) > 1 else ("", "")
    body = (f'<div class="wide"><h1>Comparer deux jeux</h1><p class="lede">Choisissez deux jeux pour superposer leurs courbes de joueurs en ligne, '
            f'relevé par relevé. Le lien de la page se met à jour : partagez-le tel quel.</p>'
            f'<form class="compare-form" id="compare" data-a="{da}" data-b="{db}"><label>Premier jeu<select name="a">{opts}</select></label>'
            f'<label>Second jeu<select name="b">{opts}</select></label></form>'
            f'<figure class="chart" id="compare-chart" data-api="{url("api/jeux/")}"><figcaption><span class="chart-title" id="compare-title">Chargement…</span>'
            f'<span class="chart-note">Joueurs en ligne, relevés horaires, heure de Paris.</span></figcaption>'
            f'<ul class="legend" id="compare-legend"></ul><div class="cmp-plot" id="compare-plot"></div><div class="cmp-x" id="compare-x"></div>'
            f'<div class="chart-foot"><span>Source : relevés horaires des API publiques de Roblox.</span></div></figure>'
            f'<div class="stats cmp-stats" id="compare-stats"></div></div>')
    return page("Comparer deux jeux Roblox", body, "Comparez la courbe de joueurs en ligne de deux jeux Roblox, heure par heure.", "comparer/")


def alerts_page(alerts, page, url):
    labels = {"forte_hausse": "Forte hausse", "entree_top10": "Entrée dans le top 10"}
    items = []
    for a in alerts[:100]:
        t = parse_iso(a["ts_utc"])
        var = fr_pct(float(a["variation"])) if a["variation"] else ""
        rk = "1er" if a["rang"] == "1" else f"{a['rang']}e"
        what = (f"passe de {fr_int(int(a['avant']))} à {fr_int(int(a['maintenant']))} joueurs en ligne en une heure ({var})"
                if a["type"] == "forte_hausse" else
                f"entre dans le top 10 au {rk} rang, contre le {a['rang_avant']}e une heure plus tôt")
        link = url(f"jeux/{game_slug(a['universe_id'], a['nom'])}/")
        items.append(f'<li class="alert-item {esc(a["type"])}"><span class="al-kind">{labels.get(a["type"], a["type"])}</span>'
                     f'<time datetime="{a["ts_utc"]}">{esc(fr_date(t.astimezone(TZ).date(), weekday=False))}, {esc(fr_hour(t))}</time>'
                     f'<p><a href="{link}">{esc(a["nom"])}</a> {esc(what)}.</p></li>')
    body = (f'<div class="narrow"><h1>Alertes</h1><p class="lede">Les mouvements les plus brusques, détectés automatiquement à chaque relevé horaire. '
            f'Seuils : une hausse d’au moins 50 % en une heure pour un jeu qui compte au moins 2 000 joueurs, ou une entrée dans le top 10 '
            f'depuis l’extérieur du top 20.</p>'
            + (f'<ol class="alerts">{"".join(items)}</ol>' if items else '<p class="empty-note">Aucune alerte pour l’instant : elles apparaissent ici dès qu’un jeu décolle.</p>')
            + f'<p class="note">Flux RSS des alertes : <a href="{url("alertes.xml")}">alertes.xml</a>. Archive complète : '
            f'<a href="{esc(github_tree("data"))}">data/alertes.csv</a>.</p></div>')
    return page("Alertes : les jeux Roblox qui décollent", body, "Les jeux Roblox qui décollent, détectés automatiquement à chaque relevé horaire.", "alertes/")


def data_page(page, url):
    base = (CONFIG.get("baseUrl") or "").rstrip("/")
    rows = [("Classement en direct (100 premiers, variation sur 1 h)", "api/classement.json"),
            ("Liste des jeux suivis", "api/jeux/index.json"),
            ("Historique horaire d’un jeu (30 jours)", "api/jeux/{universe_id}.json"),
            ("Alertes récentes", "api/alertes.json")]
    trs = "".join(f"<tr><td>{esc(a)}</td><td><code>{esc(base + '/' + b)}</code></td></tr>" for a, b in rows)
    body = (f'<div class="narrow prose page"><h1>Données ouvertes</h1>'
            f'<p>Tout ce que nous relevons est public. Studios, chercheurs, créateurs de contenu : servez-vous.</p>'
            f'<h2>API</h2><p>Des fichiers JSON mis à jour toutes les heures, sans clé ni inscription.</p>'
            f'<div class="table-wrap"><table><thead><tr><th>Contenu</th><th>Adresse</th></tr></thead><tbody>{trs}</tbody></table></div>'
            f'<h2>Archives complètes</h2><p>Chaque relevé horaire est archivé en CSV depuis le 21 octobre 2026 dans notre '
            f'<a href="{esc(github_tree("data"))}">dépôt public</a>.</p>'
            f'<h2>Licence</h2><p>{esc(LICENCE)}</p>'
            f'<h2>Besoin d’autre chose ?</h2><p>Études sur mesure, séries longues, données par genre : '
            f'<a href="{url("partenaires/")}">travaillons ensemble</a>.</p></div>')
    return page("Données ouvertes et API", body, "Les données du Relevé en accès libre : classement, historique par jeu, alertes.", "donnees/")


def api_files(recs, latest_ts, alerts, prev_ranks):
    meta = {"source": "Le Relevé, relevés horaires des API publiques de Roblox", "licence": LICENCE,
            "site": CONFIG.get("baseUrl", ""), "genere": iso(utc_now())}
    top = [r for r in recs if r["rang"]][:100]
    classement = {**meta, "releve": iso(latest_ts) if latest_ts else None, "jeux": [
        {k: r[k] for k in ("rang", "universe_id", "nom", "createur", "genre", "joueurs", "pic_24h")} |
        {"variation_1h": prev_ranks.get(r["universe_id"], {}).get("var"), "rang_1h_avant": prev_ranks.get(r["universe_id"], {}).get("rang"),
         "page": f"{CONFIG.get('baseUrl', '')}/jeux/{r['slug']}/"} for r in top]}
    index = {**meta, "jeux": [{k: r[k] for k in ("universe_id", "nom", "rang", "joueurs", "slug")} for r in recs]}
    files = {"api/classement.json": classement, "api/jeux/index.json": index,
             "api/alertes.json": {**meta, "alertes": alerts[:200]}}
    for r in recs:
        files[f"api/jeux/{r['universe_id']}.json"] = {**meta, **r}
    return {k: json.dumps(v, ensure_ascii=False, separators=(",", ":")) for k, v in files.items()}


def alerts_feed(alerts, abs_url):
    items = []
    for a in alerts[:50]:
        title = (f"{a['nom']} : +{round(float(a['variation']) * 100)} % de joueurs en une heure" if a["type"] == "forte_hausse"
                 else f"{a['nom']} entre dans le top 10 ({a['rang']}e)")
        link = abs_url(f"jeux/{game_slug(a['universe_id'], a['nom'])}/")
        from email.utils import format_datetime
        items.append(f"<item><title>{esc(title)}</title><link>{esc(link)}</link><guid isPermaLink=\"false\">{esc(a['ts_utc'] + a['type'] + a['universe_id'])}</guid>"
                     f"<pubDate>{format_datetime(parse_iso(a['ts_utc']))}</pubDate></item>")
    return (f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{esc(CONFIG["name"])} : alertes</title>'
            f'<link>{esc(abs_url("alertes/"))}</link><description>Les jeux Roblox qui décollent, détectés à chaque relevé horaire.</description>'
            f'<language>fr</language>{"".join(items)}</channel></rss>')
