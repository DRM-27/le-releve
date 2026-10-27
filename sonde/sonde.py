"""Sonde des sources des trois médias envisagés. Imprime des faits mesurés, rien n'est publié."""
import json, time, urllib.request, urllib.parse, datetime as dt, traceback, os
UA = {"User-Agent": "PlayLedger-sonde/1.0 (contact via github DRM-27)"}
def get(url, timeout=60):
    t = time.time()
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read(); return r.status, b, round(time.time() - t, 2)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:500], round(time.time() - t, 2)
def J(url):
    s, b, t = get(url); return s, (json.loads(b) if s == 200 else b.decode("utf-8", "replace")), t
def section(name, fn):
    print(f"\n######## {name}")
    try: fn()
    except Exception: traceback.print_exc()
today = dt.date.today()

def openrouter():
    s, b, t = get("https://openrouter.ai/api/v1/datasets/rankings-daily")
    print("rankings-daily sans clé :", s, b[:200])
    s, d, t = J("https://openrouter.ai/api/v1/models")
    print("models :", s, len(d.get("data", [])) if s == 200 else d[:200])
    s, b, t = get("https://openrouter.ai/rankings")
    print("page rankings :", s, len(b), "octets")

def ods(base, ds, **params):
    q = urllib.parse.urlencode(params)
    return J(f"{base}/api/explore/v2.1/catalog/datasets/{ds}/records?{q}")

def boamp():
    base = "https://boamp-datadila.opendatasoft.com"
    s, d, t = J(f"{base}/api/explore/v2.1/catalog/datasets/boamp")
    if s == 200: print("champs BOAMP :", [f["name"] for f in d.get("fields", [])][:60])
    else: print("BOAMP meta", s, str(d)[:300])
    since = (today - dt.timedelta(days=14)).isoformat()
    s, d, t = ods(base, "boamp", select="dateparution, count(*) as n", where=f"dateparution >= '{since}'", group_by="dateparution", order_by="dateparution", limit=30)
    print("BOAMP avis par jour (14 j) :", s, json.dumps(d.get("results") if s == 200 else str(d)[:300], ensure_ascii=False))
    s, d, t = ods(base, "boamp", select="nature_libelle, count(*) as n", where=f"dateparution >= '{since}'", group_by="nature_libelle", order_by="n desc", limit=15)
    print("BOAMP par nature (14 j) :", s, json.dumps(d.get("results") if s == 200 else str(d)[:300], ensure_ascii=False))
    s, d, t = ods(base, "boamp", limit=1, order_by="dateparution desc")
    if s == 200 and d.get("results"): print("exemple BOAMP clés :", list(d["results"][0].keys()))

def bodacc():
    base = "https://bodacc-datadila.opendatasoft.com"
    ds = "annonces-commerciales"
    s, d, t = J(f"{base}/api/explore/v2.1/catalog/datasets/{ds}")
    if s == 200: print("champs BODACC :", [f["name"] for f in d.get("fields", [])])
    else: print("BODACC meta", s, str(d)[:300])
    since = (today - dt.timedelta(days=14)).isoformat()
    s, d, t = ods(base, ds, select="dateparution, familleavis_lib, count(*) as n", where=f"dateparution >= '{since}'", group_by="dateparution, familleavis_lib", order_by="dateparution", limit=200)
    print("BODACC par jour et famille (14 j) :", s, json.dumps(d.get("results") if s == 200 else str(d)[:300], ensure_ascii=False))
    for w in ["familleavis = 'collective'", "familleavis = 'collective' and jugement like '*ouverture*'", "familleavis = 'collective' and search(jugement, 'ouverture')"]:
        s, d, t = ods(base, ds, select="count(*) as n", where=f"{w} and dateparution >= '2025-01-01' and dateparution <= '2025-12-31'", limit=1)
        print("2025 :", w, "->", s, d.get("results") if s == 200 else str(d)[:300])
    s, d, t = ods(base, ds, where="familleavis = 'collective'", order_by="dateparution desc", limit=2)
    if s == 200:
        for r in d.get("results", []): print("exemple procédure :", json.dumps({k: (str(v)[:300] if v else v) for k, v in r.items()}, ensure_ascii=False))
    s, d, t = ods(base, ds, select="typeavis_lib, count(*) as n", where=f"familleavis = 'collective' and dateparution >= '{since}'", group_by="typeavis_lib", limit=20)
    print("types d'avis collectifs (14 j) :", s, d.get("results") if s == 200 else str(d)[:200])

