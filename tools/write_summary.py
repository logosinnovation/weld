#!/usr/bin/env python3
"""Write ledger/audit/summary-<vertical>.json (one file per vertical): the audit figures the map shows, computed from the
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


LABELS_BY_VERT = {}
LABELS_BY_VERT["v-shipbuilding-naval"] = {1: "Round 1: all 39 profiled plants (three checkers), after profiling",
                                          2: "Round 2: closure pass (new profiles, fill-ins and new base records)",
                                          7: "Round 7: line check of all 51 profiled plants' lines after constrained rewriting (validator-gated), checkers who did not write them",
                                          9: "Base-record sample: 25 of 83 base records, seeded (reported separately; not a profile round)"}
LABELS_BY_VERT["v-mining-heavy-equipment"] = {1: "Round 1: the 40 profiled plants (after the parallel list audit)",
                                              2: "Round 2: confirming round, all 47 profiled plants, checkers rotated (after the sweep)",
                                              3: "Round 3: the 21 profiles added in the last waves (profilers G, H, I and J)",
                                              4: "Round 4: the two OSHA-closure plants profiled into the top 40 after the R3 audit (Kafka Mosinee, Laidig Mishawaka)",
                                              6: "Round 6: line check of all 71 profiled plants' lines after constrained rewriting (validator-gated), three checkers who did not write them",
                                              7: "Targeted sweep, not a sample: 64 rows flagged by tools/sweep_company_level.py because they looked company-level (rate not comparable with the sampled rounds)",
                                              9: "Base-record samples: 25 closure-3 base records, and 25 of the 51 records added on 2026-11-17 by closure 5 and the R3 miss verification (reported separately; not a profile round)"}
LABELS_BY_VERT["v-enclosures-battery-generator"] = {1: "Round 1: the 40 top-ranked plants profiled (four checkers, one per profiler batch)",
                                                    2: "Round 2: the 18 plants that entered the top 40 after the audit, leads and job-board sweeps, and the written-key re-rank",
                                                    3: "Round 3: line check of every High and Medium plant's opening line and bottleneck guess (70 lines), after the rulings",
                                                    4: "Round 4: confirming pass by other checkers: 44 rewritten and unchecked lines, 9 posting fields, 25 job-posting product rows",
                                                    5: "Round 5: line check of all 48 profiled plants' lines after constrained rewriting (validator-gated), two checkers who did not write them",
                                                    2: "Round 2: line check of every High and Medium plant's opening line and bottleneck guess (72 lines, two checkers who did not write them); 7 of the 11 corrections were blank map fields whose evidence text was right: text errors 4 / 72 = 5.6%",
                                              9: "Base-record sample: 16 base and 6 excluded records (reported separately; not a profile round)"}
LABELS_BY_VERT["v-datacenter-grid-prefab"] = {1: "Round 1: every profiled plant (six checkers, one per profiler batch, on the unmerged profiler files)",
                                              2: "Round 2: line check of every High and Medium plant's opening line and bottleneck guess (72 lines, two checkers who did not write them); 7 of the 11 corrections were blank map fields whose evidence text was right: text errors 4 / 72 = 5.6%",
                                              9: "Base-record sample: 14 of 39 base and 8 of 61 excluded records from closure 3 and the miss verifications, 20 of the sweep's 144 rows and the coordinator's 9 ruling rows, seeded (reported separately; not a profile round)"}
LABELS = {1: "Round 1: designed sample of 30 plants (all High, all customer plants, then by score), before repairs",
          2: "Round 2: 10 unsampled plants from multi-plant parents, after the first repair pass",
          3: "Round 3: all 23 plants no checker had seen, after the attribution clean-up",
          4: "Round 4: 32 plants added or changed by the first higher-tier review, after the attribution clean-up",
          5: "Round 5: 9 plants whose points changed in the final higher-tier review, plus 6 new addresses",
          7: "Round 7: line check of all 81 profiled plants' lines after constrained rewriting (validator-gated), checkers who did not write them"}
LABELS = LABELS_BY_VERT.get(vert, LABELS)
rounds = {}
for f in sorted(glob.glob(f"ledger/audit/fact-check-{vert}-*.json")):
    base = os.path.basename(f)
    m = re.search(r"round(\d)", base) or re.search(r"-R(\d)-", base)
    rnd = int(m.group(1)) if m else (9 if "-CS-" in base else 1)  # -CS- = base-record sample, kept out of round 1
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
json.dump(out, open(f"ledger/audit/summary-{vert}.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in ("status", "plants", "links")}, indent=0))
for r in out["fact_check_rounds"]:
    print(r["round"], r["display"])
