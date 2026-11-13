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

### Stage B-C merge 4: plant-finder `list-sweeps`
- 34 rows: 13 new plants (Klute York NE, Western Utility Telecom Salem OR, DiHighway New York Mills NY, QMF Steel Campbell TX, Larwel Roanoke TX, Structural & Steel Products Crowley TX, plus 7 excluded), 21 updates that add sources and postings to existing plants. 181 evidence rows; quote check 142/142 found. 16 AISC rows from pages 2-95 were verified against the full directory scrape, kept as `ledger/audit/source-snapshot-aisc-directory-2026-11-12.txt` (1,881 companies, 252 Highway Component Manufacturer holders).
- Pacific Steel Structures (Greenacres WA) is now **excluded**. Its own site says a manufacturing partner makes the poles in Tualatin OR, and the partner is unidentified (lead for the next session).
- Conflicts sent to profiling for a decision: MICA Kaufman TX (galvanizing per utility-majors, but TxDOT lists the "Kaufman Division" as an approved pole and sign-structure fabricator); CHM Fort Worth vs CHM Saginaw (one plant or two?).
- Source failures: brookfieldfabricating.com, keystonepoles.com, s-steel.com (TLS/502); app.energyhire.com (502); the T&D World directory (loads by script); old TxDOT /mpl/ URLs (404; current files are under /division/mtd/mpl/); USAspending gave distributors only.

### Stage C totals (all four slices)
- 83 plants: 58 base (included), 25 excluded. Relationships of included plants: 11 customer_other_plant, 41 lookalike, 6 new. No supplier links found by any slice (no public source names suppliers of welded parts to these makers).

