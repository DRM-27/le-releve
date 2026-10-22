"""Résumés écrits générés à partir des chiffres (pages de jeux, studios, genres) et pages questions-réponses.

Aucune phrase n'invente rien : chaque valeur vient des relevés (rec = explore.game_record) ou des faits officiels/externes.
Les phrases passent par t() : elles sont traduites dans traductions.py.
"""
import html
import json
from datetime import timedelta
from statistics import mean

import i18n
from common import FACTS, TZ, fr_big, fr_date, fr_hour, fr_int, fr_pct, fr_rank, fr_share, parse_iso, utc_now
from i18n import t

esc = html.escape


def _d(iso_s):
    return parse_iso(iso_s).astimezone(TZ).date()


def week_change(rec):
    """Moyenne des 24 dernières heures comparée à la même fenêtre sept jours plus tôt (None si l'historique manque)."""
    pts = [(parse_iso(ts), v) for ts, v in rec["serie"]]
    if not pts:
        return None
    end = pts[-1][0]
    now = [v for ts, v in pts if (end - ts).total_seconds() < 86400]
    before = [v for ts, v in pts if 7 * 86400 <= (end - ts).total_seconds() < 8 * 86400]
    if len(now) < 12 or len(before) < 12 or not mean(before):
        return None
    return mean(now) / mean(before) - 1


def genre_rank(rec, recs):
    if not rec["genre"] or not rec["rang"]:
        return None, 0
    same = sorted((r for r in recs if r["genre"] == rec["genre"] and r["rang"]), key=lambda r: r["rang"])
    pos = next((i for i, r in enumerate(same, 1) if r["universe_id"] == rec["universe_id"]), None)
    return pos, len(same)


def game_sentences(rec, recs):
    s = []
    genre = t(rec["genre"]) if rec["genre"] else ""
    gname = genre.lower() if genre and i18n.CUR not in ("en",) else genre
    if rec["createur"] and rec["cree"] and genre:
        s.append(t("{nom} est un jeu Roblox de {genre} publié par {createur}, créé le {date}.", nom=esc(rec["nom"].strip()), genre=esc(gname),
                   createur=esc(rec["createur"]), date=fr_date(__import__("datetime").date.fromisoformat(rec["cree"]), weekday=False)))
    elif rec["createur"]:
        s.append(t("{nom} est un jeu Roblox publié par {createur}.", nom=esc(rec["nom"].strip()), createur=esc(rec["createur"])))
    if rec["rang"]:
        s.append(t("Au dernier relevé, à {heure}, {n} joueurs y jouaient : c’est le {rang} jeu le plus joué parmi ceux que nous suivons.",
                   heure=fr_hour(parse_iso(rec["releve"])), n=fr_int(rec["joueurs"]), rang=fr_rank(rec["rang"])))
    else:
        s.append(t("Au dernier relevé, à {heure}, {n} joueurs y jouaient.", heure=fr_hour(parse_iso(rec["releve"])), n=fr_int(rec["joueurs"])))
    if rec["pic_24h"] is not None and rec["moyenne_24h"] is not None:
        s.append(t("Sur les dernières 24 heures, il a culminé à {pic} joueurs, pour une moyenne de {moy}.",
                   pic=fr_int(rec["pic_24h"]), moy=fr_int(rec["moyenne_24h"])))
    wc = week_change(rec)
    if wc is not None:
        s.append(t("Sa fréquentation moyenne a varié de {v} par rapport à la même période il y a sept jours.", v=fr_pct(wc)))
    pos, n = genre_rank(rec, recs)
    if pos and n >= 3:
        s.append(t("Dans le genre {genre}, il se classe {rang} sur {n} jeux suivis.", genre=esc(gname), rang=fr_rank(pos), n=n))
    if rec["jours_suivis"] >= 1:
        s.append(t("Son plus haut relevé depuis le début de notre suivi est de {n} joueurs, le {date}.",
                   n=fr_int(rec["pic_suivi"]), date=fr_date(_d(rec["pic_suivi_date"]), weekday=False)))
    if rec["visites"]:
        key = "Le jeu cumule {v} de visites" if rec["visites"] >= 1e6 else "Le jeu cumule {v} visites"
        s.append(t(key, v=fr_big(rec["visites"]))
                 + (t(", avec {p} de votes positifs.", p=fr_share(rec["note"])) if rec["note"] is not None else "."))
    return s