def sirene():
    s, d, t = J("https://recherche-entreprises.api.gouv.fr/search?q=552032534&per_page=1")
    if s == 200:
        r = d["results"][0]; print("recherche-entreprises OK", t, "s :", {k: r.get(k) for k in ["siren", "nom_complet", "activite_principale", "section_activite_principale", "tranche_effectif_salarie", "nature_juridique", "date_creation"]})
    else: print("recherche-entreprises", s, str(d)[:200])
    s, b, t = get("https://api.insee.fr/api-sirene/3.11/siren/552032534")
    print("API Sirene Insee sans clé :", s)

def decp():
    import duckdb, subprocess
    url = "https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432"
    t = time.time(); subprocess.run(["curl", "-sSL", "-o", "decp.parquet", url], check=True)
    print("téléchargement parquet :", round(time.time() - t), "s,", os.path.getsize("decp.parquet") // 1_000_000, "Mo")
    c = duckdb.connect()
    c.execute("create view d as select * from read_parquet('decp.parquet')")
    cols = [r[0] for r in c.execute("describe d").fetchall()]; print("colonnes :", cols)
    print("lignes :", c.execute("select count(*) from d").fetchone()[0])
    has = lambda x: x in cols
    if has("donneesActuelles") and has("uid"):
        print("marchés distincts (uid, données actuelles) :", c.execute("select count(distinct uid) from d where donneesActuelles").fetchone()[0])
    for dc in ["datePublicationDonnees", "dateNotification"]:
        if has(dc):
            print(f"\npar {dc}, 21 derniers jours (marchés distincts, montant total) :")
            for r in c.execute(f"select cast({dc} as date) j, count(distinct uid), round(sum(montant)/1e6,1) from d where donneesActuelles and cast({dc} as date) >= current_date - 21 group by 1 order by 1").fetchall(): print(" ", r)
            print(f" par année ({dc}) :", c.execute(f"select year(cast({dc} as date)) y, count(distinct uid) from d where donneesActuelles group by 1 order by 1 desc limit 6").fetchall())
    if has("montant"):
        print("montants : nuls/0 :", c.execute("select count(*) from d where donneesActuelles and (montant is null or montant <= 0)").fetchone()[0],
              "| > 1 Md€ :", c.execute("select count(*) from d where donneesActuelles and montant > 1e9").fetchone()[0],
              "| médiane :", c.execute("select median(montant) from d where donneesActuelles").fetchone()[0])
    tcols = [x for x in cols if x.startswith("titulaire")]; print("champs titulaire :", tcols)
    for x in ["titulaire_typeIdentifiant", "titulaire_typeIdentifiant_1"]:
        if has(x): print(x, c.execute(f"select {x}, count(*) from d where donneesActuelles group by 1 order by 2 desc limit 6").fetchall())
    for x in ["acheteur_id", "titulaire_id", "titulaire_id_1"]:
        if has(x): print("distincts", x, "(notifiés en 2025) :", c.execute(f"select count(distinct {x}) from d where donneesActuelles and year(cast(dateNotification as date)) = 2025").fetchone()[0])
    if has("titulaire_categorie"): print(c.execute("select titulaire_categorie, count(*) from d where donneesActuelles group by 1 order by 2 desc limit 6").fetchall())
    print("\nexemple ligne :", c.execute("select * from d where donneesActuelles order by datePublicationDonnees desc limit 1").fetchdf().T.to_string()[:3000])

section("OpenRouter", openrouter)
section("BOAMP", boamp)
section("BODACC", bodacc)
section("Sirene", sirene)
section("DECP", decp)
