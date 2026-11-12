#!/usr/bin/env python3
"""Validate an inbox JSON file and merge it into the ledger CSVs.

Usage:
  python3 tools/merge_inbox.py ledger/inbox/<file>.json [--dry-run] [--verify-quotes]

Inbox file: one JSON object with any of the keys verticals, plants, links,
evidence (lists of objects keyed by CSV column names). Extra keys are ignored
here and read by the coordinator.

Rules applied:
- evidence: tag in {stated, inferred, unknown}; source_type in the allowed set;
  quote <= 300 chars (trimmed and flagged if longer); stated rows need a
  source_url and a quote; inferred rows need reasoning. Bad rows are rejected
  and listed. Evidence is upserted on (claim_id, source_url).
- plants: upserted on id; a second record with the same normalised name +
  address under a different id is reported as a duplicate and merged into the
  first. Non-empty incoming values overwrite; empty ones never blank a field.
- links: upserted on (from_id, to_id, what_is_supplied).
- verticals: upserted on id.
- coverage: every non-empty plant value (for evidence-bearing fields) must have
  at least one evidence row with claim_id "<plant id>:<field>". Gaps are listed.
- --verify-quotes: re-fetch each stated source_url and check the quote appears
  (whitespace/quote-mark normalised). Misses are written to
  ledger/audit/quote-check-<inbox name>.json for the fact-checker. They are
  flagged, not dropped.
"""
import csv
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = os.path.join(ROOT, "ledger")
sys.path.insert(0, os.path.join(ROOT, "tools"))

TAGS = {"stated", "inferred", "unknown"}
STYPES = {"company site", "job posting", "news", "government file",
          "certification list", "trade association", "other"}
VERIFIED = {"not_checked", "confirmed", "corrected", "unreachable"}
EVIDENCE_FIELDS = ["name", "parent_company", "address", "website", "products", "tier",
                   "tier_secondary", "relationship", "lookalike_of", "headcount",
                   "exclusion_reason", "weld_processes", "materials", "certifications",
                   "part_size_fit", "production_type", "existing_robots", "welder_postings",
                   "triggers", "bottleneck_guess", "opening_line"]
FILES = {"verticals": "verticals.csv", "plants": "plants.csv",
         "links": "links.csv", "evidence": "evidence.csv"}


def read(name):
    p = os.path.join(L, FILES[name])
    with open(p, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def write(name, cols, rows):
    p = os.path.join(L, FILES[name])
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else str(r.get(c))) for c in cols})


def s(v):
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def nkey(name, addr):
    t = (name + "|" + addr).lower()
    t = re.sub(r"\b(inc|llc|corp|corporation|co|company|ltd|the)\b", "", t)
    return re.sub(r"[^a-z0-9|]", "", t)


