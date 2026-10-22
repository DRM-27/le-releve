"""Pages d'exploration : une page par jeu, comparateur, alertes, données ouvertes (API JSON).

Tout est calculé à partir des relevés archivés : aucune donnée tierce.
"""
import html
import json
import re
from datetime import timedelta

import charts
import pages2
import resumes
from common import (CONFIG, DATA, TZ, fr_big, fr_date, fr_hour, fr_int, fr_pct, fr_rank, fr_share, github_tree, iso, load_games,
                    parse_iso, read_csv, slugify, snap_path, utc_now)
from facts import GENRES_FR
from i18n import t
import i18n
from common import rank_html

esc = html.escape
HISTORY_DAYS = 30
INDEX_AFTER_DAYS = 7  # une page de jeu n'est proposée à Google qu'avec 7 jours d'historique
LICENCE = "Données sous licence ODbL : réutilisation libre, y compris commerciale, en citant « PlayLedger » avec un lien."


def lic():
    return t(LICENCE)


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
            "place_id": g.get("root_place_id", ""), "icon": g.get("icon", ""), "cree": g.get("created", "")[:10], "mis_a_jour": g.get("updated", "")[:10],
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
    plain = re.sub(r"<[^>]+>", "", str(value))
    return (f'<div class="stat{" long" if len(plain) > 9 else ""}"><span class="stat-label">{esc(label)}</span><span class="stat-value">{value}</span>'
            + (f'<span class="stat-note">{esc(note)}</span>' if note else "") + "</div>")


def fr_iso_date(v):
    try:
        from datetime import date as _d
        return esc(fr_date(_d.fromisoformat(v[:10]), weekday=False))
    except (ValueError, TypeError):
        return esc(v or "")


def related_games(rec, recs, url):
    ranked = [r for r in recs if r["universe_id"] != rec["universe_id"] and r["rang"]]
    ranked.sort(key=lambda r: r["rang"])
    blocks = []
    for label, key in ((t("Même studio"), "createur"), (t("Même genre"), "genre")):
        if not rec.get(key):
            continue
        same = [r for r in ranked if r.get(key) == rec[key]][:6]
        if same:
            lis = "".join(f'<li><a href="{url("jeux/" + r["slug"] + "/")}">' + (f'<img class="gicon" src="{esc(r["icon"])}" alt="" width="32" height="32" loading="lazy">' if r["icon"] else "")
                          + f'<span class="rg-name">{esc(r["nom"])}</span><span class="rg-rank">{rank_html(r["rang"])}</span></a></li>' for r in same)
            shown = t(rec[key]) if key == "genre" else rec[key]
            blocks.append(f'<div class="rg-col"><h3>{label} <span class="rg-key">{esc(shown)}</span></h3><ul>{lis}</ul></div>')
    return f'<section class="related-games"><h2>{t("Jeux proches")}</h2><div class="rg-grid">{"".join(blocks)}</div></section>' if blocks else ""


