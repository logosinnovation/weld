#!/usr/bin/env python3
"""Attribute cross-vertical fact-check files (ledger/audit/fact-check-cross-*.json) to each vertical's summary. 2026-11-17.

tools/write_summary.py globs fact-check-<vertical>-*.json only, so checks run across verticals (state permits, job-board
dates, OSHA headcounts, profiles of OSHA top-40 entrants) were missing from every vertical's audit section. This script
reads every row of those files, keeps rows whose claim belongs to a plant tagged with the vertical, and writes them into
ledger/audit/summary-<vertical>.json as round 8 ("cross-vertical checks"), replacing any earlier round 8. It also
recounts plants.profiled_fact_checked to include plants checked in these files. It never touches other rounds,
the miss rate or the known limits (unlike a bare write_summary run).
Usage: python3 tools/summary_cross.py
"""
import csv, glob, json, os

pl = list(csv.DictReader(open("ledger/plants.csv")))
vert_of = {p["id"]: p["verticals"] for p in pl}
files = sorted(glob.glob("ledger/audit/fact-check-cross-*.json"))
rows = []
for f in files:
    for r in json.load(open(f)).get("rows", []):
        r["_file"] = os.path.basename(f)
        rows.append(r)
LABEL = "Cross-vertical checks (state air permits, job-board dates, OSHA headcounts, profiles of OSHA top-40 entrants): rows for this vertical's plants"
for sf in sorted(glob.glob("ledger/audit/summary-*.json")):
    vert = os.path.basename(sf)[len("summary-"):-5]
    d = json.load(open(sf))
    mine = [r for r in rows if vert in vert_of.get(r["claim_id"].split(":")[0], "") and r.get("verdict") in ("confirmed", "corrected", "unreachable")]
    rounds = [x for x in d.get("fact_check_rounds", []) if x.get("round") != 8]
    if mine:
        by = {}
        for r in mine:
            b = by.setdefault(r["_file"], {"file": r["_file"], "checked": 0, "corrected": 0, "kinds": {}})
            b["checked"] += 1
            if r["verdict"] == "corrected":
                b["corrected"] += 1
                k = r.get("error_kind") or "other"
                b["kinds"][k] = b["kinds"].get(k, 0) + 1
        chk = sum(b["checked"] for b in by.values()); cor = sum(b["corrected"] for b in by.values())
        unr = sum(1 for r in mine if r["verdict"] == "unreachable")
        rounds.append({"round": 8, "label": LABEL, "checked": chk, "corrected": cor, "unreachable": unr,
                       "checkers": list(by.values()), "rate": round(cor / chk, 4) if chk else None,
                       "display": f"{cor} / {chk} = {100 * cor / chk:.1f}%" if chk else "n/a"})
    d["fact_check_rounds"] = sorted(rounds, key=lambda x: x["round"])
    checked_ids = {r["claim_id"].split(":")[0] for r in mine}
    for g in glob.glob(f"ledger/audit/fact-check-{vert}-*.json"):
        checked_ids |= {r["claim_id"].split(":")[0] for r in json.load(open(g)).get("rows", [])}
    prof = [p for p in pl if vert in p["verticals"] and p["status"] == "profiled"]
    d["plants"]["profiled_fact_checked"] = sum(1 for p in prof if p["id"] in checked_ids)
    json.dump(d, open(sf, "w"), indent=1)
    r8 = [x for x in d["fact_check_rounds"] if x["round"] == 8]
    print(vert, r8[0]["display"] if r8 else "no cross rows", "| profiled fact-checked", d["plants"]["profiled_fact_checked"], "of", len(prof))
