"""Télécharge les icônes officielles de jeux Roblox (API thumbnails, 512 × 512) pour les vidéos.

Usage : python tools/social/icones.py ID1,ID2,... DOSSIER
Les icônes servent d'illustration de classement, comme sur le site ; elles ne sont pas versionnées
(le dossier de sortie est temporaire : artefact du workflow ou dossier de rendu).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

API = "https://thumbnails.roblox.com/v1/games/icons?universeIds={ids}&returnPolicy=PlaceHolder&size=512x512&format=Png&isCircular=false"
UA = "PlayLedger/1.0 (+https://playledgers.com/)"


def get(url, binary=False, tries=5):
    delay = 2
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                return data if binary else json.loads(data.decode("utf-8"))
        except Exception as e:  # 429, réseau
            if i == tries - 1:
                print(f"échec {url[:90]} : {e}")
                return None
            time.sleep(delay)
            delay *= 2


def main(ids, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ok = 0
    for k in range(0, len(ids), 50):
        d = get(API.format(ids=",".join(ids[k:k + 50]))) or {}
        for item in d.get("data") or []:
            if item.get("state") != "Completed" or not item.get("imageUrl"):
                continue
            png = get(item["imageUrl"], binary=True)
            if png:
                (out / f"{item['targetId']}.png").write_bytes(png)
                ok += 1
        time.sleep(1)
    print(f"{ok} icônes sur {len(ids)} dans {out}")


if __name__ == "__main__":
    main([i for i in sys.argv[1].split(",") if i.strip()], sys.argv[2])