def game_page(rec, page, url, recs=()):
    pts = {"titre": t("{nom} : joueurs en ligne, relevés horaires", nom=rec['nom']), "unite": t("joueurs"), "points": rec["serie"],
           "csv": f"data/snapshots", "note": t("Depuis le début de notre suivi, le {date}. Heure de Paris.", date=fr_date(parse_iso(rec['suivi_depuis']).astimezone(TZ).date(), weekday=False))}
    chart = charts.line("jeu", pts, height=280).replace(
        t("Données du graphique (CSV)"), t("Relevés horaires (CSV)")) if len(rec["serie"]) > 1 else \
        f'<p class="note">{t("La courbe apparaîtra dès le deuxième relevé.")}</p>'
    roblox = f"https://www.roblox.com/games/{rec['place_id']}" if rec["place_id"] else ""
    stats = [
        stat(t("Joueurs en ligne"), fr_int(rec["joueurs"]), t("relevé de {heure}", heure=fr_hour(parse_iso(rec['releve'])))),
        stat(t("Rang"), rank_html(rec["rang"]), t("parmi les jeux suivis")),
        stat(t("Pic sur 24 h"), fr_int(rec["pic_24h"]) if rec["pic_24h"] is not None else "—", t("plus haut relevé horaire")),
        stat(t("Pic depuis le début du suivi"), fr_int(rec["pic_suivi"]), fr_date(parse_iso(rec["pic_suivi_date"]).astimezone(TZ).date(), weekday=False)),
        stat(t("Visites cumulées"), fr_big(rec["visites"]) if rec["visites"] else "—"),
        stat(t("Votes positifs"), fr_share(rec["note"]) if rec["note"] is not None else "—"),
    ]
    facts = [(t("Créateur"), esc(rec["createur"]) + (t(" (vérifié)") if rec["createur_verifie"] else "")), (t("Genre"), esc(" · ".join(x for x in (t(rec["genre"]) if rec["genre"] else "", rec["sous_genre"]) if x))),
             (t("Créé le"), fr_iso_date(rec["cree"])), (t("Dernière mise à jour"), fr_iso_date(rec["mis_a_jour"]))]
    dl = "".join(f"<dt>{k}</dt><dd>{v or '—'}</dd>" for k, v in facts)
    body = (f'<div class="wide game"><p class="crumbs"><a href="{url("classement/")}">{t("Classement")}</a></p>'
            f'<div class="game-title">' + (f'<img class="gicon big" src="{esc(rec["icon"])}" alt="" width="72" height="72">' if rec["icon"] else "") + f'<h1>{esc(rec["nom"])}</h1></div><p class="lede">{t("Joueurs en ligne, pics et visites, relevés toutes les heures depuis les API publiques de Roblox.")}</p>'
            f'<div class="stats">{"".join(stats)}</div>{resumes.game_summary_html(rec, recs)}{chart}{pages2.game_heat(rec)}{pages2.recent_updates_for(rec["universe_id"], url)}'
            f'<div class="game-meta"><dl>{dl}</dl><div class="game-links">'
            + (f'<a class="btn roblox" href="{esc(roblox)}" rel="nofollow">{t("Ouvrir sur Roblox")}</a>' if roblox else "")
            + f'<a class="btn" href="{url("comparer/?a=" + rec["universe_id"])}">{t("Comparer avec un autre jeu")}</a>'
            f'<a class="btn ghost" href="{url("api/jeux/" + rec["universe_id"] + ".json")}">{t("Données en JSON")}</a></div></div>'
            + related_games(rec, recs, url) +
            f'<section class="embed-box"><h2>{t("Badge « Classé sur PlayLedger »")}</h2><p>{t("Pour votre site, votre Discord ou la description de votre jeu : le badge se met à jour toutes les heures.")}</p>'
            f'<p><img src="{url("badge/" + rec["universe_id"] + ".svg")}" alt="Badge {esc(rec["nom"])}" height="28"></p>'
            f'<pre class="embed"><code id="badge-code">{esc(badge_code(rec))}</code></pre>'
            f'<p><button class="btn" type="button" data-copy-from="badge-code">{t("Copier le code du badge")}</button></p></section>'
            f'<section class="embed-box"><h2>{t("Intégrer ce graphique sur votre site")}</h2>'
            f'<p>{t("Courbe mise à jour toutes les heures, gratuite, avec un lien vers cette page. À coller dans un article, un wiki ou une page de créateur :")}</p>'
            f'<pre class="embed"><code id="embed-code">{esc(game_embed(rec))}</code></pre>'
            f'<p><button class="btn" type="button" data-copy-from="embed-code">{t("Copier le code")}</button> '
            f'<a class="btn ghost" href="{url("widget/jeu/" + rec["universe_id"] + "/")}">{t("Voir le widget")}</a></p></section>'
            f'<div class="toast" id="toast" role="status" aria-live="polite"></div>'
            + resumes.faq_html(resumes.game_faq(rec)) +
            f'<p class="note">{esc(lic())} {t("Les visites et votes sont ceux affichés par Roblox au dernier relevé.")}</p></div>')
    noindex = rec["jours_suivis"] < INDEX_AFTER_DAYS
    head = '<meta name="robots" content="noindex">' if noindex else ""
    title = t("{nom} : joueurs en ligne et statistiques", nom=rec['nom'])
    desc = t("Combien de joueurs sur {nom} ? Joueurs en ligne, pic sur 24 h, visites et courbe horaire, mis à jour toutes les heures.", nom=rec['nom'])
    base = (CONFIG.get("baseUrl") or "").rstrip("/") + ("/" + i18n.prefix().rstrip("/") if i18n.prefix() else "")
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "VideoGame", "name": rec["nom"], "url": f"https://www.roblox.com/games/{rec['place_id']}" if rec["place_id"] else None,
         "gamePlatform": "Roblox", "genre": rec["genre"] or None, "author": {"@type": "Organization", "name": rec["createur"]} if rec["createur"] else None,
         "image": rec["icon"] or None},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": t("Classement"), "item": f"{base}/classement/"},
            {"@type": "ListItem", "position": 2, "name": rec["nom"], "item": f"{base}/jeux/{rec['slug']}/"}]},
        resumes.faq_ld(resumes.game_faq(rec))]}
    ld["@graph"][0] = {k: v for k, v in ld["@graph"][0].items() if v is not None}
    ogi = f"og/jeux/{rec['universe_id']}.png" if rec["rang"] and rec["rang"] <= 100 else "og/site.png"
    return page(title, body, desc, f"jeux/{rec['slug']}/", extra_head=head, ld=ld, og_image=ogi), not noindex


