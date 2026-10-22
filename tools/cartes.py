"""Cartes à partager (1080 × 1350, format portrait LinkedIn / Instagram), régénérées à chaque construction.

Les chiffres viennent de rapport.collect() : mêmes calculs, mêmes sources que le rapport mensuel.
Usage : python tools/cartes.py [dossier]   (par défaut out/cartes)
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageDraw

import og
from common import DATA, ROOT, TZ, fr_big, fr_date, fr_hour, fr_int, fr_pct, fr_share
from og import BLUE, GREEN, INK, MUTED, RED, font, get_icon, wrap

W, H = 1080, 1350
BG, PANEL, LINE, AMBER = "#0b0e14", "#121924", "#1f2a3b", "#f59e0b"
M = 72


def clean(name):
    """Retire les émojis (absents de la police) et les crochets vidés qu'ils laissent."""
    import re
    t = "".join(ch for ch in name if ord(ch) < 0x2000 or 0x2010 <= ord(ch) <= 0x206F or 0x20A0 <= ord(ch) <= 0x20CF)
    t = re.sub(r"\[\s*\]|\(\s*\)", "", t)
    return re.sub(r"\s+", " ", t).strip(" -|·") or name


def canvas(kicker, title):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for x in range(0, W, 45):
        d.line([(x, 0), (x, H)], fill="#0e141e")
    for y in range(0, H, 45):
        d.line([(0, y), (W, y)], fill="#0e141e")
    # halo bleu en haut à droite
    glow = Image.new("RGB", (W, H), BG)
    gd = ImageDraw.Draw(glow)
    for r, c in ((520, "#0f1a2e"), (380, "#11203a"), (240, "#132546")):
        gd.ellipse((W - r, -r, W + r, r), fill=c)
    im = Image.blend(im, glow, .55)
    d = ImageDraw.Draw(im)
    for i, h in enumerate((16, 34, 25)):
        d.rounded_rectangle((M + i * 13, 98 - h, M + 9 + i * 13, 98), radius=2, fill=BLUE)
    d.text((M + 52, 64), "PlayLedger", font=font(34, "ExtraBold"), fill=INK)
    d.text((W - M, 72), "Données Roblox vérifiables", font=font(22, "Medium"), fill=MUTED, anchor="ra")
    d.text((M, 170), kicker.upper(), font=font(24, "Bold"), fill="#60a5fa")
    y = 210
    for line in wrap(d, title, font(64, "ExtraBold"), W - 2 * M, 3):
        d.text((M, y), line, font=font(64, "ExtraBold"), fill=INK)
        y += 74
    return im, d, y + 36


def foot(d, D, source):
    when = D["ts"]
    d.line([(M, H - 120), (W - M, H - 120)], fill=LINE, width=2)
    d.text((M, H - 98), f"Source : {source}", font=font(22, "Medium"), fill=MUTED)
    d.text((M, H - 64), f"Relevé du {fr_date(when.astimezone(TZ).date(), weekday=False)} à {fr_hour(when)} (Paris). Chaque chiffre sourcé sur PlayLedger.",
           font=font(22, "Medium"), fill="#64748b")


def hbars(im, d, y, rows, color, fmt, label_w=360, icons=None, row_h=78, bar_h=30):
    vmax = max(r[1] for r in rows) or 1
    for i, (name, v) in enumerate(rows):
        yy = y + i * row_h
        x = M
        if icons:
            ic = icons[i]
            if ic:
                im.paste(ic, (M, yy - 6), ic)
            x = M + 62
        name = clean(name)
        lines = wrap(d, name, font(26, "Bold"), label_w - (x - M) - 10, 1)
        d.text((x, yy), lines[0], font=font(26, "Bold"), fill=INK)
        bx0 = M + label_w
        bw = (W - M - 150 - bx0) * v / vmax
        d.rounded_rectangle((bx0, yy + 2, bx0 + max(bw, 6), yy + 2 + bar_h), radius=6, fill=color)
        d.text((bx0 + max(bw, 6) + 14, yy - 1), fmt(v), font=font(28, "ExtraBold"), fill=INK)
    return y + len(rows) * row_h


def big(d, y, value, label, color=INK):
    d.text((M, y), value, font=font(170, "ExtraBold"), fill=color)
    y += 200
    for line in wrap(d, label, font(38, "Medium"), W - 2 * M, 3):
        d.text((M, y), line, font=font(38, "Medium"), fill="#cbd5e1")
        y += 50
    return y + 30


