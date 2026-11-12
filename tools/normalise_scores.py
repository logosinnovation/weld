#!/usr/bin/env python3
"""Apply one scoring interpretation to every profiled plant (coordinator rule, 2026-11-12,
after advisor consultation 2).

Material & part fit (20):
  20 or 12 only when a part_size_fit evidence row for the plant quotes a dimension or
  weight of its welded parts (ft, in, lb, tons, ...; the fit judgment itself may be
  tagged inferred), or a cited claim comes from Path's own site (path-robotics.com)
  saying its cells weld that company's parts. 4 when an evidence row quotes
  aluminum-first or thin sheet. Otherwise 0
  (unknown size = unknown component = 0). A profiler's 20/12 is kept only if that test
  passes; otherwise it drops to 0.
Tightened 2026-11-12 after the fact-check (advisor consultation 3): company-level size
  evidence (a row the sweep marked company-level, or a Path page naming only the company)
  earns points only when a stated plant-level row places the product line (pole, mast arm,
  tower, sign or substation structure) at this plant; rows tagged unknown never count.
Confidence: number of components with points > 0 whose cited supporting claims
  (claim ids named in the <id>:score_<comp> reasoning) all have at least one evidence
  row tagged stated. Components with 0 points never count.
Tier: High 70+, Medium 45-69, Low <45.

Usage: python3 tools/normalise_scores.py [--apply] [--override id:component=points:reason ...]
Writes nothing without --apply. Prints every change.
"""
import csv
import re
import sys

L = "ledger/"
COMP = ["process", "material_part", "part_mix", "labor", "demand", "scale"]
DIM = re.compile(r"\d[\d,\.]*\s*(?:-|to)?\s*\d*[\d,\.]*\s*(?:ft|feet|foot|in\b|inch|inches|\"|lb|lbs|pound|ton|tons|mm|meter|m\b|')", re.I)
CID = re.compile(r"\b([pcv]-[a-z0-9-]+:[a-z_]+)")
TODAY = "2026-11-12"


def tier(t):
    return "High" if t >= 70 else ("Medium" if t >= 45 else "Low")


plants = list(csv.DictReader(open(L + "plants.csv")))
pcols = list(plants[0].keys())
ev = list(csv.DictReader(open(L + "evidence.csv")))
ecols = list(ev[0].keys())
by_claim = {}
for e in ev:
    by_claim.setdefault(e["claim_id"], []).append(e)
stated = {c for c, rows in by_claim.items() if any(r["tag"] == "stated" for r in rows)}

overrides = {}
args = sys.argv[1:]
for a in args:
    if a.startswith("--override="):
        k, v = a.split("=", 1)[1].split("=", 1)
        pts, why = v.split(":", 1)
        overrides[k] = (int(pts), why)

changes = []
for p in plants:
    if p["status"] != "profiled":
        continue
    pid = p["id"]
    sc = {c: int(float(p.get("score_" + c) or 0)) for c in COMP}
    old = dict(sc)
    old_total, old_conf = p.get("score_total"), p.get("confidence")
    # material rule
    mrows = [r for c in (f"{pid}:part_size_fit", f"{pid}:score_material_part", f"{pid}:materials")
             for r in by_claim.get(c, [])]
    size_rows = [r for r in by_claim.get(f"{pid}:part_size_fit", []) if r["quote"] and r["tag"] != "unknown"]
    city = p["city"].lower()
    PROD = re.compile(r"pole|mast|tower|sign|monopole|substation|structure", re.I)
    line_at_plant = any(r["tag"] == "stated" and PROD.search(r["quote"] or "")
                        for f in ("products", "weld_processes", "materials", "welder_postings", "production_type")
                        for r in by_claim.get(f"{pid}:{f}", []))
    def plant_level(r):
        return city in (r["quote"] or "").lower() or "company-level" not in (r["reasoning"] or "")
    has_dim = any(DIM.search(r["quote"] or "") and (plant_level(r) or line_at_plant) for r in size_rows)
    cited_m = set()
    for r in by_claim.get(f"{pid}:score_material_part", []):
        cited_m |= set(CID.findall(r["reasoning"] or ""))
    cited_m |= {f"{pid}:part_size_fit", f"{pid}:materials"}
    path_stmt = line_at_plant and any("path-robotics.com" in (r["source_url"] or "").lower()
                    for c in cited_m for r in by_claim.get(c, []))
    alum = any(r["quote"] and r["tag"] != "unknown" and re.search(r"alumin", (r["value"] or "") + (r["quote"] or ""), re.I)
               for r in by_claim.get(f"{pid}:materials", []))
    if sc["material_part"] in (20, 12) and not (has_dim or path_stmt):
        sc["material_part"] = 0
    if sc["material_part"] == 4 and not alum:
        sc["material_part"] = 0
    for k, (pts, why) in overrides.items():
        oid, comp = k.split(":")
        if oid == pid:
            sc[comp] = pts
    total = sum(sc.values())
    # confidence
    conf = 0
    for c in COMP:
        if sc[c] <= 0:
            continue
        rows = by_claim.get(f"{pid}:score_{c}", [])
        cited = set()
        for r in rows:
            cited |= set(CID.findall(r["reasoning"] or ""))
        cited.discard(f"{pid}:score_{c}")
        if cited and all(cid in stated for cid in cited):
            conf += 1
    new = {"score_" + c: str(sc[c]) for c in COMP}
    new.update(score_total=str(total), score_tier=tier(total), confidence=str(conf))
    diff = {k: (p.get(k), v) for k, v in new.items() if str(p.get(k)) != v}
    if diff:
        changes.append((pid, diff))
        p.update(new)
        if sc["material_part"] != old["material_part"]:
            note = (f" | Coordinator normalisation {TODAY}: material set to {sc['material_part']} "
                    f"(was {old['material_part']}); rule: 20/12 need a stated dimension/weight or Path's own statement; "
                    f"4 needs stated aluminum-first; unknown size = 0.")
            for r in by_claim.get(f"{pid}:score_material_part", []):
                r["value"] = str(sc["material_part"])
                r["reasoning"] = (r["reasoning"] or "") + note
        for k, (pts, why) in overrides.items():
            oid, comp = k.split(":")
            if oid == pid:
                for r in by_claim.get(f"{pid}:score_{comp}", []):
                    r["value"] = str(pts)
                    r["reasoning"] = (r["reasoning"] or "") + f" | Coordinator override {TODAY}: {why}"

for pid, diff in changes:
    print(pid, {k: f"{a}->{b}" for k, (a, b) in diff.items()})
print(f"# {len(changes)} plants changed")
prof = [p for p in plants if p["status"] == "profiled"]
print("# tiers:", {t: sum(1 for p in prof if p["score_tier"] == t) for t in ("High", "Medium", "Low")},
      "| material=0 (unknown size):", sum(1 for p in prof if p["score_material_part"] == "0"), "of", len(prof))
if "--apply" in args:
    with open(L + "plants.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pcols)
        w.writeheader()
        w.writerows(plants)
    with open(L + "evidence.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ecols)
        w.writeheader()
        w.writerows(ev)
    print("# applied")