def badge_code(rec):
    root = (CONFIG.get("baseUrl") or "").rstrip("/")
    base = root + ("/" + i18n.prefix().rstrip("/") if i18n.prefix() else "")
    return (f'<a href="{base}/jeux/{rec["slug"]}/"><img src="{root}/badge/{rec["universe_id"]}.svg" '
            f'alt="{esc(t("{nom} au classement PlayLedger", nom=rec["nom"]))}" height="28"></a>')


def game_embed(rec):
    base = (CONFIG.get("baseUrl") or "").rstrip("/") + ("/" + i18n.prefix().rstrip("/") if i18n.prefix() else "")
    return (f'<iframe src="{base}/widget/jeu/{rec["universe_id"]}/" title="{esc(t("{nom} : joueurs en ligne, par PlayLedger", nom=rec["nom"]))}" '
            f'width="100%" height="260" style="border:0;max-width:560px" loading="lazy"></iframe>')


def game_widget(rec, abs_url):
    pts = [v for _, v in rec["serie"]][-168:]
    sp = charts.sparkline(pts, 520, 120) if len(pts) > 1 else ""
    when = fr_hour(parse_iso(rec["releve"]))
    return f"""<!doctype html><html lang="{i18n.META[i18n.CUR]['html']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(rec['nom'])} | {esc(CONFIG['name'])}</title><meta name="robots" content="noindex">
<style>
body{{margin:0;background:#151d2a;color:#f8fafc;font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}}
.w{{border:1px solid #222f43;border-radius:12px;padding:14px 16px}} .top{{display:flex;align-items:center;gap:10px}}
img{{width:36px;height:36px;border-radius:8px;object-fit:cover;background:#1e293b}} h1{{font-size:15px;margin:0}} .n{{font-size:26px;font-weight:800;margin:8px 0 2px}}
.m{{color:#94a3b8;font-size:12px}} svg{{width:100%;height:110px;display:block;margin-top:8px;color:#10b981;overflow:visible}} svg.down{{color:#ef4444}} .sp-line{{fill:none;stroke:currentColor;stroke-width:2}} .sp-dot{{stroke:currentColor;stroke-width:7;stroke-linecap:round}}
a{{color:#60a5fa}}
</style></head><body><div class="w"><div class="top">{f'<img src="{esc(rec["icon"])}" alt="">' if rec["icon"] else ""}<h1>{esc(rec['nom'])}</h1></div>
<div class="n">{fr_int(rec['joueurs'])}</div><div class="m">{t("joueurs en ligne au relevé de {heure} (heure de Paris)", heure=esc(when))}</div>{sp}
<div class="m">{t("Données :")} <a href="{esc(abs_url('jeux/' + rec['slug'] + '/'))}" target="_blank" rel="noopener">{esc(CONFIG['name'])}</a>{t(", relevés horaires vérifiables")}</div></div></body></html>"""