def game_summary_html(rec, recs):
    s = game_sentences(rec, recs)
    return f'<section class="resume" aria-label="{t("En bref")}"><h2>{t("En bref")}</h2><p>{" ".join(s)}</p></section>'


def game_faq(rec):
    """Questions-réponses pour les données structurées (FAQPage) de la page d'un jeu."""
    q1 = t("Combien de joueurs sur {nom} en ce moment ?", nom=rec["nom"])
    a1 = t("Au dernier relevé, à {heure}, {n} joueurs étaient en ligne sur {nom}.", heure=fr_hour(parse_iso(rec["releve"])), n=fr_int(rec["joueurs"]), nom=rec["nom"])
    out = [(q1, a1)]
    if rec["jours_suivis"] >= 1:
        out.append((t("Quel est le record de joueurs de {nom} ?", nom=rec["nom"]),
                    t("Depuis le début de notre suivi, le plus haut relevé de {nom} est de {n} joueurs simultanés, le {date}.",
                      nom=rec["nom"], n=fr_int(rec["pic_suivi"]), date=fr_date(_d(rec["pic_suivi_date"]), weekday=False))))
    return out


def faq_ld(pairs):
    return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs]}


def faq_html(pairs):
    return (f'<section class="faq"><h2>{t("Questions fréquentes")}</h2>'
            + "".join(f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in pairs) + "</section>")


# ------------------------------------------------------------------ studios et genres
def studio_summary_html(s):
    top = s["jeux"][0]
    if len(s["jeux"]) == 1:
        txt = t("{nom} publie un des jeux que nous suivons, {jeu}, qui réunissait {j} joueurs en ligne au dernier relevé.",
                nom=esc(s["nom"].strip()), jeu=esc(top["nom"].strip()), j=fr_int(top["joueurs"]))
        if s["top100"]:
            txt += " " + t("Ce jeu figure dans le top 100.")
    else:
        txt = t("{nom} publie {n} jeux parmi ceux que nous suivons, qui réunissaient {j} joueurs en ligne au dernier relevé.", nom=esc(s["nom"].strip()), n=len(s["jeux"]), j=fr_int(s["joueurs"]))
        txt += " " + t("Son jeu le plus joué est {jeu}, avec {j} joueurs.", jeu=esc(top["nom"].strip()), j=fr_int(top["joueurs"]))
        if s["top100"] == 1:
            txt += " " + t("Un de ses jeux figure dans le top 100.")
        elif s["top100"]:
            txt += " " + t("{n} de ses jeux figurent dans le top 100.", n=s["top100"])
    return f'<section class="resume"><h2>{t("En bref")}</h2><p>{txt}</p></section>'


def genre_summary_html(genre_label, games, recs):
    tot = sum(x["joueurs"] for x in games)
    top100 = [r for r in recs if r["rang"] and r["rang"] <= 100]
    t100 = sum(r["joueurs"] for r in top100) or 1
    in100 = [r for r in games if r["rang"] <= 100]
    txt = t("Nous suivons {n} jeux de {genre}, qui réunissaient {j} joueurs en ligne au dernier relevé.", n=len(games), genre=esc(genre_label), j=fr_int(tot))
    if len(in100) == 1:
        txt += " " + t("Un seul est dans le top 100, où il pèse {p} des joueurs.", p=fr_share(in100[0]["joueurs"] / t100))
    elif in100:
        txt += " " + t("{n} d’entre eux sont dans le top 100, où ils pèsent {p} des joueurs.", n=len(in100), p=fr_share(sum(r["joueurs"] for r in in100) / t100))
    txt += " " + t("Le plus joué est {jeu} ({j} joueurs, {rang} au classement général).", jeu=esc(games[0]["nom"].strip()), j=fr_int(games[0]["joueurs"]), rang=fr_rank(games[0]["rang"]))
    return f'<section class="resume"><h2>{t("En bref")}</h2><p>{txt}</p></section>'


# ------------------------------------------------------------------ pages questions-réponses
def _facts(name):
    p = FACTS / f"{name}.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    return d.get("faits", d)


