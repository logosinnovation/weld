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
L = os.environ.get("LEDGER_DIR") or os.path.join(ROOT, "ledger")
ASSET = os.path.join(ROOT, "tools", "assets", "states-10m.json")
ATLAS_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json"
TEMPLATE = os.path.join(ROOT, "tools", "map_template.html")
OUT = os.environ.get("MAP_OUT") or os.path.join(ROOT, "map", "index.html")

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
    """Returns (sections html list, bullets for the method page, session dates). No audit numbers are read from prose."""
    lines = text.splitlines()
    sections, cur = [], None
    bullets = {"rules": [], "confidence": [], "backtest": [], "weights": [], "limits": [], "failures": [], "advisor": []}
    dates = set(re.findall(r"(?m)^## (20\d\d-\d\d-\d\d)\b", text))  # session headings only
    for ln in lines:
        if ln.startswith("## "):
            cur = {"title": ln[3:], "lines": []}
            sections.append(cur)
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
        if re.search(r"\*\*Weights", body):
            bullets["weights"].append(md_inline(body))
        elif re.search(r"Back-test result", body):
            bullets["backtest"].append(md_inline(body))
        elif re.search(r"\*\*(Process rule|Material rule|Relationship rule|Score storage)", body) or "Confidence is recomputed" in body:
            cm = re.search(r"Confidence is recomputed[^.]*\.", body)
            if cm:
                bullets["confidence"].append(md_inline(cm.group(0)))
                body = body.replace(cm.group(0), "").strip()
            bullets["rules"].append(md_inline(body))
        if re.search(r"Source failures", body):
            bullets["failures"].append(md_inline(body))
    secs = [{"title": s["title"], "html": md_block(s["lines"])} for s in sections]
    return secs, bullets, sorted(dates)


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
    factcheck = {}      # (claim_id, source_url) -> verdict record; later round overrides earlier
    rounds = {}         # vid -> {1: [checker dicts], 2: [...]}
    for path in sorted(glob.glob(os.path.join(L, "audit", "fact-check-*.json"))):
        d = load_json(path)
        if not isinstance(d, dict):
            continue
        base = os.path.basename(path)
        mr = re.search(r"round-?(\d+)", base, re.I)
        rnd = int(mr.group(1)) if mr else (int(d["round"]) if str(d.get("round", "")).isdigit() else 1)  # -1/-2/-3 = round 1
        vid = d.get("vertical") or next((v for v in vids if v in base), None)
        rows = d.get("rows") if isinstance(d.get("rows"), list) else find_rows(d)
        rows = [r for r in rows if isinstance(r, dict) and r.get("claim_id") and "*" not in r["claim_id"]]
        def cnt(st): return sum(1 for r in rows if norm_status(first_key(r, ["verdict", "status", "result"])) == st)
        checked = d.get("claims_checked") if d.get("claims_checked") is not None else len(rows)
        corrected = d.get("claims_corrected") if d.get("claims_corrected") is not None else cnt("corrected")
        unreach = d.get("claims_unreachable") if d.get("claims_unreachable") is not None else cnt("unreachable")
        kinds = d.get("error_kind_counts") or {}
        worst = d.get("worst_errors")
        if isinstance(worst, str):
            worst = [worst]
        label = d.get("checker") if d.get("checker") is not None else re.sub(r"^.*round-?2-?|\.json$", "", base)
        rec = {"file": base, "checker": label, "checked": checked, "corrected": corrected, "unreachable": unreach,
               "rate": d.get("error_rate"), "kinds": kinds, "date": d.get("date"),
               "worst": [str(x) for x in (worst or [])][:3], "repeated": [str(x) for x in (d.get("repeated_kinds") or [])]}
        rounds.setdefault(vid, {}).setdefault(rnd, []).append(rec)
        for r in rows:
            st = norm_status(first_key(r, ["verdict", "status", "result"]))
            if not st:
                continue
            note = first_key(r, ["note", "notes"]) or ""
            factcheck[(r["claim_id"], r.get("source_url") or "")] = {
                "status": st, "round": rnd, "file": base, "note": str(note)[:400],
                "kind": r.get("error_kind") or "", "new": first_key(r, ["corrected_value", "correct_value"]) or ""}
    for vid, rs in rounds.items():
        if vid not in audit:
            continue
        out = {}
        for rnd, lst in rs.items():
            lst.sort(key=lambda x: str(x["checker"]))
            chk = sum(x["checked"] for x in lst); cor = sum(x["corrected"] for x in lst)
            kinds = {}
            for x in lst:
                for k, n in (x["kinds"] or {}).items():
                    kinds[k] = kinds.get(k, 0) + n
            out[str(rnd)] = {"checkers": lst, "checked": chk, "corrected": cor,
                             "unreachable": sum(x["unreachable"] for x in lst),
                             "rate": (cor / chk) if chk else None, "kinds": kinds}
        audit[vid]["rounds"] = out
        audit[vid]["files"] = {x["file"]: {"worst": x["worst"], "repeated": x["repeated"]} for lst in rs.values() for x in lst}
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