def compare_page(recs, page, url):
    opts = "".join(f'<option value="{r["universe_id"]}">{esc(r["nom"])}</option>' for r in sorted(recs, key=lambda r: r["nom"].lower()))
    ranked = [r for r in recs if r["rang"]]
    da, db = (ranked[0]["universe_id"], ranked[1]["universe_id"]) if len(ranked) > 1 else ("", "")
    body = (f'<div class="wide"><h1>{t("Comparer deux jeux")}</h1><p class="lede">{t("Choisissez deux jeux pour superposer leurs courbes de joueurs en ligne, relevé par relevé. Le lien de la page se met à jour : partagez-le tel quel.")}</p>'
            f'<form class="compare-form" id="compare" data-a="{da}" data-b="{db}"><label>{t("Premier jeu")}<select name="a">{opts}</select></label>'
            f'<label>{t("Second jeu")}<select name="b">{opts}</select></label></form>'
            f'<figure class="chart" id="compare-chart" data-api="{url("api/jeux/")}"><figcaption><span class="chart-title" id="compare-title">{t("Chargement…")}</span>'
            f'<span class="chart-note">{t("Joueurs en ligne, relevés horaires, heure de Paris.")}</span></figcaption>'
            f'<ul class="legend" id="compare-legend"></ul><div class="cmp-plot" id="compare-plot"></div><div class="cmp-x" id="compare-x"></div>'
            f'<div class="chart-foot"><span>{t("Source : relevés horaires des API publiques de Roblox.")}</span></div></figure>'
            f'<div class="stats cmp-stats" id="compare-stats"></div>'
            f'<p class="share-row share-bar"><span class="share-label">{t("Partager")}</span>'
            f'<button class="share copy" type="button" id="copy-btn"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>{t("Copier le lien")}</button>'
            f'<a class="share x" id="x-share" href="https://twitter.com/intent/tweet" target="_blank" rel="noopener">'
            f'<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.75 3h3.07l-6.7 7.66L22 21h-6.17l-4.83-6.32L5.47 21H2.4l7.17-8.2L2 3h6.33l4.37 5.77L17.75 3Zm-1.08 16.17h1.7L7.4 4.73H5.58l11.09 14.44Z"/></svg>X</a><a class="share li" id="li-share" href="https://www.linkedin.com/sharing/share-offsite/" target="_blank" rel="noopener"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9.5h4V21H3V9.5Zm6.5 0h3.8v1.6h.1c.5-1 1.8-2 3.8-2 4 0 4.8 2.6 4.8 6V21h-4v-5.2c0-1.2 0-2.9-1.8-2.9s-2 1.4-2 2.8V21h-4V9.5Z"/></svg>LinkedIn</a></p></div>'
            f'<div class="toast" id="toast" role="status" aria-live="polite"></div>')
    return page(t("Comparer deux jeux Roblox"), body, t("Comparez la courbe de joueurs en ligne de deux jeux Roblox, heure par heure."), "comparer/")


def recent_moves(live, url):
    """Sans alerte récente : les plus forts mouvements de l'heure, sous les seuils, pour montrer que la détection tourne."""
    if not live:
        return ""
    moves = sorted([r for r in live["rows"] if r.get("var") is not None and r["maintenant"] >= 1000], key=lambda r: -abs(r["var"]))[:3]
    if not moves:
        return ""
    li = "".join(f'<li class="alert-item move"><span class="al-kind">{t("Hausse sous le seuil") if r["var"] > 0 else t("Baisse")}</span>'
                 f'<span class="pill {"up" if r["var"] > 0 else "down"}">{esc(fr_pct(r["var"]))}</span>'
                 f'<p class="mv-line">' + (f'<img class="gicon sm" src="{esc(r["icon"])}" alt="" width="24" height="24" loading="lazy">' if r.get("icon") else '<span class="gicon sm"></span>')
                 + f'<a href="{url("jeux/" + r["slug"] + "/")}">{esc(r["nom"])}</a>{t(" : {n} joueurs en ligne au dernier relevé.", n=fr_int(r["maintenant"]))}</p></li>'
                 for r in moves)
    return (f'<h2 class="sec-title">{t("Plus forts mouvements de la dernière heure")}</h2>'
            f'<p class="note">{t("Aucun jeu n’a franchi les seuils d’alerte sur les dernières 24 heures. Voici les plus fortes variations de l’heure, parmi les jeux qui comptent au moins {seuil} joueurs.", seuil=fr_int(1000))}</p>'
            f'<ol class="alerts">{li}</ol>')


