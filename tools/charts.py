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


def nice_range(vmin, vmax, n=4):
    """Bornes « rondes » autour des données (axe non nul : courbe de série temporelle, pas des barres)."""
    if vmax <= vmin:
        vmax, vmin = vmax + max(1, abs(vmax) * .05), max(0, vmin - max(1, abs(vmin) * .05))
    pad = (vmax - vmin) * .12
    lo, hi = max(0, vmin - pad), vmax + pad
    raw = (hi - lo) / n
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    step = mag
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    lo = step * int(lo // step)
    hi = step * (int(hi // step) + (1 if hi % step else 0))
    return [lo + step * i for i in range(int(round((hi - lo) / step)) + 1)]


def smooth_path(pts):
    """Courbe monotone (Fritsch-Carlson) : lisse sans dépasser les valeurs relevées."""
    n = len(pts)
    if n < 3:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    dx = [pts[i + 1][0] - pts[i][0] or 1e-6 for i in range(n - 1)]
    sl = [(pts[i + 1][1] - pts[i][1]) / dx[i] for i in range(n - 1)]
    m = [sl[0]] + [0 if sl[i - 1] * sl[i] <= 0 else (sl[i - 1] + sl[i]) / 2 for i in range(1, n - 1)] + [sl[-1]]
    for i in range(n - 1):
        if sl[i] == 0:
            m[i] = m[i + 1] = 0
            continue
        a, b = m[i] / sl[i], m[i + 1] / sl[i]
        h = a * a + b * b
        if h > 9:
            t = 3 / h ** .5
            m[i], m[i + 1] = t * a * sl[i], t * b * sl[i]
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(n - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        d += (f" C{x0 + dx[i] / 3:.1f},{y0 + m[i] * dx[i] / 3:.1f} {x1 - dx[i] / 3:.1f},{y1 - m[i + 1] * dx[i] / 3:.1f} {x1:.1f},{y1:.1f}")
    return d


def line(gid, g, height=260):
    pts = [(parse_iso(t), v) for t, v in g["points"]]
    if len(pts) < 2:
        return ""
    t0, t1 = pts[0][0], pts[-1][0]
    span = (t1 - t0).total_seconds() or 1
    vals = [v for _, v in pts]
    ticks = nice_range(min(vals), max(vals))
    lo, hi = ticks[0], ticks[-1]
    W, H = 1000, 300
    trend = "down" if vals[-1] < vals[0] else "up"

    def xy(t, v):
        return (t - t0).total_seconds() / span * W, H - (v - lo) / (hi - lo) * H

    segs, cur, prev = [], [], None
    for t, v in pts:
        if prev and (t - prev).total_seconds() > 3 * 3600:
            segs.append(cur)
            cur = []
        cur.append(xy(t, v))
        prev = t
    segs.append(cur)
    d_line = " ".join(smooth_path(s) for s in segs if s)
    d_area = " ".join(smooth_path(s) + f" L{s[-1][0]:.1f},{H} L{s[0][0]:.1f},{H} Z" for s in segs if len(s) > 1)
    grid = "".join(f'<div class="ytick" style="bottom:{(v - lo) / (hi - lo) * 100:.2f}%"><span>{compact(v)}</span></div>' for v in ticks)
    days, d = [], t0.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    while d < t1:
        left = (d - t0).total_seconds() / span * 100
        days.append(f'<div class="xtick day" style="left:{left:.2f}%"><span>{d.day}/{d.month:02d}</span></div>')
        d += timedelta(days=1)
    lx, ly = xy(*pts[-1])
    ip = max(range(len(pts)), key=lambda i: vals[i])
    px, py = xy(*pts[ip])
    peak = (f'<span class="peak" style="left:{px / W * 100:.2f}%;top:{py / H * 100:.2f}%"><i></i><b>Pic {fr_int(vals[ip])}</b></span>'
            if ip != len(pts) - 1 else "")
    data = json.dumps([[int(t.timestamp()), v] for t, v in pts], separators=(",", ":"))
    gidc = f"lg-{esc(gid)}"
    body = (f'<div class="line-head" hidden></div>'
            f'<div class="line-plot {trend}" style="height:{height}px;--plot-h:{height}px" data-points=\'{data}\' data-unit="{esc(g["unite"])}">'
            f'{grid}{"".join(days)}'
            f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="{gidc}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="currentColor" stop-opacity=".35"/><stop offset=".7" stop-color="currentColor" stop-opacity=".06"/>'
            f'<stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>'
            f'<path class="area" d="{d_area}" style="fill:url(#{gidc})"/><path class="stroke" d="{d_line}" vector-effect="non-scaling-stroke"/></svg>'
            f'{peak}<span class="end-dot" style="left:{lx / W * 100:.2f}%;top:{ly / H * 100:.2f}%"></span>'
            f'<span class="end-label" style="top:{ly / H * 100:.2f}%">{compact(vals[-1])}</span>'
            f'<div class="crosshair" hidden><span class="hline"></span><span class="cdot"></span><span class="tip"></span></div></div>')
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
