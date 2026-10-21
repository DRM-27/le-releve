"""Contrôle qualité du site construit (_site/) : liens internes cassés, images sans texte alternatif, pages sans titre.

N'empêche pas la mise en ligne : signale les problèmes dans le journal de GitHub Actions (avertissements).
"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG, ROOT

OUT = ROOT / "_site"
BASE = urlparse(CONFIG.get("baseUrl") or "").path.rstrip("/") + "/"
problems = []
pages = list(OUT.rglob("*.html"))
for p in pages:
    h = p.read_text(encoding="utf-8")
    rel = p.relative_to(OUT)
    if "<title>" not in h and "widget" not in str(rel):
        problems.append(f"{rel} : pas de titre")
    for m in re.finditer(r'<img\b[^>]*>', h):
        if "alt=" not in m.group(0):
            problems.append(f"{rel} : image sans texte alternatif")
    for m in re.finditer(r'href="([^"#?]+)', h):
        href = m.group(1)
        if href.startswith(("http", "mailto:", "data:", "javascript:")) or not href.startswith(BASE):
            continue
        target = OUT / href[len(BASE):]
        if not (target.exists() or (target / "index.html").exists()):
            problems.append(f"{rel} : lien cassé {href}")
uniq = sorted(set(problems))
for x in uniq[:100]:
    print(f"::warning::{x}")
print(f"Contrôle qualité : {len(pages)} pages, {len(uniq)} problème(s).")
