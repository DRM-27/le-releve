"""Contrôle du rythme : python3 tools/social/video/controle.py video.mp4
Mesure le mouvement toutes les 0,1 s (part de l'image qui change de façon visible entre deux instants),
repère le plus long passage figé, et compare la dernière image à la première (boucle)."""
import subprocess, sys
import numpy as np
W, H, FPS = 270, 480, 10
def frames(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", f"fps={FPS},scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.int16)
def last_first(path):
    a = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", f"scale={W}:{H},format=gray", "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True).stdout
    b = subprocess.run(["ffmpeg", "-loglevel", "error", "-sseof", "-0.3", "-i", path, "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    a = np.frombuffer(a, np.uint8).astype(np.int16); b = np.frombuffer(b, np.uint8).astype(np.int16)[-W * H:]
    return float(np.mean(np.abs(a - b)))
SEUIL = 0.0015   # part de pixels qui changent de plus de 8 niveaux : en dessous, l'image est considérée figée
bad = False
for path in sys.argv[1:]:
    f = frames(path)
    m = (np.abs(f[5:] - f[:-5]) > 8).mean(axis=(1, 2))      # mouvement sur 0,5 s, comme la mesure du retour
    fig = m < SEUIL
    run, best, start, bstart = 0, 0, 0, 0
    for i, x in enumerate(fig):
        if x:
            if run == 0: start = i
            run += 1
            if run > best: best, bstart = run, start
        else:
            run = 0
    dur = len(f) / FPS
    lf = last_first(path)
    ok = best / FPS <= 1.0 and 19 <= dur <= 25 and lf < 3
    bad = bad or not ok
    print(f"{'OK ' if ok else 'REFUSÉ '}{path.split('/')[-1]:24s} {dur:5.1f} s | figé : {fig.mean() * 100:4.1f} % du temps, plus long passage figé {best / FPS:.1f} s (à {bstart / FPS:.1f} s) | écart dernière/première image {lf:.2f}")

sys.exit(1 if bad else 0)   # règles : jamais plus d'1 s figé, 19 à 25 s, dernière image proche de la première (boucle)
