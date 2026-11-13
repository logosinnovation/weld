#!/usr/bin/env python3
"""Apply fact-checker verdicts to the ledger.

Usage: python3 tools/apply_factcheck.py ledger/audit/fact-check-<vertical>-*.json [--apply]

- evidence.csv: rows matched on (claim_id, source_url) get verified = confirmed /
  corrected / unreachable. Corrected rows take corrected_value, corrected_quote and
  corrected_tag (an "unknown" correction clears the quote and sets tag unknown). The
  original value is kept in reasoning ("fact-check 2026-11-12: was ...").
- plants.csv: when a corrected claim's field is a plants.csv column, the plant's field
  takes the corrected value.
- Prints every score component (<id>:score_*) whose reasoning cites a corrected claim,
  so the coordinator can re-score it.
"""
import csv
import json
import re
import sys

TODAY = "2026-11-12"
files = [a for a in sys.argv[1:] if not a.startswith("--")]
rows = []
for f in files:
    d = json.load(open(f))
    for r in d.get("rows", []):
        r["_file"] = f
        rows.append(r)
ev = list(csv.DictReader(open("ledger/evidence.csv")))
ecols = list(ev[0].keys())
pl = list(csv.DictReader(open("ledger/plants.csv")))
pcols = list(pl[0].keys())
pid = {p["id"]: p for p in pl}
idx = {}
for i, e in enumerate(ev):
    idx.setdefault((e["claim_id"], e["source_url"]), []).append(i)
    idx.setdefault((e["claim_id"], ""), []).append(i)

unmatched, corrected_claims, counts = [], set(), {"confirmed": 0, "corrected": 0, "unreachable": 0}
for r in rows:
    v = r.get("verdict")
    if v not in counts:
        continue
    counts[v] += 1
    hits = idx.get((r["claim_id"], r.get("source_url", ""))) or idx.get((r["claim_id"], ""), [])
    if not hits:
        unmatched.append((r["claim_id"], r.get("source_url", "")[:80]))
        continue
    for i in hits:
        e = ev[i]
        e["verified"] = v
        if v == "corrected":
            cv = (r.get("corrected_value") or "").strip()
            old = e["value"]
            if cv:
                e["value"] = cv
            cq = (r.get("corrected_quote") or "").strip()
            cu = (r.get("corrected_source_url") or "").strip()
            if cu.startswith("http"):
                e["source_url"] = cu
            if cv.lower() == "unknown" or cq.lower() == "unknown":
                e["tag"] = "unknown"
                e["quote"] = ""
            else:
                if cq:
                    e["quote"] = cq[:300]
                if r.get("corrected_tag") in ("stated", "inferred", "unknown"):
                    e["tag"] = r["corrected_tag"]
            e["reasoning"] = (e["reasoning"] + " | " if e["reasoning"] else "") + \
                f"fact-check {TODAY}: was '{old[:120]}'; {r.get('error_kind', '')}; {r.get('note', '')[:200]}"
            if e["tag"] == "inferred" and not e["reasoning"]:
                e["reasoning"] = "fact-check correction"
            corrected_claims.add(r["claim_id"])
            pid_, field = r["claim_id"].split(":", 1)
            if pid_ in pid and field in pcols and cv:
                pid[pid_][field] = cv
        if len(hits) > 1 and r.get("source_url"):
            break

cid = re.compile(r"\b([pcv]-[a-z0-9-]+:[a-z_]+)")
affected = []
for e in ev:
    if ":score_" in e["claim_id"]:
        cited = set(cid.findall(e["reasoning"] or ""))
        hit = cited & corrected_claims
        if hit:
            affected.append((e["claim_id"], e["value"], sorted(hit)))
print(json.dumps(counts), "| rows:", len(rows), "| unmatched:", len(unmatched))
for u in unmatched[:20]:
    print("  UNMATCHED", u)
print("score components citing corrected claims:")
for a in affected:
    print("  ", a)
if "--apply" in sys.argv:
    for name, cols, data in (("evidence", ecols, ev), ("plants", pcols, pl)):
        with open(f"ledger/{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(data)
    print("applied")
