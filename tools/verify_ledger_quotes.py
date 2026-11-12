#!/usr/bin/env python3
"""Re-check every stated evidence row's quote against its source page (plain fetch, then browser
recheck for misses, then the AISC snapshot for AISC-directory rows). Writes
ledger/audit/quote-check-ledger.json. Usage: python3 tools/verify_ledger_quotes.py"""
import csv, json, os, re, sys, warnings
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_page import fetch, browser
from merge_inbox import norm
ev = [e for e in csv.DictReader(open("ledger/evidence.csv")) if e["tag"] == "stated" and e["quote"] and e["source_url"].startswith("http")]
snap = norm(open("ledger/audit/source-snapshot-aisc-directory-2026-11-12.txt", errors="ignore").read())
def ok(q, t):
    q = norm(q)
    if q in t: return True
    fr = [f for f in re.split(r"\s*(?:\.\.\.|…)\s*", q) if len(f) > 8]
    return bool(fr) and all(f in t for f in fr)
urls = sorted({e["source_url"] for e in ev})
def get(u):
    try: st, t, how = fetch(u); return u, (st, norm(t))
    except Exception: return u, (0, "")
with ThreadPoolExecutor(10) as ex: pages = dict(ex.map(get, urls))
res, retry = [], set()
for e in ev:
    st, t = pages[e["source_url"]]
    v = "found" if t and ok(e["quote"], t) else ("aisc_snapshot" if "aisc.my.site.com" in e["source_url"] and ok(e["quote"], snap) else "miss")
    if v == "miss": retry.add(e["source_url"])
    res.append([e, v])
def bget(u):
    try: st, t = browser(u); return u, norm(t)
    except Exception: return u, ""
with ThreadPoolExecutor(4) as ex: bp = dict(ex.map(bget, sorted(retry)))
for r in res:
    if r[1] == "miss":
        t = bp.get(r[0]["source_url"], "")
        r[1] = "found_browser" if t and ok(r[0]["quote"], t) else ("unreachable" if not t and not pages[r[0]["source_url"]][1] else "not_found")
out = [{"claim_id": e["claim_id"], "source_url": e["source_url"], "verdict": v, "quote": e["quote"][:160]} for e, v in res]
summ = {k: sum(1 for o in out if o["verdict"] == k) for k in ("found", "found_browser", "aisc_snapshot", "not_found", "unreachable")}
json.dump({"summary": summ, "rows": out}, open("ledger/audit/quote-check-ledger.json", "w"), indent=1)
print(summ)
