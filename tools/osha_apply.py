#!/usr/bin/env python3
"""Apply OSHA ITA 300A 2025 headcounts from ledger/audit/osha-matches.json (tools/osha_match.py). 2026-11-17.

Applies only grade "auto" matches:
  - profiled plants with 100+ employees: stated headcount row; scale = the multi-plant half as already scored plus 5 for
    100+ at the site (only raises points; a current 5 whose half is unclear, or any lowering, goes to review)
  - base plants: stated headcount row only (no score)
Profiled plants under 100 employees, every lowering, and grades review / review_several / review_shared_record are
written to ledger/audit/osha-review-queue.json for a reviewer. Excluded plants are skipped.
Retires the plant's "unknown" headcount rows that the stated row supersedes. Writes data/osha_2025_cited.csv
(every cited OSHA record, all 14 kept columns). Prints the normaliser override arguments to a file.
Usage: python3 tools/osha_apply.py [--apply]
"""
import csv, json, re, sys
T = "2026-11-17"
L = "ledger/"
SRC = "https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data"
PROV = ("OSHA Injury Tracking Application Form 300A Summary Data, calendar year 2025, submissions through 2026-08-31 "
        "(source file ITA_300A_Summary_Data_2025_through_08-31-2026_2.csv per the conversion brief). Supplied by the user as a "
        "JSON conversion because osha.gov blocks this container; the source file's hash could not be verified here. "
        "Copy of the cited record: data/osha_2025_cited.csv. Matched by tools/osha_match.py (grade auto: same ZIP, street number "
        "and street name, manufacturing NAICS, the operating name shared, one candidate each way). Employer-reported annual average.")
STALE = re.compile(r"site headcount (unknown|not stated|only)|headcount unknown|headcount not stated|stale|company-level|company-wide|"
                   r"outside the window|not used|past the 36-month|site share unknown|is a target|no current s", re.I)

m = json.load(open(L + "audit/osha-matches.json"))
pl = list(csv.DictReader(open(L + "plants.csv"))); PC = list(pl[0].keys()); P = {p["id"]: p for p in pl}
ev = list(csv.DictReader(open(L + "evidence.csv"))); EC = list(ev[0].keys())
scale_rows = {}
for e in ev:
    if e["claim_id"].endswith(":score_scale"):
        scale_rows.setdefault(e["claim_id"].split(":")[0], []).append(e)

new_rows, overrides, review, cited, plan = [], [], [], {}, []
for x in m:
    i, p = x["id"], P.get(x["id"])
    if not p or p["status"] == "excluded":
        continue
    if x["grade"] != "auto":
        if x["grade"].startswith("review") and p["status"] == "profiled":
            review.append({"id": i, "why": x["grade"], "candidates": x["candidates"]})
        continue
    k = [c for c in x["candidates"] if not c["fails"]][0]
    emp = int(k["annual_average_employees"])
    act, new = "headcount_only", None
    if p["status"] == "profiled":
        cur = int(p["score_scale"] or 0)
        r = " | ".join(e["reasoning"] for e in scale_rows.get(i, []))
        if emp < 100:
            review.append({"id": i, "why": "under 100 employees (may be one building of a larger site)", "candidates": [k]}); continue
        if cur == 0:
            new, multi = 5, 0
        elif cur == 10:
            new, multi = 10, 5
        elif STALE.search(r):
            new, multi = 10, 5
        else:
            review.append({"id": i, "why": "current 5 with the earning half unclear", "candidates": [k]}); continue
        act = "raise" if new > cur else "keep"
        sup = re.findall(r"supporting claims:\s*([^|]*)", r)
        sup = ", ".join(sorted({s.strip(" ;.") for blob in sup for s in re.split(r"[;,]\s*", blob) if re.match(r"[pcv]-[a-z0-9-]+:[a-z_]+$", s.strip(" ;."))} - {i + ":headcount"}))
        if act == "raise":
            overrides.append(f"--override={i}:scale={new}:rubric {new}: " + ("multi-plant parent as scored before and " if multi else "no multi-plant parent scored; ")
                             + f"{emp} employees at the site (OSHA ITA Form 300A, 2025 annual average, record {k['ID']}); supporting claims: "
                             + ", ".join([s for s in [sup] if s] + [i + ":headcount"]))
    cited[k["ID"]] = k
    q = (f"ID {k['ID']}; establishment_name {k['establishment_name']}; company_name {k['company_name']}; street_address {k['street_address']}; "
         f"city {k['city']}; zip_code {k['zip_code']}; naics_code {k['naics_code']}; annual_average_employees {emp}; date_submitted {k['date_submitted']}")[:300]
    row = {c: "" for c in EC}
    row.update(claim_id=i + ":headcount", value=f"{emp} (2025 annual average, employer-reported to OSHA, Form 300A; establishment '{k['establishment_name']}', {k['street_address']})",
               tag="stated", quote=q, source_url=SRC, source_type="government file", retrieved_date=T, reasoning=PROV,
               produced_by="coordinator (osha_apply)", verified="not_checked")
    new_rows.append(row)
    plan.append({"id": i, "status": p["status"], "emp": emp, "act": act, "new_scale": new, "osha_id": k["ID"], "establishment": k["establishment_name"]})

print(f"headcount rows {len(new_rows)}; scale raises {len(overrides)}; review queue {len(review)}")
json.dump(review, open(L + "audit/osha-review-queue.json", "w"), indent=1)
json.dump(plan, open(L + "audit/osha-apply-plan.json", "w"), indent=1)
open(L + "audit/osha-scale-overrides.txt", "w").write("\n".join(overrides) + "\n")
if "--apply" in sys.argv:
    ids = {r["claim_id"] for r in new_rows}
    keep, retired = [], []
    for e in ev:
        if e["claim_id"] in ids and e["tag"] == "unknown":
            retired.append(e)
        else:
            keep.append(e)
    rc = L + "audit/retired-evidence.csv"; rr = list(csv.DictReader(open(rc))); RC = list(rr[0].keys())
    for e in retired:
        y = {c: e.get(c, "") for c in RC}; y["retired_why"] = f"coordinator {T}: superseded by a stated OSHA 300A 2025 headcount row"; y["retired_by"] = "coordinator (osha_apply)"; rr.append(y)
    w = csv.DictWriter(open(rc, "w", newline=""), fieldnames=RC); w.writeheader(); w.writerows(rr)
    w = csv.DictWriter(open(L + "evidence.csv", "w", newline=""), fieldnames=EC); w.writeheader(); w.writerows(keep + new_rows)
    for r in new_rows:
        P[r["claim_id"].split(":")[0]]["headcount"] = r["value"].split(" (")[0] + " (OSHA 300A, 2025 annual average)"
    w = csv.DictWriter(open(L + "plants.csv", "w", newline=""), fieldnames=PC); w.writeheader(); w.writerows(pl)
    keepcols = list(next(csv.reader(open("data/osha_2025.csv"))))
    with open("data/osha_2025_cited.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keepcols); w.writeheader()
        for r in csv.DictReader(open("data/osha_2025.csv")):
            if r["ID"] in cited: w.writerow(r)
    print(f"applied: {len(new_rows)} rows added, {len(retired)} unknown rows retired; data/osha_2025_cited.csv written")
