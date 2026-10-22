"""Images de partage (Open Graph, 1200 × 630) et badges SVG « Classé sur PlayLedger ».

Les images sont générées à chaque construction, sans être archivées dans le dépôt. Les icônes des jeux sont
téléchargées depuis le CDN de Roblox et gardées en cache ; si le téléchargement échoue, l'image se passe d'icône.
"""
import hashlib
import io
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = str(Path(__file__).resolve().parent / "og" / "SchibstedGrotesk.ttf")
CACHE = Path(os.environ.get("OG_CACHE", Path.home() / ".cache" / "releve-icons"))
W, H = 1200, 630
BG, CARD, RULE, INK, MUTED, BLUE, GREEN, RED = "#0b0e14", "#151d2a", "#222f43", "#f8fafc", "#94a3b8", "#3b82f6", "#10b981", "#ef4444"


def font(size, weight="Bold"):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def get_icon(url, size):
    if not url:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".png")
    if not p.exists():
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "PlayLedgerBot/1.0"}), timeout=6) as r:
                p.write_bytes(r.read())
        except Exception:
            return None
    try:
        im = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        return None
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=255)
    im.putalpha(mask)
    return im


def base():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill="#0f1520")
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill="#0f1520")
    # marque
    for i, h in enumerate((14, 30, 22)):
        d.rounded_rectangle((60 + i * 12, 70 - h, 69 + i * 12, 70), radius=2, fill=BLUE)
    d.text((104, 40), "PlayLedger", font=font(30, "ExtraBold"), fill=INK)
    d.text((W - 60, 46), "Chiffres vérifiables", font=font(22, "Medium"), fill=MUTED, anchor="ra")
    return im, d


def wrap(d, text, f, width, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" ,.:;") + "…"
    return lines


def spark(d, values, box, color):
    if len(values) < 2:
        return
    x0, y0, x1, y1 = box
    vmin, vmax = min(values), max(values)
    rng = (vmax - vmin) or 1
    pts = [(x0 + i * (x1 - x0) / (len(values) - 1), y1 - (v - vmin) / rng * (y1 - y0)) for i, v in enumerate(values)]
    d.polygon(pts + [(x1, y1), (x0, y1)], fill="#13233d" if color == BLUE else ("#0f2a22" if color == GREEN else "#2a1518"))
    d.line(pts, fill=color, width=5, joint="curve")


def article_card(path, kind, title, date_txt, icons=()):
    im, d = base()
    d.rounded_rectangle((60, 120, 60 + d.textlength(kind.upper(), font=font(20, "Bold")) + 28, 156), radius=6, fill="#13233d")
    d.text((74, 126), kind.upper(), font=font(20, "Bold"), fill="#60a5fa")
    y = 190
    for line in wrap(d, title, font(60, "ExtraBold"), W - 120, 4):
        d.text((60, y), line, font=font(60, "ExtraBold"), fill=INK)
        y += 70
    d.text((60, H - 70), date_txt, font=font(24, "Medium"), fill=MUTED)
    x = W - 60
    for url in list(icons)[:4][::-1]:
        ic = get_icon(url, 72)
        if ic:
            x -= 84
            im.paste(ic, (x, H - 100), ic)
    im.save(path, "PNG", optimize=True)


def game_card(path, name, icon_url, players, rank, values, var=None):
    im, d = base()
    ic = get_icon(icon_url, 150)
    tx = 60
    if ic:
        im.paste(ic, (60, 130), ic)
        tx = 240
    for i, line in enumerate(wrap(d, name, font(54, "ExtraBold"), W - tx - 60, 2)):
        d.text((tx, 135 + i * 62), line, font=font(54, "ExtraBold"), fill=INK)
    d.text((60, 330), f"{players:,}".replace(",", " "), font=font(96, "ExtraBold"), fill=INK)
    d.text((60, 440), "joueurs en ligne" + (f"  ·  {rank}e au classement PlayLedger" if rank and rank > 1 else ("  ·  n° 1 au classement PlayLedger" if rank == 1 else "")),
           font=font(28, "Medium"), fill=MUTED)
    color = BLUE if var is None else (GREEN if var >= 0 else RED)
    spark(d, values[-48:], (640, 330, W - 60, 470), color)
    d.text((60, H - 70), "Courbe et chiffres mis à jour toutes les heures", font=font(22, "Medium"), fill=MUTED)
    im.save(path, "PNG", optimize=True)


