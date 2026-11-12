# Run log

## 2026-11-12 — Session 1 (coordinator)

### Start state
- `ledger/` was empty (only `.gitkeep` files). No vertical accepted, so the run starts at Stage A.
- `data/osha_2025.csv` is not present. The OSHA steps are skipped this run (logged once, per ground rule 6).

### Source and tool access check (before any research agent)
- **Network policy:** the cloud environment ("Path Robotics", personal) started with *limited* network and no allowed hosts. Every page fetch failed: aisc.org, sec.gov, areadevelopment.com, valmont.com, census geocoder. Only WebSearch (summarised results, no exact page text) worked, which cannot meet the exact-quote rule. The coordinator asked to switch the environment to unrestricted network access; the user approved and it was applied.
- **AISC cert search (blocks plain page fetches):** `curl` to https://www.aisc.org/certsearch returns HTTP 403. Headless Chromium (Playwright, pre-installed) opens the same page with HTTP 200, title "Find a Certified Company". **Result: agents can open sites that block plain fetches by using the browser.** Use the browser only for such sites (ground rule 5).
- **Census Geocoder** (geocoding.geo.census.gov): reachable, returns JSON.
- **Wayback Machine:** the availability API (archive.org/wayback/available) works; page loads and saves on web.archive.org timed out from curl. Agents should try once per page and leave archive_url blank on failure.
- **jsdelivr** (us-atlas@3.0.1): reachable, for the map build.

### Inbox file format (set by coordinator)
Every subagent writes one JSON object to `ledger/inbox/<agent>-<label>.json` with any of these keys, each a list of objects whose keys are the CSV column names: `verticals`, `plants`, `links`, `evidence`. Agent-specific extras (e.g. `back_test`, `proposed_weights`, `confirmed_customers`, `notes`, `source_failures`) go in additional top-level keys.

### Access check, continued (after network change)
- **WebFetch tool:** still refused with DNS errors after the change (its resolver seems to keep the old policy for this session). Bash `curl`/`requests` and Playwright reach every site tested. **Workaround:** agents fetch pages with `python3 tools/fetch_page.py URL [--grep phrase | --check "quote" | --browser]`, which tries a plain fetch and falls back to headless Chromium on 403/challenge. WebSearch works and is used for discovery only; it never counts as a source quote.
- **AISC certified-company search:** the certsearch page embeds a Salesforce app. Open https://aisc.my.site.com/public/map-us in the browser: company-name and state filters, 1,881 certified companies, paged 20 at a time. Verified working on 2026-11-12.
- **SEC EDGAR:** works with a generic declared User-Agent (no personal details); the fetch helper sets one.

### ID scheme (deterministic, so parallel agents don't collide)
- Vertical: `v-<slug>` (e.g. `v-poles-substation`).
- Plant: `p-<company-slug>-<city-slug>-<state2>`, all lowercase, hyphens, company slug = short brand of the operating company (e.g. `p-valmont-jasper-tn`). If two plants share company+city, add `-2`.
- Company-level claims (not tied to one plant): `c-<company-slug>:<field>`.
- Link claim: `<from_id>:supplies:<to_id>`.
- Back-test claims: `bt-<company-slug>:<component>`.

### Merge procedure
`python3 tools/merge_inbox.py ledger/inbox/<file>.json --verify-quotes`. It validates tags, source types, quote length and reasoning; upserts plants (dedupe on normalised name + address), links, verticals, evidence; lists plant values without evidence rows; re-fetches every stated source and writes quote misses to `ledger/audit/quote-check-<file>.json` for the fact-checker. Reports go to `ledger/audit/merge-<file>.json`.

### Audit mechanics (decided before research)
- The list-auditor gets only the product definition: no company names, no ledger access. It runs as soon as plant-finder output is merged, in parallel with profiling.
- Miss rate = auditor plants that are in-definition, verified to exist, and absent from `plants.csv` (any status) ÷ auditor plants that are in-definition. Unmatched names are adjudicated by the coordinator; true misses are merged as base records with found_by = list-auditor.
- Fact error rate = claims corrected ÷ claims checked, from the fact-checker report. Unreachable sources are reported separately, not counted as confirmed.
- Budget rule: if context runs short, cut profiling batches, never the audit or the map.
