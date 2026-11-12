#!/usr/bin/env python3
"""Compare list-auditor reports with ledger/plants.csv to measure the miss rate.

Usage: python3 tools/compare_audit.py v-poles-substation ledger/audit/list-audit-*-A.json [...B.json]

Matching: same state, and (same city or a shared distinctive name token between
the auditor's name/parent and the ledger plant's name/parent). Any status
counts as found (base, profiled or excluded), per the miss-rate rule.
Prints matched, unmatched (candidate misses for coordinator adjudication) and
writes ledger/audit/miss-candidates-<vertical>.json.
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP = {"inc", "llc", "corp", "corporation", "co", "company", "the", "of", "and", "industries",
        "manufacturing", "steel", "structures", "structure", "products", "pole", "poles", "fabricating",
        "fabrication", "fabricators", "division", "plant", "utility", "lighting", "traffic", "group",
        "usa", "america", "american", "international", "systems", "metal", "metals", "works", "llp", "ltd"}


def toks(s):
    return {t for t in re.findall(r"[a-z0-9&]+", (s or "").lower()) if t not in STOP and (len(t) > 2 or t in {"kw", "pk"})}


def city(s):
    return re.sub(r"[^a-z]", "", (s or "").lower().replace("saint", "st"))


vert = sys.argv[1]
plants = list(csv.DictReader(open(os.path.join(ROOT, "ledger", "plants.csv"))))
audit = []
for p in sys.argv[2:]:
    d = json.load(open(p))
    for r in d.get("plants", []):
        r["_auditor"] = d.get("auditor", os.path.basename(p))
        audit.append(r)

# combine A and B on name+city+state
comb = {}
for r in audit:
    k = (r.get("state", "").upper(), city(r.get("city")), " ".join(sorted(toks(r.get("name")))))
    if k in comb:
        comb[k]["_auditor"] += "+" + r["_auditor"]
        comb[k]["in_definition"] = comb[k].get("in_definition") or r.get("in_definition")
    else:
        comb[k] = dict(r)

matched, unmatched, out_def = [], [], []
for r in comb.values():
    if not r.get("in_definition"):
        out_def.append(r)
        continue
    st = r.get("state", "").upper()
    at = (toks(r.get("name")) | toks(r.get("parent_company"))) - toks(r.get("city"))
    best = None
    for p in plants:
        if p["state"].upper() != st:
            continue
        idt = toks(p["id"].replace("-", " ")) - toks(p["city"]) - {p["state"].lower(), "p"}
        pt = (toks(p["name"]) | toks(p["parent_company"]) | idt) - toks(p["city"])
        same_city = city(p["city"]) == city(r.get("city")) and city(r.get("city"))
        if (same_city and (at & pt)) or (at & pt and not city(r.get("city"))):
            best = p
            break
        if at & pt and best is None:
            best = ("maybe", p)
    if isinstance(best, dict):
        matched.append((r, best["id"], best["status"]))
    else:
        unmatched.append((r, best[1]["id"] if best else ""))

print(f"auditor rows: {len(audit)}; combined unique: {len(comb)}; in-definition: {len(matched) + len(unmatched)}; out: {len(out_def)}")
print(f"matched rows: {len(matched)} -> unique ledger plants: {len({i for _, i, _ in matched})}; unmatched (candidate misses): {len(unmatched)}")
for r, hint in unmatched:
    print(f"  MISS? [{r['_auditor']}] {r.get('name')} | {r.get('city')}, {r.get('state')} | {str(r.get('products'))[:60]} | same-company-other-city: {hint} | {r.get('url')}")
json.dump({"vertical": vert,
           "combined_in_definition": len(matched) + len(unmatched),
           "matched": [{"auditor_name": r.get("name"), "city": r.get("city"), "state": r.get("state"), "ledger_id": i, "ledger_status": s} for r, i, s in matched],
           "unmatched": [{k: v for k, v in r.items()} | {"hint_same_company_other_city": h} for r, h in unmatched],
           "out_of_definition": [{"name": r.get("name"), "city": r.get("city"), "state": r.get("state"), "why_not": r.get("why_not")} for r in out_def]},
          open(os.path.join(ROOT, "ledger", "audit", f"miss-candidates-{vert}.json"), "w"), indent=1)