# ---------------------------------------------------------------- derived: unknowns, ceiling, pre-production
COMPS = [("process", "score_process", "weld_processes", 20), ("material_part", "score_material_part", "part_size_fit", 20),
         ("part_mix", "score_part_mix", "production_type", 15), ("labor", "score_labor", "welder_postings", 20),
         ("scale", "score_scale", "headcount", 10)]


def field_unknown(v, key=None):
    v = (v or "").strip().lower()
    if key == "labor" and re.match(r"none\b", v):   # "none found" carries no information: same as unknown
        return True
    return v == "" or v.startswith("unknown") or "not stated" in v


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def derive(plants, evidence):
    """Calculated, never stored: unknown components, score ceiling, pre-production flag."""
    evby = {}
    for e in evidence:
        evby.setdefault(e["claim_id"], []).append(e)
    derived, prof = {}, []
    for p in plants:
        pid = p["id"]
        d = {}
        # pre-production: status row, or triggers / status_detail naming construction or ramp-up
        st = [e["value"].strip().lower() for e in evby.get(pid + ":status", [])]
        det = [e["value"].lower() for e in evby.get(pid + ":status_detail", [])]
        flagged = any("pre-production prospect" in v and not re.search(r"found to be operating|not pre-production", v) for v in st)
        mention = re.compile(r"under construction|ramping|transition(?:ing)? (?:its|the|from)|conversion|converted|convert(?:ing)? ")
        txt = [(p.get("triggers") or "").lower()] + det
        if not flagged and any(mention.search(t) for t in txt):
            # a plant whose own status row says it is operating is not pre-production
            flagged = not any("operating" in v for v in st)
        if flagged and p["status"] != "excluded":
            d["pre"] = 1
        if p["status"] == "profiled" and str(p.get("score_total", "")).strip() != "":
            score = num(p["score_total"])
            unk, head = [], 0
            for key, sf, uf, mx in COMPS:
                if num(p[sf]) == 0 and field_unknown(p.get(uf), key):
                    unk.append(key); head += mx
            if num(p["score_demand"]) == 8:
                d["dem"] = 7          # shown beside the ceiling, never inside it
            d["unk"] = unk
            d["ceil"] = int(min(100, score + head))
            prof.append((p, d))
        if d:
            derived[pid] = d
    def avg(tier):
        r = [len(d["unk"]) for p, d in prof if p["score_tier"] == tier]
        return round(sum(r) / len(r), 1) if r else None
    low = [(p, d) for p, d in prof if p["score_tier"] == "Low"]
    stats = {"low_n": len(low), "high_n": sum(1 for p, d in prof if p["score_tier"] == "High"),
             "avg_unk_low": avg("Low"), "avg_unk_high": avg("High"), "avg_unk_medium": avg("Medium"),
             "low_mat0": sum(1 for p, d in low if "material_part" in d["unk"]),
             "low_ceil70": sum(1 for p, d in low if d["ceil"] >= 70),
             "research_first": sum(1 for p, d in low if d["ceil"] >= 70),
             "preprod": sum(1 for d in derived.values() if d.get("pre"))}
    return derived, stats


# ---------------------------------------------------------------- main
def main():
    verticals = read_csv("verticals.csv")
    plants = read_csv("plants.csv")
    links = read_csv("links.csv")
    evidence = read_csv("evidence.csv")
    vids = [v["id"] for v in verticals]
    with open(os.path.join(L, "run_log.md"), encoding="utf-8") as f:
        log_text = f.read()
    secs, bullets, log_dates = parse_log(log_text, set(vids))
    audit, factcheck, qc, qc_rows, pcheck = build_audit(vids)
    # headline audit figures come only from ledger/audit/summary.json (written by the coordinator)
    summary = load_json(os.path.join(L, "audit", "summary.json")) if os.path.exists(os.path.join(L, "audit", "summary.json")) else None
    if summary is not None and not isinstance(summary, dict):
        summary = None

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
        fcr = factcheck.get(k)
        if fcr:
            row["fc"] = fcr
        ev.setdefault(e["claim_id"], []).append(row)
    # fact-check verdicts whose (claim_id, source_url) matched no evidence row: report, never guess
    seen = {(e["claim_id"], e["source_url"]) for e in evidence}
    unmatched = [k for k in factcheck if k not in seen]
    if unmatched:
        print("NOTE: %d fact-check verdicts match no evidence row (claim_id, source_url), e.g. %s" % (len(unmatched), unmatched[:2]), file=sys.stderr)

    dates = log_dates  # first and last "## YYYY-MM-DD" session headings of run_log.md
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
    derived, dstats = derive(plants, evidence)
    data = {
        "derived": derived, "dstats": dstats,
        "meta": {"counts": counts, "dates": dates, "first": dates[0] if dates else "", "last": dates[-1] if dates else "",
                 "state_abbr": STATE_ABBR},
        "verticals": verticals, "plants": plants, "links": links, "ev": ev,
        "audit": audit, "qc": qc,
        "posting_check": pcheck.get("summary", {}),
        "log": {"sections": secs, "bullets": bullets},
        "summary": summary,
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