def make(D, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    T = D["top"]
    made = []

    # 1. top 10
    im, d, y = canvas("Classement en direct", "Les 10 jeux les plus joués sur Roblox en ce moment")
    icons = [get_icon(x["icon"], 48) for x in T[:10]]
    hbars(im, d, y + 10, [(x["nom"], x["joueurs"]) for x in T[:10]], BLUE, fr_int, label_w=430, icons=icons, row_h=84, bar_h=34)
    foot(d, D, "API publiques de Roblox, joueurs en ligne")
    im.save(out / "top10.png", optimize=True)
    made.append(("top10.png", "Les 10 jeux les plus joués"))

    # 2. concentration
    im, d, y = canvas("Concentration", "Sur Roblox, l’audience se joue sur une poignée de jeux")
    y = big(d, y + 10, fr_share(D["part_top10"]), f"des joueurs du top 100 sont sur les 10 premiers jeux. Le n° 1, {clean(T[0]['nom'])}, en réunit à lui seul {fr_share(T[0]['part'])}.", "#60a5fa")
    hbars(im, d, y, [("N° 1", T[0]["part"]), ("Top 10", D["part_top10"]), ("5 premiers studios", D["part_top5_studios"])], BLUE, fr_share, label_w=330, row_h=96, bar_h=40)
    foot(d, D, "API publiques de Roblox, top 100 par joueurs en ligne")
    im.save(out / "concentration.png", optimize=True)
    made.append(("concentration.png", "Concentration de l’audience"))

    # 3. genres
    g1 = D["genres"][0]
    im, d, y = canvas("Genres", f"{g1['nom']} : le genre qui capte le plus de joueurs sur Roblox")
    hbars(im, d, y + 10, [(g["nom"], g["part"]) for g in D["genres"][:8]], GREEN, fr_share, label_w=400, row_h=96, bar_h=40)
    foot(d, D, "API publiques de Roblox, genres déclarés par les créateurs")
    im.save(out / "genres.png", optimize=True)
    made.append(("genres.png", "Part des joueurs par genre"))

    # 4. jeux récents
    im, d, y = canvas("Renouvellement", "Les nouveaux jeux s’imposent vite sur Roblox")
    y = big(d, y + 10, fr_share(D["recents"]["part"]), f"des joueurs du top 100 sont sur des jeux créés il y a moins de 90 jours ({D['recents']['jeux']} jeux).", GREEN)
    hbars(im, d, y, [(c["nom"], c["part"]) for c in D["cohortes"]], GREEN, fr_share, label_w=330, row_h=92, bar_h=40)
    foot(d, D, "API publiques de Roblox, date de création des jeux")
    im.save(out / "renouvellement.png", optimize=True)
    made.append(("renouvellement.png", "Part des jeux récents"))

    # 5. game passes
    if D["passes"]:
        P = D["passes"]
        im, d, y = canvas("Monétisation", "Combien coûte un game pass sur Roblox ?")
        y = big(d, y + 10, f"{fr_int(P['mediane'])} R$", f"prix médian des {fr_int(P['n'])} game passes en vente sur les jeux du top 100.", AMBER)
        hbars(im, d, y, [(b["nom"], b["part"]) for b in P["bands"]], AMBER, fr_share, label_w=330, row_h=80, bar_h=36)
        foot(d, D, "API publique des game passes de Roblox")
        im.save(out / "game-passes.png", optimize=True)
        made.append(("game-passes.png", "Prix des game passes"))

    # 6. Roblox Corporation
    off = D["off"]
    if off.get("officiel.t2-2026.revenus"):
        im, d, y = canvas("Roblox Corporation", "Roblox au deuxième trimestre 2026, en six chiffres")
        cells = [("Chiffre d’affaires", "revenus"), ("Utilisateurs actifs / jour", "dau"), ("Bookings", "bookings"),
                 ("Heures d’engagement", "heures"), ("Payeurs uniques / mois", "payeurs_mensuels"), ("Reversé aux créateurs", "devex")]
        cw, ch = (W - 2 * M - 24) // 2, 232
        for i, (lab, k) in enumerate(cells):
            x0, y0 = M + (i % 2) * (cw + 24), y + 10 + (i // 2) * (ch + 22)
            d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=18, fill=PANEL, outline=LINE, width=2)
            d.text((x0 + 26, y0 + 24), lab, font=font(24, "Medium"), fill=MUTED)
            val = off.get(f"officiel.t2-2026.{k}", {}).get("d", "—")
            vl = wrap(d, val, font(40, "ExtraBold"), cw - 52, 2)
            for j, l in enumerate(vl):
                d.text((x0 + 26, y0 + 60 + j * 46), l, font=font(40, "ExtraBold"), fill=INK)
            cr = off.get(f"officiel.t2-2026.{k.replace('_mensuels', '')}_croissance", {}).get("d")
            if cr:
                d.text((x0 + 26, y0 + ch - 46), f"{cr} sur un an", font=font(24, "Bold"), fill=GREEN if not cr.startswith("−") else RED)
        foot(d, D, "communiqué de résultats de Roblox Corporation (SEC, 30/07/2026)")
        im.save(out / "roblox-t2-2026.png", optimize=True)
        made.append(("roblox-t2-2026.png", "Roblox Corporation, T2 2026"))
    return made


def latest_month():
    last = sorted(glob.glob(str(DATA / "snapshots" / "*" / "*" / "*" / "*.csv")))[-1]
    p = Path(last).parts
    return int(p[-4]), int(p[-3])


if __name__ == "__main__":
    import rapport
    y, m = latest_month()
    D = rapport.collect(y, m)
    for f, t in make(D, sys.argv[1] if len(sys.argv) > 1 else ROOT / "out" / "cartes"):
        print(f, t)
