#!/usr/bin/env python3
"""Mechanical check of opening lines and bottleneck guesses before a human-style line check. 2026-11-17.

For each line (from an inbox file's evidence rows, or from the ledger for a vertical's profiled plants):
  - its reasoning must cite at least one claim id (p-...:field or c-...:field)
  - every cited claim must exist in evidence.csv (or in the inbox file) with at least one STATED row
  - every number and date written in the line (digits, with , . / - kept) must appear in the value or quote of
    some row of a cited claim, or in that row's retrieved/source date
  - the words "posted", "currently", "is hiring", "now hiring", "are open" are flagged (constrained wording uses
    "listed <date>" and dated facts)
  - an opening line must end with a question containing "you"
Usage: python3 tools/validate_lines.py --inbox ledger/inbox/lines-X.json
       python3 tools/validate_lines.py --vertical v-enclosures-battery-generator [--tiers High,Medium]
Exit 1 if any line fails; prints one line per failure.
"""
import csv, json, re, sys

ID_RE = re.compile(r"\b([pcv]-[a-z0-9-]+:[a-z_]+)")
NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")
FLAG = re.compile(r"\b(posted|currently|is hiring|now hiring|are open|still open)\b", re.I)
MONTHS = "january february march april may june july august september october november december".split()


def norm_nums(s):
    out = set()
    for y, mo, d in re.findall(r"\b(20\d\d)-(\d\d)-(\d\d)\b", s or ""):  # ISO dates: the day and month as written in prose
        out.update({y, str(int(mo)), str(int(d))})
    for n in NUM_RE.findall(s or ""):
        n = n.strip("$%").replace(",", "")
        if n:
            out.add(n.rstrip("0").rstrip(".") if "." in n else n)
    return out


def main():
    a = sys.argv[1:]
    ev = list(csv.DictReader(open("ledger/evidence.csv")))
    by = {}
    for e in ev:
        by.setdefault(e["claim_id"], []).append(e)
    lines = []
    if "--inbox" in a:
        d = json.load(open(a[a.index("--inbox") + 1]))
        rm = {(r["claim_id"], r.get("source_url", "")) for r in d.get("evidence_remove", [])}
        for k in list(by):
            by[k] = [e for e in by[k] if (e["claim_id"], e["source_url"]) not in rm]
        for e in d.get("evidence", []):
            by.setdefault(e["claim_id"], []).append(e)
        lines = [e for e in d.get("evidence", []) if e["claim_id"].endswith((":opening_line", ":bottleneck_guess"))]
    else:
        vert = a[a.index("--vertical") + 1]
        tiers = (a[a.index("--tiers") + 1].split(",") if "--tiers" in a else ["High", "Medium", "Low"])
        pl = [p for p in csv.DictReader(open("ledger/plants.csv")) if vert in p["verticals"] and p["status"] == "profiled" and p["score_tier"] in tiers]
        for p in pl:
            for f in ("opening_line", "bottleneck_guess"):
                rows = [e for e in by.get(f"{p['id']}:{f}", []) if e["value"] == p[f]] or by.get(f"{p['id']}:{f}", [])[-1:]
                lines += rows
    fails, n = 0, 0
    for e in lines:
        v = e["value"] or ""
        if not v or v.lower().startswith("unknown"):
            continue
        n += 1
        probs = []
        cited = [c for c in ID_RE.findall(e.get("reasoning") or "") if not c.endswith((":opening_line", ":bottleneck_guess"))]
        if not cited:
            probs.append("cites no claim ids")
        pool = ""
        for c in cited:
            rows = by.get(c, [])
            if not rows:
                probs.append(f"cited claim missing: {c}")
            elif not any(r["tag"] == "stated" for r in rows):
                probs.append(f"cited claim has no stated row: {c}")
            pool += " ".join((r["value"] or "") + " " + (r["quote"] or "") for r in rows) + " "
        pool_n = norm_nums(pool)
        for num in norm_nums(v):
            if num not in pool_n and not (len(num) == 4 and num.startswith("20") and num in pool):
                probs.append(f"number not on a cited row: {num}")
        if FLAG.search(v):
            probs.append(f"wording: '{FLAG.search(v).group(0)}'")
        if e["claim_id"].endswith(":opening_line") and not (v.rstrip().endswith("?") and re.search(r"\byou(r)?\b", v.split(";")[-1] if ";" in v else v, re.I)):
            probs.append("does not end with a 'you' question")
        if probs:
            fails += 1
            print(f"FAIL {e['claim_id']}: " + "; ".join(sorted(set(probs))))
    print(f"# {n} text lines checked, {fails} failing")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