def scan_status(alerts, live):
    """Module « détection active » : dernier passage, jeux analysés, anomalies de la dernière heure."""
    if not live:
        return ""
    ts = live["ts"]
    recent = [a for a in alerts if (ts - parse_iso(a["ts_utc"])).total_seconds() <= 3600]
    n = len(recent)
    found = t("Aucune anomalie détectée") if n == 0 else t("{n} anomalie(s) détectée(s)", n=n)
    return (f'<div class="scan" role="status"><span class="scan-dot" aria-hidden="true"></span><div><p class="scan-title">{t("Système de détection actif")}</p>'
            f'<p class="scan-text">{t("Dernière analyse : {date} à {heure}, {n} jeux analysés.", date=esc(fr_date(ts.astimezone(TZ).date(), weekday=False)), heure=esc(fr_hour(ts)), n=fr_int(live["n"]))} '
            f'{found} {t("sur la dernière heure.")}</p></div>'
            f'<div class="scan-bars" aria-hidden="true">{"".join("<i></i>" for _ in range(12))}</div></div>')


def alerts_page(alerts, page, url, live=None):
    labels = {"forte_hausse": t("Forte hausse"), "entree_top10": t("Entrée dans le top 10")}
    recent24 = bool(live) and any((live["ts"] - parse_iso(a["ts_utc"])).total_seconds() <= 86400 for a in alerts)
    items = []
    for a in alerts[:100]:
        ta = parse_iso(a["ts_utc"])
        var = fr_pct(float(a["variation"])) if a["variation"] else ""
        rk = fr_rank(int(a["rang"]))
        what = (t("passe de {avant} à {apres} joueurs en ligne en une heure ({var})", avant=fr_int(int(a['avant'])), apres=fr_int(int(a['maintenant'])), var=var)
                if a["type"] == "forte_hausse" else
                t("entre dans le top 10 au {rang} rang, contre le {avant} une heure plus tôt", rang=rk, avant=fr_rank(int(a['rang_avant'])) if a['rang_avant'] else "—"))
        link = url(f"jeux/{game_slug(a['universe_id'], a['nom'])}/")
        items.append(f'<li class="alert-item {esc(a["type"])}"><span class="al-kind">{labels.get(a["type"], a["type"])}</span>'
                     f'<time datetime="{a["ts_utc"]}">{esc(fr_date(ta.astimezone(TZ).date(), weekday=False))}, {esc(fr_hour(ta))}</time>'
                     f'<p><a href="{link}">{esc(a["nom"])}</a> {esc(what)}.</p></li>')
    body = (f'<div class="narrow"><h1>{t("Alertes")}</h1><p class="lede">{t("Les mouvements les plus brusques, détectés automatiquement à chaque relevé horaire. Seuils : une hausse d’au moins {pct} en une heure pour un jeu qui compte au moins {n} joueurs, ou une entrée dans le top 10 depuis l’extérieur du top 20.", pct=fr_share(0.5, nd=0), n=fr_int(2000))}</p>'
            + scan_status(alerts, live)
            + (f'<h2 class="sec-title">{t("Alertes")}</h2><ol class="alerts">{"".join(items[:3] if recent24 else items)}</ol>' if items else "")
            + ("" if recent24 else recent_moves(live, url))
            + f'<section class="follow" id="recevoir"><h2>{t("Recevoir les alertes")}</h2>'
            f'<p>{t("Abonnez-vous au flux des alertes dans votre lecteur RSS (Feedly, Inoreader, NetNewsWire…) : vous êtes prévenu dès qu’un jeu décolle.")}</p>'
            f'<p><a class="btn" href="{url("alertes.xml")}">{t("S’abonner au flux des alertes")}</a> '
            f'<button class="btn ghost" type="button" data-copy="{esc((CONFIG.get("baseUrl") or "") + "/" + i18n.prefix() + "alertes.xml")}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></svg>{t("Copier l’adresse du flux")}</button></p>'
            f'<p><span class="btn disabled" aria-disabled="true">{t("Bot Telegram : ouverture prochaine")}</span></p>'
            f'<p class="note">{t("Les alertes sur Telegram arrivent bientôt. Abonnez-vous au flux ci-dessus pour ne rien manquer d’ici là.")}</p></section>'
            f'<div class="toast" id="toast" role="status" aria-live="polite"></div>'
            + f'<p class="note">{t("Flux RSS des alertes :")} <a href="{url("alertes.xml")}">alertes.xml</a>. {t("Archive complète :")} '
            f'<a href="{esc(github_tree("data"))}">data/alertes.csv</a>.</p></div>')
    return page(t("Alertes : les jeux Roblox qui décollent"), body, t("Les jeux Roblox qui décollent, détectés automatiquement à chaque relevé horaire."), "alertes/")