def norm(x):
    x = x.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    x = x.replace("–", "-").replace("—", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", x).strip().lower()


def validate_evidence(rows):
    ok, bad = [], []
    for e in rows:
        e = {k: s(v) for k, v in e.items()}
        why = []
        e["tag"] = e.get("tag", "").lower()
        e["source_type"] = e.get("source_type", "").lower()
        if not e.get("claim_id") or ":" not in e["claim_id"]:
            why.append("claim_id missing or has no ':'")
        if e["tag"] not in TAGS:
            why.append(f"bad tag {e['tag']!r}")
        if e["tag"] != "unknown" and e["source_type"] not in STYPES:
            why.append(f"bad source_type {e['source_type']!r}")
        if e["tag"] == "stated" and (not e.get("source_url") or not e.get("quote")):
            why.append("stated claim without source_url or quote")
        if e["tag"] == "inferred" and not e.get("reasoning"):
            why.append("inferred claim without reasoning")
        if len(e.get("quote", "")) > 300:
            e["quote"] = e["quote"][:300]
            e["_flag"] = "quote trimmed to 300"
        e["verified"] = e.get("verified") or "not_checked"
        if e["verified"] not in VERIFIED:
            why.append(f"bad verified {e['verified']!r}")
        (bad if why else ok).append((e, why))
    return [e for e, _ in ok], [(e.get("claim_id"), w) for e, w in bad]


def verify_quotes(ev, label):
    from fetch_page import fetch
    stated = [e for e in ev if e["tag"] == "stated" and e.get("source_url") and e.get("quote")]
    urls = sorted({e["source_url"] for e in stated})
    pages = {}

    def get(u):
        try:
            st, txt, how = fetch(u)
            return u, (st, norm(txt), how)
        except Exception as ex:  # noqa: BLE001
            return u, (0, "", f"error {ex}")
    with ThreadPoolExecutor(8) as ex:
        for u, r in ex.map(get, urls):
            pages[u] = r
    res = []
    for e in stated:
        st, txt, how = pages[e["source_url"]]
        if not txt or st >= 400:
            verdict = "unreachable"
        elif norm(e["quote"]) in txt:
            verdict = "found"
        else:
            # allow '...' elisions: every fragment must be present
            frags = [f for f in re.split(r"\s*(?:\.\.\.|…)\s*", norm(e["quote"])) if len(f) > 8]
            verdict = "found" if frags and all(f in txt for f in frags) else "not_found"
        res.append({"claim_id": e["claim_id"], "source_url": e["source_url"], "status": st,
                    "via": how, "verdict": verdict, "quote": e["quote"]})
    out = os.path.join(L, "audit", f"quote-check-{label}.json")
    summary = {k: sum(1 for r in res if r["verdict"] == k) for k in ("found", "not_found", "unreachable")}
    with open(out, "w") as f:
        json.dump({"summary": summary, "rows": res}, f, indent=1)
    return summary, out


def main():
    a = sys.argv[1:]
    path = a[0]
    dry = "--dry-run" in a
    label = os.path.splitext(os.path.basename(path))[0]
    data = json.load(open(path, encoding="utf-8"))
    report = {"file": path}

    # evidence
    ecols, erows = read("evidence")
    ev_in, ev_bad = validate_evidence(data.get("evidence", []))
    report["evidence_in"] = len(data.get("evidence", []))
    report["evidence_rejected"] = ev_bad
    report["quotes_trimmed"] = [e["claim_id"] for e in ev_in if e.get("_flag")]
    idx = {(r["claim_id"], r["source_url"]): i for i, r in enumerate(erows)}
    added = 0
    for e in ev_in:
        k = (e["claim_id"], e.get("source_url", ""))
        if k in idx:
            erows[idx[k]].update({c: e[c] for c in ecols if e.get(c)})
        else:
            idx[k] = len(erows)
            erows.append(e)
            added += 1
    report["evidence_added"] = added

    # plants
    pcols, prows = read("plants")
    pid = {r["id"]: r for r in prows}
    pkey = {nkey(r["name"], r["address"]): r["id"] for r in prows if r.get("address")}
    dups, padded, pupd = [], 0, 0
    for p in data.get("plants", []):
        p = {k: s(v) for k, v in p.items()}
        if not p.get("id"):
            dups.append(("NO_ID", p.get("name")))
            continue
        k = nkey(p.get("name", ""), p.get("address", ""))
        target = p["id"]
        if p["id"] not in pid and p.get("address") and k in pkey:
            target = pkey[k]
            dups.append((p["id"], target))
        if target in pid:
            for c in pcols:
                if c != "id" and p.get(c):
                    pid[target][c] = p[c]
            pupd += 1
        else:
            row = {c: p.get(c, "") for c in pcols}
            prows.append(row)
            pid[target] = row
            if p.get("address"):
                pkey[k] = target
            padded += 1
    report.update(plants_added=padded, plants_updated=pupd, plant_duplicates=dups)

    # links
    lcols, lrows = read("links")
    lk = {(r["from_id"], r["to_id"], r["what_is_supplied"]) for r in lrows}
    ladd = 0
    for l in data.get("links", []):
        l = {k: s(v) for k, v in l.items()}
        k = (l.get("from_id"), l.get("to_id"), l.get("what_is_supplied"))
        if k not in lk:
            lrows.append(l)
            lk.add(k)
            ladd += 1
    report["links_added"] = ladd

    # verticals
    vcols, vrows = read("verticals")
    vid = {r["id"]: r for r in vrows}
    vadd = 0
    for v in data.get("verticals", []):
        v = {k: s(x) for k, x in v.items()}
        if v.get("id") in vid:
            vid[v["id"]].update({c: v[c] for c in vcols if v.get(c)})
        else:
            vrows.append(v)
            vid[v["id"]] = v
            vadd += 1
    report["verticals_added"] = vadd

    # coverage of incoming plants
    claims = {r["claim_id"] for r in erows}
    gaps = []
    for p in data.get("plants", []):
        for f in EVIDENCE_FIELDS:
            val = s(p.get(f))
            if val and val.lower() != "unknown" and f"{p.get('id')}:{f}" not in claims:
                gaps.append(f"{p.get('id')}:{f}")
    report["coverage_gaps"] = gaps
    unknown_ids = [l for l in data.get("links", []) if s(l.get("from_id")) not in pid or s(l.get("to_id")) not in pid]
    report["links_with_unknown_plant_ids"] = len(unknown_ids)

    if "--verify-quotes" in a:
        summ, out = verify_quotes(ev_in, label)
        report["quote_check"] = summ
        report["quote_check_file"] = out

    if not dry:
        write("evidence", ecols, erows)
        write("plants", pcols, prows)
        write("links", lcols, lrows)
        write("verticals", vcols, vrows)
    rep = dict(report)
    for k in ("evidence_rejected", "coverage_gaps", "plant_duplicates", "quotes_trimmed"):
        rep[k + "_count"] = len(rep[k])
        rep[k] = rep[k][:15]
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    with open(os.path.join(L, "audit", f"merge-{label}.json"), "w") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
