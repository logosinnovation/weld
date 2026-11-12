# Shared brief for every subagent (set by the coordinator, 2026-11-12)

Read `CLAUDE.md` (project rules) and your own agent definition first. This file adds this session's working conventions.

## Today
retrieved_date = 2026-11-12. RECENCY_MONTHS = 24, so "recent" means on or after 2024-11-12.

## How to read web pages
- **WebFetch does not work in this session** (DNS refusal). Do not use it.
- Fetch pages from Bash: `python3 tools/fetch_page.py URL` prints the page text (HTML or PDF). Add `--grep "word"` to see only matching lines, `--check "exact quote"` to confirm a quote is on the page, `--browser` to force headless Chromium. It falls back to the browser automatically on 403s and bot challenges. Run it from the repo root `/home/user/weld`.
- Use WebSearch (load it with ToolSearch `select:WebSearch`, mode "standard") to discover URLs. **A search result summary is never a quote.** Every quote must be copied from the page text that `fetch_page.py` printed.
- AISC certified fabricators: in a Playwright script open https://aisc.my.site.com/public/map-us (company-name box, state filter; 20 rows per page). Quote the row text.
- SEC EDGAR full-text search: https://efts.sec.gov/LATEST/search-index?q=%22phrase%22&forms=10-K (JSON); filings open with the fetch helper.
- Census geocoder (JSON, no key): https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=<urlencoded>&benchmark=Public_AR_Current&vintage=Current_Current&format=json gives lat/lon, state and county FIPS (`geographies.Counties[0].STATE + COUNTY`).
- Archive: try `curl -s -m 30 "https://web.archive.org/save/<url>"` once per page at most; Wayback has been timing out. If it fails, check https://archive.org/wayback/available?url=<url> for an existing snapshot; else leave archive_url blank. Don't spend more than one attempt per page.
- `data/osha_2025.csv` is **not present** this run. Skip OSHA steps.
- No sign-ins, no LinkedIn automation (search snippets OK only as discovery), no contacting businesses, no forms except site search boxes.

## Output
Write ONE JSON file at the path your delegation names, under `ledger/inbox/`. Write it early and rewrite it as you go, so a cut-off run still leaves usable output. Shape:

```json
{
  "verticals": [ {<verticals.csv columns>} ],
  "plants":    [ {<plants.csv columns>} ],
  "links":     [ {"from_id": "...", "to_id": "...", "what_is_supplied": "...", "claim_id": "..."} ],
  "evidence":  [ {<evidence.csv columns>} ],
  "notes": "...", "source_failures": ["..."]
}
```
Column lists: see the header line of each CSV in `ledger/`. Never edit ledger CSVs yourself.

## IDs (deterministic; must match exactly)
- Vertical: `v-<slug>`. Poles and substation steel = `v-poles-substation`.
- Plant: `p-<company-slug>-<city-slug>-<state2>`, lowercase, hyphens only. company-slug = short name of the operating company (e.g. `p-valmont-jasper-tn`, `p-sabre-alvarado-tx`). Same company + city twice: append `-2`.
- Company-level claims: `c-<company-slug>:<field>`.
- Evidence claim_id: `<id>:<field>` where field is the CSV column name (e.g. `p-valmont-jasper-tn:headcount`). Several evidence rows may share a claim_id (different sources).
- Link claim_id: `<from_id>:supplies:<to_id>`. from_id = the supplier plant, to_id = the customer plant (or `c-<company>` if the customer plant is unknown).

## Evidence rules (strict)
- Every non-empty, non-"unknown" field you fill needs at least one evidence row with claim_id `<id>:<field>`.
- `quote` = exact text from the page, ≤300 characters. Paste it; don't paraphrase or fix typos. Use "..." only to join two exact fragments from the same page.
- `tag`: stated (the page says it), inferred (your reasoning; fill `reasoning`), unknown.
- `source_type`: company site | job posting | news | government file | certification list | trade association | other.
- `produced_by` = your agent name. `verified` = not_checked.
- Industry alone never sets a weld process or a tier. A bottleneck is always inferred unless the company says it.
- Business facts only: no personal names with contact details, no personal emails or phones, no home addresses.
- Not found = "unknown". Never invent.

## Field formats in plants.csv
- status: base | profiled | excluded. verticals: `v-poles-substation` (semicolon-separate if several).
- tier: OEM | Tier 1 | Tier 2 | Contract fabricator | Tier 3. relationship: known_customer | customer_other_plant | lookalike | new.
- found_by: semicolon list of the source kinds that found the plant (e.g. `company site;AISC;news`).
- headcount: a number or range as the source gives it, else unknown.
- welder_postings: short text, e.g. `3 open (oldest 2026-08-01); MIG; 2nd shift; $2,000 sign-on` or `none found`.
- Score columns: integers. score_tier: High | Medium | Low.
