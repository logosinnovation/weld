#!/usr/bin/env python3
"""Stage G: rebuild map/index.html from the whole ledger. Offline, no manual steps.

    python3 tools/build_map.py

Reads  ledger/{verticals,plants,links,evidence}.csv, ledger/run_log.md, ledger/audit/*.json
Reads  tools/map_template.html (page shell, CSS, JS) and tools/assets/states-10m.json
       (us-atlas@3.0.1, cached from cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json)
Writes map/index.html (one self-contained page; d3 7.9.0 from cdnjs is the only external script).
The script never edits the ledger and adds no data: it only reshapes what the ledger says.
"""
import csv, glob, html, json, os, re, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = os.path.join(ROOT, "ledger")
ASSET = os.path.join(ROOT, "tools", "assets", "states-10m.json")
ATLAS_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json"
TEMPLATE = os.path.join(ROOT, "tools", "map_template.html")
OUT = os.path.join(ROOT, "map", "index.html")

STATE_ABBR = {
 "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA","Colorado":"CO","Connecticut":"CT",
 "Delaware":"DE","District of Columbia":"DC","Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID","Illinois":"IL",
 "Indiana":"IN","Iowa":"IA","Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD",
 "Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT",
 "Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM","New York":"NY",
 "North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA",
 "Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT",
 "Vermont":"VT","Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY",
 "Puerto Rico":"PR",
}