def data_page(page, url):
    base = (CONFIG.get("baseUrl") or "").rstrip("/")
    rows = [(t("Classement en direct (100 premiers, variation sur 1 h)"), "api/classement.json"),
            (t("Liste des jeux suivis"), "api/jeux/index.json"),
            (t("Historique horaire d’un jeu (30 jours)"), "api/jeux/{universe_id}.json"),
            (t("Alertes récentes"), "api/alertes.json")]
    trs = "".join(f"<tr><td>{esc(a)}</td><td><code>{esc(base + '/' + b)}</code></td></tr>" for a, b in rows)
    from datetime import date as _date
    body = (f'<div class="narrow prose page"><h1>{t("Données ouvertes")}</h1>'
            f'<p>{t("Tout ce que nous relevons est public. Studios, chercheurs, créateurs de contenu : servez-vous.")}</p>'
            f'<h2>API</h2><p>{t("Des fichiers JSON mis à jour toutes les heures, sans clé ni inscription.")}</p>'
            f'<div class="table-wrap"><table><thead><tr><th>{t("Contenu")}</th><th>{t("Adresse")}</th></tr></thead><tbody>{trs}</tbody></table></div>'
            f'<h2>{t("Archives complètes")}</h2><p>{t("Chaque relevé horaire est archivé en CSV depuis le {date} dans notre", date=fr_date(_date(2026, 10, 21), weekday=False))} '
            f'<a href="{esc(github_tree("data"))}">{t("dépôt public")}</a>.</p>'
            f'<h2>{t("Intégrer le classement sur votre site")}</h2><p>{t("Un widget gratuit, mis à jour toutes les heures. Copiez ce code dans votre page :")}</p>'
            f'<pre class="embed"><code id="embed-code">{esc(embed_code())}</code></pre>'
            f'<p><button class="btn" type="button" data-copy-from="embed-code">{t("Copier le code")}</button> <a class="btn ghost" href="{url("widget/")}">{t("Voir le widget")}</a></p>'
            f'<div class="toast" id="toast" role="status" aria-live="polite"></div>'
            f'<h2>{t("Licence")}</h2><p>{esc(lic())}</p>'
            f'<h2>{t("Besoin d’autre chose ?")}</h2><p>{t("Études sur mesure, séries longues, données par genre :")} '
            f'<a href="{url("partenaires/")}">{t("travaillons ensemble")}</a>.</p></div>')
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": "Relevés horaires des jeux Roblox",
          "description": "Joueurs en ligne, visites, favoris et votes des jeux Roblox les plus joués, relevés toutes les heures depuis le 21 octobre 2026.",
          "url": base + "/donnees/", "license": "https://opendatacommons.org/licenses/odbl/1-0/", "isAccessibleForFree": True,
          "creator": {"@type": "Organization", "name": CONFIG["name"]}, "temporalCoverage": "2026-10-21/..",
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": base + "/api/classement.json"},
                           {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"https://github.com/{CONFIG.get('repo')}/tree/main/data"}]}
    return page(t("Données ouvertes et API"), body, t("Les données de PlayLedger en accès libre : classement, historique par jeu, alertes."), "donnees/", ld=ld)


