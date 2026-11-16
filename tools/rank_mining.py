#!/usr/bin/env python3
"""Rank a vertical's base and profiled plants by the coordinator's documented key
(relationship, tier, stated welder_postings rows capped at 3, headcount, number of sources)
and show where given plant ids fall.

Usage: python3 tools/rank_mining.py v-mining-heavy-equipment [--top N] [--mark id1,id2] [--base-only]
"""
import csv, re, sys
from collections import defaultdict
vert = sys.argv[1]
args = sys.argv[2:]
top = int(args[args.index("--top") + 1]) if "--top" in args else 60
mark = set(args[args.index("--mark") + 1].split(",")) if "--mark" in args else set()
pl = [r for r in csv.DictReader(open("ledger/plants.csv")) if vert in r["verticals"]]
ev = list(csv.DictReader(open("ledger/evidence.csv")))
post, src = defaultdict(int), defaultdict(set)
for r in ev:
    pid = r["claim_id"].split(":")[0]
    if r["claim_id"].endswith(":welder_postings") and r["tag"] == "stated":
        post[pid] += 1
    if r["source_url"]:
        src[pid].add(r["source_url"])
REL = {"known_customer": 0, "customer_other_plant": 1, "lookalike": 2, "new": 3}
TIER = {"OEM": 0, "Tier 1": 1}
def hc(s):
    m = re.search(r"[\d,]{2,}", s or "")
    return int(m.group(0).replace(",", "")) if m else 0
cand = [p for p in pl if p["status"] in ("base", "profiled") and ("--base-only" not in args or p["status"] == "base")]
cand.sort(key=lambda p: (REL.get(p["relationship"], 4), TIER.get(p["tier"], 2), -min(post[p["id"]], 3),
                         -hc(p["headcount"]), -len(src[p["id"]])))
for i, p in enumerate(cand, 1):
    if i <= top or p["id"] in mark:
        print(i, "*" if p["id"] in mark else " ", p["status"][:4], p["id"], p["relationship"], p["tier"],
              "posts", post[p["id"]], "score", p["score_total"] or "-")
