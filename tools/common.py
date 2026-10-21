"""Outils partagés : chemins, temps, lecture des relevés, mise en forme française."""
import csv
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("MEDIA_DATA_DIR", ROOT / "data"))
FACTS = Path(os.environ.get("MEDIA_FACTS_DIR", ROOT / "facts"))
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(CONFIG.get("tz", "Europe/Paris"))
UTC = timezone.utc

NNBSP = " "  # espace fine insécable : séparateur de milliers et avant % en français

SNAP_FIELDS = ["ts_utc", "universe_id", "playing", "visits", "favorites", "up_votes", "down_votes"]
SORT_FIELDS = ["ts_utc", "sort_id", "position", "universe_id", "player_count", "is_sponsored"]
GAME_FIELDS = ["universe_id", "root_place_id", "name", "creator_name", "creator_type", "creator_verified",
               "genre_l1", "genre_l2", "created", "updated", "max_players", "first_seen", "last_in_sort", "icon"]


# ---------- temps ----------
def utc_now():
    return datetime.now(UTC).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def snap_path(kind, dt):
    """Fichier horaire d'un relevé, rangé par heure UTC."""
    dt = dt.astimezone(UTC)
    return DATA / kind / f"{dt:%Y}" / f"{dt:%m}" / f"{dt:%d}" / f"{dt:%H}.csv"


def paris_day_bounds(d):
    """Début et fin (UTC) d'une journée à Paris."""
    start = datetime(d.year, d.month, d.day, tzinfo=TZ)
    end = start + timedelta(days=1)
    return start.astimezone(UTC), end.astimezone(UTC)


def hours_of_day(d):
    start, end = paris_day_bounds(d)
    h = start
    while h < end:
        yield h
        h += timedelta(hours=1)


def paris_today():
    return utc_now().astimezone(TZ).date()


# ---------- lecture ----------
def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def load_games():
    return {r["universe_id"]: r for r in read_csv(DATA / "games.csv")}


def load_day_snapshots(d):
    """Relevés horaires d'une journée (heure de Paris) : liste de (datetime UTC, {uid: ligne})."""
    out = []
    for h in hours_of_day(d):
        rows = read_csv(snap_path("snapshots", h))
        if not rows:
            continue
        ts = parse_iso(rows[0]["ts_utc"])
        out.append((ts, {r["universe_id"]: r for r in rows}))
    return out


def rel(path):
    return str(Path(path).resolve().relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path)


# ---------- mise en forme (français par défaut, autres langues via i18n.CUR) ----------
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
        "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = {"en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
          "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
          "pt-br": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]}
DAYS = {"en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
        "pt-br": ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]}
# séparateur de milliers, séparateur décimal, espace avant %
NUM = {"fr": (NNBSP, ",", NNBSP), "en": (",", ".", ""), "es": (".", ",", NNBSP), "pt-br": (".", ",", "")}


def _lang():
    try:
        import i18n
        return i18n.CUR
    except ImportError:
        return "fr"


def _group(n, sep):
    return f"{n:,}".replace(",", sep)


def fr_int(n):
    n = int(round(n))
    th = NUM[_lang()][0]
    # en espagnol, pas de séparateur pour les nombres à quatre chiffres (norme RAE)
    s = str(abs(n)) if _lang() == "es" and abs(n) < 10000 else _group(abs(n), th)
    return ("-" if n < 0 else "") + s


def fr_dec(x, nd=1):
    th, dec, _ = NUM[_lang()]
    s = f"{abs(x):,.{nd}f}".replace(",", "\x00").replace(".", dec).replace("\x00", th)
    return ("-" if x < 0 else "") + s


def _trim(s):
    dec = NUM[_lang()][1]
    return s.rstrip("0").rstrip(dec) if dec in s else s


BIG = {"fr": (("milliard", "milliards"), ("million", "millions")), "en": (("billion", "billion"), ("million", "million")),
       "es": (("mil millones", "mil millones"), ("millón", "millones")), "pt-br": (("bilhão", "bilhões"), ("milhão", "milhões"))}


def fr_big(n):
    """121 176 / 1,2 million / 65,3 milliards / 32,69 millions (deux décimales au plus, zéros inutiles retirés)."""
    a = abs(n)
    L = _lang()
    (b1, b2), (m1, m2) = BIG[L]
    for unit, (one, many) in ((1e9, (b1, b2)), (1e6, (m1, m2))):
        if a >= unit:
            v = n / unit
            plural = abs(v) >= 2 if L in ("fr", "pt-br") else abs(v) != 1
            return f"{_trim(fr_dec(v, 2))} " + (many if plural else one)
    return fr_int(n)


def fr_pct(x, signed=True, nd=1):
    """x en fraction (0,123 -> +12,3 %)."""
    v = x * 100
    sign = "+" if signed and v > 0 else ("−" if v < 0 else "")
    return f"{sign}{fr_dec(abs(v), nd)}{NUM[_lang()][2]}%"


def fr_share(x, nd=1):
    return f"{fr_dec(x * 100, nd)}{NUM[_lang()][2]}%"


def fr_date(d, weekday=True):
    L = _lang()
    if L == "en":
        s = f"{MONTHS['en'][d.month - 1]} {d.day}, {d.year}"
        return f"{DAYS['en'][d.weekday()]}, {s}" if weekday else s
    if L in ("es", "pt-br"):
        s = f"{d.day} de {MONTHS[L][d.month - 1]} de {d.year}"
        return f"{DAYS[L][d.weekday()]}, {s}" if weekday else s
    s = f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"
    return f"{JOURS[d.weekday()]} {s}" if weekday else s


def fr_hour(dt):
    t = dt.astimezone(TZ)
    L = _lang()
    if L == "en":
        h = t.hour % 12 or 12
        return f"{h}:{t.minute:02d}{NNBSP}{'a.m.' if t.hour < 12 else 'p.m.'}"
    if L == "es":
        return f"{t.hour}:{t.minute:02d}"
    if L == "pt-br":
        return f"{t.hour}h{t.minute:02d}"
    return f"{t.hour}{NNBSP}h" if t.minute == 0 else f"{t.hour}{NNBSP}h{NNBSP}{t.minute:02d}"


def fr_rank(n):
    L = _lang()
    if L == "en":
        suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suf}"
    if L in ("es", "pt-br"):
        return f"{n}.º" if L == "es" else f"{n}º"
    return "1er" if n == 1 else f"{n}e"


def rank_html(n):
    """Rang avec exposant (« 2<sup>e</sup> », « 2<sup>nd</sup> »)."""
    if not n:
        return "—"
    r = fr_rank(n)
    num = str(n)
    return f"{num}<small>{r[len(num):]}</small>" if r[len(num):] else num


def slugify(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    out = []
    for ch in s.lower():
        out.append(ch if ch.isalnum() else "-")
    slug = "-".join(p for p in "".join(out).split("-") if p)
    return slug[:80] or "article"


def github_blob(path):
    repo = CONFIG.get("repo") or "OWNER/REPO"
    return f"https://github.com/{repo}/blob/main/{path}"


def github_tree(path):
    repo = CONFIG.get("repo") or "OWNER/REPO"
    return f"https://github.com/{repo}/tree/main/{path}"
