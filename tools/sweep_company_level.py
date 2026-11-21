#!/usr/bin/env python3
"""Fact-check sweep (2026-11-12): retag company-level sources used as stated plant-level evidence.
(a) a stated row on a plant id, for a plant-level field, whose source_url supports the same field on 2+
    plant ids and whose quote does not contain the plant's city -> tag inferred.
(b) a stated row on a plant id citing path-robotics.com whose quote does not contain the plant's city -> inferred.
Usage: python3 tools/sweep_company_level.py [--apply]"""
import csv, sys
from collections import defaultdict
FIELDS = {"weld_processes","materials","certifications","part_size_fit","production_type","existing_robots",
          "products","triggers","welder_postings","headcount","bottleneck_guess","prospect_test","relationship"}
ev = list(csv.DictReader(open("ledger/evidence.csv"))); EC = list(ev[0].keys())
pl = {p["id"]: p for p in csv.DictReader(open("ledger/plants.csv"))}
use = defaultdict(set)
for e in ev:
    pid, _, f = e["claim_id"].partition(":")
    if pid.startswith("p-") and f in FIELDS and e["tag"] == "stated" and e["source_url"]:
        use[(e["source_url"], f)].add(pid)
n = defaultdict(int)
for e in ev:
    pid, _, f = e["claim_id"].partition(":")
    if not (pid.startswith("p-") and f in FIELDS and e["tag"] == "stated" and pid in pl): continue
    city = pl[pid]["city"].lower()
    q = (e["quote"] or "").lower()
    why = None
    if len(use[(e["source_url"], f)]) >= 2 and city not in q:
        why = f"company-level source: the same page supports {f} for {len(use[(e['source_url'], f)])} plants and the quote does not name {pl[pid]['city']}"
    elif "path-robotics.com" in e["source_url"].lower() and city not in q:
        why = "Path's page names the company, not this plant"
    if why:
        n["a" if "company-level" in why else "b"] += 1
        e["tag"] = "inferred"
        e["reasoning"] = (e["reasoning"] + " | " if e["reasoning"] else "") + f"sweep 2026-11-12: retagged inferred; {why}"
        print("RETAG", e["claim_id"], "|", e["source_url"][:70])
print(dict(n))
if "--apply" in sys.argv:
    w = csv.DictWriter(open("ledger/evidence.csv", "w", newline=""), fieldnames=EC); w.writeheader(); w.writerows(ev); print("applied")
