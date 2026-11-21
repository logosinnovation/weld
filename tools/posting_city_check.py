#!/usr/bin/env python3
"""Wrong-plant sweep: for every evidence row sourced from a job posting for a plant,
check that the plant's city (or street address) appears on the posting page.

Usage: python3 tools/posting_city_check.py [plant_id ...]   (default: all profiled plants)
Writes ledger/audit/posting-city-check.json and prints the misses.
"""
import csv
import json
import os
import re
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_page import fetch  # noqa: E402

plants = {r["id"]: r for r in csv.DictReader(open("ledger/plants.csv"))}
ids = sys.argv[1:] or [i for i, r in plants.items() if r["status"] == "profiled"]
rows = [e for e in csv.DictReader(open("ledger/evidence.csv"))
        if e["source_type"] == "job posting" and e["claim_id"].split(":")[0] in ids and e["source_url"]]
urls = sorted({e["source_url"] for e in rows})


def get(u):
    try:
        st, t, how = fetch(u)
        return u, (st, re.sub(r"\s+", " ", t).lower())
    except Exception as ex:  # noqa: BLE001
        return u, (0, "")


with ThreadPoolExecutor(8) as ex:
    pages = dict(ex.map(get, urls))
out = []
for e in rows:
    pid = e["claim_id"].split(":")[0]
    p = plants[pid]
    st, t = pages[e["source_url"]]
    city = p["city"].lower()
    street = re.sub(r"\s+", " ", p["address"].split(",")[0].lower()) if p["address"] and "unknown" not in p["address"].lower() else ""
    if not t:
        v = "unreachable"
    elif city in t or (street and street in t):
        v = "city_on_page"
    else:
        v = "CITY_NOT_ON_PAGE"
    out.append({"claim_id": e["claim_id"], "tag": e["tag"], "city": p["city"], "source_url": e["source_url"], "verdict": v})
json.dump({"summary": {k: sum(1 for o in out if o["verdict"] == k) for k in ("city_on_page", "CITY_NOT_ON_PAGE", "unreachable")},
           "rows": out}, open("ledger/audit/posting-city-check.json", "w"), indent=1)
print({k: sum(1 for o in out if o["verdict"] == k) for k in ("city_on_page", "CITY_NOT_ON_PAGE", "unreachable")})
for o in out:
    if o["verdict"] != "city_on_page":
        print(o["verdict"], o["claim_id"], o["tag"], o["city"], o["source_url"][:100])
