#!/usr/bin/env python3
"""Rank a vertical's included (base) plants for profiling, per CLAUDE.md step 5.

Order: relationship (customer_other_plant, lookalike first; known_customer is
profiled as an extra), then tier (OEM, Tier 1 first), then open welder
postings, headcount, number of finding sources.

Usage: python3 tools/rank_for_profiling.py v-poles-substation [N]
Prints a ranked TSV: rank, id, name, city, state, relationship, tier, postings, headcount, n_sources
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vert = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 40

REL = {"customer_other_plant": 0, "lookalike": 0, "known_customer": 0, "new": 1}
TIER = {"OEM": 0, "Tier 1": 0}


def postings(v):
    v = (v or "").lower()
    if not v or "none" in v or v == "unknown":
        return 0
    m = re.search(r"(\d+)", v)
    return int(m.group(1)) if m else 1


def headcount(v):
    nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", v or "")]
    return max(nums) if nums else 0


rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "ledger", "plants.csv")))
        if vert in r["verticals"] and r["status"] in ("base", "profiled")]
rows.sort(key=lambda r: (REL.get(r["relationship"], 2), TIER.get(r["tier"], 1),
                         -postings(r["welder_postings"]), -headcount(r["headcount"]),
                         -len([x for x in r["found_by"].split(";") if x.strip()])))
print("rank\tid\tname\tcity\tstate\trelationship\ttier\tpostings\theadcount\tn_sources")
for i, r in enumerate(rows[:n], 1):
    print(f"{i}\t{r['id']}\t{r['name']}\t{r['city']}\t{r['state']}\t{r['relationship']}\t{r['tier']}\t"
          f"{postings(r['welder_postings'])}\t{r['headcount']}\t{len(r['found_by'].split(';'))}")
print(f"# included plants in vertical: {len(rows)}")
