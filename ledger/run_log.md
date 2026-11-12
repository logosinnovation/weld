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
