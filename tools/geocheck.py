#!/usr/bin/env python3
"""Flag plants whose lat/lon is far from their recorded city, using Census Gazetteer
place / county-subdivision centroids (2024).
Usage: python3 tools/geocheck.py GAZ_DIR [--fix]
--fix: replace coordinates more than 25 km off with the city centroid (and Census county)."""
import csv, math, sys, re, requests
gdir = sys.argv[1]
cent = {}
for fn in ("2024_Gaz_cousubs_national.txt", "2024_Gaz_place_national.txt"):  # place overrides cousub
    for line in open(f"{gdir}/{fn}", encoding="latin-1").read().splitlines()[1:]:
        f = [x.strip() for x in line.split("\t")]
        name = re.sub(r"\s+(city|town|village|CDP|borough|township|municipality|city and borough|charter township)$", "", f[3 if fn.startswith('2024_Gaz_place') else 3])
        cent[(f[0], name.lower())] = (float(f[-2]), float(f[-1]))
def km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1]-a[1]); dp = p2-p1
    return 2*6371*math.asin(math.sqrt(math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2))
def county(lat, lon):
    j = requests.get("https://geocoding.geo.census.gov/geocoder/geographies/coordinates", params={"x": lon, "y": lat, "benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"}, timeout=30).json()
    c = j["result"]["geographies"]["Counties"][0]; return c["STATE"] + c["COUNTY"]
p = "ledger/plants.csv"; rows = list(csv.DictReader(open(p))); cols = list(rows[0].keys())
fix = "--fix" in sys.argv; changed = []
for r in rows:
    if not r["lat"]: print("NO_COORD", r["id"]); continue
    c = cent.get((r["state"], r["city"].lower().replace("st.", "saint").strip())) or cent.get((r["state"], r["city"].lower().strip()))
    if not c: print("NO_CITY_MATCH", r["id"], r["city"], r["state"]); continue
    d = km((float(r["lat"]), float(r["lon"])), c)
    if d > 25:
        print(f"FAR {d:.0f} km", r["id"], r["city"], r["state"], r["lat"], r["lon"], "->", c)
        if fix:
            r["lat"], r["lon"] = f"{c[0]:.6f}", f"{c[1]:.6f}"; r["county_fips"] = county(*c); changed.append(r["id"])
if fix and changed:
    w = csv.DictWriter(open(p, "w", newline=""), fieldnames=cols); w.writeheader(); w.writerows(rows); print("fixed", changed)
