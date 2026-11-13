#!/usr/bin/env python3
"""Write ledger/audit/summary.json: the audit figures the map shows, computed from the
ledger and audit files (not parsed from run_log prose).

Usage: python3 tools/write_summary.py v-poles-substation [--miss "5/64 = 7.8%"] [--miss-note "..."]
       [--miss-history "a|b|c"] [--limit "..."]...
Fact-check rounds: files ledger/audit/fact-check-<vertical>-{1,2,3}.json = round 1;
-round2-*.json = round 2; -round3-*.json = round 3; -round4-*.json = round 4.
"""
import csv
import glob
import json
import os
import re
import sys
from collections import Counter

vert = sys.argv[1]
args = sys.argv[2:]


def opt(name, many=False):
    vals = [args[i + 1] for i, a in enumerate(args) if a == name and i + 1 < len(args)]
    return vals if many else (vals[-1] if vals else None)


LABELS = {1: "Round 1: designed sample of 30 plants (all High, all customer plants, then by score), before repairs",
          2: "Round 2: 10 unsampled plants from multi-plant parents, after the first repair pass",
          3: "Round 3: all 23 plants no checker had seen, after the attribution clean-up",
          4: "Round 4: plants added or changed after the higher-tier review"}
rounds = {}
for f in sorted(glob.glob(f"ledger/audit/fact-check-{vert}-*.json")):
    base = os.path.basename(f)
    m = re.search(r"round(\d)", base)
    rnd = int(m.group(1)) if m else 1
    d = json.load(open(f))
    r = rounds.setdefault(rnd, {"round": rnd, "label": LABELS.get(rnd, f"Round {rnd}"), "checked": 0, "corrected": 0,
                                "unreachable": 0, "checkers": []})
    r["checked"] += int(d.get("claims_checked", 0))
    r["corrected"] += int(d.get("claims_corrected", 0))
    r["unreachable"] += int(d.get("claims_unreachable", 0))
    r["checkers"].append({"file": base, "checked": d.get("claims_checked"), "corrected": d.get("claims_corrected"),
                          "kinds": d.get("error_kind_counts", {})})
for r in rounds.values():
    r["rate"] = round(r["corrected"] / r["checked"], 4) if r["checked"] else None
    r["display"] = f"{r['corrected']} / {r['checked']} = {100 * r['rate']:.1f}%" if r["checked"] else "n/a"

plants = [p for p in csv.DictReader(open("ledger/plants.csv")) if vert in p["verticals"]]
st = Counter(p["status"] for p in plants)
prof = [p for p in plants if p["status"] == "profiled"]
checked_ids = set()
for f in glob.glob(f"ledger/audit/fact-check-{vert}-*.json"):
    for row in json.load(open(f)).get("rows", []):
        checked_ids.add(row["claim_id"].split(":")[0])
v = next((r for r in csv.DictReader(open("ledger/verticals.csv")) if r["id"] == vert), {})
out = {
    "vertical": vert,
    "status": v.get("status"),
    "plants": {"found": len(plants), "included": st["base"] + st["profiled"], "profiled": st["profiled"],
               "excluded": st["excluded"],
               "tiers": dict(Counter(p["score_tier"] for p in prof)),
               "profiled_fact_checked": sum(1 for p in prof if p["id"] in checked_ids),
               "material_unknown": sum(1 for p in prof if p["score_material_part"] == "0")},
    "links": sum(1 for _ in csv.DictReader(open("ledger/links.csv"))),
    "evidence_rows": sum(1 for _ in csv.DictReader(open("ledger/evidence.csv"))),
    "fact_check_rounds": [rounds[k] for k in sorted(rounds)],
    "miss_rate": {"value": opt("--miss"), "note": opt("--miss-note"),
                  "history": (opt("--miss-history") or "").split("|") if opt("--miss-history") else []},
    "known_limits": opt("--limit", many=True),
}
json.dump(out, open("ledger/audit/summary.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in ("status", "plants", "links")}, indent=0))
for r in out["fact_check_rounds"]:
    print(r["round"], r["display"])
