#!/usr/bin/env python3
"""Re-check not_found rows of a quote-check report using headless Chromium.
Usage: python3 tools/recheck_quotes.py ledger/audit/quote-check-<label>.json"""
import json, re, sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_page import browser
from merge_inbox import norm
p = sys.argv[1]
d = json.load(open(p))
cache = {}
for r in d["rows"]:
    if r["verdict"] != "not_found":
        continue
    u = r["source_url"]
    if u not in cache:
        try:
            st, t = browser(u); cache[u] = norm(t)
        except Exception as e:
            cache[u] = ""
    t = cache[u]
    frags = [f for f in re.split(r"\s*(?:\.\.\.|…)\s*", norm(r["quote"])) if len(f) > 8]
    if t and frags and all(f in t for f in frags):
        r["verdict"] = "found"; r["via"] = "browser-recheck"
d["summary"] = {k: sum(1 for r in d["rows"] if r["verdict"] == k) for k in ("found", "not_found", "unreachable")}
json.dump(d, open(p, "w"), indent=1)
print(json.dumps(d["summary"]))
for r in d["rows"]:
    if r["verdict"] == "not_found":
        print("NOT_FOUND", r["claim_id"], "|", r["source_url"][:90], "|", r["quote"][:110])
