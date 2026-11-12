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

## Stage A — vertical planning (2026-11-12)
- vertical-planner returned 17 verticals, 252 evidence rows, 16 customer checks, a back-test of 14 customers and a weights proposal. Merge: 0 rejected rows, 0 coverage gaps. Quote check: 125/125 stated quotes found verbatim (20 only after a browser re-check; `tools/recheck_quotes.py`).
- Source failures reported by planner: 12 (in the inbox file's `source_failures`). Notable: Sabre Industries' site shows a "confirm you are human" wall, so plant-finder must use other routes; Path's Cheetah case page returns 404 and its archived copy would not load.

### Advisor consultation 1: accept/reject verticals and score weights
Asked: which verticals to accept or reject, and whether to apply the planner's proposed weights (back-test 2 of 14 High).
Advice and decisions applied:
- **Accepted (7):** poles-substation (rank 1), shipbuilding-naval, mining-heavy-equipment, enclosures-battery-generator, datacenter-grid-prefab, trailers-chassis-mobile-power, bridge-structural-steel. Each has a plain "pass" fit test on stated evidence.
- **Rejected (2):** wind-towers (oversize, submerged-arc dominated), transmission-lattice-towers (bolted assembly). Tubular transmission poles stay in poles-substation.
- **Kept as candidate (8), needs planner re-test:** transformer-tanks, defense-ground-vehicles, cranes-lifting, pressure-vessels-tanks, oil-gas-skids, truck-bodies, agricultural-equipment, rail-cars. Rail cars stays a candidate rather than rejected because its high-volume claim is only inferred.
- **Weights: no change.** Back-test result: 2 of 14 confirmed customers score High (Valmont 80, EK Machine 80); 7 Medium, 5 Low. Five of the 14 have no identifiable US plant to score (Lockheed Martin, Schenck Process, TransAmerican, which makes in Mexico, and HII and TYCROP, scored at company level). The shortfall is mostly "not found = 0" from a light 1-3 page pass, not a bad fit. The planner's own reweighting reached only 4 of 14. Changing weights on shallow data would be overfitting. Revisit next session using profiler-depth scores for the customer plants.
- **Process rule clarified (face value, not a new tier):** MIG/flux-core stated in production at the plant = 20 even if submerged-arc seams are also stated; record both. Only submerged arc, or only generic "welding", stated = 0. Never infer MIG from "pole plant".
- **Customer-plant extras:** Millerbernd, Nello and Valmont customer plants are profiled as extras beyond the 40, to give a profiler-depth back-test for the next weight decision.
- **Relationship rule:** `known_customer` only when the source names the plant, or the company has a single welding site (tagged inferred). Otherwise every plant of that parent = `customer_other_plant`. `lookalike` only for direct product competitors, naming the customer. Nello (passed acceptance test only) and Valmont (2021 reference) keep those caveats; opening lines must not assert a current deployment. TransAmerican gets no plant row unless a US plant is found.
- **Score storage:** one evidence row per component, claim_id `<id>:score_process` (etc.), value = points, reasoning = rubric level + supporting claim_ids. Confidence = number of components whose supporting claims are stated.

## Vertical 1: Poles and substation steel (`v-poles-substation`), started 2026-11-12
### Final product definition (identical text given to plant-finder and list-auditor)
Welded steel poles and pole-type structures made in a US plant from formed plate or tube, where these structures are a named product line or core stated capability of the plant: tapered and multi-sided transmission and distribution poles; substation structures (dead-end, bus-support and equipment-support steel); and lighting, high-mast, traffic-signal, sign-support and telecom monopole structures. Out of scope (recorded as excluded with the reason, not dropped): bolted lattice towers (angle-member transmission and self-supporting telecom towers), concrete, wood and fiberglass/composite poles, wind towers, plants that only galvanize, coat, distribute or install, and general fabricators that build such structures only as occasional custom jobs. Aluminum-first pole plants are kept and noted.

Ambiguity resolved by coordinator: "Aluminum-first plants are kept and noted" (CLAUDE.md prospect test) is read as *included*, with materials noting aluminum-first. Their material score will reflect it.

### Stage B-C plan: 4 plant-finder slices in parallel
1. `customers`: Valmont (every US plant in scope), Millerbernd, Nello. Relationship known_customer / customer_other_plant per the rule above.
2. `utility-majors`: other utility T&D pole and substation-structure makers (Valmont lookalikes), e.g. Sabre, Meyer Utility Structures (Arcosa), Nucor Towers & Structures, Thomas & Betts / ABB, FWT, and every other competitor found.
3. `lighting-traffic-telecom`: lighting, high-mast, traffic-signal, sign-support and telecom monopole makers (Millerbernd/Nello lookalikes).
4. `list-sweeps`: AISC directory (incl. the Highway Component Manufacturer filter, as a discovery list only), trade associations, state DOT qualified-products lists, federal awards, EPA FRS, state-plus-product searches, welder postings naming poles.
Merge change: `found_by` and `verticals` are now unioned across slices, and a profiled record is never downgraded to base.

### Stage B-C merge 1: plant-finder `customers` (Valmont, Millerbernd, Nello)
- 20 plants: 11 base, 9 excluded (Valmont concrete Tuscaloosa AL and Bristol IN; galvanizing Midland PA; composites Newberry SC; tower plants Salem OR and Plymouth IN; Valley NE irrigation campus; Millerbernd circular-products plants Winsted (595 Industrial Dr) and Sauk Rapids). 131 evidence rows; quote check 99 found, 0 not found, 1 unreachable. No supplier links found.
- **Coordinator change:** p-millerbernd-winsted-mn and p-nello-south-bend-in were submitted as known_customer (inferred, "only pole site"). Changed to customer_other_plant under the strict rule: Path names no plant and both parents have more than one welding site.
- Coverage gaps accepted: parent_company and website (identity fields, no separate quote); tier and postings on excluded plants; "none found" postings (a negative result). The map will mark any displayed value without an evidence row as unsourced.
- Known gap: Valmont's locations pages don't list its steel-pole plants, so the Valmont set comes from job postings, the 10-K and news. More Valmont pole plants probably exist; the list-auditor will test this.
- Geocoding: the Census geocoder had no match for 7 plants. Those use OpenStreetMap Nominatim coordinates, several of them city centroids, noted per plant.
- Source failures: Valmont locations widget (JS map, no plant list); valmont.jobs.net, career.com and kansasworks (403/401/proxy error).

### Stage B-C merge 2: plant-finder `utility-majors`
- 24 plants: 21 base, 3 excluded. 173 evidence rows; quote check 64 found, 0 not found, 5 unreachable. No supplier links found.
- Included, all lookalike of Valmont: Sabre (Alvarado TX, Sioux City IA, Bossier City LA); FWT (Fort Worth TX, Hicksville OH; 2015 source); Meyer/Arcosa (Steele AL, Clinton IL, Hager City WI, Fort Worth TX, Lancaster SC); Nucor Towers & Structures (Decatur AL, West Hazleton PA); Sovereign Steel (Allentown PA); DIS-TRAN (Pineville LA, Washington Court House OH); MICA Steelworks (Haltom City TX); CHM Utility (Fort Worth TX); Pacific Steel Structures (Greenacres WA); Pelco Structural (Claremore OK); Grid Structures (Amite City LA); Browning Enterprise (Attalla AL).
- Excluded: Nucor Crawfordsville IN and Brigham City UT, still under construction (they don't weld yet, so they fail the prospect test today). Logged as strong future triggers to revisit next session. MICA Kaufman TX is galvanizing only.
- No row: Thomas & Betts / ABB (its steel-structures business became Meyer, now under Arcosa); TransAmerican (no US plant); Sabre Structures-PA (town not named).
- Most plants have city-centroid coordinates only (street address unknown).
- **Geocode check** (`tools/geocheck.py`, Census Gazetteer 2024 centroids): p-meyer-clinton-il was placed in Clinton *County* IL, 178 km from Clinton city. Corrected to the Clinton city centroid, county 17039 (DeWitt). Midland PA was flagged, but the Gazetteer's other Midland caused it; the coordinates are right.
- Source failures: Sabre site (human check, not attempted); career.com and careerbuilder (bot challenge); nucortowersandstructures.com (proxy 502); Nominatim (refused requests from the coordinator, so the Census Gazetteer was used instead).

### Stage B-C merge 3: plant-finder `lighting-traffic-telecom`
- 27 plants (26 new; Pelco Claremore updated, now carrying the lighting/traffic view): 22 base, 5 excluded. Excluded: Hapco Oklahoma City (groundbreaking only), TAPP Houston (offices and distribution; poles made in Mexico), Ackerman & Baynes and Clark Machine (general fabricators), Hadco Littlestown (luminaires). 242 evidence rows; quote check 126 found, 1 not found (p-maico-ellsworth-ks:products, flagged for the fact-checker), 0 unreachable.
- Prospect test: 8 plants stated, 14 inferred (no reachable page says in-house welding). Hapco Abingdon is aluminum-first (kept, noted). Arcosa Telecom Muskogee says its monopoles are mostly fabricated with sister company Meyer, so its own welding needs confirming.
- Source failures: TxDOT approved-fabricator PDFs (404); s-steel.com, keystonepoles.com, brookfieldfabricating.com, structuresusa.com (parked), walpar.com, commercialfabricators.com unreachable.
- Unresolved leads (not recorded): Interstate Structures, Woerner Wire Works, White Oaks Metal, Summit Manufacturing, Pittsburg Tank & Tower, WirelessPSC, Griffin Welding, L&M Fabrication, Specialty Fab, the third Arcosa steel traffic plant.

### Stage F (list audit) launched early, 2026-11-12
- Two independent list-auditors (A: product and buyer angle; B: geography, registries and hiring) were started while the list-sweeps plant-finder was still running, to save time. They get only the product definition and are barred from `ledger/`, so starting early doesn't affect their independence. The miss rate is computed against the final merged list, using the combined auditor set (A ∪ B). The user also asked for maximum quality and delegation ("Ultra Code"), which is the reason for two auditors instead of one.