### Stage D-E plan
- Rank (`tools/rank_for_profiling.py`): the top 40 included plants, plus 2 customer-plant extras (LaX Spring Grove and Westby, Nello's other plants; ranks 51-52) for the profiler-depth back-test, plus MICA Kaufman to resolve its conflict. 43 plants in 5 batches grouped by company, run as a workflow with a quote-repair check after each batch (user asked for "Ultra Code").
- Known rank-script quirk: Meyer Clinton's postings text includes a year, which the parser read as 2026 postings. It ranks first either way.

### Stage F: list audit comparison (preliminary, 2026-11-12)
- Auditor A (product and buyer angle): 52 rows, 42 in definition, about 68 searches, dry after the last 10. Auditor B (geography, registry and hiring): 74 rows, 65 in definition (B rates about 30 of them low confidence: one registry row or a search summary only), about 58 web searches, 45 AISC name queries and 25 fetches.
- `tools/compare_audit.py` (A ∪ B): 95 unique rows, 81 marked in definition, 70 matched to the ledger (54 unique ledger plants), 11 unmatched.
- Coordinator adjudication of the 11:
  - **Not misses (already in the ledger, name or city spelled differently):** TAPP (excluded TAPP Houston row), Nucor Crawfordsville (B gives New Ross, the same plant), Structures USA Elizabethtown, Grid Structures Amite. Those 4, plus the 54 matched plants and the TAPP row, give 57 auditor plants found in the ledger.
  - **Confirmed misses with a quoted source (3):** Valmont Elkhart IN (Ohio DOT signal-supports list), Walpar-Valmont Birmingham AL (Maryland overhead-sign list), Raycap North Charleston SC (concealed 5G poles).
  - **Unverified, search summaries only (4):** Valmont Ferndale WA, DIS-TRAN Chicago Heights IL, Race Rock Brookshire TX, Cem-Tec Phoenix AZ. Sent to a plant-finder (`audit-misses`) to verify. That agent also takes Race Rock Crowley TX, Ehresmann Engineering and a possible Meyer Tulsa plant as extra leads.
- **Preliminary miss rate:** between 3/60 = 5.0% (only the 3 confirmed) and 7/64 = 10.9% (if all 4 open candidates prove real). Both are under the 20% advisor threshold. The final figure is set after verification.
- Pattern: all 3 confirmed misses are Valmont or Valmont-family sites (2) or telecom small-cell poles (1), and 3 of the 4 open ones are Valmont, DIS-TRAN or Race Rock sites. Company-level locations pages under-report plants; state DOT qualified lists caught them.

### Stage F: final miss rate, v-poles-substation
- The `audit-misses` plant-finder verified the open candidates. Base records added: Valmont Elkhart IN, Valmont (Walpar) Birmingham AL, Valmont Ferndale WA, Raycap North Charleston SC, Race Rock Brookshire TX, Cem-Tec Phoenix AZ, and Ehresmann Yankton SD (an extra lead, not an auditor plant). Excluded: DIS-TRAN Chicago Heights IL (plate processing only) and Race Rock Crowley TX (no pole or substation product named; borderline). Unverified, no row: Meyer Tulsa (only a blocked job-posting snippet; Ameron Tulsa already covers Arcosa's Tulsa poles).
- **Miss rate = 6 / 63 = 9.5%.** 6 verified in-definition auditor plants were absent from the ledger (Elkhart, Birmingham, Ferndale, Raycap, Race Rock Brookshire, Cem-Tec). The denominator is 57 auditor plants found in the ledger plus those 6; DIS-TRAN Chicago Heights is dropped as out of definition. Under the 20% threshold, so no advisor escalation is needed for the miss rate.
- The misses are merged with found_by starting `list-auditor`. They are base records, not profiled this session.

### Supply chain (extra plant-finder slice, step 4 only)
- None of the four main slices found a supplier relationship, so a dedicated supply-chain plant-finder ran. Result: 6 links (3 stated, 3 inferred), 2 new excluded plant rows (the Tier 3 Nucor sheet mills at Trinity AL and Crawfordsville IN). Stated: Meyer (company level) → Arcosa Telecom Muskogee, monopole fabrication; Nucor mills (company level) → Nucor Brigham City, plate and sheet; DIS-TRAN Chicago Heights → DIS-TRAN Washington Court House, plate processing. Inferred: the adjacent Nucor sheet mills → Nucor Decatur and Crawfordsville pole plants; MICA Kaufman galvanizing → MICA Haltom City.
- Known limit: public sources rarely name a pole maker's suppliers or a plant's customers. Plate service centers and galvanizers market to "the pole industry" without naming makers. The map's supply-chain view is therefore thin for this vertical.
- Source failures: sabregalvanizing.com (TLS mismatch, then 502), nawindpower.com (reset, then 502), manufacturing-today.com (403).

### Stage D-E wave 2 (decision logged)
- After wave 1 the user asked for maximum quality and explicitly told the coordinator to keep going ("be daring... triple A"). The coordinator read that as license to go past FULL_PROFILES_PER_VERTICAL = 40 and profile every included plant in the vertical, so the call list has no "not yet profiled" gaps. Wave 2: 23 plants in 3 batches (Valmont audit-miss plants plus telecom; Texas and lighting; sign and regional), with the same per-batch quote and arithmetic verify stage.

### Stage D-E wave 1 merged (5 batches, 43 plants)
- 42 profiled, 1 excluded (Valmont McCook). Verify stages: 264 quotes checked, 30 fixed, 25 claims downgraded to inferred or unknown, 16 arithmetic fixes. Defects found by verifiers: job postings from a sister plant used as stated evidence (Ameron Tulsa, Meyer Lancaster, Nucor Decatur and Sabre Alvarado, all re-sourced or retagged inferred); a Millerbernd 1970s company-history size quoted as current; an unsupported posting date at Valmont Tulsa; 4 rows with a bad source_type.
- Conflicts resolved by profilers: MICA Kaufman is profiled (TxDOT's Aug 2026 high-mast list gives Kaufman TX as an approved fabrication location), 40 → Low. CHM Fort Worth and CHM Saginaw are kept as two plants.

### Advisor consultation 2: scoring consistency, McCook, miss-rate matching (2026-11-12)
Asked: batches scored the material component differently (12 as a fallback for unknown part size vs 0), plus whether to reinstate McCook. Advice and decisions:
- **Material rule (consistency, not a weight change):** 20 or 12 only when a source quotes a dimension or weight of the plant's or company's welded parts, or Path's own site says its cells weld them. 4 when an evidence row quotes aluminum-first. Otherwise 0 (unknown size is an unknown component, so 0). The planner-era 12 fallback ("likely beyond 65 ft") is dropped: 12 is a size finding and needs size evidence. Implemented in `tools/normalise_scores.py`, run over all profiled plants after wave 2 merges. Confidence is recomputed with one rule: components with points above 0 whose cited supporting claims are all tagged stated.
- **McCook reinstated** (its posting names overhead sign structures fabricated with GMAW, which are in definition; the same bar admitted the DOT-listed sign shops). Profiled in an add-on batch.
- **Miss-rate matching bug fixed:** `compare_audit.py` was matching on city tokens taken from ids and names, so same-city plants could hide each other (e.g. auditor rows for Meyer Fort Worth and Structural & Steel Products Fort Worth were matched to FWT Fort Worth). City and state tokens are now stripped before matching, and the denominator counts unique plants. **Corrected miss rate: 6 / 65 = 9.2%.** DIS-TRAN Chicago Heights is out of definition and not counted. One lead is pending: auditor B's AISC row "Arcosa Telecom Structures, Tulsa OK", in the add-on batch. If it proves a distinct plant, the rate is 7 / 66 = 10.6%.
- **Wrong-plant sweep** (`tools/posting_city_check.py`): of 159 job-posting evidence rows on profiled plants, 30 pages don't show the plant's city. 21 of those are company-level or explicitly inferred sister-plant claims (acceptable). 5 are stated plant-level claims: Millerbernd Tallo (expired, 2), Universal Paylocity (dynamic page, 2), Nucor Decatur welder_postings (1). These are priority items for the fact-checkers.
- **Fact-check plan:** run after wave 2 and normalisation. Sample: every High plant, every customer plant, all 6 links, then fill to 30+. Report the verify-stage repair counts beside the fact-checker's error rate.

### Add-on batch: McCook and Arcosa Telecom Tulsa
- p-valmont-mccook-ne reinstated and profiled. The profiler scored 65 with material 12, taken from a company-level 2017 Valmont communication-structures brochure (shaft sections up to 53 ft). Coordinator override: material 0, because the dimension isn't tied to McCook and 53 ft would be the "fits a cell" level, not the Rove level. Other Valmont plants without a plant-level size score 0. Applied via `normalise_scores.py --override`.
- Arcosa Telecom Structures, Tulsa (AISC row): **not a confirmed distinct plant**. Arcosa Telecom names only Muskogee, and Ameron Tulsa says it also makes telecom and small-cell products. Most likely the same site as p-ameron-tulsa-ok, or an office. No row written. **Final miss rate stays 6 / 65 = 9.2%.**

### Stage G (first build)
- map-builder wrote `tools/build_map.py` (with `tools/map_template.html` and a cached `tools/assets/states-10m.json`). Re-running it rebuilds `map/index.html` (about 1.2 MB, self-contained; d3 7.9.0 from cdnjs is the only external request) from the ledger and audit files. Tested in headless Chromium at desktop and phone widths, light and dark, with zero console errors. The final rebuild runs after the fact-check.
- Display decisions: "live trigger" = demand component 15; values without an evidence row show a "no evidence row" marker; score totals are labelled "calculated"; company-level link endpoints (c-...) are listed without a map line.

### Stage D-E wave 2 merged, and scores normalised (2026-11-12)
- Wave 2 (23 plants): 20 profiled, 3 excluded (Flagpoles Inc East Setauket: aluminum-only, no carbon or stainless; Commercial Fabricators Bridgeview: no website, DOT listing only, in-house welding not shown; Mid-Park Clarkson: sign structures are one division of a multi-line highway-products maker). Verify stages: 108 quotes checked, 3 fixed, 13 claims downgraded.
- **Crowley duplicate resolved:** Race Rock consolidated Structural & Steel Products, and both records give 400 N Tarrant St, Crowley TX. p-structural-steel-products-crowley-tx keeps the profile (75, High: FCAW stated in Crowley postings, several open roles, the Feb 2025 two-building facility as a trigger, a robotic weld cell operator posting). p-race-rock-crowley-tx stays excluded as a duplicate.
- **Normaliser applied** (`tools/normalise_scores.py --apply`) to all 63 profiled plants, with two coordinator overrides: McCook material 0 (company-level brochure dimension); Valmont Columbus part mix 8 (its own posting says "high-volume, fast-paced environment"). 42 plants changed. Material is 0 for 51 of 63 plants, because no source states the part size.
- **Result: 63 profiled, High 3 / Medium 21 / Low 39.** Most plants lose material points for lack of stated part sizes. That is a data gap (pole makers rarely publish section dimensions), not evidence of poor fit, and the map's method page says so.

### Stage F: fact-check, v-poles-substation (2026-11-12)
- 3 independent fact-checkers, 30 profiled plants (all 3 High, all 14 customer plants, then by score), all 6 links, plus the 6 priority rows from the wrong-plant sweep.
- **Fact error rate = 42 / 355 = 11.8%** (claims corrected ÷ claims checked; 1 unreachable, not counted). By checker: 10/136 (7.4%), 18/88 (20.5%, all Valmont plants), 14/131 (10.7%).
- Error kinds: quote does not support value 19, wrong plant or location 14, other 9. Repeated patterns: (a) company-wide Valmont brochures (a 2008 transportation catalog; a 2017 communication-structures brochure that places production at Plymouth IN and Salem OR) and multi-site Valmont posting boilerplate used as **stated plant-level** evidence; (b) Path video pages that name only the company, used as stated plant-level facts (Millerbernd existing_robots, LaX relationship); (c) compound values with a clause that comes from a different page than the cited one; (d) "AWS D1.1" recorded as a certification when the source only says work follows the code.
- Verdicts applied (`tools/apply_factcheck.py --apply`): 313 confirmed, 42 corrected, 1 unreachable, written to the verified column; corrected values copied to evidence and plant fields. 20 score components cite a corrected claim and need re-scoring.
- Error rate is over 10%, so the advisor checkpoint is required (next entry).

### Advisor consultation 3: fact error rate over 10% (2026-11-12)
Asked: the error rate is 11.8% and two error kinds repeat; what to fix and whether the vertical can be marked done. Advice and actions:
- Report 11.8% as measured. None of the 42 corrections is an invented fact or a closed plant; all are attribution and tagging errors. Fix with sweeps across all 63 plants plus re-scoring, not re-research.
- **Apply step checked:** all 356 verdicts matched their exact (claim_id, source_url) row; no fallback matches.
- **Sweep (a), company-level sources** (`tools/sweep_company_level.py --apply`): 65 stated plant-level rows whose URL supports the same field for 2 or more plants, and whose quote doesn't name the plant's city, were retagged inferred (10-K text, company sites, the Nello divisions page, DOT lists without city, the Path funding article used for every Valmont plant's relationship). **Sweep (b), Path sources:** 1 more row.
- **McCook returned to excluded:** the fact-checker showed its only in-scope evidence is multi-site boilerplate, and a Nebraska MEP directory describes the plant as pipe welding. The vertical row `v-poles-substation:hiring_pain`, which cited the same posting, was retagged inferred. This reverses the reinstatement in consultation 2.
- **Material rule tightened:** company-level size evidence counts only when a stated plant-level row places the product line at the plant; rows tagged unknown never count. Elkhart and Ferndale lose 20; Millerbernd keeps 20 (its Winsted posting names big-pole work), but its confidence drops 6 → 5.
- **Re-scored from fact-check findings:** Nucor Decatur labor 0 → 12 (open posting dated 2026-11-05); Elkhart, Ferndale and Birmingham part mix → 0 (production type unknown at plant level); Arcosa Muskogee material 12 → 0 ("towers up to 400 ft" is a finished height, not a part size). The other flagged components keep their points (core facts confirmed; only citations changed).
- **Still to do:** a compound-value and opening-line repair pass on the 33 unsampled plants; resolve whether Elkhart and Ferndale are operating pole plants (this affects the miss rate); a deciding fact-check on about 10 unsampled plants from multi-plant parents (under 10% → done, otherwise partial); the map must not show values without evidence rows.

### Repair pass (after advisor consultation 3)
- 4 repair agents: 256 evidence rows repaired or added across all 60 profiled plants. Compound values trimmed or split per source; 11 "AWS D1.1" code references removed from certifications; opening lines rewritten from stated claims and tagged inferred ("composed"), with source_url blanked on 20 of them; parent_company and website evidence rows added (ground rule 1); 4 truncated-URL rows replaced. Score change: Union Metal part mix 15 → 8 (its page states high-volume pole fabrication). Confidence recomputed by the normaliser.
- **Valmont Elkhart and Ferndale excluded (current operation unverified).** Elkhart is listed today only as "Valmont Extrusions". Ferndale is absent from Valmont's current locations, which list West Coast Engineering only at Delta, BC, and its last evidence is a 2017 brochure. Not marked closed.
- **New finding:** arcosa.com states "CRH Completes $8.5B Acquisition of Arcosa" (Oct 2026). Parent of the 5 Meyer plants, Arcosa Telecom, Arcosa Traffic and Ameron set to "Arcosa, Inc. (acquired by CRH, completed Oct 2026)".
- **Miss rate, final: 4 / 63 = 6.3%.** The verified in-definition misses are Valmont Birmingham, Raycap North Charleston, Race Rock Brookshire and Cem-Tec Phoenix. Elkhart and Ferndale leave both the numerator and the denominator, because their in-definition status is unverified. History: 9.5% → 9.2% (matching fix) → 6.3% (Elkhart and Ferndale unverified).
- Counts now: 60 profiled, High 3 / Medium 20 / Low 37.

### Stage F: deciding fact-check (round 2, after repairs)
- 2 independent fact-checkers on 10 unsampled plants from multi-plant parents (Sabre x2, FWT x2, Sovereign, Meyer x2, DIS-TRAN WCH, Arcosa Traffic, Ameron).
- **Round 2 fact error rate = 12 / 62 = 19.4%** (A: 4/22, B: 8/40; 0 unreachable). No invented facts, closed plants or wrong processes. Kinds: quote does not support value 10, other 2. Patterns: (a) a legal suffix ("LLC") added to parent_company that isn't on the cited page; (b) "no open posting" stated as if the page said it, when it's a search result; (c) a 2015 company-level sentence tagged as a plant fact (FWT Fort Worth); (d) a stale owner (Sabre Alvarado: Kohlberg, from 2015).
- Fixes: verdicts applied; sweep retagged 19 parent_company rows with unsupported legal suffixes and 19 stated "no posting" welder_postings rows as inferred. Sabre ownership updated from the Blackstone releases: Blackstone funds acquired Sabre in 2021, and TPG signed to acquire a majority stake on 2026-02-06 (expected close Q2 2026), with Blackstone keeping a minority. Applied to the 3 Sabre and 2 FWT plants. Two earlier rows that carried a Blackstone quote under a 2015 URL now point at the Blackstone release. Sabre Bossier part mix 15 → 0 (its supporting claim says part mix isn't stated).
- Open item: Ameron Tulsa may be two sites (2333 S Yukon, and the 2011 Cherokee Industrial Park steel-pole plant). Unresolved; the rows stay confirmed at city level.
- **Decision (rule set in advisor consultation 3: under 10% → done, otherwise partial): v-poles-substation = PARTIAL.** The plant list, profiles, audit and map are complete. The remaining work is one more attribution sweep and a confirming fact-check. Both error rates are reported as measured; the round-2 sample was chosen to stress-test multi-plant parents after repairs, so it isn't a random sample.

### Advisor consultation 4: before closing the session (2026-11-12)
Asked: confirm "partial" and what must happen before the final report. Advice and actions:
- **Partial confirmed;** no third fact-check round this session.
- **Checker notes nobody had applied:** opening-line problems from both rounds went to a repair agent, which rewrote 14 lines from stated claims only. It added stated rows for Sabre Bossier and Sovereign city, Arcosa Sumterville products, and Meyer Lancaster's posting duties. 5 superseded stated opening-line rows were removed. Checker 1's score notes confirmed the top-10 arithmetic. Maico's MIG fact (process 20) had no evidence row, so one was added from maicoind.com/equipment. Nucor Decatur demand is already 15 (Oct 2026 $60M expansion).
- **Ledger-wide quote check** (`tools/verify_ledger_quotes.py`): 862 stated rows; 840 verified (795 plain, 28 browser, 17 AISC snapshot). The committed AISC snapshot was found to be a partial scrape and was replaced with the full one. Of the 22 misses: 6 Census geocoder API rows retagged inferred with an explanation; 16 retagged inferred (expired or changed pages, or PDF table layout), none of them the only support for a score. Report: `ledger/audit/quote-check-ledger.json`.
- **Smoke test** of the final build in headless Chromium: the Method page shows 12/62 = 19.4% and 42/355 = 11.8%, miss rate 6.3%, the partial badge, 60 profiled; 0 console errors.
- Coverage: 40 of the 60 profiled plants were independently fact-checked across the two rounds. archive_url is filled on 1 of 2,435 evidence rows, because Wayback page loads and saves timed out all session.

## Session 1 summary (2026-11-12)
- Vertical **v-poles-substation: PARTIAL.** 94 plants found, 60 included, all 60 profiled, 34 excluded; 6 supplier links. High 3 / Medium 20 / Low 37. 51 of 60 score 0 on material because no source states the part size: a data gap, not poor fit.
- **Fact error rate:** round 1 (designed sample of 30 plants) 42/355 = 11.8%; round 2 (10 unsampled multi-plant-parent plants, after repairs) 12/62 = 19.4%. **Miss rate:** 4/63 = 6.3%, or 6/65 = 9.2% if the unverified Valmont Elkhart and Ferndale count as misses.
- **Weights:** unchanged. Profiler-depth scores for the pole customers, for next session's weight decision: Millerbernd Winsted 88, Nello South Bend 67, best Valmont plant (Claremore) 60.
- **Deviations from the brief:** every included plant was profiled (60), not just the top 40; two list auditors were used and started before plant-finder finished; the environment's network was switched to unrestricted (applies to future sessions); WebFetch was unusable, so a fetch helper replaced it.
- **Next session:** (1) one attribution sweep plus a confirming fact-check on poles, to reach done; (2) then the next vertical by rank: shipbuilding and naval defense (`v-shipbuilding-naval`).
- **Open leads:** Valmont Elkhart (3403 vs 58027 Charlotte Ave) and Ferndale status; Ameron Tulsa's possible second site (Cherokee Industrial Park); Pacific Steel Structures' Tualatin OR manufacturing partner; Nucor Crawfordsville IN and Brigham City UT once they're producing; a possible Millerbernd 150,000 sq ft expansion (location unknown); CRH's acquisition of Arcosa and TPG's majority stake in Sabre as account-level triggers.

## 2026-11-13: Session 2 (continuing v-poles-substation)
User instructions: explain why Low scores often reflect missing data; add the Nucor Indiana and Utah plants; answer the two open questions (Ameron's possible second Tulsa site; Pacific Steel Structures' Tualatin OR partner); then an attribution clean-up, a confirming fact-check, and a review by a higher-tier model before marking the vertical done; shipbuilding after that.

### Pre-production prospects (rule added)
- **New rule:** a plant under construction that will make in-scope products is included as a **pre-production prospect** (status base, then profiled), not excluded. Rationale: these plants have no welding process or robots locked in yet, which makes them some of the most actionable prospects for Path. Their scores will mostly show 0s because the plant isn't operating yet.
- Applied to p-nucor-crawfordsville-in and p-nucor-brigham-city-ut (the user's instruction), and, for consistency, p-hapco-oklahoma-city-ok (groundbreaking 2026; reported aluminum focus, kept and noted). Each has an evidence row `<id>:status` recording the decision.
- The Crawfordsville row quotes "The facility currently employs 328 people", so it may already be operating; the profiler checks this.

### Why a Low score often means missing data, not poor fit (user asked for this to be explained)
- The rubric awards points only for evidence; an unknown component scores 0 (CLAUDE.md). Three components depend on facts many pole makers never publish: **material and part fit (20)** needs a stated part dimension or weight; **labor (20)** needs a live welder posting; **demand (15)** gets its top level only from a dated plant-level trigger. A plant can be an excellent fit and still score Low because these facts aren't public.
- Measured on the 60 profiled plants (2026-11-13): Low plants average **2.2 unknown components** out of 6, against 0.3 for High plants. **35 of the 37 Low plants score 0 on material only because no source states their part size.** **26 of the 37 Low plants could reach High (70+)** if their unknown components were resolved favourably.
- Map change (Stage G): each profiled plant shows **unknowns** (components scored 0 because the underlying field is unknown) and a **ceiling** (score + the maximum points of its unknown components + 7 if demand sits at the vertical-level 8). Unknown-field mapping: process→weld_processes, material→part_size_fit, part mix→production_type, labor→welder_postings, scale→headcount. The ceiling is a calculated research-priority signal, not a score, and is labelled as such: "Low score, high ceiling" means research the plant before dismissing it.

### Session 2, phase 1 merged (2026-11-13)
- **Open question 1, Ameron Tulsa: two sites, both active.** (a) **2333 S Yukon Ave** (p-ameron-tulsa-ok): EPA facility registry name "NOV AMERON TULSA POLE PRODUCTS WELDING & FABRICATION". This is the older plant ("The company already has a plant in Tulsa at 2333 South Yukon", News On 6, 2011) and the address on state DOT lists. (b) **4903 E 66th St N** (new p-ameron-tulsa-ok-2): EPA name "NOV AMERON TULSA POLE PRODUCTS TUBE MANUFACTURING", NAICS 331210. It is the 2011 $35M Cherokee Industrial Park steel-pole plant (inferred: the address is about 1 km south of Whirlpool, matching "just south of the Whirlpool plant"). Both list Arcosa as parent and filed toxics release reports through 2024. Yukon's products and other rows that came from the 2011 announcement were moved to the 66th St plant.
- **Open question 2, Pacific Steel Structures' partner: H.W. Metal Products (HW Metals), 19480 SW 118th Ave, Tualatin OR** (new p-hw-metals-tualatin-or). Pacific Steel's own PDF says "HW Metals, Inc is Pacific Steel Structures manufacturing partner. We have a long term agreement in place to provide fabrication for us on all tapered tubular structures." HW confirms the partnership on its own site and states MIG, submerged arc and gantry welding, D1.1-certified welders, and towers up to 138" x 138" x 70'. Link added: HW Metals → Pacific Steel. Discrepancy noted: Pacific says 140,000 sq ft; HW says 120,000 sq ft under roof.
- **Pre-production plants profiled:** Nucor Crawfordsville / New Ross IN is **already operating** (328 employees; robotic plasma and weld cells; $105M expansion announced 2026-10-08): 65, Medium. Nucor Brigham City UT is ramping up (a Nucor posting dated 2026-11-11 lists it as a production facility; the October release still says under construction): 32, Low. Hapco Oklahoma City is under construction (ground broken Aug 2026, operations expected late 2027, aluminum-first): 24, Low.
- **Attribution clean-up:** 263 previously unchecked stated rows on all 60 plants: 168 confirmed, 95 corrected. Kinds: compound value or missing clause 32, company-level tagged stated 19, detail or suffix not on the page 11, a search result tagged stated 10, a judgement tagged stated 8, stale or undated 4, sister-plant evidence 2, other 9. All quotes were on their pages; the corrections are attribution and wording. One score change: Stony Brook scale 5 → 0 (28 → 23). 13 opening lines rewritten. 16 superseded rows retired.
- Every new and changed quote is verified: plain or browser fetch, and AISC rows against the full snapshot.
- New lead, not yet in the ledger: an Arcosa Telecom plant in Catoosa OK (monopoles).

### Session 2, phase 2: confirming fact-check (round 3) and new profiles
- **Round 3 fact error rate = 18 / 219 = 8.2%** (A 5/74, B 3/90, C 10/55; 0 unreachable). It covered all 23 profiled plants that no fact-checker had seen, so **every profiled plant has now been independently fact-checked at least once.** No wrong plants, wrong processes, closed plants or invented facts. Kinds: quote does not support value 12, other 6. Verdicts applied; corrected_source_url is now honoured by `apply_factcheck.py`.
- **Consistency rules settled by the coordinator** (from checker score notes):
  1. *Part mix* may rest on a company-level (inferred) claim: it earns points but no confidence. "One-offs or production runs" / "prototype to mass production" = mixed (8), not custom (15). Applied: Stony Brook 15 → 8, Browning 15 → 8.
  2. *Process 20* needs MIG or flux-core named as a requirement in a welder or fitter posting for this plant, or stated by the plant. A "preferred" qualification in a non-welding role doesn't count. Applied: Nucor Crawfordsville 20 → 0 (65 → 45). Grid Amite gains a stated FCAW requirement from its own welder posting (to be added, then 0 → 20).
  3. *Scale* needs a stated multi-plant parent; a plant still under construction doesn't make a company multi-plant. Applied: Hapco Abingdon 5 → 0, Hapco OKC 5 → 0, Raycap 5 → 0.
- 12 duplicate or stale rows retired (duplicate opening-line rows on KW Sugar Land, CHM Fort Worth and SSP Fort Worth; the stale Metal Pros "none found" postings row).
- New profiles: **HW Metals, Tualatin OR: 63, Medium** (MIG, SAW and gantry welding; parts up to 138" x 138" x 70'); **Ameron 66th St, Tulsa: 33, Low.**
- **Catoosa telecom lead: not confirmed** (one closed posting; Arcosa's job board, EPA records and 10-Ks name no Catoosa telecom plant). **New, stronger lead:** Arcosa's 15300 Tiger Switch Rd site (Tulsa mailing address, in Catoosa, Rogers County). EPA lists it as Arcosa Wind Towers plant 1675, and live Oct-Nov 2026 postings there are for Meyer Utility Structures, one naming "the Tulsa, OK utility pole manufacturing plant". It looks like the idled wind-tower plant Arcosa's 10-K says it is converting to utility structures. If confirmed it is a list miss: auditor B's "Meyer Utility Structures - Tulsa" row had been wrongly matched to Ameron Tulsa by city.

### Meyer Tulsa added; Grid re-scored; miss rate updated
- **New p-meyer-tulsa-ok** (Meyer Utility Structures / Arcosa Wind Towers, 15300 Tiger Switch Rd, Tulsa OK 74116; the geocoder places it in Catoosa city, Rogers County): **75, High, confidence 4.** Arcosa's Q4 2025 call (2026-02-27): "we are currently preparing for a transition of our Tulsa, Oklahoma facility from wind towers to utility structures." Meyer postings (Sep-Nov 2026) cite "the Tulsa, OK utility pole manufacturing plant", a 2G flux-core weld test, a night premium and several open welder roles. Correction to the earlier lead: the "idled wind tower facility" in the 10-K is Clinton IL (already in the ledger; it "began delivering utility poles in the second quarter" of 2026).
- **Grid Structures, Amite: 40 → 60, Medium.** Its own Amite welder posting lists "1-2 years welding experience with some flux core welding (FCAW)" under desired skills. Process rule applied: a process named in a welder posting for the plant = 20 (Nucor Crawfordsville's was a preferred qualification in a non-welding robotic-operator role, so it stays 0).
- **Hapco OKC opening line:** both clauses now rest on stated rows (operations expected late 2027; welding among 80+ new jobs).
- **Miss rate, updated: 5 / 64 = 7.8%.** Meyer Tulsa is a verified in-definition auditor plant (auditor B's "Meyer Utility Structures - Tulsa") that `compare_audit.py` had matched to Ameron Tulsa by city. Misses: Valmont Birmingham, Raycap, Race Rock Brookshire, Cem-Tec, Meyer Tulsa. Lesson for the matcher: two different companies in the same city must not match on city alone.
- Counts: 97 plants, 66 profiled, 31 excluded. High 4 / Medium 23 / Low 39.
