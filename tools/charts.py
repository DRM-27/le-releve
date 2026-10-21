"""Graphiques en HTML + SVG, sans dépendance. Le texte reste en HTML (lisible sur mobile), les tracés en SVG.

Chaque graphique a : un titre, une note de source, une vue tableau et un lien vers le CSV des données tracées.
"""
import html
import json
from datetime import timedelta

from common import TZ, fr_dec, fr_int, fr_pct, fr_share, github_blob, parse_iso, NNBSP

esc = html.escape


def compact(n):
    a = abs(n)
    if a >= 1e6:
        return f"{fr_dec(n / 1e6, 1).replace(',0', '')}{NNBSP}M"
    if a >= 1e3:
        return f"{fr_dec(n / 1e3, 0)}{NNBSP}k"
    return fr_int(n)


def nice_ticks(vmax, n=4):
    if vmax <= 0:
        return [0, 1]
    raw = vmax / n
    mag = 10 ** len(str(int(raw))) / 10
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    top = step * (int(vmax / step) + (1 if vmax % step else 0))
    return [step * i for i in range(int(round(top / step)) + 1)]


def frame(gid, title, body, csv, table, note="", source="Relevés horaires des API publiques de Roblox"):
    return (f'<figure class="chart" id="graphique-{esc(gid)}">'
            f'<figcaption><span class="chart-title">{esc(title)}</span>'
            f'{f"<span class=chart-note>{esc(note)}</span>" if note else ""}</figcaption>'
            f'{body}'
            f'<div class="chart-foot"><span>Source : {esc(source)}.</span> '
            f'<a href="{esc(github_blob(csv))}">Données du graphique (CSV)</a></div>'
            f'<details class="chart-table"><summary>Voir les valeurs</summary>{table}</details>'
            f'</figure>')


def bars(gid, g):
    rows = g["rows"]
    vmax = max(r["valeur"] for r in rows) or 1
    items = []
    for r in rows:
        w = r["valeur"] / vmax * 100
        val = fr_share(r["valeur"]) if g.get("unite") == "%" else fr_int(r["valeur"])
        items.append(f'<li class="bar-row" data-tip="{esc(r["nom"])} : {val}{"" if g.get("unite") == "%" else " " + esc(g["unite"])}">'
                     f'<span class="bar-label">{esc(r["nom"])}</span>'
                     f'<span class="bar-track"><span class="bar" style="width:{w:.2f}%"></span>'
                     f'<span class="bar-value">{val}</span></span></li>')
    table = "<table><thead><tr><th>Jeu</th><th>Joueurs</th></tr></thead><tbody>" + "".join(
        f"<tr><td>{esc(r['nom'])}</td><td class=num>{fr_share(r['valeur']) if g.get('unite') == '%' else fr_int(r['valeur'])}</td></tr>" for r in rows) + "</tbody></table>"
    return frame(gid, g["titre"], f'<ol class="bars">{"".join(items)}</ol>', g["csv"], table)


def diverging(gid, g):
    rows = g["rows"]
    vmax = max(abs(r["valeur"]) for r in rows) or 1
    items = []
    for r in rows:
        v = r["valeur"]
        w = abs(v) / vmax * 32
        side = "pos" if v >= 0 else "neg"
        items.append(f'<li class="div-row {side}" data-tip="{esc(r["nom"])} : {fr_pct(v)}">'
                     f'<span class="bar-label">{esc(r["nom"])}</span>'
                     f'<span class="div-track"><span class="bar" style="width:{w:.2f}%"></span>'
                     f'<span class="bar-value" style="--w:{w:.2f}%">{fr_pct(v)}</span></span></li>')
    note = f"Moyenne de joueurs du jour comparée à {g.get('reference', 'la période précédente')}."
    table = "<table><thead><tr><th>Jeu</th><th>Variation</th></tr></thead><tbody>" + "".join(
        f"<tr><td>{esc(r['nom'])}</td><td class=num>{fr_pct(r['valeur'])}</td></tr>" for r in rows) + "</tbody></table>"
    return frame(gid, g["titre"], f'<ol class="diverging">{"".join(items)}</ol>', g["csv"], table, note)