def site_card(path, tagline):
    im, d = base()
    y = 200
    for line in wrap(d, tagline, font(76, "ExtraBold"), W - 120, 3):
        d.text((60, y), line, font=font(76, "ExtraBold"), fill=INK)
        y += 86
    d.text((60, H - 80), "Classements, tendances et analyses de Roblox, chaque chiffre relié à sa source", font=font(26, "Medium"), fill=MUTED)
    im.save(path, "PNG", optimize=True)


def badge_svg(rank, players, name):
    rk = "n° 1" if rank == 1 else (f"{rank}e" if rank else "suivi")
    left, right = "PlayLedger", f"{rk} du classement · {players:,} joueurs".replace(",", " ")
    lw, rw = 29 + int(len(left) * 7.4) + 10, 14 + int(len(right) * 7.1)
    w = lw + rw
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="28" role="img" aria-label="{esc(name)} : {esc(right)}, selon PlayLedger">'
            f'<title>{esc(name)} : {esc(right)}, selon PlayLedger</title>'
            f'<rect width="{w}" height="28" rx="6" fill="#151d2a"/><rect width="{lw}" height="28" rx="6" fill="#1e293b"/>'
            f'<rect x="{lw - 6}" width="6" height="28" fill="#1e293b"/>'
            f'<g fill="#3b82f6"><rect x="10" y="15" width="3" height="6" rx="1"/><rect x="15" y="8" width="3" height="13" rx="1"/><rect x="20" y="11" width="3" height="10" rx="1"/></g>'
            f'<g font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="12" font-weight="700">'
            f'<text x="29" y="18.5" fill="#f8fafc">{esc(left)}</text><text x="{lw + 8}" y="18.5" fill="#cbd5e1">{esc(right)}</text></g></svg>')


def waiting_pdf(path, name, date_txt):
    """PDF d'une page (A4) affiché tant que la première édition du rapport n'est pas sortie."""
    w, h = 1240, 1754
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    for x in range(0, w, 60):
        d.line([(x, 0), (x, h)], fill="#0f1520")
    for y in range(0, h, 60):
        d.line([(0, y), (w, y)], fill="#0f1520")
    for i, hh in enumerate((20, 44, 32)):
        d.rounded_rectangle((110 + i * 17, 170 - hh, 122 + i * 17, 170), radius=3, fill=BLUE)
    d.text((180, 122), name, font=font(44, "ExtraBold"), fill=INK)
    d.text((110, 560), "RAPPORT MENSUEL", font=font(30, "Bold"), fill="#60a5fa")
    d.text((110, 610), "État de Roblox", font=font(110, "ExtraBold"), fill=INK)
    y = 790
    for line in wrap(d, f"La première édition sort le {date_txt}.", font(46, "Bold"), w - 220, 3):
        d.text((110, y), line, font=font(46, "Bold"), fill=INK)
        y += 62
    y += 30
    for line in wrap(d, "Merci de votre inscription : vous la recevrez par e-mail dès sa sortie, puis chaque nouvelle édition. "
                        "Ce lien affichera toujours la dernière édition.", font(34, "Medium"), w - 220, 6):
        d.text((110, y), line, font=font(34, "Medium"), fill=MUTED)
        y += 48
    d.text((110, h - 150), "Chaque chiffre relié à sa source · données publiques de Roblox", font=font(28, "Medium"), fill="#64748b")
    im.save(path, "PDF", resolution=150)
