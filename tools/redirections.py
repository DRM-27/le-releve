"""Transforme l'ancienne adresse GitHub Pages en redirections vers le nouveau domaine.

Usage : python tools/redirections.py <site construit> <dossier de sortie> <nouvelle adresse>
Chaque page HTML devient une page minuscule qui renvoie, à la même adresse, vers le nouveau domaine
(balise canonical + meta refresh + JavaScript qui garde la requête et l'ancre). Les flux et fichiers
de données sont recopiés tels quels : leurs liens pointent déjà vers le nouveau domaine.
GitHub Pages ne sait pas faire de vraies redirections 301 ; c'est la méthode recommandée à défaut."""
import html, shutil, sys
from pathlib import Path

src, out, new = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].rstrip("/")
if out.exists():
    shutil.rmtree(out)
n = 0
for f in src.rglob("*"):
    if f.is_dir():
        continue
    rel = f.relative_to(src).as_posix()
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if f.suffix == ".html":
        path = rel[:-len("index.html")] if rel.endswith("index.html") else rel
        url = html.escape(f"{new}/" if rel == "404.html" else f"{new}/{path}")
        js = (f"var p=location.pathname.replace(/^\\/le-releve/,'');"
              f"location.replace('{new}'+p+location.search+location.hash);") if rel == "404.html" else \
             f"location.replace('{new}/{path}'+location.search+location.hash);"
        dest.write_text(
            f'<!doctype html><html><head><meta charset="utf-8"><title>PlayLedger a déménagé</title>'
            f'<link rel="canonical" href="{url}">'
            f'<meta http-equiv="refresh" content="0; url={url}"><script>{js}</script></head>'
            f'<body><p>PlayLedger est maintenant sur <a href="{url}">{url}</a>.</p></body></html>', encoding="utf-8")
        n += 1
    elif f.suffix in (".xml", ".json", ".txt", ".csv", ".svg", ".ico", ".png", ".webmanifest"):
        shutil.copy2(f, dest)
print(f"{n} pages transformées en redirections vers {new}")