def line(gid, g, height=260):
    pts = [(parse_iso(t), v) for t, v in g["points"]]
    if len(pts) < 2:
        return ""
    t0, t1 = pts[0][0], pts[-1][0]
    span = (t1 - t0).total_seconds() or 1
    ticks = nice_ticks(max(v for _, v in pts))
    top = ticks[-1]
    W, H = 1000, 300

    def xy(t, v):
        return (t - t0).total_seconds() / span * W, H - v / top * H

    # coupe la ligne quand il manque plus de 2 relevés d'affilée
    segs, cur, prev = [], [], None
    for t, v in pts:
        if prev and (t - prev).total_seconds() > 3 * 3600:
            segs.append(cur)
            cur = []
        cur.append(xy(t, v))
        prev = t
    segs.append(cur)
    d_line = " ".join("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in s) for s in segs if s)
    d_area = " ".join(f"M{s[0][0]:.1f},{H} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in s) + f" L{s[-1][0]:.1f},{H} Z"
                      for s in segs if len(s) > 1)
    grid = "".join(f'<div class="ytick" style="bottom:{v / top * 100:.2f}%"><span>{compact(v)}</span></div>' for v in ticks)
    # repères de jours (minuit à Paris)
    days, d = [], t0.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    while d < t1:
        left = (d - t0).total_seconds() / span * 100
        days.append(f'<div class="xtick" style="left:{left:.2f}%"><span>{d.day}/{d.month:02d}</span></div>')
        d += timedelta(days=1)
    lx, ly = xy(*pts[-1])
    data = json.dumps([[int(t.timestamp()), v] for t, v in pts], separators=(",", ":"))
    body = (f'<div class="line-plot" style="height:{height}px" data-points=\'{data}\' data-unit="{esc(g["unite"])}">'
            f'{grid}{"".join(days)}'
            f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
            f'<path class="area" d="{d_area}"/><path class="stroke" d="{d_line}" vector-effect="non-scaling-stroke"/></svg>'
            f'<span class="end-dot" style="left:{lx / W * 100:.2f}%;top:{ly / H * 100:.2f}%"></span>'
            f'<span class="end-label" style="top:{ly / H * 100:.2f}%">{fr_int(pts[-1][1])}</span>'
            f'<div class="crosshair" hidden><span class="tip"></span></div></div>')
    # vue tableau : maximum, minimum et moyenne par jour
    byday = {}
    for t, v in pts:
        byday.setdefault(t.astimezone(TZ).date(), []).append(v)
    table = ("<table><thead><tr><th>Jour</th><th>Max.</th><th>Min.</th><th>Relevés</th></tr></thead><tbody>" +
             "".join(f"<tr><td>{k.day}/{k.month:02d}</td><td class=num>{fr_int(max(v))}</td><td class=num>{fr_int(min(v))}</td>"
                     f"<td class=num>{len(v)}</td></tr>" for k, v in sorted(byday.items())) + "</tbody></table>")
    return frame(gid, g["titre"], body, g["csv"], table, g.get("note", "Heure de Paris. Un point par relevé horaire."))


def render(gid, g):
    if g.get("source"):
        pass
    if gid == "variations":
        return diverging(gid, g)
    if "rows" in g:
        return bars(gid, g)
    return line(gid, g)


def sparkline(values, w=120, h=28, trend=None):
    if len(values) < 2:
        return ""
    vmax = max(values) or 1
    vmin = min(values)
    rng = (vmax - vmin) or 1
    step = w / (len(values) - 1)
    xy = [(i * step, h - 2 - (v - vmin) / rng * (h - 4)) for i, v in enumerate(values)]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    trend = trend or ("down" if values[-1] < values[0] else "up")
    gid = f"sg{abs(hash(pts)) % 10**8}"
    return (f'<svg class="spark {trend}" viewBox="0 0 {w} {h}" width="{w}" height="{h}" preserveAspectRatio="none" aria-hidden="true">'
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".28"/>'
            f'<stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="0,{h} {pts} {w},{h}" fill="url(#{gid})"/>'
            f'<polyline points="{pts}" vector-effect="non-scaling-stroke"/></svg>')
