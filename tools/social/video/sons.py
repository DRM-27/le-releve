"""Effets sonores synthétisés (aucun échantillon, aucun droit) et mixage d'une piste à partir d'une liste d'événements.

sons.piste([(t, "pop"), (t, "whoosh"), ...], duree, "sortie.wav")
"""
import wave

import numpy as np

SR = 44100


def _t(d):
    return np.arange(int(SR * d)) / SR


def _env(n, a=0.004, d=0.1):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)
    return e


def sweep(f0, f1, d, wave_="sine"):
    t = _t(d)
    f = f0 * (f1 / f0) ** (t / d)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) if wave_ == "sine" else np.sign(np.sin(ph)) * 0.6


def noise(d, lp=0.0):
    x = np.random.default_rng(7).standard_normal(int(SR * d))
    if lp > 0:  # passe-bas simple
        y = np.zeros_like(x)
        for i in range(1, len(x)):
            y[i] = y[i - 1] + lp * (x[i] - y[i - 1])
        x = y / (np.abs(y).max() + 1e-9)
    return x


def pop():
    s = sweep(700, 1300, 0.12) * _env(int(SR * .12), .002, .035)
    c = noise(0.012) * np.linspace(1, 0, int(SR * .012)) * .4
    s[: len(c)] += c
    return s * .55


def tick():
    n = noise(0.018) * _env(int(SR * .018), .001, .004)
    return n * .22


def whoosh():
    d = .42
    n = noise(d, lp=.08)
    e = np.sin(np.pi * np.linspace(0, 1, len(n))) ** 2
    return n * e * .35


def rise():
    d = .7
    n = int(SR * d)
    s = sweep(220, 1400, d) * np.linspace(.2, 1, n) * np.exp(-np.maximum(0, _t(d) - .55) / .05)
    w = np.zeros(n)
    wh = whoosh()
    w[: min(n, len(wh))] = wh[: min(n, len(wh))]
    return s * .32 + w * .5


def fall():
    d = .75
    s = sweep(1100, 120, d) * _env(int(SR * d), .01, .35)
    return s * .4


def impact():
    d = .55
    t = _t(d)
    s = np.sin(2 * np.pi * (55 + 40 * np.exp(-t / .04)) * t) * np.exp(-t / .16)
    s[: int(SR * .015)] += noise(.015) * .7
    return s * .9


def flash():
    d = .9
    t = _t(d)
    s = sum(np.sin(2 * np.pi * f * t) for f in (523.25, 659.25, 783.99, 1046.5)) / 4
    return s * _env(len(t), .005, .28) * .45


def clash():
    d = .5
    t = _t(d)
    s = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((540, 1), (1270, .7), (2310, .5), (3390, .3)))
    s = s * np.exp(-t / .12) * .35
    s[: int(SR * .02)] += noise(.02) * .6
    out = np.zeros(int(SR * .75))
    out[: len(s)] += s
    out[int(SR * .2): int(SR * .2) + len(s)] += s * .9
    return out


def chime():
    out = np.zeros(int(SR * 1.0))
    for k, f in enumerate((880, 1108.7, 1318.5, 1760)):
        n = int(SR * .5)
        s = np.sin(2 * np.pi * f * _t(.5)) * _env(n, .003, .16) * .3
        i = int(SR * .07 * k)
        out[i: i + n] += s
    return out


def depart():
    out = np.zeros(int(SR * 1.5))
    for k in range(3):
        n = int(SR * .12)
        i = int(SR * .32 * k)
        out[i: i + n] += np.sin(2 * np.pi * 440 * _t(.12)) * .35
    n = int(SR * .45)
    i = int(SR * .96)
    out[i: i + n] += np.sin(2 * np.pi * 880 * _t(.45)) * _env(n, .005, .25) * .45
    return out


def question():
    out = np.zeros(int(SR * 1.1))
    for k, f in enumerate((784, 988)):
        n = int(SR * .7)
        s = np.sin(2 * np.pi * f * _t(.7)) * _env(n, .004, .22) + np.sin(2 * np.pi * 2 * f * _t(.7)) * _env(n, .004, .1) * .3
        i = int(SR * .22 * k)
        out[i: i + n] += s * .3
    return out


def bulle():
    s = sweep(400, 900, .08) * _env(int(SR * .08), .002, .03)
    return s * .35


def tension():
    d = 1.6
    t = _t(d)
    f = 70 * (2.2 ** (t / d))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) + .35 * np.sin(2 * np.pi * np.cumsum(2.01 * f) / SR)
    e = (t / d) ** 1.6 * np.exp(-np.maximum(0, t - d + .05) / .02)
    return s * e * .45 + noise(d, lp=.05) * e * .12


def rewind():
    d = .7
    t = _t(d)
    s = sweep(1600, 300, d) * .25 + np.sign(np.sin(2 * np.pi * 38 * t)) * noise(d, lp=.3) * .18
    return s * np.sin(np.pi * t / d) ** .6


def thud():
    d = .3
    t = _t(d)
    return np.sin(2 * np.pi * (90 + 60 * np.exp(-t / .03)) * t) * np.exp(-t / .08) * .7


SONS = {"pop": pop, "tick": tick, "whoosh": whoosh, "rise": rise, "fall": fall, "impact": impact,
        "flash": flash, "clash": clash, "chime": chime, "depart": depart, "question": question, "bulle": bulle,
        "tension": tension, "rewind": rewind, "thud": thud}


def piste(evts, duree, out):
    mix = np.zeros(int(SR * (duree + 1.5)))
    cache = {}
    for t, nom in evts:
        if nom not in cache:
            cache[nom] = np.asarray(SONS[nom](), dtype=float)
        s = cache[nom]
        i = int(SR * t)
        j = min(len(mix), i + len(s))
        if i < len(mix):
            mix[i:j] += s[: j - i]
    mix = mix[: int(SR * duree)]
    pk = np.abs(mix).max()
    if pk > 0:
        mix = mix / pk * 0.85
    pcm = (np.stack([mix, mix], 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
