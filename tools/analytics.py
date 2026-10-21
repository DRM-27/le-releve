"""Pages les plus lues sur 7 jours, via Cloudflare Web Analytics (sans cookie). Écrit data/populaires.json.

Ne fait rien tant que les secrets CF_API_TOKEN et CF_ACCOUNT_ID et le réglage analytics.cloudflareSiteTag ne sont pas définis.
"""
import json
import os
import sys
import urllib.request
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG, DATA, iso, utc_now

token, account = os.environ.get("CF_API_TOKEN"), os.environ.get("CF_ACCOUNT_ID")
site = CONFIG.get("analytics", {}).get("cloudflareSiteTag")
if not (token and account and site):
    print("Mesure d'audience non branchée : rien à faire.")
    sys.exit(0)
now = utc_now()
query = """query($a: String!, $s: String!, $from: Time!, $to: Time!) { viewer { accounts(filter: {accountTag: $a}) {
  rumPageloadEventsAdaptiveGroups(limit: 20, orderBy: [count_DESC], filter: {siteTag: $s, datetime_geq: $from, datetime_leq: $to}) {
    count dimensions { requestPath } } } } }"""
body = json.dumps({"query": query, "variables": {"a": account, "s": site, "from": iso(now - timedelta(days=7)), "to": iso(now)}}).encode()
req = urllib.request.Request("https://api.cloudflare.com/client/v4/graphql", data=body,
                             headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    groups = d["data"]["viewer"]["accounts"][0]["rumPageloadEventsAdaptiveGroups"]
except Exception as e:
    print(f"Mesure d'audience indisponible : {e}")
    sys.exit(0)
pages = [{"path": g["dimensions"]["requestPath"], "vues": g["count"]} for g in groups]
(DATA / "populaires.json").write_text(json.dumps({"genere": iso(now), "periode_jours": 7, "pages": pages}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(pages)} pages populaires.")
