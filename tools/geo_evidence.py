#!/usr/bin/env python3
"""Add evidence rows for plant coordinates that have none (ground rule 1), 2026-11-17.

For each plant whose lat, lon or county_fips has a value but no evidence row, query the
Census Geocoder with the recorded street address:
- match within 1.5 km of the stored point: inferred rows citing the geocoder query URL,
  quote = the matched address, value = the stored value (unchanged);
- match farther away: the stored point is kept and the row records both points and the
  distance (flagged in the report for a human);
- no match or no street address: an inferred row saying the point is approximate
  (city-level or from another registry), with no source URL.
Usage: python3 tools/geo_evidence.py [--apply] [--json report.json]
"""
import csv, json, math, sys, time, urllib.parse, datetime
import requests

TODAY = datetime.date.today().isoformat()
L = "ledger/"
pl = list(csv.DictReader(open(L + "plants.csv")))
ev = list(csv.DictReader(open(L + "evidence.csv")))
EC = list(ev[0].keys())
have = {e["claim_id"] for e in ev}


def km(a, b, c, d):
    r = math.radians
    x = math.sin(r(c - a) / 2) ** 2 + math.cos(r(a)) * math.cos(r(c)) * math.sin(r(d - b) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(x))


def geocode(addr):
    q = urllib.parse.quote(addr)
    url = (f"https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address={q}"
           "&benchmark=Public_AR_Current&vintage=Current_Current&format=json")
    for attempt in range(3):
        try:
            j = requests.get(url, timeout=30).json()
            m = j["result"]["addressMatches"]
            if not m:
                return url, None
            m = m[0]
            cty = m["geographies"].get("Counties", [{}])[0].get("GEOID", "")
            return url, (m["matchedAddress"], float(m["coordinates"]["y"]), float(m["coordinates"]["x"]), cty)
        except Exception:
            time.sleep(2 + attempt * 3)
    return url, "error"


def row(cid, val, tag, quote, url, reasoning):
    r = {k: "" for k in EC}
    r.update(claim_id=cid, value=val, tag=tag, quote=quote, source_url=url,
             source_type="government file" if url else "other", retrieved_date=TODAY,
             reasoning=reasoning, produced_by="coordinator (geo_evidence)", verified="not_checked")
    return r


new, report = [], []
for p in pl:
    need = [f for f in ("lat", "lon", "county_fips") if p[f] and f"{p['id']}:{f}" not in have]
    if not need:
        continue
    addr = p["address"]
    street = addr and not addr.lower().startswith("unknown") and any(ch.isdigit() for ch in addr.split(",")[0])
    clean = addr.split("[")[0].split(" (")[0].strip() if street else ""
    res, url = None, ""
    if clean:
        url, res = geocode(clean)
        time.sleep(0.3)
    try:
        lat, lon = float(p["lat"]), float(p["lon"])
    except ValueError:
        lat = lon = None
    if res and res != "error" and lat is not None:
        mad, glat, glon, gcty = res
        d = km(lat, lon, glat, glon)
        if d <= 1.5:
            why = f"Census Geocoder API response for the recorded street address (query result, not quote-checkable); stored point within {d:.2f} km of the match"
            if "county_fips" in need and gcty and gcty != p["county_fips"]:
                why += f"; NOTE geocoder county {gcty} differs from stored {p['county_fips']}"
                report.append({"id": p["id"], "issue": "county differs", "stored": p["county_fips"], "geocoder": gcty})
            for f in need:
                new.append(row(f"{p['id']}:{f}", p[f], "inferred", f"Census Geocoder matched address: {mad}", url, why))
            continue
        report.append({"id": p["id"], "issue": f"stored point {d:.1f} km from geocoder match", "matched": mad,
                       "geocoder": [glat, glon, gcty], "stored": [lat, lon, p["county_fips"]]})
        why = (f"Stored point kept; the Census Geocoder matches the recorded address {d:.1f} km away "
               f"({glat:.6f},{glon:.6f}, county {gcty}). The stored point came from another registry or a manual placement; flagged for review.")
        for f in need:
            new.append(row(f"{p['id']}:{f}", p[f], "inferred", f"Census Geocoder matched address: {mad}", url, why))
        continue
    reason = ("approximate point: no street address on record, so the point is city-level"
              if not clean else "approximate point: the Census Geocoder found no match for the recorded street address")
    report.append({"id": p["id"], "issue": reason})
    for f in need:
        new.append(row(f"{p['id']}:{f}", p[f], "inferred", "", url if clean else "",
                       reason + "; value as placed by the agent that wrote the base record (city centroid or registry point)"))

print(f"rows to add: {len(new)}; flagged: {len(report)}")
if "--json" in sys.argv:
    json.dump(report, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
if "--apply" in sys.argv:
    cur = list(csv.DictReader(open(L + "evidence.csv")))  # re-read: other merges may have landed meanwhile
    now = {e["claim_id"] for e in cur}
    add = [r for r in new if r["claim_id"] not in now]
    w = csv.DictWriter(open(L + "evidence.csv", "w", newline=""), fieldnames=EC)
    w.writeheader(); w.writerows(cur + add)
    print(f"appended {len(add)}")
    print("applied")
