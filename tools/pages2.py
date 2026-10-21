"""Pages d'exploration, vague 2 : tendances, mises à jour, heures de pointe, records, studios, genres, hub Explorer.

Tout est calculé à partir des relevés archivés. Quand l'historique est trop court, la page le dit et annonce
la date à laquelle la fonction sera complète, plutôt que d'afficher un chiffre fragile.
"""
import glob
import html
from datetime import timedelta
from statistics import mean

import charts
from common import (CONFIG, DATA, TZ, fr_date, fr_hour, fr_int, fr_pct, github_tree, parse_iso, read_csv, slugify, utc_now)

esc = html.escape
JOURS_COURTS = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]


def icon(rec, size=28):
    if rec.get("icon"):
        return f'<img class="gicon" src="{esc(rec["icon"])}" alt="" width="{size}" height="{size}" loading="lazy" style="width:{size}px;height:{size}px">'
    return f'<span class="gicon" style="width:{size}px;height:{size}px;display:inline-block"></span>'


def soon(title, text, when=""):
    return (f'<div class="soon"><span class="soon-tag">Bientôt</span><h2>{esc(title)}</h2><p>{esc(text)}</p>'
            + (f'<p class="soon-when">Disponible à partir du {esc(when)}.</p>' if when else "") + "</div>")


def game_link(url, rec):
    return f'<a href="{url("jeux/" + rec["slug"] + "/")}">{esc(rec["nom"])}</a>'


def tracking_start():
    files = sorted(glob.glob(str(DATA / "snapshots/*/*/*/*.csv")))
    if not files:
        return None
    rows = read_csv(__import__("pathlib").Path(files[0]))
    return parse_iso(rows[0]["ts_utc"]) if rows else None


# ------------------------------------------------------------------ tendances (page Découvrir)
def trends_page(recs, page, url):
    by_uid = {r["universe_id"]: r for r in recs}
    files = sorted(glob.glob(str(DATA / "sorts/*/*/*/*.csv")))
    if not files:
        return page("Tendances", '<div class="wide"><h1>Tendances</h1>' + soon("Classements de la page Découvrir", "Le premier relevé n’a pas encore eu lieu.") + "</div>", path="tendances/")
    import pathlib
    latest = read_csv(pathlib.Path(files[-1]))
    t_last = parse_iso(latest[0]["ts_utc"])
    ref = None
    for f in reversed(files[:-1]):
        rows = read_csv(pathlib.Path(f))
        if rows and (t_last - parse_iso(rows[0]["ts_utc"])).total_seconds() >= 23 * 3600:
            ref = rows
            break
    if ref is None and len(files) > 1:
        ref = read_csv(pathlib.Path(files[0]))
    t_ref = parse_iso(ref[0]["ts_utc"]) if ref else None
    sections = []
    labels = {"top-trending": ("En tendance", "Les jeux que Roblox met en avant dans « Top Trending », dans l’ordre de la page Découvrir."),
              "up-and-coming": ("Nouveautés à suivre", "La sélection « Up-and-Coming » de Roblox : souvent les futurs succès.")}
    for sid, (title, lede) in labels.items():
        cur = [r for r in latest if r["sort_id"] == sid and r["is_sponsored"] == "0"]
        before = {r["universe_id"] for r in (ref or []) if r["sort_id"] == sid}
        items = []
        for r in cur[:30]:
            rec = by_uid.get(r["universe_id"])
            if not rec:
                continue
            new = ref is not None and r["universe_id"] not in before
            items.append(f'<li class="tr-item"><span class="tr-pos">{r["position"]}</span>{icon(rec, 36)}<div class="tr-name">{game_link(url, rec)}'
                         f'<span class="sub">{esc(rec["createur"])}</span></div>'
                         + ('<span class="tag new">Nouvelle entrée</span>' if new else "")
                         + f'<span class="tr-val">{fr_int(rec["joueurs"])}<small>joueurs</small></span></li>')
        n_new = sum(1 for r in cur if ref is not None and r["universe_id"] not in before)
        since = f"depuis le relevé du {fr_date(t_ref.astimezone(TZ).date(), weekday=False)} à {fr_hour(t_ref)}" if t_ref else ""
        sections.append(f'<section class="tr-sec"><h2>{esc(title)}</h2><p class="lede">{esc(lede)}</p>'
                        + (f'<p class="note">{n_new} nouvelle(s) entrée(s) {esc(since)}.</p>' if ref else "")
                        + f'<ol class="tr-list">{"".join(items)}</ol></section>')
    body = (f'<div class="wide"><h1>Tendances</h1><p class="lede">Ce que Roblox met en avant sur sa page Découvrir, relevé toutes les heures. '
            f'Relevé du {esc(fr_date(t_last.astimezone(TZ).date(), weekday=False))} à {esc(fr_hour(t_last))}. Emplacements sponsorisés exclus.</p>'
            f'<div class="tr-grid">{"".join(sections)}</div>'
            f'<p class="note">Archives horaires des classements : <a href="{esc(github_tree("data/sorts"))}">data/sorts</a>.</p></div>')
    return page("Tendances : les jeux que Roblox met en avant", body,
                "Les jeux en tendance et les nouveautés à suivre sur Roblox, relevés toutes les heures, avec les nouvelles entrées.", "tendances/")


