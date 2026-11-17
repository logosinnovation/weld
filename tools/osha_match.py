#!/usr/bin/env python3
"""Match ledger plants to OSHA ITA Form 300A 2025 establishments (data/osha_2025.csv). 2026-11-17.

Candidates share state and 5-digit ZIP with the plant. AUTO (accepted without review) needs every gate:
  - manufacturing NAICS (31-33)
  - same street number AND a shared street-name token (house number, suffixes and directions do not count)
  - a shared distinctive token between the OSHA establishment/company name and the plant's OPERATING name
    ("(former ...)" text removed; a parent-only overlap does not count; city, state and generic words never count)
  - exactly one such candidate for the plant, and no other plant claims the same OSHA record
  - the establishment name itself, if it carries a distinctive word, shares one with the plant (else it may be a
    subsidiary, a contractor or another business on the site)
  - plausible values: annual_average_employees > 0, hours per employee 500-4,000
REVIEW: a plant with a candidate that fails only some gates (same ZIP, manufacturing NAICS, a name overlap with the
operating name or parent), or an AUTO candidate with odd hours. Everything else is no match.
Writes ledger/audit/osha-matches.json. Usage: python3 tools/osha_match.py
"""
import csv, json, re
from collections import defaultdict, Counter

L = "ledger/"
STOP = set("inc llc co corp corporation company the of and ltd lp group usa us america american industries industry manufacturing mfg plant facility division div intl international holdings products services systems solutions technologies technology enterprises dba".split())
# words that say where or what, not who: never enough on their own to tie a record to a company
GENERIC = set("fabrication fabricators fabricating fabricated steel steels metal metals works power energy equipment machine machinery tank tanks structures structural plant yard shipyard shop campus north south east west new city county former headquarters hq main street road avenue drive boat boats marine general great tower towers pole poles utility electric engineering mining heavy truck trailer trailers service repair dry dock site building bldg facility fabrications fab".split())
STATES = set("al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii idaho illinois indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan minnesota mississippi missouri montana nebraska nevada ohio oklahoma oregon pennsylvania tennessee texas utah vermont virginia washington wisconsin wyoming".split())
STREET_GENERIC = set("st street rd road ave avenue dr drive hwy highway blvd boulevard ln lane pkwy parkway way ct court pl place cir circle trl trail n s e w ne nw se sw north south east west us state sr rt route co county fm suite ste unit bldg building".split())


def toks(s):
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if t not in STOP and len(t) > 1}


def operating_name(n):
    n = re.sub(r"\((?:[^)]*\b(?:former|formerly|previously|ex-)\b[^)]*)\)", " ", n or "", flags=re.I)
    return re.sub(r"\b(?:former|formerly)\b.*$", " ", n, flags=re.I)


def zip5(s):
    m = re.findall(r"\b(\d{5})(?:-\d{4})?\b", s or "")
    return m[-1] if m else ""


def stnum(s):
    m = re.match(r"\s*(\d+)", s or "")
    return m.group(1) if m else ""


def sttoks(s):
    first = (s or "").split(",")[0]
    first = re.sub(r"^\s*\d+[a-z]?\b", " ", first.lower())  # drop the house number
    return {t for t in re.findall(r"[a-z0-9]+", first) if t not in STREET_GENERIC}


def is_mfg(naics):
    return (naics or "")[:2] in ("31", "32", "33")


def main():
    osha = defaultdict(list)
    for r in csv.DictReader(open("data/osha_2025.csv")):
        osha[(r["state"], r["zip_code"])].append(r)
    plants = list(csv.DictReader(open(L + "plants.csv")))
    out, claim = [], defaultdict(list)
    for p in plants:
        z = zip5(p["address"])
        rec = {"id": p["id"], "status": p["status"], "name": p["name"], "address": p["address"], "headcount": p["headcount"]}
        if not z:
            rec.update(grade="no_zip", candidates=[]); out.append(rec); continue
        place = toks(p["city"]) | {p["state"].lower()} | STATES
        own = toks(operating_name(p["name"])) - place - GENERIC
        par = toks(p["parent_company"]) - place - GENERIC
        cands = []
        for r in osha.get((p["state"], z), []):
            C = toks(r["establishment_name"]) | toks(r["company_name"])
            o_own, o_par = sorted(own & C), sorted(par & C)
            if not (o_own or o_par):
                continue
            S = bool(stnum(p["address"])) and stnum(p["address"]) == stnum(r["street_address"])
            N = bool(sttoks(p["address"]) & sttoks(r["street_address"]))
            emp = int(r["annual_average_employees"] or 0)
            hrs = int(r["total_hours_worked"] or 0)
            hpe = hrs / emp if emp else 0
            fails = []
            if not is_mfg(r["naics_code"]): fails.append("naics_not_manufacturing")
            if not S: fails.append("street_number_differs")
            if not N: fails.append("street_name_differs")
            if not o_own: fails.append("parent_name_only")
            E = toks(r["establishment_name"]) - place - GENERIC
            if E and not (E & (own | par)): fails.append("establishment_named_otherwise")
            if emp <= 0: fails.append("zero_employees")
            elif not 500 <= hpe <= 4000: fails.append("odd_hours_per_employee")
            cands.append({"fails": fails, "own_overlap": o_own, "parent_overlap": o_par, "hours_per_employee": round(hpe),
                          **{k: r[k] for k in ("ID", "establishment_ID", "establishment_name", "company_name", "street_address", "city", "zip_code", "naics_code", "industry_description", "annual_average_employees", "total_hours_worked", "date_submitted")}})
        cands.sort(key=lambda c: (len(c["fails"]), -len(c["own_overlap"])))
        clean = [c for c in cands if not c["fails"]]
        if len(clean) == 1:
            grade = "auto"
        elif len(clean) > 1:
            grade = "review_several"
        elif any(is_mfg(c["naics_code"]) and c["own_overlap"] or (is_mfg(c["naics_code"]) and c["parent_overlap"] and "street_number_differs" not in c["fails"]) for c in cands):
            grade = "review"
        else:
            grade = "none"
        rec.update(grade=grade, candidates=cands[:6])
        if grade == "auto":
            claim[clean[0]["ID"]].append(p["id"])
        out.append(rec)
    dup = {i for i, ps in claim.items() if len(ps) > 1}
    for rec in out:
        if rec["grade"] == "auto" and [c for c in rec["candidates"] if not c["fails"]][0]["ID"] in dup:
            rec["grade"] = "review_shared_record"
    json.dump(out, open(L + "audit/osha-matches.json", "w"), indent=1)
    print(Counter((o["status"], o["grade"]) for o in out))


if __name__ == "__main__":
    main()
