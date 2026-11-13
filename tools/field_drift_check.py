#!/usr/bin/env python3
"""Flag plant fields whose process terms or numbers appear in no evidence row (value or
quote) for the same claim. Heuristic; prints candidates for a human or agent to fix.
Usage: python3 tools/field_drift_check.py [--all] [--json out.json]  (--all includes base records)"""
import csv, json, re, sys
TERMS = re.compile(r"\b(GMAW|MIG|FCAW|flux[- ]core|SAW|sub ?arc|submerged|TIG|GTAW|SMAW|stick|spray|pulse|robot\w*|cobot\w*|AWS|D1\.1|D1\.\d|ISO ?\d+|AISC|CWB)\b", re.I)
NUM = re.compile(r"\b\d[\d,\.]*\b")
FIELDS = ["weld_processes", "materials", "certifications", "headcount", "part_size_fit", "existing_robots",
          "welder_postings", "triggers", "products", "production_type"]
by = {}
for e in csv.DictReader(open("ledger/evidence.csv")):
    by.setdefault(e["claim_id"], []).append((e["value"] or "") + " " + (e["quote"] or "") + " " + (e["reasoning"] or ""))
out = []
for p in csv.DictReader(open("ledger/plants.csv")):
    if p["status"] not in (("profiled", "base") if "--all" in sys.argv else ("profiled",)):
        continue
    for f in FIELDS:
        v = p.get(f) or ""
        if not v or v.lower().startswith("unknown"):
            continue
        blob = " ".join(by.get(f"{p['id']}:{f}", [])).lower().replace(",", "")
        miss_t = sorted({t.lower() for t in TERMS.findall(v) if t.lower() not in blob})
        miss_n = sorted({n for n in NUM.findall(v.replace(",", "")) if n.strip(".") and n.strip(".") not in blob})
        if miss_t or miss_n:
            out.append({"id": p["id"], "field": f, "value": v[:200], "terms_unbacked": miss_t, "numbers_unbacked": miss_n})
for o in out:
    print(o["id"], o["field"], o["terms_unbacked"], o["numbers_unbacked"], "|", o["value"][:110])
print("#", len(out), "candidates")
if "--json" in sys.argv:
    json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