# ------------------------------------------------------------------ mises à jour détectées
def updates_page(recs, page, url):
    by_uid = {r["universe_id"]: r for r in recs}
    ups = list(reversed(read_csv(DATA / "mises-a-jour.csv")))
    rows = []
    for u in ups[:60]:
        rec = by_uid.get(u["universe_id"])
        if not rec:
            continue
        t = parse_iso(u["ts_utc"])
        before = int(u["joueurs"] or 0)
        after = [v for ts, v in ((parse_iso(a), b) for a, b in rec["serie"]) if 20 * 3600 <= (ts - t).total_seconds() <= 28 * 3600]
        if after:
            v = after[len(after) // 2]
            delta = (v / before - 1) if before else None
            res = f'{fr_int(v)} joueurs 24 h après' + (f' <span class="pill {"up" if delta >= 0 else "down"}">{esc(fr_pct(delta))}</span>' if delta is not None else "")
        else:
            res = '<span class="muted">Effet sur 24 h : mesure en cours</span>'
        rows.append(f'<li class="up-item">{icon(rec, 36)}<div><p class="up-title">{game_link(url, rec)} a été mis à jour</p>'
                    f'<p class="up-meta">Détecté le {esc(fr_date(t.astimezone(TZ).date(), weekday=False))} à {esc(fr_hour(t))}, '
                    f'{fr_int(before)} joueurs à ce moment-là. {res}</p></div></li>')
    head = (f'<div class="narrow"><h1>Mises à jour détectées</h1><p class="lede">Chaque heure, nous relevons la date de dernière mise à jour '
            f'affichée par Roblox pour chaque jeu suivi. Quand elle change, la mise à jour est notée ici, avec le nombre de joueurs au moment '
            f'de la détection puis 24 heures après.</p>'
            f'<p class="note">Ce que montre cette page : ce qui s’est passé après une mise à jour, pas forcément à cause d’elle. '
            f'Un week-end, un événement ou une vidéo peuvent aussi jouer.</p>')
    if not rows:
        body = head + soon("Les premières détections arrivent", "Aucune mise à jour n’a encore été détectée depuis le début du suivi. "
                           "Elles apparaîtront ici dès le prochain changement.") + "</div>"
    else:
        body = head + f'<ol class="up-list">{"".join(rows)}</ol><p class="note">Archive : <a href="{esc(github_tree("data"))}">data/mises-a-jour.csv</a>.</p></div>'
    return page("Mises à jour détectées sur les jeux Roblox", body, "Les mises à jour des jeux Roblox détectées heure par heure, et ce qui s’est passé 24 heures après.", "mises-a-jour/")


def recent_updates_for(uid, url):
    ups = [u for u in read_csv(DATA / "mises-a-jour.csv") if u["universe_id"] == uid][-3:]
    if not ups:
        return ""
    li = "".join(f'<li>{esc(fr_date(parse_iso(u["ts_utc"]).astimezone(TZ).date(), weekday=False))} à {esc(fr_hour(parse_iso(u["ts_utc"])))}</li>' for u in reversed(ups))
    return f'<div class="mini-box"><h3>Mises à jour détectées</h3><ul>{li}</ul><a href="{url("mises-a-jour/")}">Toutes les mises à jour</a></div>'


# ------------------------------------------------------------------ heures de pointe
def heat_grid(series, unit="joueurs"):
    """series : liste de (datetime UTC, valeur). Retourne (html, nb de cases remplies)."""
    cells = {}
    for t, v in series:
        lt = t.astimezone(TZ)
        cells.setdefault((lt.weekday(), lt.hour), []).append(v)
    avg = {k: mean(v) for k, v in cells.items()}
    if not avg:
        return "", 0
    vmax = max(avg.values()) or 1
    vmin = min(avg.values())
    rows = []
    for d in range(7):
        tds = []
        for h in range(24):
            v = avg.get((d, h))
            if v is None:
                tds.append('<td class="hc empty" title="Pas encore de relevé"></td>')
            else:
                k = (v - vmin) / ((vmax - vmin) or 1)
                tds.append(f'<td class="hc" style="--k:{k:.3f}" title="{JOURS_COURTS[d]} {h} h : {fr_int(v)} {unit} en moyenne"></td>')
        rows.append(f'<tr><th scope="row">{JOURS_COURTS[d]}</th>{"".join(tds)}</tr>')
    hours = "".join(f'<th scope="col">{h if h % 3 == 0 else ""}</th>' for h in range(24))
    best = max(avg, key=avg.get)
    low = min(avg, key=avg.get)
    table = (f'<div class="heat-wrap"><table class="heat"><thead><tr><th></th>{hours}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
             f'<div class="heat-legend"><span>Moins de joueurs</span><i></i><span>Plus de joueurs</span></div>'
             + (f'<p class="heat-best">Créneau le plus fréquenté relevé : <b>{JOURS_COURTS[best[0]]} {best[1]} h</b> ({fr_int(avg[best])} {unit} en moyenne). '
             f'Le plus creux : <b>{JOURS_COURTS[low[0]]} {low[1]} h</b> ({fr_int(avg[low])}).</p>' if len(avg) >= 84 else
                '<p class="heat-best">Les créneaux les plus et les moins fréquentés seront indiqués quand la moitié de la semaine aura été relevée.</p>'))
    return table, len(avg)


def peak_page(recs, page, url):
    from explore import load_history
    hist = load_history(28)
    totals = {}
    for u, s in hist.items():
        for t, r in s:
            totals[t] = totals.get(t, 0) + int(r["playing"] or 0)
    grid, n = heat_grid(sorted(totals.items()))
    start = tracking_start()
    full = (start + timedelta(days=7)).astimezone(TZ).date() if start else None
    note = (f'<p class="note">Carte en cours de constitution : {n} créneaux horaires relevés sur 168. Elle sera complète le '
            f'{esc(fr_date(full, weekday=False))}, puis s’affinera chaque semaine.</p>' if n < 168 and full else "")
    body = (f'<div class="wide"><h1>Heures de pointe sur Roblox</h1><p class="lede">À quelle heure les joueurs sont-ils là ? Moyenne des joueurs en ligne '
            f'sur l’ensemble des jeux que nous suivons, par jour et par heure (heure de Paris). De quoi choisir le moment d’une mise à jour ou d’un lancement.</p>'
            f'{note}<section class="chart heat-box">{grid}</section>'
            f'<p class="note">Chaque jeu a aussi sa propre carte sur sa page. Le total porte sur les jeux suivis, pas sur toute la plateforme.</p></div>')
    return page("Heures de pointe sur Roblox", body, "À quelle heure jouent les joueurs Roblox ? Carte des heures de pointe, jour par jour, heure par heure.", "heures-de-pointe/")


def game_heat(rec):
    pts = [(parse_iso(a), b) for a, b in rec["serie"]]
    grid, n = heat_grid(pts)
    if n < 24:
        return ('<section class="mini-box"><h2>Heures de pointe</h2><p class="note">Carte disponible après une journée complète de relevés pour ce jeu.</p></section>')
    return f'<section class="chart heat-box"><span class="chart-title">Heures de pointe de ce jeu</span><span class="chart-note">Joueurs en ligne en moyenne, heure de Paris. {n} créneaux sur 168 relevés.</span>{grid}</section>'


# ------------------------------------------------------------------ records
def records_page(recs, page, url):
    start = tracking_start()
    span = (utc_now() - start).total_seconds() / 86400 if start else 0
    ranked = sorted([r for r in recs if r["serie"]], key=lambda r: -r["pic_suivi"])[:50]
    rows = "".join(f'<tr data-href="{url("jeux/" + r["slug"] + "/")}"><td class="num">{i}</td><td class="game"><div class="gcell">{icon(r, 36)}<div>{game_link(url, r)}'
                   f'<span class="sub">{esc(r["createur"])}</span></div></div></td><td class="num">{fr_int(r["pic_suivi"])}</td>'
                   f'<td class="hide-s">{esc(fr_date(parse_iso(r["pic_suivi_date"]).astimezone(TZ).date(), weekday=False))} à {esc(fr_hour(parse_iso(r["pic_suivi_date"])))}</td></tr>'
                   for i, r in enumerate(ranked, 1))
    weekly = ""
    if span >= 3:
        now = utc_now()
        fresh = [r for r in recs if r["serie"] and (now - parse_iso(r["pic_suivi_date"])).total_seconds() <= 24 * 3600
                 and (parse_iso(r["pic_suivi_date"]) - parse_iso(r["suivi_depuis"])).total_seconds() >= 3 * 86400]
        fresh.sort(key=lambda r: -r["pic_suivi"])
        items = "".join(f'<li>{icon(r, 28)}{game_link(url, r)} : nouveau record de suivi, {fr_int(r["pic_suivi"])} joueurs</li>' for r in fresh[:10])
        weekly = (f'<section class="rec-new"><h2>Records battus ces dernières 24 heures</h2>'
                  + (f'<ul class="rec-list">{items}</ul>' if items else '<p class="note">Aucun record de suivi battu ces dernières 24 heures.</p>') + "</section>")
    else:
        when = (start + timedelta(days=3)).astimezone(TZ).date() if start else None
        weekly = soon("Records battus", "Pour annoncer un record, il faut au moins trois jours d’historique : sinon, chaque jeu « bat son record » tous les soirs.",
                      fr_date(when, weekday=False) if when else "")
    body = (f'<div class="wide"><h1>Records</h1><p class="lede">Le plus haut nombre de joueurs simultanés relevé pour chaque jeu depuis le début de notre suivi, '
            f'le {esc(fr_date(start.astimezone(TZ).date(), weekday=False)) if start else "—"}. Ce sont des records de suivi, pas des records historiques des jeux.</p>'
            f'{weekly}<h2 class="sec-title">Plus hauts pics relevés</h2><div class="table-wrap sticky-head"><table class="live"><thead><tr><th class="num">#</th><th>Jeu</th>'
            f'<th class="num">Pic relevé</th><th class="hide-s">Quand</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
    return page("Records de joueurs sur Roblox", body, "Les plus hauts pics de joueurs simultanés relevés sur les jeux Roblox, et les records battus.", "records/")


# ------------------------------------------------------------------ studios
def studio_slug(name):
    return slugify(name)[:60] or "studio"


def studios(recs):
    groups = {}
    for r in recs:
        if not r["createur"]:
            continue
        groups.setdefault(r["createur"], []).append(r)
    out = []
    for name, games in groups.items():
        games.sort(key=lambda r: -r["joueurs"])
        out.append({"nom": name, "slug": studio_slug(name), "jeux": games, "joueurs": sum(g["joueurs"] for g in games),
                    "top100": sum(1 for g in games if g["rang"] and g["rang"] <= 100), "verifie": any(g["createur_verifie"] for g in games)})
    out.sort(key=lambda s: -s["joueurs"])
    return out


def studios_pages(recs, page, url):
    st = studios(recs)
    pages = {}
    trs = "".join(f'<tr data-href="{url("studios/" + s["slug"] + "/")}"><td class="num">{i}</td><td class="game"><div class="gcell">{icon(s["jeux"][0], 36)}<div>'
                  f'<a href="{url("studios/" + s["slug"] + "/")}">{esc(s["nom"])}</a><span class="sub">Meilleur jeu : {esc(s["jeux"][0]["nom"])}</span></div></div></td>'
                  f'<td class="num">{fr_int(s["joueurs"])}</td><td class="num hide-s">{s["top100"]}</td><td class="num hide-s">{len(s["jeux"])}</td></tr>'
                  for i, s in enumerate(st[:100], 1))
    body = (f'<div class="wide"><h1>Classement des studios</h1><p class="lede">Les créateurs (groupes et développeurs) dont les jeux réunissent le plus de joueurs '
            f'en ce moment, parmi les jeux que nous suivons.</p><div class="table-wrap sticky-head"><table class="live"><thead><tr><th class="num">#</th><th>Studio</th>'
            f'<th class="num">Joueurs en ligne</th><th class="num hide-s">Jeux dans le top 100</th><th class="num hide-s">Jeux suivis</th></tr></thead>'
            f'<tbody>{trs}</tbody></table></div><p class="note">Le créateur est celui qu’affiche Roblox pour chaque jeu. Un même studio peut publier sous plusieurs noms.</p></div>')
    pages["studios/index.html"] = page("Classement des studios Roblox", body, "Les studios Roblox dont les jeux réunissent le plus de joueurs en ce moment.", "studios/")
    for s in st:
        if s["joueurs"] < 500 and s["top100"] == 0:
            continue
        rows = "".join(f'<tr data-href="{url("jeux/" + g["slug"] + "/")}"><td class="game"><div class="gcell">{icon(g, 36)}<div>{game_link(url, g)}'
                       f'<span class="sub">{esc(g["genre"])}</span></div></div></td><td class="num">{fr_int(g["joueurs"])}</td>'
                       f'<td class="num">{g["rang"] or "—"}</td></tr>' for g in s["jeux"])
        b = (f'<div class="wide"><p class="crumbs"><a href="{url("studios/")}">Studios</a></p><h1>{esc(s["nom"])}</h1>'
             f'<div class="stats"><div class="stat"><span class="stat-label">Joueurs en ligne</span><span class="stat-value">{fr_int(s["joueurs"])}</span></div>'
             f'<div class="stat"><span class="stat-label">Jeux dans le top 100</span><span class="stat-value">{s["top100"]}</span></div>'
             f'<div class="stat"><span class="stat-label">Jeux suivis</span><span class="stat-value">{len(s["jeux"])}</span></div></div>'
             f'<div class="table-wrap"><table class="live"><thead><tr><th>Jeu</th><th class="num">Joueurs en ligne</th><th class="num">Rang</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div></div>')
        noindex = '<meta name="robots" content="noindex">' if s["top100"] == 0 else ""
        pages[f"studios/{s['slug']}/index.html"] = page(f"{s['nom']} : jeux Roblox et joueurs en ligne", b,
                                                        f"Les jeux Roblox de {s['nom']} et leur nombre de joueurs en ligne, mis à jour toutes les heures.",
                                                        f"studios/{s['slug']}/", extra_head=noindex)
    return pages, st


# ------------------------------------------------------------------ genres
def genres_pages(recs, page, url):
    groups = {}
    for r in recs:
        if r["genre"] and r["rang"]:
            groups.setdefault(r["genre"], []).append(r)
    pages, index = {}, []
    for g, games in sorted(groups.items(), key=lambda kv: -sum(x["joueurs"] for x in kv[1])):
        games.sort(key=lambda r: r["rang"])
        sl = slugify(g)
        tot = sum(x["joueurs"] for x in games)
        index.append((g, sl, len(games), tot, games[0]))
        rows = "".join(f'<tr data-href="{url("jeux/" + x["slug"] + "/")}"><td class="num">{i}</td><td class="game"><div class="gcell">{icon(x, 36)}<div>{game_link(url, x)}'
                       f'<span class="sub">{esc(x["createur"])}</span></div></div></td><td class="num">{fr_int(x["joueurs"])}</td><td class="num hide-s">{x["rang"]}</td></tr>'
                       for i, x in enumerate(games[:100], 1))
        b = (f'<div class="wide"><p class="crumbs"><a href="{url("genres/")}">Genres</a></p><h1>Les jeux Roblox de {esc(g.lower())} les plus joués</h1>'
             f'<p class="lede">{len(games)} jeux suivis dans ce genre, {fr_int(tot)} joueurs en ligne au dernier relevé. Genre attribué par Roblox, mis à jour toutes les heures.</p>'
             f'<div class="table-wrap"><table class="live"><thead><tr><th class="num">#</th><th>Jeu</th><th class="num">Joueurs en ligne</th>'
             f'<th class="num hide-s">Rang général</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
        pages[f"genres/{sl}/index.html"] = page(f"Jeux Roblox de {g.lower()} : les plus joués en ce moment", b,
                                               f"Les jeux Roblox de {g.lower()} qui comptent le plus de joueurs en ligne, mis à jour toutes les heures.", f"genres/{sl}/")
    cards = "".join(f'<li class="card"><a href="{url("genres/" + sl + "/")}"><span class="tag">{n} jeux</span><h3>{esc(g)}</h3>'
                    f'<p>{fr_int(tot)} joueurs en ligne. En tête : {esc(top["nom"])}.</p></a></li>' for g, sl, n, tot, top in index)
    pages["genres/index.html"] = page("Genres de jeux Roblox", f'<div class="wide"><h1>Genres</h1><p class="lede">Les jeux suivis, regroupés par genre.</p>'
                                      f'<ol class="cards grid3">{cards}</ol></div>', "Les jeux Roblox les plus joués, genre par genre.", "genres/")
    return pages


# ------------------------------------------------------------------ hub Explorer
EXPLORER_GROUPS = [
    ("temps-reel", "Temps réel", "Ce qui bouge sur Roblox, heure par heure.", [
        ("tendances/", "Tendances", "Ce que Roblox met en avant, et les nouvelles entrées."),
        ("heures-de-pointe/", "Heures de pointe", "À quelle heure jouent les joueurs, jour par jour."),
        ("mises-a-jour/", "Mises à jour détectées", "Les mises à jour des jeux, et ce qui s’est passé après."),
        ("records/", "Records", "Les plus hauts pics relevés et les records battus.")]),
    ("analyser", "Analyser", "Mettre les jeux, les studios et les genres face à face.", [
        ("comparer/", "Comparer deux jeux", "Deux courbes superposées, un lien à partager."),
        ("studios/", "Studios", "Les créateurs qui réunissent le plus de joueurs."),
        ("genres/", "Genres", "Les jeux les plus joués, genre par genre."),
        ("monetisation/", "Monétisation", "Le prix des game passes des jeux du top 100.")]),
    ("donnees", "Données et outils", "Réutiliser nos chiffres, et savoir d’où ils viennent.", [
        ("methode/", "Méthode", "Comment chaque chiffre est relevé, calculé et relié à sa source."),
        ("donnees/", "API et données ouvertes", "Tout en JSON et en CSV, gratuitement."),
        ("widget/", "Widget à intégrer", "Le classement en direct sur votre site, mis à jour toutes les heures."),
        ("feed.xml", "Flux RSS", "Chaque nouvel article dans votre lecteur de flux."),
        ("actus-officielles/", "Actualités officielles", "Annonces aux développeurs et documents financiers de Roblox.")]),
]


def explorer_page(page, url, extra=()):
    groups = ""
    for gid, title, sub, items in EXPLORER_GROUPS:
        cards = "".join(f'<li class="card"><a href="{url(p)}"><h3>{esc(t)}</h3><p>{esc(d)}</p></a></li>' for p, t, d in items)
        groups += (f'<section class="ex-group" aria-labelledby="ex-{gid}"><div class="ex-head"><h2 id="ex-{gid}">{esc(title)}</h2>'
                   f'<p>{esc(sub)}</p></div><ol class="cards grid-ex n{len(items)}">{cards}</ol></section>')
    return page("Explorer les données de Roblox", f'<div class="wide"><h1>Explorer</h1><p class="lede">Tous les outils du Relevé, calculés à partir de nos relevés horaires.</p>'
                f'{groups}</div>', "Tous les outils du Relevé pour explorer les données de Roblox.", "explorer/")


# ------------------------------------------------------------------ monétisation (game passes)
def monetization_page(recs, page, url):
    import pathlib
    from statistics import median
    files = sorted(glob.glob(str(DATA / "passes/*.csv")))
    head = ('<div class="wide"><h1>Monétisation : le prix des game passes</h1><p class="lede">Combien coûtent les game passes des jeux les plus joués ? '
            'Relevé une fois par jour, en Robux, à partir de l’API publique de Roblox. Les passes retirés de la vente ne sont pas comptés dans les prix.</p>')
    if not files:
        return page("Prix des game passes sur Roblox", head + soon("Premier relevé des game passes", "Les prix des passes du top 100 sont relevés une fois par jour. "
                    "Le premier relevé arrive dans les prochaines heures.") + "</div>", "Le prix des game passes des jeux Roblox les plus joués.", "monetisation/")
    rows = read_csv(pathlib.Path(files[-1]))
    day = rows[0]["date"] if rows else ""
    by = {}
    for r in rows:
        by.setdefault(r["universe_id"], []).append(r)
    by_uid = {r["universe_id"]: r for r in recs}
    prices_all = [int(r["prix"]) for r in rows if r["en_vente"] == "1" and r["prix"]]
    games = []
    for uid, ps in by.items():
        pr = [int(p["prix"]) for p in ps if p["en_vente"] == "1" and p["prix"]]
        rec = by_uid.get(uid)
        if rec and pr:
            games.append((rec, len(pr), median(pr), min(pr), max(pr)))
    games.sort(key=lambda x: x[0]["rang"] or 999)
    bands = [(0, 99, "Moins de 100"), (100, 499, "100 à 499"), (500, 999, "500 à 999"), (1000, 4999, "1 000 à 4 999"), (5000, 10**9, "5 000 et plus")]
    band_rows = [{"nom": lab, "valeur": round(sum(1 for p in prices_all if lo <= p <= hi) / len(prices_all), 4)} for lo, hi, lab in bands] if prices_all else []
    chart = charts.bars("prix", {"titre": "Répartition des prix des game passes en vente (Robux)", "unite": "%", "rows": band_rows,
                                 "csv": f"data/passes/{day}.csv"}) if band_rows else ""
    stats = (f'<div class="stats"><div class="stat"><span class="stat-label">Passes en vente relevés</span><span class="stat-value">{fr_int(len(prices_all))}</span></div>'
             f'<div class="stat"><span class="stat-label">Prix médian</span><span class="stat-value">{fr_int(median(prices_all)) if prices_all else "—"} R$</span></div>'
             f'<div class="stat"><span class="stat-label">Jeux avec passes</span><span class="stat-value">{len(games)}</span></div></div>')
    trs = "".join(f'<tr data-href="{url("jeux/" + g.get("slug") + "/")}"><td class="num">{g["rang"]}</td><td class="game"><div class="gcell">{icon(g, 36)}<div>{game_link(url, g)}'
                  f'<span class="sub">{esc(g["genre"])}</span></div></div></td><td class="num">{n}</td><td class="num">{fr_int(med)} R$</td>'
                  f'<td class="num hide-s">{fr_int(lo)} – {fr_int(hi)} R$</td></tr>' for g, n, med, lo, hi in games)
    body = (head + f'<p class="note">Relevé du {esc(fr_date(__import__("datetime").date.fromisoformat(day), weekday=False))}. Source : <a href="{esc(github_tree("data/passes"))}">data/passes</a>.</p>'
            + stats + chart + f'<div class="table-wrap"><table class="live"><thead><tr><th class="num">Rang</th><th>Jeu</th><th class="num">Passes en vente</th>'
            f'<th class="num">Prix médian</th><th class="num hide-s">Fourchette</th></tr></thead><tbody>{trs}</tbody></table></div></div>')
    return page("Prix des game passes sur Roblox", body, "Combien coûtent les game passes des jeux Roblox les plus joués ? Prix médians, fourchettes et répartition.", "monetisation/")


# ------------------------------------------------------------------ actualités officielles
def official_page(page, url):
    ann = read_csv(DATA / "officiel" / "annonces.csv")[:30]
    sec = read_csv(DATA / "officiel" / "sec.csv")[:15]
    def d(s):
        try:
            t = parse_iso(s if s.endswith("Z") else s + "T00:00:00Z")
            return fr_date(t.astimezone(TZ).date(), weekday=False)
        except Exception:
            return s
    a_html = "".join(f'<li><time>{esc(d(a["date"]))}</time><a href="{esc(a["lien"])}" rel="noopener">{esc(a["titre"])}</a></li>' for a in ann)
    s_html = "".join(f'<li><time>{esc(d(s["date"]))}</time><a href="{esc(s["lien"])}" rel="noopener">{esc(s["type"])}'
                     + (f' : {esc(s["description"])}' if s["description"] and s["description"] not in s["type"] else "") + "</a></li>" for s in sec)
    body = ('<div class="narrow"><h1>Actualités officielles</h1><p class="lede">Les annonces de Roblox aux développeurs et les documents déposés par '
            'Roblox Corporation auprès du régulateur boursier américain (SEC). Titres et liens d’origine uniquement, relevés une fois par jour.</p>'
            + (f'<h2 class="sec-title">Annonces aux développeurs</h2><ol class="news">{a_html}</ol>' if a_html else soon("Annonces aux développeurs", "Premier relevé dans les prochaines heures."))
            + (f'<h2 class="sec-title">Documents financiers (SEC)</h2><ol class="news">{s_html}</ol>' if s_html else soon("Documents financiers", "La SEC exige une adresse de contact pour accéder à ses données : ce relevé s’activera dès que l’adresse du média sera renseignée."))
            + '</div>')
    return page("Actualités officielles de Roblox", body, "Les annonces officielles de Roblox aux développeurs et les documents financiers de Roblox Corporation.", "actus-officielles/")
