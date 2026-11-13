"""Relevé de tendances : Google Trends (5 ans) + pages vues Wikipédia.
Sortie : labo/tendances/resultats.json et resultats.md. Lancé par .github/workflows/tendances.yml."""
import json, time, datetime, pathlib, urllib.request, urllib.parse
from pytrends.request import TrendReq

ICI = pathlib.Path(__file__).parent
mots = [l.split('|', 1) for l in (ICI / 'mots.txt').read_text().splitlines() if l.strip() and not l.startswith('#')]
py = TrendReq(hl='fr-FR', tz=-60)
res = []

def mesure(serie):
    v = [float(x) for x in serie]
    if len(v) < 110 or max(v) == 0:
        return None
    dern = sum(v[-13:]) / 13           # 3 derniers mois
    an = sum(v[-65:-52]) / 13          # mêmes 3 mois un an plus tôt
    cinq = sum(v) / len(v)
    return {"niveau_3m": round(dern, 1), "an_dernier_3m": round(an, 1),
            "evol_1an_pct": round((dern - an) / an * 100) if an else None,
            "vs_moyenne_5ans": round(dern / cinq, 2) if cinq else None,
            "pic": int(max(v))}

for pays, mot in mots:
    item = {"pays": pays or "monde", "mot": mot}
    for essai in range(3):
        try:
            py.build_payload([mot], timeframe='today 5-y', geo=pays)
            df = py.interest_over_time()
            item["trends"] = mesure(df[mot]) if not df.empty else None
            try:
                rq = py.related_queries()[mot]["rising"]
                item["requetes_en_hausse"] = [] if rq is None else rq.head(8).to_dict('records')
            except Exception:
                item["requetes_en_hausse"] = []
            break
        except Exception as e:
            item["erreur"] = str(e)[:120]
            time.sleep(60 * (essai + 1))
    res.append(item)
    time.sleep(12)

# Pages vues Wikipédia (FR), 24 derniers mois, pour recouper
WIKI = {"Facturation électronique": "fr", "Accessibilité du web": "fr", "Règlement sur l'intelligence artificielle": "fr",
        "Diagnostic de performance énergétique": "fr", "Jesmonite": "en", "N8n": "en", "Impression 3D": "fr",
        "Directive NIS 2": "fr", "Vibe coding": "en"}
fin = datetime.date.today().replace(day=1)
debut = (fin - datetime.timedelta(days=760)).replace(day=1)
wiki = {}
for art, lang in WIKI.items():
    u = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/user/"
         f"{urllib.parse.quote(art.replace(' ', '_'), safe='')}/monthly/{debut:%Y%m%d}00/{fin:%Y%m%d}00")
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "chamawn-labo/1.0 (github.com/DRM-27)"}), timeout=30)
        it = json.load(r)["items"]
        wiki[f"{lang}:{art}"] = {i["timestamp"][:6]: i["views"] for i in it}
    except Exception as e:
        wiki[f"{lang}:{art}"] = {"erreur": str(e)[:100]}

out = {"date": datetime.datetime.utcnow().isoformat(timespec='minutes') + "Z", "source": "Google Trends via pytrends, 5 ans, hebdo ; Wikimedia pageviews", "trends": res, "wikipedia": wiki}
(ICI / 'resultats.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
lignes = ["| Pays | Mot | Niveau 3 mois | Évol. 1 an | vs moy. 5 ans |", "|---|---|---|---|---|"]
for i in sorted(res, key=lambda x: -((x.get("trends") or {}).get("evol_1an_pct") or -999)):
    t = i.get("trends") or {}
    lignes.append(f"| {i['pays']} | {i['mot']} | {t.get('niveau_3m', '—')} | {t.get('evol_1an_pct', i.get('erreur', '—'))} | {t.get('vs_moyenne_5ans', '—')} |")
(ICI / 'resultats.md').write_text(f"# Tendances au {out['date']}\n\n" + "\n".join(lignes) + "\n")
print("\n".join(lignes))