def embed_code():
    base = (CONFIG.get("baseUrl") or "").rstrip("/") + ("/" + i18n.prefix().rstrip("/") if i18n.prefix() else "")
    return (f'<iframe src="{base}/widget/" title="{esc(t("Classement en direct des jeux Roblox, par PlayLedger"))}" '
            f'width="100%" height="520" style="border:0;max-width:420px" loading="lazy"></iframe>')


def widget_page(live, url, abs_url):
    """Page autonome, sans en-tête, faite pour être intégrée dans une iframe."""
    rows = live["rows"][:10] if live else []
    items = "".join(
        f'<li><span class="w-rank">{r["rang"]}</span>'
        + (f'<img src="{esc(r["icon"])}" alt="" width="28" height="28" loading="lazy">' if r.get("icon") else '<span class="w-ph"></span>')
        + f'<a href="{esc(abs_url("jeux/" + r["slug"] + "/"))}" target="_blank" rel="noopener">{esc(r["nom"])}</a>'
        f'<span class="w-val">{fr_int(r["maintenant"])}</span></li>' for r in rows)
    when = t("Relevé du {date} à {heure}", date=fr_date(live['ts'].astimezone(TZ).date(), weekday=False), heure=fr_hour(live['ts'])) if live else ""
    return f"""<!doctype html><html lang="{i18n.META[i18n.CUR]['html']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Classement en direct des jeux Roblox")} | {esc(CONFIG['name'])}</title><meta name="robots" content="noindex">
<style>
:root{{color-scheme:light dark;--bg:#fff;--ink:#1b2a41;--mut:#6f7c8b;--rule:#e6ebef;--acc:#1d4fc4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16202c;--ink:#e6ecf2;--mut:#8592a1;--rule:#2a3747;--acc:#86a9ff}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}}
.w{{border:1px solid var(--rule);border-radius:10px;padding:12px 14px}} h1{{font-size:15px;margin:0 0 2px}} p{{margin:0 0 8px;color:var(--mut);font-size:12px}}
ol{{list-style:none;margin:0;padding:0}} li{{display:grid;grid-template-columns:20px 28px 1fr auto;gap:8px;align-items:center;padding:6px 0;border-top:1px solid var(--rule)}}
img,.w-ph{{border-radius:6px;width:28px;height:28px;background:var(--rule)}} a{{color:inherit;text-decoration:none;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
a:hover{{text-decoration:underline}} .w-rank{{color:var(--mut)}} .w-val{{font-weight:700;font-variant-numeric:tabular-nums}}
.foot{{margin-top:8px;font-size:12px}} .foot a{{color:var(--acc)}}
</style></head><body><div class="w"><h1>{t("Jeux Roblox les plus joués")}</h1><p>{esc(when)}{t(", joueurs en ligne")}</p><ol>{items}</ol>
<div class="foot">{t("Classement :")} <a href="{esc(abs_url('classement/'))}" target="_blank" rel="noopener">{esc(CONFIG['name'])}</a>{t(", données vérifiables")}</div></div></body></html>"""


def api_files(recs, latest_ts, alerts, prev_ranks):
    meta = {"source": "PlayLedger, relevés horaires des API publiques de Roblox", "licence": LICENCE,
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
        title = (t("{nom} : {var} de joueurs en une heure", nom=a['nom'], var=fr_pct(float(a['variation']), nd=0)) if a["type"] == "forte_hausse"
                 else t("{nom} entre dans le top 10 ({rang})", nom=a['nom'], rang=fr_rank(int(a['rang']))))
        link = abs_url(f"jeux/{game_slug(a['universe_id'], a['nom'])}/")
        from email.utils import format_datetime
        items.append(f"<item><title>{esc(title)}</title><link>{esc(link)}</link><guid isPermaLink=\"false\">{esc(a['ts_utc'] + a['type'] + a['universe_id'])}</guid>"
                     f"<pubDate>{format_datetime(parse_iso(a['ts_utc']))}</pubDate></item>")
    return (f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{esc(CONFIG["name"])} : {t("alertes")}</title>'
            f'<link>{esc(abs_url("alertes/"))}</link><description>{t("Les jeux Roblox qui décollent, détectés à chaque relevé horaire.")}</description>'
            f'<language>{i18n.META[i18n.CUR]["html"]}</language>{"".join(items)}</channel></rss>')
