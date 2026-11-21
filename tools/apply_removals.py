#!/usr/bin/env python3
"""Retire evidence rows listed under an inbox file's "evidence_remove" key.

Usage: python3 tools/apply_removals.py ledger/inbox/<file>.json [--apply]
Each entry {claim_id, source_url, why} removes the evidence row(s) with that exact
(claim_id, source_url) pair. A blank source_url matches only rows whose source_url is
blank. Removed rows are appended to ledger/audit/retired-evidence.csv with the reason,
so nothing disappears without a trace (ground rule 7 spirit).
"""
import csv
import json
import os
import sys

f = sys.argv[1]
rem = json.load(open(f)).get("evidence_remove", [])
ev = list(csv.DictReader(open("ledger/evidence.csv")))
cols = list(ev[0].keys())
want = {(r["claim_id"], r.get("source_url", "")): r.get("why", "") for r in rem}
keep, gone, hit = [], [], set()
for e in ev:
    k = (e["claim_id"], e["source_url"])
    if k in want:
        gone.append(dict(e, retired_why=want[k], retired_by=os.path.basename(f)))
        hit.add(k)
    else:
        keep.append(e)
miss = [k for k in want if k not in hit]
print(f"{f}: {len(rem)} listed, {len(gone)} rows removed, {len(miss)} not found")
for k in miss:
    print("  NOT FOUND", k[0], k[1][:90])
if "--apply" in sys.argv:
    with open("ledger/evidence.csv", "w", newline="") as o:
        w = csv.DictWriter(o, fieldnames=cols)
        w.writeheader()
        w.writerows(keep)
    path = "ledger/audit/retired-evidence.csv"
    new = not os.path.exists(path)
    with open(path, "a", newline="") as o:
        w = csv.DictWriter(o, fieldnames=cols + ["retired_why", "retired_by"])
        if new:
            w.writeheader()
        w.writerows(gone)
    print("applied")