def _fact_link(f, shown, github_blob):
    src = f.get("src", "")
    href = src if src.startswith("http") else github_blob(src.split("#")[0])
    return f'<a class="fait" href="{esc(href)}" data-fact="{esc(f["l"])}" data-where="{esc(src)}">{esc(shown)}</a>'


def players_now_page(page, url, recs, latest_ts, loc_fact, github_blob, charts):
    """« Combien de joueurs sur Roblox en ce moment ? »"""
    live = [r for r in recs if r["serie"] and parse_iso(r["releve"]) == latest_ts]
    live.sort(key=lambda r: -r["joueurs"])
    tot_all = sum(r["joueurs"] for r in live)
    top100 = live[:100]
    tot100 = sum(r["joueurs"] for r in top100)
    when = f'{fr_date(latest_ts.astimezone(TZ).date(), weekday=False)}, {fr_hour(latest_ts)}'
    off, ext = _facts("officiel"), _facts("externe")
    dau = off.get("officiel.t2-2026.dau")
    rec = ext.get("ext.roblox.ccu_aout25")
    # courbe : total du top 100 à chaque relevé des 7 derniers jours
    by_ts = {}
    for r in recs:
        for ts, v in r["serie"]:
            by_ts.setdefault(ts, []).append(v)
    cutoff = latest_ts - timedelta(days=7)
    series = [[ts, sum(sorted(vs, reverse=True)[:100])] for ts, vs in sorted(by_ts.items()) if parse_iso(ts) >= cutoff]
    chart = charts.line("total", {"titre": t("Joueurs en ligne sur les 100 jeux les plus joués"), "unite": t("joueurs"), "points": series,
                                  "csv": "data/snapshots", "note": t("Un point par relevé horaire, heure de Paris.")}, height=260) if len(series) > 1 else ""
    answer = t("Au relevé du {quand}, les {n} jeux Roblox que nous suivons comptaient {tot} joueurs en ligne, dont {t100} sur les 100 plus joués.",
               quand=when, n=fr_int(len(live)), tot=f"<strong>{fr_int(tot_all)}</strong>", t100=fr_int(tot100))
    ctx = []
    if dau:
        ctx.append(t("Roblox Corporation déclare {dau} d’utilisateurs actifs par jour en moyenne au deuxième trimestre 2026 : c’est le chiffre officiel le plus récent sur l’audience de la plateforme.",
                     dau=_fact_link(dau, loc_fact("officiel.t2-2026.dau", dau), github_blob)))
    if rec:
        ctx.append(t("Le record de joueurs connectés en même temps sur Roblox est de {n}, atteint le 23 août 2025.",
                     n=_fact_link(rec, loc_fact("ext.roblox.ccu_aout25", rec), github_blob)))
    ctx.append(t("Roblox ne publie pas en temps réel le nombre total de joueurs connectés : notre total ne couvre que les jeux que nous suivons, soit ceux qui sont passés par les classements de la page Découvrir ces deux dernières semaines."))
    top5 = "".join(f'<li><a href="{url("jeux/" + r["slug"] + "/")}">{esc(r["nom"])}</a> : {fr_int(r["joueurs"])} {t("joueurs")}</li>' for r in top100[:5])
    pairs = [(t("Combien de joueurs sur Roblox en ce moment ?"), re_text(answer)),
             (t("Combien d’utilisateurs actifs Roblox compte-t-il par jour ?"), re_text(ctx[0]) if dau else ""),
             (t("Quel est le record de joueurs simultanés sur Roblox ?"), re_text(ctx[1]) if dau and rec else "")]
    pairs = [(q, a) for q, a in pairs if a]
    body = (f'<div class="narrow qa"><p class="kicker">{t("Mis à jour toutes les heures")}</p><h1>{t("Combien de joueurs sur Roblox en ce moment ?")}</h1>'
            f'<div class="answer">{answer}</div>{chart}'
            f'<h2>{t("Les jeux les plus joués en ce moment")}</h2><ol class="qa-list">{top5}</ol><p><a href="{url("classement/")}">{t("Voir le classement complet")}</a></p>'
            f'<h2>{t("Pour situer ce chiffre")}</h2>' + "".join(f"<p>{c}</p>" for c in ctx)
            + faq_html(pairs) + "</div>")
    ld = {"@context": "https://schema.org", **faq_ld(pairs)}
    return page(t("Combien de joueurs sur Roblox en ce moment ?"), body,
                t("Le nombre de joueurs en ligne sur les jeux Roblox, relevé toutes les heures, avec les chiffres officiels et le record de la plateforme."),
                "joueurs-roblox-en-ce-moment/", ld=ld)