def read_csv(name):
    with open(os.path.join(L, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # a broken audit file must not stop the map
        print("WARN: cannot read", path, e, file=sys.stderr)
        return None


# ---------------------------------------------------------------- geometry
def topo_to_geojson(topo):
    sc, tr = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        arcs.append(pts)

    def arc_pts(i):
        return arcs[i] if i >= 0 else list(reversed(arcs[~i]))

    def ring(idx):
        out = []
        for i in idx:
            p = arc_pts(i)
            out.extend(p if not out else p[1:])
        res, last = [], None
        for lon, lat in out:  # 3 decimals (~100 m) is plenty at page scale
            q = [round(lon, 3), round(lat, 3)]
            if q != last:
                res.append(q)
            last = q
        return res

    feats = []
    for g in topo["objects"]["states"]["geometries"]:
        if g["type"] == "Polygon":
            coords = [ring(r) for r in g["arcs"]]
        else:
            coords = [[ring(r) for r in poly] for poly in g["arcs"]]
        name = g["properties"]["name"]
        feats.append({"type": "Feature", "id": g.get("id"),
                      "properties": {"name": name, "abbr": STATE_ABBR.get(name, "")},
                      "geometry": {"type": g["type"], "coordinates": coords}})
    return {"type": "FeatureCollection", "features": feats}


def load_geo():
    if not os.path.exists(ASSET):
        os.makedirs(os.path.dirname(ASSET), exist_ok=True)
        print("downloading", ATLAS_URL)
        urllib.request.urlretrieve(ATLAS_URL, ASSET)
    with open(ASSET, encoding="utf-8") as f:
        return topo_to_geojson(json.load(f))


# ---------------------------------------------------------------- run log
def md_inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


def md_block(lines):
    out, inlist = [], False
    for ln in lines:
        if ln.startswith("- ") or re.match(r"^\s+- ", ln):
            if not inlist:
                out.append("<ul>"); inlist = True
            out.append("<li>" + md_inline(ln.strip()[2:]) + "</li>")
            continue
        if inlist:
            out.append("</ul>"); inlist = False
        if ln.startswith("### "):
            out.append("<h4>" + md_inline(ln[4:]) + "</h4>")
        elif ln.startswith("## "):
            out.append("<h3>" + md_inline(ln[3:]) + "</h3>")
        elif ln.strip():
            out.append("<p>" + md_inline(ln) + "</p>")
    if inlist:
        out.append("</ul>")
    return "\n".join(out)


def parse_log(text, vertical_ids):
    """Returns (sections html list, per-vertical audit lines, bullets for the method page)."""
    lines = text.splitlines()
    sections, cur = [], None
    cur_vertical = None
    per_v = {}      # vid -> {"miss": (headline, line), "fact": ...}
    bullets = {"rules": [], "backtest": [], "weights": [], "limits": [], "failures": [], "advisor": []}
    dates = set(re.findall(r"20\d\d-\d\d-\d\d", text))
    for ln in lines:
        if ln.startswith("## "):
            cur = {"title": ln[3:], "lines": []}
            sections.append(cur)
            m = re.search(r"`(v-[a-z0-9-]+)`", ln)
            cur_vertical = m.group(1) if m and m.group(1) in vertical_ids else None
            continue
        if cur is None:
            continue
        cur["lines"].append(ln)
        if ln.startswith("### Advisor consultation"):
            bullets["advisor"].append(ln[4:])
        body = ln.strip()
        if not body.startswith("- "):
            continue
        body = body[2:]
        for kind, pat in (("corrected_miss", r"\*\*Corrected miss rate[^*]*\*\*"),
                          ("miss", r"\*\*Miss rate[^*]*\*\*"),
                          ("fact", r"\*\*Fact error rate[^*]*\*\*")):
            m = re.search(pat, body)
            if m and cur_vertical:
                pct = re.search(r"(\d+(?:\.\d+)?)\s*%", m.group(0))
                per_v.setdefault(cur_vertical, {})[kind] = {
                    "headline": m.group(0).strip("*").strip(),
                    "pct": float(pct.group(1)) if pct else None,
                    "line": md_inline(body)}
        if re.search(r"\*\*Weights", body):
            bullets["weights"].append(md_inline(body))
        elif re.search(r"Back-test result", body):
            bullets["backtest"].append(md_inline(body))
        elif re.search(r"\*\*(Process rule|Material rule|Relationship rule|Score storage)", body) or "Confidence is recomputed" in body:
            bullets["rules"].append(md_inline(body))
        if re.search(r"Known (limit|gap)|Coverage gaps accepted|city-centroid|city centroids", body):
            bullets["limits"].append(md_inline(body))
        if re.search(r"Source failures", body):
            bullets["failures"].append(md_inline(body))
    secs = [{"title": s["title"], "html": md_block(s["lines"])} for s in sections]
    return secs, per_v, bullets, sorted(dates)


# ---------------------------------------------------------------- audit json
def find_rows(obj):
    """Find a list of dicts that carry claim_id anywhere in a fact-check json."""
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj) and any("claim_id" in x for x in obj):
            return obj
        for x in obj:
            r = find_rows(x)
            if r:
                return r
    elif isinstance(obj, dict):
        for v in obj.values():
            r = find_rows(v)
            if r:
                return r
    return []


def first_key(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return None


def norm_status(s):
    s = str(s or "").lower()
    if "unreach" in s:
        return "unreachable"
    if "correct" in s or s in ("wrong", "error", "incorrect", "fail"):
        return "corrected"
    if "confirm" in s or s in ("ok", "pass", "correct_as_stated", "supported"):
        return "confirmed"
    return ""


def build_audit(vids):
    audit = {v: {} for v in vids}
    factcheck = {}
    for path in sorted(glob.glob(os.path.join(L, "audit", "fact-check-*.json"))):
        d = load_json(path)
        if not d:
            continue
        vid = first_key(d, ["vertical"]) or re.sub(r"^fact-check-|\.json$", "", os.path.basename(path))
        rows = find_rows(d)
        checked = first_key(d, ["claims_checked", "checked", "n_checked"]) or len(rows)
        corrected = first_key(d, ["claims_corrected", "corrected", "n_corrected"])
        if corrected is None:
            corrected = sum(1 for r in rows if norm_status(first_key(r, ["status", "verdict", "result", "verified"])) == "corrected")
        rate = first_key(d, ["fact_error_rate", "error_rate"])
        if rate is None and checked:
            rate = corrected / checked
        if isinstance(rate, str):
            m = re.search(r"[\d.]+", rate); rate = float(m.group(0)) if m else None
            if rate and rate > 1: rate /= 100
        kinds = first_key(d, ["error_kind_counts", "error_kinds", "kinds", "counts_by_kind"]) or {}
        unreach = sum(1 for r in rows if norm_status(first_key(r, ["status", "verdict", "result", "verified"])) == "unreachable")
        if vid in audit:
            audit[vid]["factcheck"] = {"file": os.path.basename(path), "checked": checked, "corrected": corrected,
                                       "rate": rate, "unreachable": unreach, "kinds": kinds}
        for r in rows:
            st = norm_status(first_key(r, ["status", "verdict", "result", "verified"]))
            if not st:
                continue
            note = first_key(r, ["correct_value", "corrected_value", "correction", "note", "notes", "error_kind", "kind"])
            factcheck[r["claim_id"]] = {"status": st, "note": str(note) if note else "", "file": os.path.basename(path)}
    for path in sorted(glob.glob(os.path.join(L, "audit", "list-audit-*.json"))):
        d = load_json(path)
        if not d or d.get("vertical") not in audit:
            continue
        pl = d.get("plants")
        n = len(pl) if isinstance(pl, list) else pl
        in_def = sum(1 for p in pl if p.get("in_definition")) if isinstance(pl, list) else None
        audit[d["vertical"]].setdefault("listaudit", []).append({
            "auditor": d.get("auditor"), "angle": d.get("angle"), "rows": n, "in_definition": in_def,
            "searches": d.get("searches_run"), "until_dry": d.get("searches_until_dry")})
    for path in sorted(glob.glob(os.path.join(L, "audit", "miss-candidates-*.json"))):
        d = load_json(path)
        if not d or d.get("vertical") not in audit:
            continue
        audit[d["vertical"]]["miss_candidates"] = {
            "combined_in_definition": d.get("combined_in_definition"),
            "matched": len(d.get("matched", [])), "unmatched": len(d.get("unmatched", [])),
            "out_of_definition": len(d.get("out_of_definition", []))}
    # verification overview
    qc = {"found": 0, "not_found": 0, "unreachable": 0, "files": 0}
    qc_rows = {}
    for path in sorted(glob.glob(os.path.join(L, "audit", "quote-check-*.json"))):
        d = load_json(path)
        if not d:
            continue
        qc["files"] += 1
        for r in d.get("rows", []):
            v = r.get("verdict")
            key = "found" if v == "found" else "unreachable" if v == "unreachable" else "not_found"
            qc[key] += 1
            qc_rows[(r.get("claim_id"), r.get("source_url"))] = key
    pc = load_json(os.path.join(L, "audit", "posting-city-check.json"))
    return audit, factcheck, qc, qc_rows, (pc or {})


# ---------------------------------------------------------------- main
def main():
    verticals = read_csv("verticals.csv")
    plants = read_csv("plants.csv")
    links = read_csv("links.csv")
    evidence = read_csv("evidence.csv")
    vids = [v["id"] for v in verticals]
    with open(os.path.join(L, "run_log.md"), encoding="utf-8") as f:
        log_text = f.read()
    secs, per_v, bullets, log_dates = parse_log(log_text, set(vids))
    audit, factcheck, qc, qc_rows, pcheck = build_audit(vids)
    for v, d in per_v.items():
        audit[v]["log"] = d

    # evidence indexed by claim_id, compact keys
    ev = {}
    pc_rows = {(r.get("claim_id"), r.get("source_url")): r.get("verdict") for r in pcheck.get("rows", [])}
    for e in evidence:
        row = {"v": e["value"], "t": e["tag"], "q": e["quote"], "u": e["source_url"], "st": e["source_type"],
               "d": e["retrieved_date"], "a": e["archive_url"], "r": e["reasoning"], "by": e["produced_by"],
               "vf": e["verified"]}
        k = (e["claim_id"], e["source_url"])
        if qc_rows.get(k) in ("not_found", "unreachable"):
            row["qc"] = qc_rows[k]
        if pc_rows.get(k) == "CITY_NOT_ON_PAGE":
            row["cc"] = 1
        ev.setdefault(e["claim_id"], []).append(row)

    dates = sorted({e["retrieved_date"] for e in evidence if re.match(r"\d{4}-\d\d-\d\d$", e["retrieved_date"])}
                   | {p["last_checked"] for p in plants if re.match(r"\d{4}-\d\d-\d\d$", p["last_checked"])}
                   | {v["last_checked"] for v in verticals if re.match(r"\d{4}-\d\d-\d\d$", v["last_checked"])}
                   | set(log_dates))
    included = [p for p in plants if p["status"] in ("base", "profiled")]
    counts = {
        "verticals_total": len(verticals),
        "verticals_done": sum(1 for v in verticals if v["status"] == "done"),
        "verticals_accepted": sum(1 for v in verticals if v["status"] == "accepted"),
        "verticals_partial": sum(1 for v in verticals if v["status"] == "partial"),
        "plants_found": len(plants),
        "plants_included": len(included),
        "plants_profiled": sum(1 for p in plants if p["status"] == "profiled"),
        "plants_excluded": sum(1 for p in plants if p["status"] == "excluded"),
        "evidence_rows": len(evidence),
    }
    try:
        commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = ""
    data = {
        "meta": {"counts": counts, "dates": dates, "first": dates[0] if dates else "", "last": dates[-1] if dates else "",
                 "commit": commit, "state_abbr": STATE_ABBR},
        "verticals": verticals, "plants": plants, "links": links, "ev": ev, "factcheck": factcheck,
        "audit": audit, "qc": qc,
        "posting_check": pcheck.get("summary", {}),
        "log": {"sections": secs, "bullets": bullets},
    }
    geo = load_geo()
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()

    def js(o):
        return json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    page = tpl.replace("__DATA__", js(data)).replace("__GEO__", js(geo))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote", OUT, "%.0f KB" % (len(page) / 1024), counts)


if __name__ == "__main__":
    main()
