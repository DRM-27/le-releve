"""Filme une page de format : python3 tools/social/video/filmer.py PAGE.html DONNEES.json verif | video SORTIE.mp4 | stills t1 t2 …
verif : passe toutes les images aux contrôles sans filmer ; video : filme, contrôle chaque image et ajoute le son.
La piste son est synthétisée à partir de window.SFX (sons.py), puis assemblée sans réencoder l'image."""
import json, os, subprocess, sys
from playwright.sync_api import sync_playwright
import shutil
import sons
CHROME = next((c for c in ("/usr/bin/google-chrome", shutil.which("chromium"), shutil.which("google-chrome")) if c and os.path.exists(c)), None)

page, dataf, mode = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(dataf))
stem = os.path.splitext(page)[0]
with sync_playwright() as p:
    b = p.chromium.launch(**({"executable_path": CHROME} if CHROME else {}), args=["--force-color-profile=srgb"])
    pg = b.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file://" + os.path.abspath(page))
    pg.evaluate("Promise.all(['400','600','700','800','900'].map(w => document.fonts.load(w + ' 40px SG', 'Aa0 àéç€ ×÷−'))).then(() => document.fonts.ready)")
    pg.evaluate("d => init(d)", data)
    pg.evaluate("Promise.all([...document.images].map(i => i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; })))")
    pg.wait_for_timeout(300)
    if mode == "stills":
        for t in sys.argv[4:]:
            pg.evaluate(f"render({t}); verif({t})")
            pg.screenshot(path=f"{stem}_{t}.png")
        print("contrôles :", pg.evaluate("window.ERREURS") or "OK")
    elif mode == "verif":
        n = int(round(pg.evaluate("DURATION") * 30))
        pg.evaluate(f"(() => {{ for (let i = 0; i < {n}; i++) {{ render(i / 30); verif(i / 30); }} }})()")
        ctl = pg.evaluate("window.ERREURS")
        print(os.path.basename(page), "contrôles :", "OK" if not ctl else "")
        for k, v in ctl.items():
            print("  ✗", v)
        if ctl:
            sys.exit(1)
    elif mode == "slides":  # (carrousel, plus tard)
        n = pg.evaluate("NSLIDES")
        for i in range(n):
            pg.evaluate(f"slide({i})")
            pg.screenshot(path=f"{sys.argv[4]}-{i + 1}.png")
        print("ok", n, "images")
    else:
        out = sys.argv[4]
        tmpv, tmpa, tmp = out.replace(".mp4", ".video.mp4"), out.replace(".mp4", ".wav"), out.replace(".mp4", ".part.mp4")
        dur = pg.evaluate("DURATION")
        n = int(round(dur * 30))
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", "30", "-c:v", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmpv],
                              stdin=subprocess.PIPE)
        for i in range(n):
            pg.evaluate(f"render({i / 30}); verif({i / 30})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
        ff.stdin.close()
        if ff.wait() == 0:
            sons.piste(pg.evaluate("window.SFX"), dur, tmpa)
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmpv, "-i", tmpa, "-map", "0:v", "-map", "1:a",
                                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", tmp])
            if r.returncode == 0:
                os.replace(tmp, out)
                os.remove(tmpv); os.remove(tmpa)
                print("ok", out, n, "images,", len(pg.evaluate("window.SFX")), "sons")
    if errs:
        print("ERREURS JS :", errs)
    if mode == "video":
        ctl = pg.evaluate("window.ERREURS")
        print("contrôles :", "OK" if not ctl else "")
        for k, v in ctl.items():
            print("  ✗", v)
        if (ctl or errs) and os.path.exists(out):
            os.replace(out, out.replace(".mp4", ".refusee.mp4"))   # une vidéo qui échoue aux contrôles n'est jamais publiable
            print("vidéo refusée :", out.replace(".mp4", ".refusee.mp4"))
            b.close(); sys.exit(1)
    if errs:
        b.close(); sys.exit(1)
    b.close()