def most_played_page(page, url, recs, latest_ts):
    """« Quels sont les jeux Roblox les plus joués ? » : maintenant et en moyenne sur 7 jours."""
    live = sorted([r for r in recs if r["rang"]], key=lambda r: r["rang"])
    cutoff = latest_ts - timedelta(days=7)
    avg7 = []
    for r in recs:
        vals = [v for ts, v in r["serie"] if parse_iso(ts) >= cutoff]
        if len(vals) >= 24:
            avg7.append((mean(vals), r))
    avg7.sort(key=lambda x: -x[0])
    days = min(7, max(1, round((latest_ts - min((parse_iso(r["suivi_depuis"]) for r in recs), default=latest_ts)).total_seconds() / 86400)))
    now_rows = "".join(f'<tr data-href="{url("jeux/" + r["slug"] + "/")}"><td class="num">{r["rang"]}</td><td class="game"><a href="{url("jeux/" + r["slug"] + "/")}">{esc(r["nom"])}</a>'
                       f'<span class="sub">{esc(r["createur"])}</span></td><td class="num">{fr_int(r["joueurs"])}</td></tr>' for r in live[:20])
    avg_rows = "".join(f'<tr data-href="{url("jeux/" + r["slug"] + "/")}"><td class="num">{i}</td><td class="game"><a href="{url("jeux/" + r["slug"] + "/")}">{esc(r["nom"])}</a>'
                       f'<span class="sub">{esc(r["createur"])}</span></td><td class="num">{fr_int(round(v))}</td></tr>' for i, (v, r) in enumerate(avg7[:20], 1))
    n1 = live[0] if live else None
    answer = (t("Au relevé de {heure}, le jeu Roblox le plus joué était {jeu}, avec {n} joueurs en ligne, devant {j2} et {j3}.",
                heure=fr_hour(latest_ts), jeu=f"<strong>{esc(n1['nom'])}</strong>", n=fr_int(n1["joueurs"]), j2=esc(live[1]["nom"]), j3=esc(live[2]["nom"]))
              if len(live) >= 3 else "")
    if avg7:
        answer += " " + t("En moyenne sur les {d} derniers jours, c’est {jeu} qui réunit le plus de joueurs ({n} en moyenne).", d=days, jeu=esc(avg7[0][1]["nom"]), n=fr_int(round(avg7[0][0])))
    pairs = [(t("Quel est le jeu le plus joué sur Roblox en ce moment ?"), re_text(answer))] if answer else []
    th = f'<thead><tr><th class="num">#</th><th>{t("Jeu")}</th><th class="num">{t("Joueurs")}</th></tr></thead>'
    body = (f'<div class="wide qa"><p class="kicker">{t("Mis à jour toutes les heures")}</p><h1>{t("Les jeux Roblox les plus joués")}</h1>'
            f'<div class="answer">{answer}</div>'
            f'<div class="{"qa-two" if avg_rows else "qa-one"}"><section><h2>{t("En ce moment")}</h2><div class="table-wrap"><table class="live">{th}<tbody>{now_rows}</tbody></table></div></section>'
            + (f'<section><h2>{t("En moyenne sur {d} jours", d=days)}</h2><div class="table-wrap"><table class="live">{th}<tbody>{avg_rows}</tbody></table></div></section>' if avg_rows else "")
            + f'</div><p class="note">{t("Moyenne des relevés horaires de chaque jeu sur la période. Jeux sponsorisés exclus.")} <a href="{url("methode/")}">{t("Méthode")}</a></p>'
            + faq_html(pairs) + "</div>")
    ld = {"@context": "https://schema.org", **faq_ld(pairs)} if pairs else None
    return page(t("Les jeux Roblox les plus joués aujourd’hui et cette semaine"), body,
                t("Le classement des jeux Roblox les plus joués en ce moment et en moyenne sur la semaine, mis à jour toutes les heures."),
                "jeux-roblox-les-plus-joues/", ld=ld)


def re_text(h):
    import re
    return html.unescape(re.sub(r"<[^>]+>", "", h))
