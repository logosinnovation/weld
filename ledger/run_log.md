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

### Higher-tier review (3 reviewers on Fable, 2026-11-13): all three said "fix first"
Reports: `ledger/audit/review-fable-evidence.json` (13 findings), `-coverage.json` (15), `-sales.json` (14). Blockers: (1) labor wrong at about 11 Arcosa and Sabre plants whose own job boards show open, dated welder postings; (2) Millerbernd, Path's published case-study account, shown as a cold prospect; (3) Valmont Valley NE wrongly excluded, and Valmont El Dorado KS, V&S Schuler and ROHN Peoria missing; (4) **correction: the statement above that "every profiled plant has now been independently fact-checked" was false**: HW Metals, Ameron 66th St and Meyer Tulsa, added after round 3, had not been; (5) the Method page showed stale audit figures.

Coordinator decisions applied now (mechanical):
- **Relationship rule extended:** known_customer also applies when Path's source names the product line and the ledger shows that line is made at only one of the parent's sites. Applied: Millerbernd Winsted → known_customer (Path's case study names its T&I poles; the other two sites make circular products). Nello and Valmont stay customer_other_plant (FAT only; 2021 reference naming no plant). The map will show their Path status as a badge and route existing accounts separately.
- **Confidence rule tightened:** demand 8 (vertical outlook only) never counts toward confidence.
- **Re-scored:** DiHighway material 12 → 0 (an assembled span, not a part size); Race Rock Brookshire material 12 → 0 (no stated size); Valmont Tulsa demand 15 → 8 (the "trigger" was a hiring event); LaX Spring Grove and Westby demand 15 → 8 (company-level statement; Westby opening undated); Sabre Bossier scale 10 → 5 (2017 headcount).
- **Owner strings made consistent:** Arcosa plants all carry the CRH acquisition; the Sabre/FWT TPG deal is shown as agreed with completion not verified; Sovereign shows "acquisition agreed June 2022"; Crest spelling unified; the CHM Saginaw and Hapco parents filled in; lookalike_of normalised to Valmont / Millerbernd / Nello. HW Metals → relationship new, Tier 1 (contract fabricator for a sales firm, not a competitor of a Path customer). MICA Kaufman's leftover exclusion_reason cleared.
- **Process rule wording clarified:** MIG or flux-core named (required, desired or preferred) in a welder or fitter posting for this plant, or stated by the plant, = 20. A qualification in a non-welding role (e.g. robotic-cell operator) does not count.
- **Inclusion rule written down (review coverage-8/-12):** a plant with a current government or certification listing (state DOT qualified list, AISC certification) for an in-scope product is included (base, low confidence), not excluded, unless a source shows it is closed or the product is made elsewhere. Aluminum-only plants (no carbon or stainless welding) are excluded by the prospect test; aluminum-first plants that also weld steel are included and noted.
- **Miss-rate presentation:** 5/64 = 7.8% is measured against two auditors who share the finder's sources, so it is a lower bound. The reviewer found further plants; the rate is recomputed after they are checked.

## 2026-11-13: review fixes merged (workflow poles-review-fixes-1)

- **Merged** review-fix-labor (24 plants, 183 rows), review-fix-valmont (5 plants, 153 rows) and review-fix-coverage (21 plants, 354 rows), in that order. Before each merge its `evidence_remove` list was applied with the new `tools/apply_removals.py`: 53 superseded rows retired (33 + 18 + 2). Each retired row is kept with its reason in `ledger/audit/retired-evidence.csv`.
- **Quote checks:**
  - Labor: 100/100 found.
  - Valmont: 52 found. The 5 "not found" are AISC rows; all match the committed AISC snapshot exactly. The 1 unreachable is a closed Teal copy of Elkhart's "Welder 1st Shift - Steel" posting (404).
  - Coverage: 150 found. The 13 "not found" are all AISC rows, and all 13 match the snapshot.
- **Coordinator decisions on the agents' open questions:**
  - FWT Fort Worth: process and labor set to 0 (option b; 53 -> 21 Low). The tie of Sabre's "Kenn" site to FWT's address is inferred, and inferred-attribution postings earn no points (precedent: DIS-TRAN Washington Court House and the old Alvarado sister-plant row). The Kenn posting is kept as a lead.
  - Valmont Birmingham Tacker: counted as a welding role (production tack welding with a GMAW qualification test is manual welding). 45 Medium.
  - Valmont Claremore: process and part size rest on a ~Nov 2024 posting, and the values now say "as of ~Nov 2024". Kept: how a plant welds is a standing fact, and the 24-month window applies to triggers. 80 High.
  - Structural & Steel Products Crowley: the Fitter/Welder Leadman roles count, under the counting rule (working leads weld).
  - V&S Canton and Burton process: 12 (CLAUDE.md "mixed with TIG" = 12; the QMF precedent). Under the session-2 wording they would be 68; not applied.
  - V&S Muskogee material 20: the seam welder's capacity (60 ft x 80 in) bounds the largest pole section, which fits the 2026 analyst cell limits. LSI material 20: steel poles 4-6 in, up to 39 ft, fit the 2026 limits. Both are boundary calls, noted in their rows.
  - ROHN scale 5: two Peoria divisions are two physical plants.
  - Hughes Brothers: a boundary inclusion (steel H-frames to 345 kV).
  - Exclusion reasons cleared by hand on Valley, Elkhart and Plymouth (the merge doesn't overwrite with blanks).
- **Normaliser bug fixed:** the dimension regex in `normalise_scores.py` missed curly quote marks (60' and 80" typed as ’ and ”), so it zeroed Muskogee and LSI material. Fixed and restored (55 and 48 Medium). Only these two plants were affected: the earlier run only lowers scores, and HW Metals scores 20 on another row. V&S Canton's 6" figure is an angle-punching capacity, not a welded part, and it stays 0.
- **Field drift:** Western Utility Telecom listed "GMAW spray transfer" and "2 seam welders" with no evidence row. The field is trimmed to what the rows quote, and the score_process reasoning is corrected (FCAW alone meets 20). The new `tools/field_drift_check.py` flags 21 more candidates (`ledger/audit/field-drift-2026-11-13.json`). Real cases include Millerbernd's and Nello South Bend's "AWS/AISC" certifications, Nello Westby's "robotics investment" trigger, and Nucor Crawfordsville's, Hapco Oklahoma City's and Klute's trigger figures. These go to the attribution clean-up (phase F2).
- **Counts now:** 117 plants in the vertical; 80 included and profiled, 37 excluded. Tiers: High 8, Medium 32, Low 40. Material unknown (0) on 68 of 80.
- **Miss rate, two measures:**
  - Auditor-measured: 5/64 = 7.8%. A lower bound: the two auditors share the finder's sources.
  - Finder first pass against every plant verified to date: 22 of the 80 included plants were not on the finder's included list. That is 7 found by the list auditors (Elkhart, Birmingham, Raycap, Race Rock, Cem-Tec, Ehresmann, Meyer Tulsa), 2 by follow-up research (HW Metals, Ameron 66th St N), 11 by the higher-tier review (Valmont El Dorado, V&S x3, ROHN, Sabre Conroe, CommStructures, Hughes, LSI, Musco, U.S. Pole), and 2 wrongly excluded then reinstated (Valley, Plymouth). **22/80 = 27.5%**, over the 20% advisor threshold, so it goes to the advisor at the done checkpoint. All 22 are in the ledger now. 9 leads remain unverified (in review-fix-coverage `unverified`).

## 2026-11-13: phase F2, attribution clean-up and round-4 fact-check (workflow poles-f2-cleanup-factcheck)

- **Editors A and B:** rewrote the opening line and bottleneck guess for all 80 profiled plants.
  - Opening lines are composed only from stated claims, which are named in each row's reasoning. They lead with the newest fact, contain no pitch language, and end in a "you" question.
  - Lines for existing Path accounts (Millerbernd, Nello/LaX, Valmont) are framed for account expansion and assert no plant-level deployment.
  - "Unclear" bottlenecks are now "unknown". Hughes Brothers carries the only stated bottleneck, in its own words.
  - 113 superseded rows retired (82 + 31). Each plant now has exactly one opening_line row and one bottleneck_guess row, each matching plants.csv (checked).
- **Attribution clean-up:** 24 plants' fields trimmed or re-sourced. Certifications that were code references or personnel became AISC-snapshot rows (Millerbernd, Nello South Bend, MICA Kaufman). Trigger figures are now quoted with dates (Nucor Crawfordsville, Klute, Nucor West Hazleton, Crowley). Undated or unbacked clauses were dropped (QMF Fanuc, Race Rock "$100M" in products, West Hazleton "welder hiring"). 40 rows replaced. `field_drift_check.py` now flags 9 candidates, all false positives.
- **Round 4 fact-check** (16 plants never checked + 16 with new posting rows): A 8/125 = 6.4%, B 13/64 = 20.3%, C 8/137 = 5.8%. **Pooled 29/326 = 8.9%.**
  - Every correction is "quote does not support value": compound clauses from a sibling page, company-level pages tagged stated at a plant, legal suffixes, and supervisory "Lead" postings counted as welder postings.
  - No wrong plant, wrong process, closed plant or invented fact.
  - Checker B's set (all new plants from the review) is over 10% on its own.
  - On a strict page-only reading, checker A's rate is 16.0%; the clauses involved were all confirmed on a sibling primary source the same day.
  - All 31 corrections applied with `apply_factcheck.py` (0 unmatched).
- **Coordinator decisions:**
  - Ameron 66th St N process 20 -> 0: the only source is a Facility Foreman posting, a non-welding role. Total 13.
  - Hughes Brothers: headcount 304 (company counter, inferred to the site) gives scale 5. A new stated triggers row (Oct 10 2025: robotics investment, another seam welder, "we are adding welders"; each fragment checked on the page) gives demand 15. Total 35, still Low.
  - Sabre Hicksville: renamed "Sabre Industries (Hicksville, OH)". Process 20 and labor 20 are kept, unlike FWT Fort Worth: Sabre's own board lists a single Hicksville site (761 West High Street), so its Hicksville postings belong to this plant. The FWT history is the only inferred part.
  - Muskogee labor stays 20 on 2 non-lead postings open at once, plus mandatory Fridays. Meyer Fort Worth's count drops from 6 to 5, labor unchanged.
  - 17 prospect_test rows carrying a "pass" verdict retagged from stated to inferred.
- **Counts:** 117 plants; 80 profiled, 37 excluded; High 8 / Medium 32 / Low 40. All 80 profiled plants have now been fact-checked in at least one round (summary.json: profiled_fact_checked 80).
- **Leads for the final review:** street addresses found on primary job boards for 9 plants whose address is unknown (Claremore, Clinton, Meyer Fort Worth, Lancaster, Steele, Hager City, Alvarado, Sioux City, Hicksville); Musco multi-plant (EPA FRS lists Oskaloosa sites); Western Utility's AISC listing.

## 2026-11-13: higher-tier final review (workflow poles-final-fable-review)

- The first attempt was cut off by a usage limit; it left an empty inbox stub and half-finished map edits, committed as WIP `9fae162`. The rerun finished both.
- **Ledger review (top-tier model): "ready" once its inbox file is merged.** 0 blockers, 8 majors (all fixed in its inbox), 5 minors. File: `ledger/audit/review-fable-final-ledger.json`.
  - Re-derived all 40 High and Medium plants component by component.
  - Re-read counted postings on the primary boards for 22 of them (Arcosa UKG, Valmont Workday, Sabre's own UKG Ready). No counted posting had closed, no trigger older than 24 months was scored 15, and there was no invented fact, wrong plant or closed plant.
- **Merged** `fable-final-fixes.json`: 23 superseded rows retired first, then 1 plant added, 29 updated and 186 rows added; 0 rejected, 0 coverage gaps. Coordinator decisions:
  - **FWT Fort Worth: the reviewer's tie is accepted, reversing option (b).** EPA FRS names SABRE-FWT at 5750 E Interstate 20, and Sabre's own board files the counted "Kenn" requisitions under that address. The tie is now stated, not inferred. Renamed "Sabre-FWT (Fort Worth ...)". Score 21 -> 61, Medium.
  - Ameron Yukon process 0 -> 20: the Arcosa board summary says "qualified MIG Fitter/Welders". Total 61, Medium.
  - Nucor Decatur process 0 -> 20: "Mig Flux core welding experience" in its own Fitter Welder posting. 60, Medium. Address 913 Maero St, Trinity.
  - Nello South Bend labor 12 -> 20: two welder listings are live on Nello's careers page at once. 75, High. Sensitivity: the listings show no year; if they are stale, 55.
  - MICA Haltom City labor stays 20, now on three Haltom City roles listed at once (aggregator; Indeed blocked). The company-wide signing bonus no longer carries it.
  - Meyer Clinton demand 15 now rests on Arcosa postings calling Clinton "our new plant" and "a startup manufacturing facility".
  - **New plant: Sabre Industries Marshall TX** (2938 Brown Rd, site code MarU). 61 Medium. Rests on Sabre's own board only, so it needs a fact-check.
  - **7 exclusions reversed under the written inclusion rule** (a current DOT listing for an in-scope product means included): Commercial Fabricators Bridgeview, Mid-Park Clarkson, Ackerman & Baynes, Clark Machine, Griffin Welding, L&M Fabrication, Specialty Fab. They are now base records, not profiled, with exclusion reasons cleared by hand.
  - Street addresses and geocodes added for 13 plants (job boards, EPA FRS). The pins move up to 15.5 km; no county FIPS changes.
  - Musco scale 0 -> 5 (multi-site per EPA FRS); Western Utility's certification is AISC Highway Component Manufacturer; Meyer Tulsa's count drops 3 -> 2 (a supervisory Lead), labor unchanged.
- **Map review (top-tier model): "ready".** 10 map defects fixed. The ones that matter most:
  - Score reasoning that contradicted the points (61 rows) now shows the latest coordinator basis first.
  - The pre-production banner was false for the converting Meyer plants.
  - AISC snapshot matches were shown as failed quote checks.
  - Stated-only mode differed between the page and the CSV.
  - Every Low profile now explains which components are unknown and the ceiling.
  - Zero console errors at 1440 px, at 390 px and in dark mode. File: `ledger/audit/review-fable-final-map.json`.
- **Full quote re-check** (`verify_ledger_quotes.py`): 1,204 found plain, 26 found in a browser, 44 matched the AISC snapshot, 6 not found.
  - The two Meyer address quotes are JSON in the posting page's HTML source, checked by the reviewer in raw HTML.
  - Two are website-name rows on unscored plants (Griffin, Allstate).
  - Grid Structures: its Welder posting closed between 11-12 and 11-13. A Fitter (Day & Night Shift) posting for Grid at Amite is open; checked today, it holds labor at 12. The FCAW process row is kept as a standing fact (Claremore precedent), and the welder_postings row is updated.
- `verticals.csv` reason updated to current counts. The `v-poles-substation:status` evidence row is set to partial (it said accepted).
- **Counts:** 118 plants: 81 profiled, 7 base, 30 excluded. High 9 / Medium 35 / Low 37. 80 of 81 profiled plants fact-checked; Sabre Marshall is not yet checked.
- **Miss rate:** the auditor-measured figure is unchanged at 5/64 = 7.8%; every auditor plant is now in the ledger, and `compare_audit.py`'s 5 "MISS?" lines are all matcher artifacts. The finder first-pass figure is **30/88 = 34.1%**: 22 earlier, plus Marshall, plus the 7 reinstated. That is over the 20% advisor threshold; see advisor consultation 5.

### Advisor consultation 5 (2026-11-13): before marking done; miss rate over 20%

- **Advice:** keep the vertical partial for one bounded pass.
  1. An independent round-5 fact-check of everything the final review changed. FWT Fort Worth comes first: the Kenn-site tie may still be inferred if Sabre's board files every Fort Worth requisition under 5750 I-20.
  2. An independent check of the opening lines, which were rewritten before later corrections landed.
  3. Reconcile the miss-rate figures, and report "never found" apart from "found but wrongly excluded".
  4. Close the open leads (Sabre 36th St, Sioux City Murray St, STP, York SC, the unverified names, the AISC sweep names).
  5. Decide Sabre part mix, LSI's prospect test and Klute's parent row.
- **Done if** round 5 is at or under 10% and the leads are closed; otherwise ship as partial.
- **What changed:**
  - `apply_factcheck.py` now stamps today's date.
  - `ledger/audit/stale-lines-2026-11-13.json` lists 86 line rows whose cited claims changed; it goes to the line checker.
  - **One Sabre part-mix rule:** every Sabre plant builds engineered pole assemblies to drawings with volume not stated, which is mixed, 8. Alvarado and Sioux City 68 -> 61; Bossier 53 -> 61. No tier change.
  - LSI keeps its inferred prospect_test pass, flagged for verification. Klute's parent row no longer says "no company website".
  - Round 5 launched: fact-checker A (the 9 changed plants plus 6 addresses), the line checker (44 High and Medium plants plus 10 Low), and a plant-finder for the leads.
- **Miss rate recounted from the audit files:**
  - `compare_audit.py` still matches "Meyer Utility Structures - Tulsa" to Ameron Tulsa, and Ehresmann was never an auditor plant, so the earlier 5/64 was mis-built.
  - Auditor-found plants now included: 58. Of these, 8 were not on the finder's included list (Cem-Tec, Race Rock, Raycap, Valmont Birmingham, Elkhart, Plymouth, Valley, Meyer Tulsa). **Auditor-measured miss rate 8/58 = 13.8%**: 6/58 = 10.3% never found, 2/58 wrongly excluded.
  - First pass against all 88 included plants: **never found 21/88 = 23.9%; found but wrongly excluded 9/88 = 10.2%** (30/88 = 34.1% together).

## 2026-11-13: round 5 (workflow poles-round5)

- **Fact-check round 5** (independent fact-checker A; the 9 plants whose points changed in the final review, plus 6 new addresses): **14/170 = 8.2%**, applied (0 unmatched). 13 of the 14 are one finding:
  - **FWT Fort Worth's site tie is inferred after all.** Sabre's own board files every Fort Worth requisition under "5750 I-20" whatever its site code (Kenn, 36th, AlvU), and EPA lists separate Sabre Fort Worth sites at 2400 NE 36th St and 2300 W Risinger Rd. Under the precedent, process and labor are 0: total 61 -> 21, Low, confidence 0. The opening line is rewritten to state only what EPA and the board show. The final review's reversal of option (b) is itself reversed.
  - Without that block the rate is 1/157 = 0.6%.
  - Confirmed as scored: Ameron Yukon process; Nucor Decatur process and address; Meyer Clinton demand; Musco scale; Nello labor (datePublished 2026-01-30 and 2026-02-02, both still listed); all 6 addresses.
- **My own error, corrected:** I read only page 1 of Southland's careers board and recorded Grid's Welder posting as closed. Round 5-A read the board's API: requisition 621269191, Welder (Day & Night Shift), is open alongside the Fitter. Labor 12 -> 20 (several at once), total 60 -> 68 Medium. The FCAW row stands on a live posting; the false note was removed. The line checker's two Grid corrections assumed the closed posting and were not applied; the existing Grid lines are accurate.
- **Line check, round 5** (98 lines: opening line and bottleneck for the 44 High and Medium plants, plus 10 Low opening lines): **16/98 = 16.3% corrected**, of which 9/98 = 9.2% fixed a fact and 7 only the closing question ("you"). Fact fixes: posting counts after the Lead corrections (Meyer Fort Worth 6 -> 5, Arcosa Muskogee), inferred triggers or products presented as stated (Nucor West Hazleton, ROHN, Ameron 66th St), and Muskogee's monopole clause. 13 corrections applied; 3 not applied (the 2 Grid rows above, and FWT's bottleneck, which assumed a stated tie).
- **Lead close-out (plant-finder):** 17 leads closed.
  - 1 included as a base record: **Sabre Industries 36th Street, 2400 NE 36th St, Fort Worth** (EPA TRI facility, not closed; 6 open requisitions coded "36th", one a longseamer welding pole shafts by FCAW, GMAW or SAW). The tie of the "36th" code to that address is inferred.
  - 10 excluded: Sabre 2101 Murray St Sioux City (consolidated at Southbridge in 2015), KCB Towers, WirelessPSC (designer, no plant), ROHN Frankfort (historic), Outdoor Wireless Networks Euless (boundary; only a 2019 source), Lehigh Utility (boundary; only bridge-mounted sign supports and sign posts listed), GSI Highway, Kasco, Crescent Designed Metals, Structures America.
  - 6 left unverified, each with what was tried: Sabre STP code, Sabre York SC, M.D. Henry, Tower Innovations, MEGATRO, Larson Camouflage.
  - Quotes: 30 found live, 33 match the AISC snapshot, 3 come from the AISC live detail panel (excluded plants only).
  - **New lead, not checked:** a possible MICA Steelworks welding site at Euless TX (a JobTarget "Welder - 2nd shift" hit returned 404; MICA calls Euless an office).
- **Sabre site codes:** round 5-A found Sabre's board uses one address per city with several site codes (Sioux City IowaSG and IowaT, Bossier SBST and SBSU, Conroe ConSG, ConT and ConU, Alvarado AlvSG and AlvU). The lead close-out confirmed Sioux City is a single consolidated site. No evidence of a second plant in the other three cities; the codes read as business units at one site. Logged as a known limit.
- **Counts:** 129 plants: 81 profiled, 8 base, 40 excluded. High 9 / Medium 34 / Low 38.
- **Miss rate:** auditor-measured 8/58 = 13.8%. Finder first pass 31/89 = 34.8%: 22 never found (24.7%) and 9 found but wrongly excluded (10.1%).

### Advisor consultation 6 (2026-11-13): done checkpoint after round 5

- **Advice:** close; three small blockers, and no further fact-check round or consultation needed once they are cleared.
  1. Run the Sabre site-code sweep that was logged as settled but not checked.
  2. Apply round 5-A's line findings (Nello, Musco) and script three checks over all 81 profiled lines.
  3. Close the MICA Euless lead, and check whether any inferred row with an unfound quote earns points.
  - Report round 5 on stated rows too, log the finder-process remedy, and make the smoke test assert the current figures.
- **What was done:**
  1. **Sabre sweep:** EPA FRS queried for SABRE in TX, LA and IA (saved as `ledger/audit/source-snapshot-epa-frs-sabre-2026-11-13.txt`).
     - One Sabre fabrication site each in Alvarado (8653 E Hwy 67, plus Sabre Galvanizing next door at 8669, the "SG" codes), Conroe (3575 Pollok Dr) and Bossier City (5031 Hazel Jones Rd). Each matches the ledger address.
     - Sioux City: 7101 Southbridge (2101 Murray St consolidated there in 2015; lead close-out).
     - Fort Worth has three Sabre sites (5750 E I-20, 2400 NE 36th St, 2300 W Risinger Rd), which is why FWT's postings can't be placed.
     - Alvarado, Bossier City, Conroe and Sioux City scores stand.
  2. **Line checks over all 81 profiled lines** (one row per plant, matching plants.csv; closing question ends in "?" with "you"; every cited claim has a stated row): 6 problems found and fixed.
     - DIS-TRAN Washington Court House and CHM Fort Worth questions made second person.
     - Ameron 66th St and ROHN re-cited to stated rows (open_postings + address; name + address).
     - Musco: the "air-conditioned welding" clause dropped (it was held only by an inferred row).
     - Nello South Bend passes: its Path clause cites the stated c-nello:path_customer row and asserts no plant-level deployment.
  3. **Unfound inferred quotes:** of the 13, only PennFab's weld_processes row is cited by a point-earning score, and PennFab's process 20 also rests on a stated row (services/welding page). The row's source_url is moved from the blog index to the article, and the quote was checked there. The other 12 are Census geocode descriptions or website rows on unscored plants. MICA Euless lead sent to a plant-finder.
- **Round 5 rate:** 14/170 = 8.2% over all checked rows; **13/139 = 9.4% on stated rows only** (1 inferred row corrected). Both are under 10%.
- **Lead counts:** working leads count, under the counting rule. Round 4-C found that Clinton's and Lancaster's leads weld (clip welding, full-penetration welds), while Meyer Fort Worth's, Muskogee's and Meyer Tulsa's are supervisory. Not an inconsistency.
- **Finder-process remedy for the next vertical** (miss rate: 24.7% never found on the first pass). Run inside the plant-finder stage, not after it:
  - (a) an AISC directory name sweep for every parent and known maker;
  - (b) a sweep of every parent's own job board by city;
  - (c) EPA FRS and TRI name queries;
  - (d) the inclusion rule applied at finding time, so DOT-listed plants are not excluded on judgement.
  - **Convergence:** the last two passes found one plant each (Sabre Marshall; Sabre 36th St).
- **Smoke test** saved as `tools/smoke_map.js`. It opens the Method tab and asserts 81, 8.9%, 8.2%, 13.8%, 34.8%, "Round 5" and "partial", and that no stale text remains ("every included plant is profiled", "27.5%", "5/64"). Pass, 0 console errors.

## 2026-11-13: v-poles-substation marked DONE

- **MICA Euless lead closed:** included as base record p-mica-euless-tx (3501 House Anderson Rd; Tarrant County 48439).
  - A current "Welder - 2nd shift" posting names the "MICA Steelworks Euless, Texas Plant" (flux core and metal core, UT-passable welds; Tallo shows it posted Oct 13 2026, updated Nov 12).
  - EPA FRS 110070704100 lists "MICA STEELWORKS EULESS" (SIC fabricated structural metal).
  - MICA's contact page calls Euless an "office", but it calls the TxDOT-approved Kaufman plant an office too. Products are inferred at company level.
  - 12/12 quotes found.
  - New lead, not checked: MICA postings at Rhome TX. **The one open lead**, carried to the next pass.
- **Done criteria (advisor consultation 6) met:** round 5 is 8.2% (9.4% on stated rows), under 10%; the three blockers are cleared (Sabre site sweep, line checks over all 81 plants, MICA Euless); leads are closed (1 included, 10 excluded, 6 unverified with what was tried; Rhome logged as open).
- verticals.csv and the `v-poles-substation:status` row are set to done. summary.json and the map are rebuilt; `tools/smoke_map.js` passes (0 console errors).
- **Final counts:** 130 plants found; 90 included (81 profiled, 9 base), 40 excluded. Profiled tiers High 9 / Medium 34 / Low 38.
- **Fact error rate by round:** 11.8%, 19.4%, 8.2%, 8.9%, 8.2%.
- **Miss rate:** auditor-measured 8/58 = 13.8%. Finder first pass 32/90 = 35.6%: 23 never found (25.6%) and 9 wrongly excluded (10.0%).
- **Weights:** unchanged from CLAUDE.md, the whole vertical through. The coordinator rules for applying them are logged above.
- **Next vertical by rank:** Shipbuilding and naval defense. Not started; CLAUDE.md allows one vertical per session, so it waits for the user's go-ahead.

## 2026-11-13: v-shipbuilding-naval (Shipbuilding and naval defense), Stages B-C started

- **Session rule:** CLAUDE.md says one vertical per session. The user asked in this session to "continue with the next vertical", so the second vertical runs here. The user's explicit instruction overrides the default.
- **Vertical** (rank 2, accepted 2026-11-12): "Welded steel ship and barge structures built in US shipyards and their structural-assembly suppliers: hull blocks, panels, units and modules, foundations and naval components for Navy, commercial, workboat, unmanned-vessel and inland-barge construction." Confirmed Path customers: HII (production agreement; scope starts with small steel structures), Saronic (Franklin LA), LAD Services (Louisiana barges).
- **Boundary rules set at find time** (from the poles lessons; logged before research):
  1. **Construction, not repair:** a yard qualifies if it builds new hulls, barges or structural units, or fabricates structural assemblies or naval components for builders. A repair- or conversion-only yard is excluded ("repair-only; definition covers construction"), kept in the ledger, and marked boundary where repair includes major steel renewal.
  2. **Material:** aluminum-only and fiberglass builders are excluded. Aluminum-first yards that also weld steel are kept and noted (material scores 4).
  3. **Inclusion at find time:** a current government, Navy or industry listing naming the plant as a builder or supplier of in-scope structures, or a current welder posting tying in-scope work to the site, means included (base). Judgement exclusions need a quoted reason.
  4. **Multi-site parents:** one record per physical yard or plant. Navy prime work at one yard does not carry to sister yards (relationship customer_other_plant unless a source names the site).
  5. **Pre-production and expansion sites** (new yards under construction) are included and flagged, as on poles.
- **Finder process (remedy from the poles vertical):** the sweeps run inside Stage B: EPA FRS by name and by NAICS 336611, MARAD and Shipbuilders Council lists, Navy and submarine industrial-base supplier announcements, and each parent's own job board by city. The finder is split into four parallel slices by company group and region.

### Ships Stages B-C merged (workflow ships-finder)

- **Four slices merged:** 134 plants written (97 base, 37 excluded), 1,266 evidence rows added, 15 supplier links. 0 rows rejected, 0 duplicate ids.
  - A: Navy primes and major yards, 40 plants.
  - B: Gulf commercial, workboat and barge yards, 39.
  - C: inland, Atlantic, Great Lakes and Pacific yards, 36.
  - D: naval structure and module suppliers (Keel, Trident, Gulf Copper, Rhoads, BAE, BWXT, Anduril and others), 19.
- **Gaps to repair:**
  - 96 coverage gaps, all parent_company or website fields (B 65, C 31).
  - 36 quotes not found and 32 pages unreachable. Most are JavaScript job boards (ADP, Paylocity, which need the browser) or EPA FRS timeouts.
  - Address conflicts to resolve: NASSCO Jacksonville (excluded) and BAE Jacksonville share 8500 Heckscher Dr; two Conrad Morgan City records share 995 Duhon Blvd; Trident Lockport has no address.
- **Ranking:** `rank_for_profiling.py` misparsed postings for this vertical (ZIP codes and years read as posting counts). The coordinator ranked instead by relationship, tier, the number of stated welder_postings rows, headcount and sources.
- **Relationship rule for this vertical** (the slices were inconsistent):
  - known_customer: the source names the site (Saronic Franklin), or a single-site customer.
  - customer_other_plant: other HII sites, Saronic Brownsville, other LAD sites.
  - lookalike, naming the customer:
    - (a) Navy or Coast Guard combatant, auxiliary or submarine builders -> HII;
    - (b) plants building structural units, modules or hull sections for Navy yards -> HII, because Path's HII scope is "small steel structures" in HII's distributed shipbuilding;
    - (c) inland or coastal barge, tug and workboat builders -> LAD Services;
    - (d) unmanned or small military steel craft -> Saronic.
  - new: everything else in scope (ferries, research and fishing vessels, yachts).
  - Profilers apply the rule to their plants; the repair agent applies it to the rest.
- **Profiling selection (40, per FULL_PROFILES_PER_VERTICAL):**
  - every customer and customer_other_plant site (7);
  - the Navy combatant and submarine yards;
  - HII, EB and Ingalls structural-unit suppliers (Keel x3, Trident x2, Gulf Copper Galveston, Rhoads, BAE Jacksonville);
  - the leading barge and workboat yards by postings and sources.
  - 4 profilers x 10, grouped by company. The other 57 included plants stay base.

### Ships Stages D-E merged (workflow ships-profile)

- **Merged:** profilers A-D (40 plants) and repair-1 (77 base and excluded records), with each file's evidence_remove applied before its merge (58 rows retired). 0 rows rejected, except one example row with no reasoning (Eastern Nelson). 0 coverage gaps.
- **Southwest Shipyard Channelview** is excluded as repair-only, per the boundary rule (its own page lists only barge-repair docks). Profiled: 39.
- **Philly Shipyard** is set to relationship new (Jones Act and MARAD ships; only a Navy design-study subcontract). lookalike_of cleared by hand.
- **NASSCO Jacksonville** moves to 2999 Mayport Rd (nassco.com). EPA also registers it at 8500 Heckscher Dr, BAE's address. Conrad Deepwater Repair is a distinct yard next to Deepwater South (its own page, acreage and phone) and stays excluded as repair-only.
- **Ships tiers (39 profiled):** High 16, Medium 12, Low 11. Material is unknown (0) on most plants.
- **Coordinator rules for this vertical** (the profilers split; these apply in fact-check and normalisation):
  1. **TIG.** Process scores 12 ("mixed with TIG") when the plant's own structural or production welder or fitter postings name TIG/GTAW alongside MIG or FCAW, even as a plus. It scores 20 when TIG appears only in a separate pipe or specialty welder role, because structural production welding is then MIG or FCAW.
  2. **Hull size.** Material is 12 (too big to move, suited to Rove) when a stated dimension or weight of the welded product the plant builds (vessel, barge, block, unit or module) exceeds the cell limits. It is 20 when a stated welded part fits a cell. A facility, crane or lift capacity is not a part size; NASSCO's blast-cell size and NNS's superlift weight go to the fact-checkers to judge under this rule.
  3. **Shared job-board locations.** A posting counts for a plant only when the board's location field or the posting text names that site. A city shared by several of the company's sites does not count (Bollinger Pascagoula labor 0). A Workday requisition-location field that names a yard does count (Eastern Allanton).
  4. **Grants.** A dated MARAD Small Shipyard Grant or similar award for equipment at the plant within 24 months is a plant-level trigger (demand 15).

### Ships Stage F, round 1 (workflow ships-stage-f; resumed after a usage-limit stop)

- **Fact-check, all 39 profiled plants:**
  - A 8/205 = 3.9%, B 16/202 = 7.9%, C 23/236 = 9.7%. **Pooled 47/643 = 7.3%.**
  - Kinds: quote does not support value 37, other 10 (an article date or status restated as current). No invented fact, wrong process or closed plant.
  - Applied with `apply_factcheck.py`, 0 unmatched. The tool now honours a checker's `plants_csv_value`: "keep current" leaves the plant field alone when the corrected row is one fragment of a multi-row claim.
- **Coordinator rulings on score notes:**
  - NABRICO Ashland City demand 15 -> 8: the sale covers the whole barge business, a company-level event. 73 High.
  - JamesBuilt process 12 -> 0: a pooled multi-site posting. 47 Medium.
  - NASSCO material 12 -> 0: 52x52x30 ft is a facility envelope. 75 High.
  - LAD demand 15 -> 8: the award and grant name only the shared city. 28 Low.
  - Senesco material 12 -> 0: the figure is a machine capability. 35 Low.
  - NNS material 12 stands: the 704 t, ~80x105 ft superlift is a stated welded block.
  - Rule 1 confirmed by the checkers at EB, Austal, Eastern Allanton and Philly (TIG only in pipe roles, so 20), and at St. Johns, OPIP, Keel Hollywood, Rhoads, Trident and Conrad Deepwater South (TIG in the production posting, so 12).
- **Pending evidence** (agent `ships-fills-1`):
  - Bollinger Pascagoula labor 0 -> 20: ADP's HomeDepartment "BMS Pascagoula" names this yard, not the repair yard, the same test as Eastern's location field. To apply once a stated row quotes it.
  - Chesapeake process 20 -> 12: TIG in a production fitter posting; needs its row.
  - Caruthersville Yard II to be excluded: fiberglass barge-cover manufacturing.
  - Extra live postings at JamesBuilt and Gunderson.
- 36 tier, tier_secondary and prospect_test rows tagged stated retagged inferred (they are judgements).
- **List audit:**
  - Auditor A: 199 rows (112 in, 87 out), 58 searches. Auditor B: 147 rows (103 in, 44 out), 84 searches.
  - `compare_audit.py`: 153 in-definition auditor plants matched to 72 ledger plants, with **59 candidate misses**. Some are matcher artifacts (Keel Yonges Island, EB Quonset, Eastern Allanton, SanJac, Giddings). Many are real: towboat and barge yards, Fairlead x2, Hadrian, Bayou Metal, Galliano, NNS Norfolk campus. 19 rest only on the 2023 Shipbuilding History small-builder list.
  - Two plant-finders are verifying all 59 (workflow ships-miss-verify) before the miss rate is computed. It will clearly be over 20%, so it goes to the advisor.
- **Ships tiers now (39 profiled):** High 16, Medium 11, Low 12.
- **Fill-ins merged (`ships-fills-1`):** 20 rows retired first, then 36 added; 0 rejected. Quotes: 18 found plain, 1 found with --browser (Chesapeake's Paylocity page).
  - Bollinger Pascagoula labor 0 -> 20. HomeDepartment "BMS Pascagoula" is on Welder A (2026-05-20), Pipewelder A, Shipfitter A and Welder Lead B. Bollinger's own release defines BMS (shipbuilding) apart from BMR (repair), and its careers page sends Mississippi Shipbuilding to this board and the repair yards to another. 55 Medium. Sensitivity: 35 if the department field is not accepted; no open requisition carries a repair department.
  - Chesapeake process 20 -> 12: "SMAW, MIG, TIG" in the Fabricator & Fitter posting (rule 1). 55 Medium.
  - JamesBuilt: the two postings previously counted are hidden (display:none) on the live page, so they are retired. Labor 20 now rests on a Structural Steel Fitter and a Welder Trainee, both James Built, Calvert City. 55 Medium; 47 if the trainee is not counted.
  - Gunderson: its own board (jobs.gem.com/giwx) lists an experienced Fitter/Welder (JobTarget date Mar 3, 2026) and a Fitter/Welder Trainee in Portland. Labor 12 -> 20, 82 High.
  - Caruthersville Yard II excluded as fiberglass barge-cover manufacturing (EPA FRS 110017980595 "CARUTHERSVILLE COMPOSITES", SIC 3089; separate "Covers" board location; Waterways Journal May 2026).
- **Tool bug fixed:** `apply_factcheck.py` wrote a checker's "(keep current ...)" and "(identical to ...)" notes into 6 plant fields (NABRICO x2, Chesapeake). The fields were restored from the commit before the apply, and the tool now recognises those forms. No evidence row was affected.

### Ships miss verification (workflow ships-miss-verify) and miss rate

- **All 59 candidate misses resolved** by two plant-finders:
  - **30 verified misses**, now base records, plus 2 sister yards named by the candidates' own sites (DSC Poplarville, Bludworth Orange).
  - **12 already in the ledger** under another id or city (matcher artifacts: Keel Yonges Island, EB Quonset, Eastern Allanton, SanJac, Giddings, Serodino and others).
  - **2 excluded**, aluminum-only: Midship Marine; Bayou Metal (its HII ROMULUS work is aluminum).
  - **Duplicates folded:** Fairlead Portsmouth into Newport News; the TAI Holdings award resolved to its builder, Steiner Construction.
  - **17 unverified**, each with what was tried: Catalyst, Master Marine, Eagle Fabrication, Hope, Bourg, Inland Boat Works, Sisco, Mobro, Newton, Rodriguez Bayou La Batre, Sneed, Progressive, Moe, Galliano MUSV yard, Yager, and the Keel Saginaw and Merrill sites.
  - Merge: 34 plants added, 486 evidence rows, 3 links; 0 rejected, 0 coverage gaps. Quotes: 289 found, 7 unreachable (transient).
- **Miss rate (auditor-measured): 30 / 107 = 28.0%.**
  - Denominator: in-definition auditor plants that exist. 77 were found in the ledger (72 matched by the script plus 5 matcher artifacts that are included) plus the 30 verified misses.
  - 5 auditor plants are excluded in the ledger, each with a quoted reason (Breaux Brothers aluminum, Metal Shark aluminum, Eastern Port St Joe repair, Southwest Channelview repair, Foss Rainier). They are not counted as misses.
  - **Over the 20% threshold**, so it goes to the advisor (CLAUDE.md).
- **Where the misses are:** small inland towboat, barge and dredge builders (Verret, Eymard, Intracoastal Iron Works, FMT, Main Iron Works, John Bludworth, Superior Marine Ways, Sterling, Bludworth, Vessel Repair, Westport, National Maintenance, Donjon, DSC, Ellicott, Duckworth, Jemison, Williams, Rodriguez Coden, Blakeley, WCT, JT Marine, New Pacific, Moran, Marine Group, Steiner Construction), plus Navy structure suppliers (Fairlead, Colonna's Steel America, Hadrian Cherokee, NNS Norfolk campus).
  - The finder slices B and C under-swept the small Gulf and inland builders.
  - Slice D missed Fairlead, Colonna's Steel America and Hadrian, and slice A missed NNS's own Norfolk site.
- **Counts:** 168 plants in the vertical: 39 profiled, 88 base, 41 excluded.

### Advisor consultation 7 (2026-11-13): ships miss rate 28.0% (over 20%)

- **Advice:** not done. Ship it as partial now, then run one bounded closure pass:
  1. A plant-finder on auditor B's unchecked names, auditor A's leftovers, all FY2023-26 MARAD Small Shipyard Grant recipients reconciled by script, and the open leads.
  2. Profile the NNS Norfolk campus (customer_other_plant). Resolve LAD's three sites (the record may be on the wrong yard; two are missing).
  3. Check the 94 matched audit rows by eye.
  4. Re-run the scripted line checks.
  5. One fact-checker on the closure work.
  6. Fix the summary writer, which would overwrite poles.
  - **Done if** the closure pass adds no top-40 plant and only a handful overall, and its checker is at or under 10%.
- **What changed:**
  - `write_summary.py` now writes `ledger/audit/summary-<vertical>.json` with round labels per vertical. The poles file was renamed to `summary-v-poles-substation.json`, contents unchanged. The map-builder is updating the map to read one summary per vertical.
  - Ships set to **partial** (verticals.csv and the status evidence row); `summary-v-shipbuilding-naval.json` written.
  - **Matched rows checked by eye** (94):
    - Steiner Construction was paired with Steiner Shipyard, a different company, and Rodriguez Coden with Master Boat Builders. Both are already among the 30 verified misses.
    - West Gulf Marine was paired with Gulf Copper Galveston. It is now an 18th unverified candidate.
    - Galliano (Houma) was paired with LaShip, another Chouest Houma yard. Plausibly the same; already unverified.
    - Conrad Deepwater South was matched to the main yard; it is in the ledger as its own record.
    - **Miss rate unchanged at 30/107 = 28.0%; upper bound 48/125 = 38.4%** if all 18 unverified are real. The log's "72 plus 5" is corrected: the 77 found are the matched-and-included plants plus the resolved-to-existing ones.
  - **Scripted line checks on the 39 ships plants** found 8 problems:
    - The same placeholder bug, in another form: "(same as corrected_value)" had been written into the NASSCO and Sturgeon Bay opening lines. Restored from their rows; `apply_factcheck.py` now handles that form.
    - Two missing bottleneck rows (OPIP, Keel Goose Creek) added as unknown.
    - Keel Goose Creek's question made second person.
    - LAD's line cites a triggers claim that is now inferred (company-level); it goes to the LAD profiler.

### Ships closure pass (workflow ships-closure; three agents hit the usage limit and were resumed)

- **Closure-1 (unchecked auditor names, unverified candidates, leads):** 58 decisions.
  - 7 base: Accurity Owensboro (Tier 1, structural fabrication for NNS through Colonna's from Aug 2026), Ellicott New Richmond, West Gulf Marine, Western Towboat, Sunflower Dubuque, Stabbert Anacortes, Sisco Marine.
  - 8 excluded: Saronic Austin, DSC Greenbush, Bludworth Pier 38, NNS Hampton (light manufacturing), Trident Baltimore, Fishersville and High Bridge (machinery), Textron New Orleans.
  - 6 resolved to existing; 37 unverified, each with what was tried.
  - The agent hit the usage limit after writing its complete file (58 decision lines), so the file was used as written.
- **Closure-2 (MARAD Small Shipyard Grants FY2023-26):** 104 awards, 93 unique recipients, reconciled by script and checked by eye.
  - 42 already in the ledger, 1 new base (Burger Boat, yachts), 34 excluded (21 repair-only, 2 aluminum-only, 11 not shipbuilders), 16 unverified.
  - The award-by-award reconciliation is in the inbox file's `grant_reconciliation` key.
- **Merged:** 50 plants added, 782 evidence rows; 0 rejected, 0 coverage gaps. Quotes: 423 of 423 found.
- **Convergence:** the closure pass added 8 included plants, all base and without welder postings. Its best new plant (Accurity) ranks 41st by the profiling order, so the pass added no top-40 plant, which meets the consultation-7 condition.
- **Ranking check across all ships base plants:** 7 base plants from the list audit now rank inside the top 40 (Keel Alma, Fairlead Newport News, Nichols Brothers, Vessel Repair Port Arthur, DSC Poplarville, Colonna's, Westport Orange), plus NNS Norfolk (being profiled). These 7 and Accurity go to one more profiler, so the scored set matches the ranking. One fact-checker then covers all closure and fill-in work.
- **Closure profiles merged** (16 rows retired first, then 64 added; 24/24 quotes found):
  - **NNS Norfolk** (customer_other_plant): profiled, 33 Low. Steel panels for CVN 80 since Nov 2023 (one panel 8,200 lb), so material 20 on weight alone, a boundary call. **Not confirmed operating after 2023**: HII's current NNS fact sheet names only Goose Creek as an additional site.
  - **LAD Hwy 662 (Amelia facility):** record corrected and renamed. The county stays 22007: LA 662 is in Assumption Parish, and EPA's "St. Mary" is the mailing area. The opening line is rebuilt from company-level stated rows; 28 Low.
  - **New base record:** LAD Stephensville Rd (EPA "LAD SALVAGE", St. Martin Parish 22099), customer_other_plant. LAD's third facility was not found (unverified; Berwick and Amelia leads).
  - **Trident Lockport excluded** under the Ferndale precedent: no address or facility record, only a regional posting. Scores, opening line and bottleneck cleared by hand; its 2 links deleted.
- **Closure-2 rerun (second pass):** Burger Boat withdrawn. Its dated builds are aluminium; steel appears only as a capability phrase. The plant row and 15 rows were removed (kept in retired-evidence.csv); it is now an unverified lead, not an excluded plant. Sunflower resolves to closure-1's record. Net new base records from the grants: 0.
- **Map (map-builder):**
  - Reads `summary-<vertical>.json`; one Method audit section per vertical, with each vertical's own fact-check files.
  - HII, Saronic and LAD sites appear in the existing-accounts block.
  - Company-level link targets (c-electric-boat) show as company nodes.
  - Pre-production badges: Saronic Port Alpha, Master Boat's new facility, Anduril Arsenal-2, Hadrian Cherokee, New Pacific.
  - `tools/smoke_map.js` asserts both verticals' figures and cross-contamination. SMOKE PASSED, 0 console errors.

### Ships profiler E and fact-check round 2 (workflow ships-final-profile-check)

- **Profiler E:** the 8 base plants ranking inside the top 40 are now profiled. DSC Poplarville 75 High; Colonna's Steel America 72 High; Accurity 67 Medium (after the ruling below); Nichols Brothers 64 Medium; Keel Alma 53 Medium; Vessel Repair Port Arthur 35 Low; Fairlead Newport News 28 Low; Westport Orange 23 Low. Merged: 12 rows retired, 196 added; 0 rejected.
- **Fact-check round 2 (checker D, confirming): 22/360 = 6.1%** (6.4% without the 18 unreachable rows, 16 of them an EPA FRS maintenance outage).
  - By set: profiler-E plants 10/159 = 6.4%; fill-in and closure plants 3/124 = 2.6%; base-record sample 9/77 = 13.0% (6 defects on 5 plants, no score effect).
  - Kinds: quote does not support value 18, other 4 (dates or tense). No wrong plant, wrong process, closed plant or invented fact. Applied, 0 unmatched.
  - Worst: Gunderson's line presented a March 2025 contract as current; Sunflower had three clauses not on its 2023 page; DSC had a company-level row tagged stated.
- **Coordinator rulings:**
  - Accurity process 12 -> 20 under rule 1: the production welder posting names FCAW and GMAW only; GTAW is on a general shop list that also covers pipe spools. 67 Medium.
  - NNS Norfolk material 20 -> 0: one panel weight without dimensions does not establish a cell fit. 13 Low. Its opening line now asks whether the campus still builds panels rather than assuming it does. Its recorded address matches Fairlead's Norfolk address: flagged.
- **Ships now:** 218 plants; 47 profiled (High 18 / Medium 15 / Low 14), 87 base, 84 excluded. Every top-40 plant by the ranking is profiled.
- **Fact error rate by round:** 7.3%, 6.1%.
- summary-v-shipbuilding-naval.json rewritten; map rebuilt; smoke passed.

### Advisor consultation 8 (2026-11-13): ships done checkpoint after round 2

- **Advice:** mark done after five scripted fixes; no new agent round and no further consultation.
  1. Re-run the ranking and correct "every top-40 plant is profiled" (LAD Stephensville).
  2. Recount the miss rate (Sisco and West Gulf were confirmed in closure).
  3. Run `verify_ledger_quotes.py` over the whole ledger, and zero any High or Medium component whose quote can't be re-found.
  4. Re-run the line checks on all 47 plants and sweep for tense errors.
  5. Update verticals.csv, the status row, the smoke test and the map; republish.
  - Not blocking: base records are the weak layer (13.0% sample; run drift on base too); posting searches were not run for most audit-added base plants; Accurity's late posting made it a top-40 plant (profiled and checked); NNS Norfolk's address flag; next-vertical remedy: run the blind audit right after the finder.
- **Done so far:**
  1. **Ranking on the final ledger:** the only base plant in the top 40 is LAD Stephensville (9th, customer_other_plant). It stays unscored because no source says which LAD yard builds new barges. Status rows added to both LAD records and to NNS Norfolk (operation after 2023 unconfirmed; address shared with Fairlead's Norfolk site).
  2. **Miss rate recount:** closure-1 confirmed Sisco Marine and West Gulf Marine (both auditor candidates). **32/109 = 29.4%**; 15 auditor candidates remain unverified, so the upper bound is 47/124 = 37.9%.
  4. **Line checks on all 47 profiled ships plants:** 0 problems. Tense sweep: 3 bottlenecks presented dated work as current and were reworded with the date (Gunderson's March 2025 Tidewater contract, DSC's Dec 2025 release, St. Johns' 2025 orders). The other "while" uses join two current stated facts.
  - **Drift:** `field_drift_check.py --all` now includes base records. It flags 73 ships rows (`ledger/audit/field-drift-ships-2026-11-13.json`), many of them date, day-count or pay-rate formats. This is a known limit and the first follow-up, along with posting searches on base records.
  3. `verify_ledger_quotes.py` is running.
- **Fix 3: full-ledger quote re-check** (`verify_ledger_quotes.py`, 2026-11-14): 2,901 found plain, 41 found in a browser, 79 matched the AISC snapshot, 291 not found.
  - 237 of the 291 are EPA FRS rows. The registry was returning 503 (maintenance) during the run and still is, so these are outage results. Each was found at its merge-time check.
  - 28 not-found rows carry points on High or Medium plants. They were re-checked in a browser fragment by fragment, and 18 still miss. All 18 are job-board rows (ADP, Ashby, UltiPro, Paycom, Workday, Jamis, Nucor, Vaia) that independent fact-checkers confirmed on 2026-11-13 through each board's API or a browser. The page-fetch tool cannot reproduce those reads.
  - One posting is known to have closed since: Valmont Brenham's Flip-Tack Welder (Workday 404 on 2026-11-14).
  - **Ruling:** posting rows are a dated 2026-11-13 snapshot, confirmed that day by independent checkers, so no component is zeroed. The limit is stated on the map.
- **Fix 5:** ships set to **done** (verticals.csv; the status evidence row). `summary-v-shipbuilding-naval.json` rewritten (miss 29.4%; limits as above). smoke_map.js asserts done, 29.4%, 7.3% and 6.1%. Map rebuilt: **SMOKE PASSED**. Republished to the same link.

## 2026-11-14: v-shipbuilding-naval marked DONE

- **Final counts:** 218 plants; 134 included (47 profiled, 87 base), 84 excluded. Tiers: High 18 / Medium 15 / Low 14.
- **Fact error rate:** round 1 7.3% (47/643, all 39 first-wave profiles); round 2 6.1% (22/360; base-record sample 13.0%).
- **Miss rate:** 29.4% (32/109), up to 37.9%. Weights unchanged.
- **Remedy for the next vertical:** run the blind list audit right after the finder, before choosing the 40, and search welder postings for every base record before ranking.
- **Next vertical by rank:** Mining and heavy equipment. Not started; it waits for the user.

## 2026-11-14: v-mining-heavy-equipment (Mining and heavy equipment), Stages B-C started

- **Instruction:** the user said "Start it." (next vertical by rank, in this session).
- **Vertical** (rank 3, accepted 2026-11-12): "Heavy welded steel plate structures for mining, construction and bulk-material equipment made in US plants: buckets, truck bodies, booms, excavator and loader arms, frames, hydraulic tanks and wear attachments."
  - Confirmed Path customers: Mine Rite (Wyoming; specialty mining attachments; 85% of work moved to a Path cell) and Schenck Process (2021 application).
  - Not confirmed: AMSi and Cheetah (analyst report only).
  - Demand outlook and plant count are unknown from Stage A; the finders must supply a stated vertical demand-outlook row.
- **Boundary rules, set before research:**
  1. **In:** plants whose core welded products are structures for mining machines, construction and earthmoving machines, or bulk-material and aggregate equipment (crushers, screens, conveyors, feeders), and the attachments, buckets, haul-truck and off-road dump bodies, booms, arms, frames and hydraulic tanks for them. This covers OEM plants, Tier 1 and Tier 2 weldment suppliers, and attachment makers.
  2. **Out to other verticals** (excluded here with the reason, so a later vertical can pick them up):
     - agricultural equipment (v-agricultural-equipment);
     - cranes and lifting equipment (v-cranes-lifting);
     - on-road dump and truck bodies (v-truck-bodies);
     - trailers and chassis (v-trailers-chassis-mobile-power).
     - Forestry machines count as construction equipment when the plant also builds construction or mining machines; a forestry-only plant is boundary, kept and noted.
  3. **Assembly-only:** a plant that only assembles bought-in weldments (paint and assembly, engines, drivetrains, electronics) fails the prospect test and is excluded, with a quote.
  4. **One record per physical plant.** The large OEMs (Caterpillar, Deere, Komatsu, Volvo CE, CNH, Doosan Bobcat and others) get a record per US plant that welds structures.
  5. **High-volume fit:** a high-volume plant with fixed robot lines stays in, but part mix scores 0 where identical high-volume parts are stated. Its weak fit is recorded, not excluded.
  6. Inclusion at find time, pre-production sites, and relationship as on ships:
     - known_customer: Mine Rite's plant if a single site;
     - lookalike: Mine Rite for mining attachments, truck bodies, buckets and tanks; Schenck for bulk-material equipment;
     - new: otherwise.
- **Process remedies from ships:**
  - The blind list audit runs **in parallel with the finders**, before profiling is chosen.
  - Finders record welder postings, with dates and site, for every plant, so the ranking is not provisional.
  - EPA FRS and NAICS sweeps (333120 construction machinery, 333131 mining machinery, 333922 conveying equipment, 332312 fabricated structural metal where products fit) run inside the finder stage.

### Mining Stages B-C merged; research paused (weekly usage limit)

- **Finders (workflow mining-find-and-audit):** 4 slices.
  - A: OEMs, 61 plants. B: mining specialists and attachments, 31. C: bulk-material equipment, 46. D: weldment suppliers, 53, plus the vertical's demand outlook.
  - Three cross-slice duplicates were folded into slice B's ids before the merge: Epiroc Two Harbors = LaBounty, Epiroc Dexter = Paladin, Epiroc Ooltewah = Paladin/C&P. Same addresses; 30 of slice A's rows were remapped.
  - **Merged:** 188 plants (165 base, 23 excluded), 2,115 evidence rows, 3 links; 0 rejected, 0 coverage gaps.
  - **Quotes:** 1,298 found. 55 EPA FRS rows unreachable (the outage continues). 45 not found: 44 are browser-only job boards (Mayville Engineering's UKG, ADP) whose page text the finder captured; 1 is a Gradall page.
- **Blind list audit:** run in parallel with the finders (the process remedy from ships).
  - Auditor A (company and product angle): 141 rows, 110 in definition, 81 searches.
  - Auditor B (registries and geography): **stopped at the account's weekly usage limit (resets Nov 19)** after 28 rows.
  - `compare_audit.py`: 116 in-definition auditor plants, 74 ledger plants matched, **36 candidate misses**, about 31% before verification. Mostly attachment makers, paving and roadbuilding machine makers, and LBX, SANY, Takeuchi, Kubota Salina, L&H Industrial, Weldall and Hol-Mac.
- **Status: partial** (CLAUDE.md rule 8: research stops, the map ships). No mining plant is profiled or fact-checked yet. Summary written; map rebuilt (smoke passed) and republished.
- **To resume after Nov 19:**
  1. Finish auditor B.
  2. Verify the 36 candidates.
  3. Rank, with postings searched per plant (the finders already did this for their plants), and profile the top 40.
  4. Fact-check all profiles.
  5. Advisor checkpoints: miss rate (likely over 20%) and done.

### 2026-11-16: mining resumed (agents available again before the Nov 19 reset)

- A probe agent ran, so the limit had lifted for agent work.
- **Auditor B finished** (resumed blind from its own partial file): 145 rows, 108 in definition, 76 discovery searches; dry after about 61.
- **Auditor A's 36 candidates verified** (two plant-finders): 24 new base records, 6 excluded (e.g. Superior Pekin is an office; LBX Lexington is HQ and distribution), 2 resolved to existing, 4 unverified (TerraSource Duncan, Blue Diamond and others). Merged: 30 plants, 446 rows; 0 rejected. Quotes: 305 found, 6 not found, 4 unreachable (EPA outage). 3 coverage gaps to fix.
- **Comparison with both auditors complete:** 177 in-definition auditor plants (deduplicated), 117 ledger plants matched, 31 still unmatched. 7 of the 31 are auditor A candidates already decided; 24 are new from auditor B and are being verified (workflow mining-verify-b).
- **Auditor B's candidates verified** (mining-misses-3 and -4; the two halves overlapped on Craig, which was written once):
  - 14 base: Klein Jacksonville TX and Ontario CA (haul-truck water tanks), Construction Attachments Lenoir, Rimpull Olathe, Alliance Fabrication Gary, Stedman Aurora, REMco Stockton (current site; Livermore is old), TCI Walnut, Craig Ethridge and others.
  - 5 excluded, e.g. Sakai Adairsville (assembly only; its frames come from Advanced Steel Technology, Rome GA) and Caterpillar Elkader (closed).
  - 4 unverified, e.g. Monarch Milwaukee (no 2023+ source) and Morton Metalcraft (now Matcor, Morton IL: a lead).
  - Merged: 19 plants, 315 rows; 0 rejected. Quotes: 221 found, 4 not found, 4 unreachable.
- **Miss rate (verified, both auditors): 38 / 126 = 30.2%.**
  - Denominator: in-definition auditor plants now included in the ledger, matched or resolved, plus verified misses the script didn't match (CMI Waverly, Niece Buda, REMco Stockton).
  - Upper bound with the 8 unverified: 46/134 = 34.3%.
  - 13 auditor rows remain unmatched; all are decided (excluded or unverified).
  - **Over the 20% threshold: advisor checkpoint.**
- **Vertical now:** 237 plants (203 base, 34 excluded). Not yet profiled.
- **Where the misses are:** small attachment and bucket makers (Amulet, Genesis, Skid Pro, Virnig, East, Steel Unlimited, Construction Attachments, Craig), roadbuilding and paving machine makers (GOMACO, Weiler, LeeBoy, CMI), aggregate equipment (Stedman, REMco, TCI, General Kinematics), mining service fabricators (L&H Industrial, Phillips, Ground Force, Klein), and weldment suppliers (Weldall, Hol-Mac, Alliance, Warren).
  - Running the audit in parallel caught these **before** profiling was chosen, which was the point of the remedy.

### Advisor consultation 9 (2026-11-16): mining miss rate 30.2% before profiling

- **Advice:** 30.2% does not block profiling, because the audit ran first and all 38 misses are in the pool. But the list has not converged, so the vertical stays partial. Before ranking, by script:
  1. check matched pairs by eye;
  2. print the in/out disagreements;
  3. compute the auditor overlap;
  4. settle the relationship rule that decides the top 40, and confirm the Mine Rite and Schenck records;
  5. run a duplicate check by address and coordinates;
  6. fix the tools (mining product words; tonnage that is payload or capacity);
  7. put the rules in the profiler brief.
  - Then launch the profilers on the top 40 together with one closure finder.
  - **Done rule as on ships:** closure adds no top-40 plant and only a handful overall, and the confirming fact-check is at or under 10%.
- **Done:**
  1. **Matched pairs:** 5 of 164 share no distinctive name token. Two are false matches: Roadtec/Carlson was paired with Komatsu Chattanooga, Heatec with Astec Jerome Ave. Both have their own ledger records, so no miss is hidden. The other three match correctly. Multi-name groups are all the same plant.
  2. **Disagreements and rules:**
     - Asphalt and concrete plant equipment is **in** (construction equipment built from heavy welded steel: drums, silos, frames): Astec Chattanooga, Heatec, Astec Blair, Rexcon Burlington.
     - Wood, organics and recycling grinders (Terex Newton, Peterson Eugene) are **boundary**, kept and noted like forestry-only plants.
     - Telehandlers are lifting equipment, so Manitou Yankton goes to the closure finder to set out of vertical.
     - Komatsu Franklin, Komatsu Chattanooga, Caterpillar Clayton and Joy Lebanon (auditor B: assembly, machining or repair evidence only) and Hensley Dallas (a foundry; buckets are made at Mansfield) go to the closure finder to confirm welding or exclude.
     - Auditor plants the ledger excludes (Takeuchi, SANY, LBX, Terramac, Sakai, Bomag, Fairchild, CNH Burlington, Cat Wamego and Elkader) each carry a quoted reason.
  3. **Overlap:** auditor A found 93 and auditor B 94 of the ledger's included plants, with 66 in common. The Chapman estimate of the auditor-reachable population is about 132. The ledger includes 203, holding every auditor plant plus suppliers and fabricators. (The advisor's 240-290 used pre-merge numbers.)
  4. **Relationship rule (written):** a plant whose stated products include mining-machine structures (haul or mining trucks, shovels, draglines, continuous miners, underground mining vehicles, roof bolters) is a lookalike of Mine Rite, which makes heavy mining weldments. 15 plants flipped from new, with inferred relationship rows. Komatsu Chattanooga (articulated haul trucks are construction equipment) and Masaba (aggregate) are not flipped. Construction-machine plants stay new.
     - Mine Rite Buffalo WY is the known_customer.
     - Schenck Process's US business is now Coperion (Hillenbrand). Sabetha KS and Whitewater WI are customer_other_plant; the 2021 reference names no site.
     - Mechanical top 40 printed. It includes Komatsu Milwaukee (2nd), Cat South Milwaukee (6th), Komatsu Peoria (7th) and Cat Decatur (8th).
  5. **Duplicates:** none new. Telsmith/Super Steel Mequon share an address because Super Steel runs the old Telsmith plant (Telsmith excluded). Superior Morris has three adjacent Highway 28 records, for the profilers to confirm.
  6. **Tools:** `normalise_scores.py` now has mining product words, and a tonnage that is a payload, capacity, rating or class no longer counts as a part weight; no poles or ships score changed. `write_summary.py` has mining round labels. Summary and verticals.csv updated.

### 2026-11-16: mining Stages D-E merged (four profilers, closure pass 1)

- **Merged** (`apply_removals` first, then `merge_inbox --verify-quotes`):
  - **Profilers A-D:** 40 plants profiled, none excluded; 880 evidence rows added, 48 retired.
  - **Closure 1:** 21 new plants (14 base, 7 excluded) and 5 updated; 317 rows; 1 link; 7 rows retired. 0 rejected, 0 coverage gaps, 0 duplicates.
- **Quote check:** 448 found, 22 not found, 3 unreachable.
  - 16 of the not-found quotes are posting dates and street addresses that sit only in the page's JSON-LD or itemprop attributes (Astec, Paycom, Paylocity, Doosan, UltiPro, Rippling, Betterteam). All 16 were confirmed by curl against the raw page source.
  - **Tool fix:** `fetch_page.fetch(..., with_raw=True)` now appends the unescaped raw source, and `merge_inbox` and `verify_ledger_quotes` use it, so such quotes verify from now on.
  - The rest are on pages that 404 now (an expired Ground Force posting) or are duplicate rows; they go to the fact-check.
- **Closure status changes applied:**
  - Excluded: Hensley Dallas (foundry), Komatsu Franklin (engineering and product hub, inferred and reversible), Paladin Akron (customer center).
  - Kept: Komatsu Chattanooga (welding robots and booms, July 2026), Komatsu Lebanon (continuous miners welded on site), Manitou Yankton (telehandlers and articulated loaders; no split stated).
  - Caterpillar Clayton stays base with prospect_test unknown and is not to be profiled until welding is shown.
  - The consultation 9 boundary note was meant for Peterson Eugene (grinders), not p-astec-eugene-or (JCI crushers); the closure finder applied it to Peterson.
- **Coordinator rulings on the profilers' questions:**
  1. **Headcount older than 36 months earns no scale points** (extends the Sabre Bossier 2017 precedent).
     - Terex Durand's Aug 2023 "over 100" falls outside, so scale goes 10 to 5 (total 53).
     - Austin Mills (Mar 2024), Deere Davenport (Oct 2024), Komatsu Peoria (Jun 2026) and Bobcat Bismarck (Oct 2025) are inside.
  2. **Relationship rule, clarified:**
     - An OEM plant whose stated products are the machines themselves stays **new**, even if it fabricates its own buckets.
     - Lookalike of Mine Rite is for plants that sell attachments, buckets, bodies or tanks as products, or (consultation 9) build mining-machine structures.
     - Applying this: Deere Davenport and Bobcat Bismarck go to new. Cat Victoria stays a lookalike (it sells attachments for Cat machines). Komatsu Lebanon goes to a lookalike (continuous miners).
     - Construction-attachment makers (Paladin, Werk-Brau, Virnig, Rockland, Bobcat Litchfield, TAG) stay lookalikes: buckets and attachments are products under rule 6.
     - Coperion Kansas City is customer_other_plant (same parent as the Schenck successor); its stale lookalike_of was cleared.
  3. **Werk-Brau material 0** (normaliser): the bucket sizes are attributed to "made in Findlay" and Werk-Brau has three Fostoria Ave sites, so this is a shared-city attribution, the same as rule 3 for postings. It would be 88 High if a source places the buckets at 2800 Fostoria. Lead: the other two sites.
  4. **Conditional overtime is not mandatory overtime.** "Potential for mandatory OT" and "Fridays as needed" earn labor 12, not 20 (Bobcat Litchfield, Virnig).
  5. **A welder posting with a robot in the title counts when its text requires manual welding** (Virnig Robotic Welder; Metalcraft Beaver Dam and Fall River). Pure robot-operator roles are still listed but not counted.
  6. **"Wire feed" without MIG or flux-core named earns process 0** (Ground Force), the same as the stated rule.
  7. **Undated aggregator Welder postings** set process as a standing fact (Claremore precedent) but earn no labor points (Coperion Whitewater and Kansas City).
- **Normaliser:** 13 plants changed. Werk-Brau 88 to 68; Durand 58 to 53. Eleven plants lost confidence points because their score rows cite unknown fields: a component resting on an unknown headcount or part size earns no confidence. `normalise_scores.py` now stamps overrides with today's date instead of a fixed one.
- **Scores (40 profiled):** 1 High, 25 Medium, 14 Low.
  - Material is 0 on 38 of 40: mining and construction sources almost never state a welded part's size or weight. Payloads, bucket capacities and machine classes are not part sizes under mining rule 1.
  - So the mining ceiling without a stated part size is 80, and most strong plants land at 53-68.
  - Mine Rite (the known customer) scores 23: Path's own case-study pages now 404 and it has no dated posting, the same missing-data pattern as the Low pole customers.
- **Convergence check (done rule):** under the documented ranking key (relationship, tier, stated posting rows, headcount, sources), two closure plants would have ranked inside the top 40:
  - iRock Valley View OH (rank 25, open Welder/Fabricator posting);
  - Process Machinery Shelbyville KY (rank 34).
  - Closure 1 added 14 base plants, which is not a handful. **The list has not converged.**
  - Next: profile those two; run closure pass 2 on the 25 unverified leads, the 36 ECHO 333131 unverified facilities, and the profilers' leads (Werk-Brau 2500 and 4000 Fostoria, Virnig Fort Madison, Rockland Claysburg, Curry's other sites); run the round-1 fact-check over all 40 profiles in parallel.

### 2026-11-16: mining round-1 fact-check, profiler E and closure pass 2

- **Profiler E** (the two closure-1 plants that ranked inside the top 40):
  - Process Machinery Shelbyville KY: **90 High**, confidence 5. A Structural Fitter posting gives parts from 200 to 50,000 lb (fits the 2026 analyst cell limit); MIG required; three welder/fitter roles open; $11.5M expansion with 30 jobs (Oct 2025). Scale 0 (Kentucky headcount 90).
  - iRock Valley View OH: 48 Medium. GMAW/FCAW Welder/Fabricator open; part mix 8.
  - 53 rows, 4 retired; 25 quotes found.
- **Closure pass 2** (three finders): 44 plants, 649 rows, 0 rejected, 0 coverage gaps, 0 duplicates.
  - **2A (leads):** 8 base, 9 excluded, 2 resolved, 12 unverified.
    - Werk-Brau: the NLRB unit covers production at 2800 and 4000 Fostoria, and a 4000 inspector posting checks "welded products", so both sites weld. No source places the bucket line at 2800, so material stays 0. 4000 Fostoria is a new base record (p-werk-brau-findlay-oh-2).
    - Matcor: Morton West, Morton East, Independence KS and Welcome NC, all Tier 1, new.
    - Mellott Warfordsburg: Fabricator posting open 150 days.
    - Bauer/GEFCO Conroe: boundary, drill rigs.
    - Virnig Fort Madison: pre-production.
    - Excluded: Caterpillar Houston PA (closed 2016), the old P&H site in West Milwaukee (demolition from Nov 2025), Paladin CustomWorks Dubuque and Davenport (installation sites), Gainwell/CAI Hico (repair), Rockland Claysburg (steel prep), Curry East Freedom (cylinder machining) and Curry Curryville (trucking center), Johnson Machine Works (water gates).
    - WOTCO resolves to Austin Mills; GreyStone to Superior Columbus.
  - **2B (36 unresolved EPA 333131 sites):** 8 base and 2 more found along the way, 11 excluded, 17 unverified.
    - Base: Cogar Pearisburg (the former Bucyrus/Caterpillar site), Derrick Buffalo (Welder posting, tied to the site by ZIP), Excel Amarillo, MGL Lakeland, Pierce Pacific Portland, Supreme Stoneboro (undated postings), Vroom Tucson (boundary), Williams Bonne Terre and St. Louis, DCL Charlevoix.
    - Excluded: Sandvik Bristol, Goodman Chicago and Universal Cedar Rapids (closed); DBT Norris City (service); Metso Manchester (test center); and others out of the vertical.
  - **2C (EPA 333120 construction machinery, 599 active facilities reconciled by script):** 127 matched, 6 new base, 12 resolved to existing, 15 unverified, 102 triaged only, 346 skipped.
    - Base: Gencor Orlando, Marquette and Chambersburg; Etnyre Oregon IL (2 MIG Welder postings, Oct 20); Schwing St. Paul (5 Welder postings, oldest about 168 days); Erie Strayer.
    - Not yet researched: forestry grinders (Morbark, Bandit), Caterpillar LaGrange and York, Bomag Kewanee, M-B Companies, Allen Engineering and others.
- **Quote checks:** every miss was a JSON-LD date on a page that only loads in a browser.
  - **Tool fix:** the Playwright fallback in `fetch_page.py` now also returns the page source when raw text is asked for (`--check` asks for it).
  - All 6 misses re-checked and found; Erie Strayer's 403 pages load in the browser.
- **Round-1 fact-check (4 checkers, all 40 profiles): 71 corrected of 623 claims = 11.4%, 0 unreachable.**

  | Checker | Corrected / checked | Rate |
  |---|---|---|
  | A | 12/155 | 7.7% |
  | B | 17/147 | 11.6% |
  | C | 29/155 | 18.7% |
  | D | 13/166 | 7.8% |

  - **Kinds:** quote does not support value 56, other 13, wrong plant or location 2; wrong process, wrong tier, closed business and invented fact 0. No corrected row changed a score component.
  - **Repeated patterns:**
    - (a) company- or brand-level product, parent and robot facts tagged stated at one site of a multi-site company (Klein, Werk-Brau, Getman, L&H, Ground Force, Tabor, McLanahan, Coperion);
    - (b) legal suffixes and group names not on the cited page;
    - (c) thin rows: the cited page carries the fact but the row value does not (Mega, Werk-Brau, Virnig, Rockland);
    - (d) Workday `startDate` (the posting date) written as the job's "start date";
    - (e) Vaia aggregator postings called "undated" although their JSON-LD dates them;
    - (f) stated prospect_test "pass" rows that are judgements;
    - (g) old figures shown as current (Litchfield's 2021 "250+").
  - **Applied** with `apply_factcheck.py`: 552 confirmed, 71 corrected, 0 unmatched. Checker C's 18 rows whose plant field must not change were marked keep in a scratch copy. 41 plant fields changed, all intended.
- **Status:** 302 plants (196 base, 42 profiled, 64 excluded). Profiled: 2 High, 26 Medium, 14 Low.
- **Convergence:** closure 2 puts 6 more plants inside the top 40 under the ranking key (Mellott, Werk-Brau 4000, DCL, Cogar, Supreme, Virnig Fort Madison). Etnyre and Schwing have 2 and 5 open welder postings but rank about 105th because their relationship is new. Not converged.
- **Advisor checkpoint:** fact error rate over 10%, and the list has not converged.
- **Tool:** `tools/rank_mining.py` prints the documented ranking key for any vertical.

### Advisor consultation 10 (2026-11-16): fact error rate 11.4% and no convergence

- **Advice:**
  - The 11.4% is a labelling problem, not a research problem; keep it as the round-1 headline.
  - Before anything else:
    1. Run the normaliser after the merges and make it rewrite stale score rows.
    2. Re-rank on counted open postings: `rank_mining.py` was counting "none found", inspector and maintenance rows.
    3. Finish checker B's hand edits.
    4. Rerun the address and coordinate duplicate check.
  - Decide the score-moving rulings together:
    - one shared-city test for Austin, McLanahan, Werk-Brau, Bobcat Bismarck and Curry;
    - a written distinction between Deere's recall and Valmont Tulsa;
    - the Komatsu Peoria, Mine Rite, ESCO, PHIL and Liebherr calls;
    - whether Etnyre and Schwing are in the vertical.
  - Sweep by pattern across all 42 profiles: script the mechanical patterns and use one agent for company-level facts and thin rows. Then run a confirming round with the checkers rotated, including Process Machinery.
  - **Convergence:** the done rule is failing (closure added 14, then 24). Run one bounded final pass (the 102 triaged 333120 rows, the named leads, and NAICS 333922 by script or as a limit). Mark done only if it yields a handful of base plants and none with a counted open welder posting. Otherwise ship as partial with limits and ask the user before going further.
- **Done:**
  1. **Normaliser:** it now rewrites every profiled plant's score_*, score_total, score_tier and confidence rows to match plants.csv; 35 stale rows synced. Profiler E's scores normalise unchanged (Process Machinery 90, iRock 48).
  2. **Ranking:** `rank_mining.py` now counts open welder postings from the plant's welder_postings field ("N open", capped at 3). A posting whose plant is not stated counts 0: Eagle Crusher's one careers-page Welder is claimed by both its Bucyrus and Galion records.
     - **Corrected count of closure-2 entrants with a counted open posting inside the top 40: two,** Mellott Warfordsburg (23rd) and Derrick Buffalo (30th). It is not six.
     - Supreme Stoneboro (undated own-board "New Opening" roles) and Schwing and Etnyre (5 and 2 open; new relationship) also have postings.
  3. **Shared-city test (one rule, written):** a fact that names only a city counts for a plant when the company has no other production site in that city. It also counts when the company's other buildings there are within about 1 km doing the same kind of production: that is one campus, recorded as one plant. Otherwise the attribution is inferred and earns no points.
     - **Werk-Brau:** 2800, 4000 and 2500 Fostoria Ave are within about 0.6 km (Census geocodes, interpolated), and 2800/4000 form one 2022 NLRB production unit. So it is one campus: material 20, total **88 High**. The 4000 record is folded in as a duplicate.
     - **McLanahan:** 900 Beaver St is 540 m from 200 Wall St, so one campus; 61 stands.
     - **Austin Mills:** the "newly leased facility close to our main facility" has no address, so distance is unknown and labor stays 0.
     - **Bobcat Bismarck:** three EPA addresses and no site address on the record, so labor stays 0.
     - **Curry Hollidaysburg:** the second site is Curry Rail Services, a separate business that recruits through its own form. Curry Supply's board posts no rail roles, so the postings count by board (Bollinger precedent); 61 stands.
     - **Duplicate check by coordinates**, campus rule applied:
       - Rockland Bedford 172 Friendship Village Rd (0.56 km) is folded into 152 Weber Lane;
       - Superior Morris Components (319) and Crushing (305 Highway 28) are folded into 315;
       - MEC Neillsville 1506 is folded into 1515 Industrial Park Dr.
       - Ken Garner Victoria sits 20 m from Caterpillar Victoria but is a different company (a supplier), so it stays separate.
  4. **Demand:** a hiring event is labor evidence. It is a demand trigger only when the source states a plant-level production increase as its cause.
     - Deere Davenport's recall ("increased production demand", Jan 2026) keeps 15, so it stays 72 High.
     - Valmont Tulsa's state hiring event stated no cause (8 stands).
     - A trigger must be a dated event (expansion, building, contract, acquisition, or a recall or hire tied to stated production growth). Komatsu Peoria's $28M office HQ that "won't add new jobs" goes to 8 (65 to 58).
     - Mine Rite's founder quote ("more demand coming our way than we can handle") is a statement, not an event, so it stays 8, the same standard as iRock's "aggressive growth phase".
  5. **Smaller calls:**
     - ESCO Elko part mix 15 to 8: the posting names repairs, rebuilds and modifications but not custom or high-mix (60 to 53).
     - PHIL scale 0 to 5: its own history page states production at Peoria and "the Dallas, TX location", recorded as c-philippi-hagenbuch:multi_plant (63 to 68). PHIL Dallas is a list lead.
     - Liebherr scale 0 to 5: Liebherr USA states "manufacturing facilities" (plural), recorded as c-liebherr:multi_plant (23 to 28).
     - Etnyre (asphalt distributors and chip spreaders: road-construction equipment) and Schwing (welded concrete boom pumps) are in the vertical, relationship new. Their truck-mounted and trailer lines are noted for v-truck-bodies and v-trailers.
  6. **Mechanical sweeps:**
     - 114 stated prospect_test "pass" rows retagged inferred.
     - Workday startDate written as "start date": 4 evidence rows and the Durand and Mount Vernon plant fields now say "posted".
     - Masaba's "undated" Vaia row reworded.
     - **Ruling 7 wording corrected:** the Coperion Vaia postings are dated in their JSON-LD (Kansas City 2025-12-11, Sabetha 2026-02-03, Whitewater 2026-05-15). The outcome stands: none is on Hillenbrand's own board today, so they set process as a standing fact but earn no labor points.
- **Next (workflow mining-sweep-profile-close):**
  - one sweep agent for company-level facts tagged stated at a site, thin rows, legal suffixes and old figures shown as current, across all 42 profiles;
  - profiler F on Mellott, Derrick, Supreme, Schwing and Etnyre;
  - the bounded final closure pass (3A: the 102 triaged 333120 rows plus the named leads; 3B: NAICS 333922 by script).
  - Then a rotated confirming fact-check round, including Process Machinery and iRock.

## 2026-11-16: mining sweep, profiler F and closure pass 3 merged (Stages D-E, closure)

- **Merged** (0 rows rejected, 0 coverage gaps, 0 duplicates in every file; each agent's dry run found every stated quote on its page):
  - **mining-sweep-1 and mining-sweep-2:** the attribution sweep across all 42 profiles. 122 evidence rows replaced under their existing keys and 4 added, 37 plants updated, 21 opening lines replaced. No score points moved; the normaliser changed only Werk-Brau's confidence, 5 to 4 (its production_type rows are now inferred, company-level).
  - **mining-profiler-F:** Etnyre Oregon IL 68, Schwing St. Paul MN 61, Mellott Warfordsburg PA 60, Supreme Stoneboro PA 55, Derrick Buffalo NY 48 (all Medium). 115 rows added, 6 retired to ledger/audit/retired-evidence.csv.
  - **mining-closure-3A** (the 102 not-attempted ECHO 333120 rows plus 5 named leads): 57 plants (36 base, 7 of them boundary; 21 excluded), 835 rows. 38 left unverified, 11 skipped with a reason.
  - **mining-closure-3B** (ECHO 333922, 612 active facilities, reconciled by script): 11 plants (10 base, 1 excluded), 174 rows. 25 matched, 83 unverified (67 not attempted), 492 skipped with a reason.
- **Counts:** 370 mining plants: 47 profiled, 232 base, 91 excluded (279 included). Profiled tiers: 3 High (Process Machinery 90, Werk-Brau 88, Deere Davenport 72), 30 Medium, 14 Low.
- **Consultation 10 done test: failed.** The bounded final pass yielded 46 new base plants, not a handful. Four new base plants have a dated welder posting on the company's own board that names the site: Exodus Superior WI (2026-10-02), PPI Lenox IA (2026-10-21), Syntron Saltillo MS (two, 2026-11-02) and West River Oakwood VA (JSON-LD 2022-10-07, probably evergreen). Six more have undated own-board postings naming the site (M-B New Holstein, G.R. Trussville, HEM Grundy Center, Allied Sherwood, Quality Urbandale, Bandit Remus). Mining therefore ships as **partial**, and the user is asked before any further mining research.
- **Open limits for the partial label:** 38 unverified 333120 rows and 83 unverified 333922 rows (67 not attempted); Arcosa Shoring Union City MI (two dated Fitter/Welder postings, site not settled); PPI Pella (postings name only "Pella, IA", several PPI sites there); Vermeer Freeman SD (aggregator posting only, own board unreachable).
- **Leads for other verticals:** Kloeckner Paton IA (agricultural), Intercontinental Engineering Riverside MO (shipbuilding-naval), Etnyre and Schwing trailer and truck lines (trailers, truck bodies).
- **Sweep notes for the record:** TAG's two Discovery Dr facilities treated as one campus (about 15 m apart, interpolated geocodes), to be confirmed in round 2. Process Machinery's careers page lists an "Ohio Branch" in Columbus; if it produces, its company-level rows must become inferred (round 2 checks).
- **Next:** round-2 confirming fact-check, rotated (workflow mining-factcheck-round-2): checker A takes round-1 B's plants, B takes D's, C takes A's, D takes C's, and E takes the seven never-checked plants (Process Machinery, iRock and profiler F's five).

## 2026-11-16: mining round-2 fact-check (confirming, rotated) applied

- **Round 2:** five fact-checkers over all 47 profiled plants. Rotation: A took round-1 B's plants, B took D's, C took A's, D took C's, and E took the seven never-checked plants (Process Machinery, iRock and profiler F's five).
  - **24 / 727 = 3.3% corrected, 0 unreachable** (A 4/153, B 4/137, C 4/156, D 5/143, E 7/138). Round 1 was 11.4%. No invented fact, wrong process, wrong tier or closed business in any report.
  - Main kinds: an EPA facility name stated as the operator's identity (Tabor Princeton name, address and opening line; Paladin's C&P Attachments name and address), now inferred; company boilerplate stated at one site (L&H production_type); thin rows (Metalcraft Fall River robots, Liebherr postings, Komatsu Peoria chassis, Komatsu Milwaukee headcount split).
  - Applied with `tools/apply_factcheck.py` (703 confirmed, 24 corrected, 0 unmatched).
- **Coordinator rulings on the checkers' score notes:**
  - Tabor Princeton part mix 8 to 0 (21 to 13) and Coperion Whitewater part mix 8 to 0 (40 to 32): the only product lists name no site, so the consultation 10 shared-site rule gives inferred attribution 0. Lead: Coperion's Jul 31 2024 brochure could restore Whitewater's 8 as a stated row.
  - TAG Chattanooga scale 5 to 0 (21 to 16): its two Discovery Dr buildings (about 334 m apart, same production) are one campus, so TAG is a single-plant company with 70+ employees.
  - Mellott Warfordsburg part mix 15 to 8 (60 to 53): the custom-fabrication sentence is company-level and Mellott has a second production site (Marion Machine).
  - Schwing St. Paul part mix stays 8 with its basis moved to the stated product menu. Schwing scale 5 stands under the current rules (the multi-plant sentence sits under a 1990s heading; the 36-month limit is written for headcount only). Recorded as a limit, not changed.
  - Mine Rite labor stays 0: the About page's "Now hiring welders" links to a Jan 2019 PDF.
  - Deere Davenport material stays 20: the welded 13-ft-wide bucket over 16,000 lb fits the 2026 analyst cell limits (it would be 12 under the older 10,500 lb sheet).
  - **Confidence consistency:** a headcount past the 36-month limit earns nothing and now supports no confidence, like an unknown headcount (Yankton and Durand 3 to 2). A part-mix 15 that rests on an inferred company-level row earns points but no confidence (Rockland 4 to 3). These standing rulings live in `ledger/audit/no-confidence-claims.csv`, which `tools/normalise_scores.py` now reads on every run. L&H 4 to 3 followed mechanically from its retagged production_type. Werk-Brau stays 4: its part mix already counted no confidence, and its material rests on the consultation 10 one-campus ruling.
  - A general rule ignoring unknown-tagged cited claims was considered and not adopted: it would change 13 poles plants' confidence in a finished vertical.
  - Six stale reasoning texts got coordinator notes (Durand 58, Whitewater and Kansas City "undated", Mount Vernon "start date", ESCO "level 15").
- **Proposed sweeps not run** (round 2 is under 10%, so they are logged as limits for a later pass): EPA-name identity rows across all base records; thin rows where a field clause sits on no row.
- **Leads:** Super Steel Mequon expansion (Jun 30 2026, aggregator snippet only; demand 15 if a primary source confirms); Bobcat Bismarck's three FRS addresses within about 0.5 km (labor 12 if shown to be one campus); Ground Force Idaho postings on idahoworks.gov (no welder role).
- **Counts:** 370 plants, 279 included (47 profiled, 232 base), 91 excluded. Profiled tiers High 3 / Medium 30 / Low 14. Summary rewritten (`ledger/audit/summary-v-mining-heavy-equipment.json`); verticals.csv status partial.

### Advisor consultation 11 (2026-11-16): marking mining partial after round 2

- **Advice:**
  - Partial is right and round 2 (3.3%) clears the 10% limit.
  - The round-2 part-mix rulings contradicted the standing session-2 rule 1 (a company-level part mix earns points but no confidence). Pick one rule for all 47.
  - Script the two new confidence rulings across all 47 profiles.
  - Read checker E on Process Machinery and every report's field_drift_notes.
  - Recompute the limits from the inbox tables.
  - Fix the ranking reads of closure-3 fields and state how many base plants outrank profiled ones.
  - Rerun the duplicate check on the 68 new records.
  - Run the new smoke assertions.
- **Done:**
  1. **One part-mix rule, the standing one.** Mellott back to 15 (53 to 60) and Coperion Whitewater back to 8 (32 to 40). Both earn no confidence for part mix (Mellott listed in `no-confidence-claims.csv`; Whitewater's production_type is inferred only).
     - Tabor Princeton stays 0 on a different, written ground: the product list is a brand listing, and the plant's identity as that brand's maker rests only on the EPA facility name. With the plant-to-brand tie itself inferred, no product list is attributable to the plant.
     - Werk-Brau, Rockland, L&H and Ground Force were already scored under the standing rule.
  2. **Confidence sweep across all 47:**
     - Stated headcounts dated before Nov 2023 that a scale score cites: Werk-Brau (Apr 2022, company-level) and Bobcat Litchfield (Apr 2021) added to the list. Werk-Brau confidence 4 to 3, Litchfield 3 to 2.
     - Komatsu Milwaukee also has an Oct 2024 stated row, so it is unchanged.
     - Part mix 15 resting on an inferred row with only a weaker stated row: Rockland and Mellott, both listed.
  3. **Process Machinery confirmed by checker E**, component by component (90 High).
     - The Columbus "Ohio Branch" is not shown to be a production site: every manufacturing statement names Shelbyville, and the 2025 post presents PMI as a dealer for Ohio. Its company-level rows stand.
     - The 50,000 lb part weight (Structural Fitter posting, Shelbyville) and the $11.5M expansion (Oct 2025 groundbreaking; construction under way on 2026-10-28) are confirmed.
  4. **Field drift fixed** (ground rule 1), 11 fields:
     - Yankton name ("KPI-JCI" dropped).
     - Products trimmed to their rows: General Kinematics, Derrick, Etnyre, Schwing, Mellott and L&H.
     - The three Metalcraft products rows widened to checker R2-B's verified text from mtlcraft.com/industries (company-level).
     - A Komatsu Peoria address row added for ZIP 61639 (checker R2-C's suggested row; quote re-checked).
  5. **Ranking:**
     - PPI Pella's field now says "site not named", so it counts 0.
     - Quality Urbandale's "2 listed" is "2 open (undated)" under the Nello rule.
     - **Nine base plants rank inside the top 47** by the documented key, **six with a counted open posting:** M-B New Holstein (3), Syntron (2), West River, Allied, PPI Lenox and Exodus.
     - G.R. Trussville and HEM rank lower because their relationship is "new" (relationship is the first sort key).
  6. **Limits recomputed from the closure tables:**
     - About 155 registry rows and leads are unverified: 17 from 333131 (after closure 2B), 55 from 333120 (17 researched in 2C plus 38 in 3A) and 83 from 333922. 67 of the 333922 rows were not researched.
     - Nine closure-3 base plants have an open own-board welder posting naming the site: four dated, five undated.
     - The closure-3 base records (1,009 rows) had only the finders' own quote checks.
  7. **Duplicate check on the 68 new records:** coordinate and name matches within 1 km or the same city found only different companies (e.g. PPI Corning vs Brown Bear, 60 m apart). No merges.
- **Status:** v-mining-heavy-equipment stays **partial**. Further mining work waits on the user.

## 2026-11-16: user asked to keep pushing mining toward done

### Advisor consultation 12 (2026-11-16): plan and done test for the push to done

- **Advice:**
  - Write the done test before launching, or closure repeats (14, then 24, then 46).
  - Keep the blind re-audit truly blind and on different methods from the ECHO-by-NAICS closure passes.
  - Rule on West River, M-B New Holstein and PPI Pella first.
  - Full effort on the 67 unresearched 333922 rows; cap the already-researched unverified rows at one new source type each.
  - Profile now, re-rank once after the audit, run one follow-up profile wave with the fact-check, then go to the done checkpoint. No loop.
- **Done test (replaces consultation 10's test, fixed before any result is seen):**
  1. **Frame:** plants in EPA NAICS 333131, 333120 and 333922, plus Tier 1s reached through OEM supplier links. Fabricators outside that frame are a stated limit, not misses.
  2. **Miss rate:** the blind re-audit's verified miss rate is 20% or less against the list as it stands after this wave, and no verified miss would rank in the top 40 by the profiling key with a counted open welder posting.
  3. **Profiles:** every plant in the top 40 by the key is profiled, and the fact-check of the new profiles is 10% or less. The independent sample of closure-3 base records is reported separately (as in ships).
  4. **Stop:** if the re-audit's verified miss rate is over 20%, mining is partial again and the user is asked. There is no closure pass 5.
- **Rulings:**
  - **Standing-ad rule:** a welder posting live today on a real applicant board (an ATS or careers board with an apply flow) counts as open (labor 12) whatever its date, and never as open 60+ days when its date shows it is a standing ad (West River, JSON-LD 2022-10-07). A static web-page line that links to a dated notice (Mine Rite's 2019 PDF) is not a posting.
  - **M-B New Holstein: excluded** (mostly sweeping and snow attachments; same ruling as its Chilton sister plant). Kept as a lead for a municipal/snow equipment vertical.
  - **PPI Pella:** the profiler settles the campus question from the addresses of PPI's Pella sites. Until then its postings count 0.
- **Ranking after the exclusion:** six base plants in the top 40 (Syntron 17, West River 28, Allied 32, PPI Lenox 33, Exodus 35, DCL 38).
- **Wave (workflow mining-push-to-done):**
  - **profiler G:** the six top-40 base plants.
  - **profiler H:** the next three by rank (Pierce Pacific 41, PPI Pella 44, Construction Attachments 47), plus three lower-ranked plants with counted postings (G.R. Trussville, HEM Grundy Center, Quality Urbandale).
  - **closure-4A:** the 67 unresearched ECHO 333922 rows.
  - **closure-4B:** one new source type each for the 88 researched-but-unverified registry rows.
  - **Two blind list auditors** on methods other than ECHO by NAICS.
  - **One fact-checker** on an independent sample of closure-3 base records.

### 2026-11-16: mining push-to-done wave merged (workflow mining-push-to-done)

- **Profilers G and H (12 plants), merged** after 22 evidence removals; 0 rejected, 0 coverage gaps.
  - Scores: G.R. Trussville 63, Exodus 53, Allied 47, Pierce Pacific 43, Syntron 41, Construction Attachments 36, PPI Lenox 33, HEM 28, West River 23 (after ruling), PPI Pella 21, Quality Urbandale 16, DCL 16.
  - Accepted profiler calls: Quality Urbandale postings not attributed (a second Quality Manufacturing air source at 5701 Park Ave, Des Moines); PPI Pella campus test fails (2103 Washington St and Van Gorp are 3-4 km away); Exodus demand 8 (expansion completed 2024-07-16, before the 24-month window); HEM labor 12 (JSON-LD date matches another requisition to the second: a re-list stamp, not a proven 60+ day opening).
- **Coordinator rulings** (`ledger/inbox/coordinator-mining-R2-rulings.json`):
  - **West River labor 12 -> 0.** Its employment page states that listed openings "does not mean that we are currently hiring for the position". An explicit disclaimer overrides the consultation 12 standing-ad default. Total 35 -> 23.
  - **G.R. postings dated.** A coordinator re-fetch found JSON-LD datePosted 2026-08-24 on job 3562124 (the job URL redirects to /apps/new, which the profiler's fetch missed), confirming the CS fact-check. Labor stays 20 (two at once; now also 60+ days).
  - **Six crusher and screen makers re-tagged lookalike of Schenck Process** under the written relationship rule: Astec Eugene, Gundlach Belleville, Superior Belen, Fab-Tec Moscow, RD Olson Kelso, Vermeer Freeman (flagged by the CS fact-check).
- **Closure pass 4, merged:** 4A (67 unresearched NAICS 333922 rows): 14 new base, 2 resolved, 27 unverified, 24 skipped. 4B (88 unsettled rows): 14 new base, 9 excluded, 3 resolved, 53 unverified. Quotes all found on the agents' dry runs.
  - New base with counted postings: Thomas Conveyor Burleson TX (Martin Sprocket; 4 dated welder postings, oldest about 97 days), Orthman Cleburne TX (1 dated), Tread Roanoke VA (1 dated).
  - Not counted: Process Barron Pelham (site not settled), ASGCO Nazareth (maintenance duties), Screw Conveyor Winona ("We are hiring!" with no specific opening), Douglas Pell City (2011 ad, no site).
- **CS base-sample fact-check (closure-3 records, 25 plants, reported separately): 5 / 325 = 1.5%** (stated rows only 4/224 = 1.8%). Applied.
- **Vertical now:** 407 plants: 59 profiled, 247 base, 101 excluded.
- **Re-rank:** four unprofiled base plants are now in the top 40: Thomas Conveyor (9), Astec Eugene (17), Tread Roanoke (32), Orthman Cleburne (37).
- **Blind re-audit (R2-A: CONEXPO-CON/AGG 2026 exhibitor directory, AEM members, Curlie, 10-K property lists; R2-B: OEM supplier/dealer lists, job searches by product, plant news 2023-26):**
  - 225 in-definition auditor plants; 125 ledger plants matched; 72 unmatched candidates.
  - Of those, 7 are unconfirmed sites (HQ/office/brand) and 1 is already in the ledger; 64 remain (45 core, 17 boundary, 2 earlier-unverified leads).
  - **Unverified miss rate about 64 / 190 = 33.7%; 26.2% even counting core only.** To get under 20%, 33 of the 64 would have to fail verification; both auditors quote-checked their rows, so that is implausible.
  - Neither auditor reached a dry point. Where the misses are: CONEXPO exhibitors our EPA/NAICS-based closure passes never touched: small attachment and bucket makers (Wain-Roy, Berlon, B&D, Leading Edge, Dymax, Digga, Worksaver, Danuser, Lowe), aggregate and bulk equipment (Fisher, Midwestern, Smico, JVI, Mule, Redline, DEMI, Oquamax, iSC), asphalt and concrete plant makers (ADM, ALmix, CEMCO Olney, JEL, MERTS, Aesco Madsen), and weldment suppliers (Superior Mfg Winston-Salem, ATACO, Amerequip, C-I-T, Custom Products).

### Advisor consultation 13 (2026-11-16): re-audit miss rate over 20%

- **Verdict:** mining stays partial. Verification cannot bring the rate under 20% (33 of 64 candidates would have to fail). No closure pass 5. One bounded last wave, then the user is asked.
- **Relationship sweep (blocking for the wave):** the written rule was applied by script to every non-excluded `new` mining row, not only the six the checker named. 12 flipped (`ledger/inbox/coordinator-mining-relationship-sweep.json`):
  - lookalike of Mine Rite: Paladin Dexter and Delhi, LaBounty, Pengo Laurens and Cokato, Genesis, NPK (attachments sold as products); Kress (coal haulers); Brookville (underground mining vehicles); Komatsu Homer City and Duffield (continuous miners, Komatsu Lebanon precedent);
  - lookalike of Schenck Process: American Pulverizer (crushers).
  - Kept new under earlier rulings: Tier 1 weldment suppliers (MEC, Morton, Matcor, Metalcraft, Hol-Mac), machine OEMs (Deere Davenport, Bobcat Bismarck, Komatsu Chattanooga), batch- and asphalt-plant makers, Broce (sweepers first).
- **Top 40 after the sweep:** seven unprofiled base plants: Thomas Conveyor (9), Brookville (11), Astec Eugene (18), Kress (21), NPK (26), Tread (35), Paladin Dexter (40). Orthman drops to 41.
- **Standing-ad rule, amended:** a live standing ad counts as open (12) unless the company states that listed openings do not mean it is hiring (West River, labor 0). Vince Hagan's 2023 Welder/Fitter page is not on its current list, so it was never counted; no change.
- **G.R.:** both posting dates now have their own quoted rows (2026-08-24); labor reasoning rewritten.
- **Last wave:** verify the 64 candidate misses (ledger checked by name first; dated postings on each plant's own board); fact-check the 12 G/H profiles; profile the seven top-40 base plants. After the merge, re-rank once; any miss-derived plant that lands in the top 40 is listed as a stated limit, not profiled.
- **Reporting:** the miss rate reported is this audit's verified figure; merging the misses does not lower it. Coverage by segment and auditor B's scratchpad file-name exposure are stated.

### 2026-11-16: mining last wave merged (consultation 13 plan)

- **Workflow mining-last-wave** (5 agents, about 98 min): two miss verifiers, fact-checker R3-GH, profiler I, fact-checker R3-I. No agent errors.
- **Miss verification (71 unmatched re-audit candidates):** 46 new base, 10 excluded, 15 unverified, 0 already in the ledger.
  - Excluded: Kenco Roseville (castings), Dirt Dog Commerce (agricultural), Cedarapids Cedar Rapids (office), Cemen Tech Indianola (truck mixers, v-truck-bodies), Twinkle West Liberty (fabrication contracted out), Reliable Asphalt Shelbyville (dealer), SWECO Florence (process separators), Conveyor Components Croswell (non-welded), Wausau Wooster (old Rayco plant, now snow plows), CMI Oklahoma City (HQ; CMI builds in Waverly IA).
  - Pemberton Longwood FL: base with in-definition unknown (welding not stated); not counted as a verified miss.
- **Verified miss rate (blind re-audit): 45/163 = 27.6%** (recomputed in consultation 14; first written as 45/171 = 26.3%). See consultation 14 for the denominator.
- **Done test condition 2: failed.** Two verified misses rank in the top 40 with counted postings (see consultation 14).
- **Profiler I (the seven top-40 base plants):** Thomas Conveyor Burleson 88 High, Brookville 83 High, Tread Roanoke 75 High, NPK Walton Hills 65, Kress Brimfield 63, Astec Eugene 61, Paladin Dexter 53. 24 superseded rows removed before merge.
- **Fact-check round 3:** R3-GH 7/251 = 2.8%; R3-I 8/109 = 7.3%; **round 3 combined 15/360 = 4.2%** (target 10%). Main kind: clauses in compound values or site-tie judgements the cited page does not carry. Six sibling rows of corrected compound values (Brookville and Kress products and production_type) synced to the corrected text. Coordinator sweep for unquoted single-site clauses in stated rows found one more (Bear Iron Works address), trimmed.
- **Coordinator rulings:**
  - **Brookville material stays 20, confidence 3** (reversed in consultation 14). The site tie to 175 Evans St is inferred (Brookville Services at 4 S Pickering St, 1.3 km away, does service and rebuilds). Kept under the ships repair-only precedent (a rebuild shop is not a production site), ships rule 2 (a whole steel vehicle's stated dimension) and the Werk-Brau welded-not-stated precedent. The claim is added to `no-confidence-claims.csv`. If material went to 0, Brookville would be 63 Medium.
  - **Paladin Dexter kept as a profiled boundary plant (53).** No Paladin page says what Dexter builds; the sweeper identity rests on an EPA facility name and an old directory. An inferred identity is not enough to exclude a plant with a live welding posting; stated as a limit on the map.
  - **Quality Urbandale tier corrected to Tier 1; relationship stays lookalike of Mine Rite** under the tank-supplier precedent (Standard Iron Hartford, Engineered Welding, Metalcraft).
  - **DCL Charlevoix:** no page ties the EPA Traverse City record to DCL production; no change.
  - **West River:** score_total and score_tier reasoning rewritten for 23.
- **Vertical now:** 463 plants: 66 profiled, 286 base, 111 excluded.
- **Status: partial.** The user is asked: accept partial and move to battery storage, or authorise one directory-driven pass (CEMA, MINExpo, CONEXPO Equipment Components) followed by a fresh blind audit.

### Advisor consultation 14 (2026-11-16): before the final report, mining partial

- **Asked:** whether the last-wave report could go out as written (one verified miss in the top 40; Brookville 83 High; miss 26.3% with a 17.6% core-only figure).
- **Advice and what changed:**
  1. **Relationship rule over the 46 new base plants.** Run by hand against the written rule. One flip: **Fecon, Lebanon OH, new -> lookalike of Mine Rite** (Bull Hog mulching attachments sold as products; Vail Holton precedent; Fecon's tractors do not override the attachment line). Its stale `new` row was removed (`ledger/inbox/coordinator-mining-consultation-14.json`). Batch- and asphalt-plant makers, grinder and dredge OEMs and Tier 1 weldment shops stay new; tank suppliers (Superior Mfg, ATACO) are already lookalikes.
     - **Re-rank:** Fecon is rank 11 (three undated own-board welder postings, counted as open under the standing-ad rule); General Steel & Supply Dickinson is rank 23. **Two verified misses in the top 40 with counted postings.** Next miss-derived plant: Digga at 46.
  2. **Brookville material 20 -> 0, total 83 -> 63 Medium, confidence 3.** The written campus rule (consultation 10) makes a fact count for a plant only when the company has no other production site in that city or the other buildings are within about 1 km doing the same production. Brookville Services (4 S Pickering St, 1.3 km) does service and mining rebuilds, so the tie is inferred and earns no points. Keeping 20 would have been a new exception. The override reasoning on the score row carries the upside (83 High). The no-confidence row added for Brookville was withdrawn.
  3. **Miss rate recomputed: 45/163 = 27.6%; upper bound 61/179 = 34.1%.** The 225 auditor rows: 153 matched 125 ledger plants (23 plants were found more than once, which is the 28-row gap), 72 unmatched. Of the 125, 117 are included and 8 excluded with sourced reasons (Terex Louisville distribution centre, Telsmith Mequon closed, Caterpillar Wamego closed, CNH Burlington closed, Bobcat Wahpeton cylinders, LBX Lexington HQ, BOMAG Ridgeway assembly, Komatsu Franklin engineering); these leave the count, as in the ships method. Denominator = 117 included + 1 already (Ashland WI) + 45 verified. The 17.6% core-only figure was dropped: it removed boundary plants from the misses only.
- **Also reported:** R3-I alone 7.3% (12.8% counting untrimmed siblings); the compound-clause sweep was run only on the seven newest profiles; the map's CSV download does nothing in the published viewer.
- **Status: partial.** Vertical now: 463 plants, 66 profiled (High 5 / Medium 38 / Low 23), 286 base, 111 excluded.

## v-enclosures-battery-generator (rank 4): Stages B-C started 2026-11-16

- **User decision (2026-11-16):** mining accepted as partial; profile its two top-40 misses (Fecon, General Steel; workflow mining-top40-misses) and start battery-storage and generator enclosures.
- **Definition:** welded steel enclosures, sub-base fuel tanks, skids and containers for generator sets and battery energy storage made in US plants.
- **Boundary rules (finders and auditors follow these exactly):**
  1. **In:** generator enclosures (weatherproof, sound-attenuated, walk-in), sub-base (belly) fuel tanks and genset day tanks, generator base frames and skids, BESS enclosures, containers and skids, and genset packagers that fabricate these.
  2. **Genset OEM plants** are in only when the plant itself welds enclosures, base frames or tanks; engine-only, alternator-only or final-assembly plants are excluded with the reason.
  3. **Other verticals (record as excluded with the reason; kept as leads):** e-houses, switchgear and power-distribution skids, modular data-center structures (v-datacenter-grid-prefab); trailer and chassis builds for mobile power (v-trailers-chassis-mobile-power) unless the plant also builds the enclosures or tanks; transformer tanks (v-transformer-tanks); general aboveground fuel-storage tanks with no genset line (v-pressure-vessels-tanks).
  4. **Boundary (kept, noted):** ISO container modifiers with a stated BESS or genset enclosure line; aluminum-first enclosure shops (aluminum noted); thin-sheet enclosure skins (weak fit noted).
  5. **Out:** battery cell and module makers with no welded steel structure; distributors, rental fleets and service-only sites.
- **Relationship:** EK Machine (three Wisconsin facilities; a Path account per Path's roster and EK's "Path Lead Welder" posting) is known_customer where the source names the site, customer_other_plant for its other sites. Lookalike of EK Machine for plants that fabricate generator enclosures, sub-base tanks or BESS enclosures or skids as a stated product. New otherwise.
- **Finder-process remedy from mining (consultation 13):** the misses came from trade-show and association directories the registry passes never reached, so every finder starts from directories (EGSA member directory, POWERGEN International and RE+ exhibitor lists, Data Center World, NFPA 110 / UL 2200 listing searches where public), then EPA FRS / ECHO NAICS sweeps (335312, 332420, 332322, 332313, 332439), then each company's job board by city.
- **Workflow battery-find-and-audit:** four plant-finders by slice (A genset OEM plants; B enclosure, packager and sub-base tank makers; C BESS enclosures, containers and skids; D directory and registry sweep) and two blind list auditors in parallel.

### 2026-11-16: mining top-40 misses profiled (workflow mining-top40-misses); mining closed as partial

- **Profiler J:** Fecon, Lebanon OH **76 High** (20/20/8/20/8/0, confidence 4): three production welder roles live at once on its own Paycor board, GMAW/MIG and FCAW required, no dates anywhere; parent Windjammer Capital (2022), not Komatsu; single site (ECHO, ISO certificate). General Steel & Supply (Fisher), Dickinson ND **28 Low** (0/0/15/0/8/5, confidence 0).
- **Fact-check R3-J:** 1/57 = 1.75% on the round-3 basis (General Steel tier retagged inferred; confidence 1 -> 0). Round 3 overall now 16/417 = 3.8%.
- **Coordinator rulings:**
  - **General Steel: strict campus rule, as for Brookville (consultation 14).** The company states two fabrication facilities; a 2021 Dickinson Press ad puts repair, manufacturing and warehouse space at "Our Dickinson location" (3020 Energy Drive) but gives no building addresses, and ECHO carries a separate Fisher shop record in Northgate Industrial Park. Postings listed, earning 0. Upside 75 High (80 if Fisher counts as a multi-plant parent). `p-general-steel-dickinson-nd:production_type` added to `no-confidence-claims.csv`.
  - **Fecon labor 20 kept:** several counted postings open at once earn 20, as for Brookville and Kress; standing-ad status only blocks the 60+ days route. The "# of Openings: 0" field shows on all 23 Fecon postings, read as unused. At 12 it would be 68 Medium.
  - **Fecon material 20 kept** (assembled crusher weights 3,330-3,965 lb; Pierce Pacific precedent). **Demand 8 kept:** a Sourcewell cooperative purchasing award is a sales channel, not a plant-level contract.
- **Top 40 by the profiling key is now fully profiled.** Mining: 463 plants, 68 profiled (High 6 / Medium 38 / Low 24), 284 base, 111 excluded. **Status: partial, accepted by the user;** next vertical v-enclosures-battery-generator (finders running).

## 2026-11-16: battery storage Stages B-C merged
- Merged battery-finder B, A, C, D (in that order; empty incoming values never blank a field). 98 records touched: 71 base and 27 excluded from the finders, plus verticals added to Sabre Bossier City (profiled, poles), Ultraquip Stockton (excluded) and Gulf Island Houma (ships exclusion kept word for word behind "v-shipbuilding-naval only:"; base for battery storage on its own Paylocity board's "Fabrication Enclosures" welder roles at 567 Thompson Rd).
- Enercon East Peoria came from slices A and B. Plant fields reconciled by hand: website from B, headcount from A, parent_company records that the sources differ on the acquisition date (Generac release: February 2026; Enercon site: April 2026). Both parent rows stay in evidence, each with its own source's value.
- Two links point to company placeholders (c-rolls-royce-power-systems, c-multiquip), as the earlier c- links do.
- Source failures: EPA FRS REST 503 or maintenance all session (ECHO used instead); cat.com 502; businesswire.com and nasdaq.com 502; investors.generac.com, powersystemstoday.com, compactequip.com 403; tesla.com jobs (Akamai 403); POWERGEN official exhibitor list behind a form (not used); UL Product iQ sign-in (not used); web.archive.org 429 to fetch_page (curl works).
- compare_audit: 163 auditor rows, 137 unique, 91 in definition; 66 matched rows map to 52 ledger plants; 25 candidate misses, several of them matcher misses (Rehlko Mosel, Chillicothe Metal, EK Machine, Fabcon are already in the ledger). Verification of the rest goes to a plant-finder.
- **Miss verification (plant-finder battery-misses, 18 candidates):** 10 real misses written as base (Sea Box Cinnaminson NJ, Yancey Griffin GA, Yancey Batesville MS, Martin Energy Tipton MO, Power Pool Plus Greenwood SC, Com-Fab Plain City OH, HOLT Waco TX, Taylor Power Richland MS, Stateline Power Greenville OH, Harvard Integrations Tea SD); 2 out of definition, written as 3 excluded records (nVent TRACHTE Chattanooga, Houston, Oregon WI: e-houses and substation buildings, rule 3); 2 already in the ledger (Fidelity Waco = p-fidelity-mcgregor-tx, two evidence rows added; Coastline Longwood = p-coastline-power-deland-fl); 4 not verifiable, no record (Panel Built Blue Ridge GA, Yancey Cordele GA "will refurbish" with no fit-out shown, Epic Power Ocala FL site down, Hennig/AME Rockford IL 2008-only source). Merged; 182 evidence rows, 0 rejected.
- **Miss rate: 10/61 = 16.4%** (method as for mining): 52 pre-existing ledger plants matched, minus 3 the ledger excludes with sourced reasons = 49; plus 2 already in the ledger that the matcher missed (Rehlko Mosel, Chillicothe Metal); plus 10 verified misses. Upper bound 13/64 = 20.3% if Panel Built Blue Ridge, Epic Power and Hennig Rockford prove real (Cordele is pre-production by rule 6, not a miss). Under the 20% advisor threshold on the verified figure. Auditor A was not shown dry (search budget ran out while the new-plant angle still produced plants); auditor B near-dry.
- **Profiling (workflow battery-profile-top40, started 2026-11-16):** top 40 by the profiling key (Sabre Bossier City already profiled for poles, so 40 base plants), four plant-profilers in parallel (A: EK Machine, Generac, Enercon, Rehlko, Blue Star, Hennig, Harvard; B: Newberry, Taylor, Martin, Power Pool Plus, Panel Built, HOLT, General Industries, Stateline, Modern Welding; C: Tesla, ECA Waller, Gulf Island, United Alloy, Freeman, Acoustical Sheetmetal; D: Technibus, JTS, Tomball Controls, PowerSecure, Yancey), each followed by its own fact-checker (R1-A to R1-D). Battery material rule: kW/MW ratings and gallons alone are not part sizes; material 20 needs a stated dimension or weight of a welded steel part at the site; aluminum-first or thin-sheet skins score 4.

## 2026-11-17: battery storage profiling merged (workflow battery-profile-top40; R1 fact-check)
- The first run was lost to a container restart before any agent finished; re-run in full.
- Merged battery-profiler A-D (apply_removals then merge; 0 rejected, 0 gaps), applied fact-check R1-A to R1-D: **R1-A 7/199 = 3.5%, R1-B 13/156 = 8.3%, R1-C 4/199 = 2.0%, R1-D 2/158 = 1.3%; round 1 overall 26/712 = 3.7%.** Main error kind: "quote does not support value" (clauses from another page or a company product page placed inside a plant's stated row). 4 rows unreachable (archived Generac Eagle page; web.archive.org failed every attempt).
- R1-B found Martin Energy's own Paycom board (29 roles; Structural Welder and Pipe Welders at Tipton). Its two suggested rows were merged by the coordinator and left **not_checked** (authored by the checker, so not independently confirmed).
- **Advisor consultation 15** (coordinator rulings before normalising). Changes from the advice: Hennig is scored without the campus rule (the Panel and Sub Welder requisitions sit at the board location whose address names the record's address; the Alpine Rd Tank Welders are listed, not counted); EK Fall River material stays 20 on the Path route (its Path Lead Welder leads "tank welders on Path Robotics projects" at Fall River) rather than a thin-sheet 4; Martin's demand cites the May 2026 report, not the 2024 announcement; Cordele and the other leads go to a closure finder; sweeps, geocode evidence and field drift before the done checkpoint.
- **Rulings:**
  - Held as base, prospect_test unknown, score fields and score/opening/bottleneck rows removed (Caterpillar Clayton precedent): Rehlko Mosel (final assembly), Rehlko Kenosha and Generac Belvidere (pre-production, welding not shown), Stateline Greenville (no welding or steel shown), ASC Production Rd (no welding tied to the campus), ECA Waller (operating status unverified).
  - Newberry West Memphis excluded (rule 3: round petroleum tanks, quoted); lookalike_of cleared.
  - PowerSecure Randleman relationship lookalike -> new (no generator enclosure, sub-base tank or BESS product stated). **Lookalike rule for this vertical, written once:** a stated product (company-level is enough) of generator enclosures, sub-base or day tanks, or BESS enclosures or skids makes a plant a lookalike of EK Machine even when the site tie of that product is inferred; skids, tanks or stands with no genset or BESS link do not.
  - Martin labor 20 (several counted at once on its own board; pipe welders count, Bollinger precedent) and demand 15: 75 High.
  - ASC Hudome Way ZIP tie accepted (the same ADP board gives Production Rd roles ZIP 23454 and their own location; Derrick Buffalo precedent): 67.
  - Tomball Von Ormy labor 20 -> 12 (JSON-LD date conflicts with the board's published date; one posting): 67 Medium.
  - Tomball Pleasanton labor 20 kept (rubric: mandatory overtime, "Mandatary Fridays"). Power Pool Plus process 20 kept (the posting states the shop's process; the counting rule is for labor) and material 4 by override (thin sheet stated; the normaliser's 4-test checks only aluminum).
  - Harvard and JTS material 20 kept (Werk-Brau precedent); their part_size_fit rows, Freeman Batavia production_type and Newberry Memphis headcount added to no-confidence-claims.csv.
- **Result:** 111 battery records: 34 profiled (High 9, Medium 17, Low 8), 46 base, 31 excluded. Top: Harvard Integrations Tea SD 88, EK Machine Fall River 87 (known customer), JTS Abilene 80, United Alloy Union OH 75, Martin Energy Tipton 75, Hennig Machesney Park 72, Yancey Griffin 72, Yancey Batesville 72, Gulf Island Houma 71.
- **Leads closure finder (battery-leads), merged 2026-11-17:** Yancey Barnesville GA (460 Industrial Rd; 7 welder requisitions on Yancey's UKG board, fuel tanks and aluminum stud frames; aluminum-first noted) and Wedlake Fabricating, Tulsa OK (IES; "manufacturer of custom generator enclosures"; Fitter/Welder with $2,500 sign-on bonus) new base; Yancey Cordele GA (502 S Midway Rd, refurbishment under way, Welder posting 2026-11-02 naming the site) new base under rule 6; Greiner Industries, Mount Joy PA (IES) excluded (structural, plate and bridge fabrication; rule 3 lead). Not verifiable: Rehlko Kohler WI (no posting on Rehlko's Workday API; expired aggregator copies only), Tomball San Angelo TX (management postings only, no address). No site: United Alloy Quincy IL (leased weld shop opened 2023; no longer listed).
- **Miss rate corrected: 11/62 = 17.7%** (Cordele, an auditor candidate, is now a verified miss). Upper bound 14/65 = 21.5% if Panel Built Blue Ridge, Epic Power Ocala and Hennig/AME Rockford prove real. Barnesville and Wedlake came from profiler and checker leads, not from the auditors' lists, so they do not enter the miss rate.
- Barnesville (24th), Wedlake (28th) and Cordele (33rd) rank in the top 40, so they go to profiler E and fact-checker R2-E (workflow battery-profile-leads), as for the mining top-40 misses.
- **Coordinate evidence (ground rule 1), all verticals:** about 460 plants had lat, lon or county values with no evidence row. tools/geo_evidence.py re-queried the Census Geocoder for each recorded street address and writes inferred rows: matched within 1.5 km (most), matched farther away (9 flagged, stored point kept, both points recorded; worst Hapco Oklahoma City 16 km, Metal Pros Wichita 12.8 km, Deere Coffeyville 9.6 km, BIW Brunswick 6.1 km), or approximate (110 no geocoder match, 17 no street address). Report: ledger/audit/geo-evidence-report.json.
- **Base-record sample (fact-checker CS-battery, 16 base + 6 excluded, random.Random(20261117)):** 7/212 = 3.3% (9/218 = 4.1% with six "unknown" welder_postings rows outside the tag scope). Applied. Findings: job boards missed or partly read (Global Power Components' own Workday board; Maysteel's Dayforce board read as 11 of 18 openings), so GPC Milwaukee, Maysteel Garland and Lynchburg now show one open welder posting each; nVent TRACHTE Chattanooga's exclusion premise was false (nVent's BESS page states BESS enclosures and skid platforms), relationship corrected to lookalike, status left for the sweep; Simplex relationship new -> lookalike (day tanks are on the lookalike list).
- **Coordinator rulings on the checker's questions:** (1) fact-checks include "unknown"- and "none found"-tagged welder_postings rows from now on, since they set labor to 0; (2) the relationship rule is not applied to excluded records (relationship has no use on an excluded record).
- **Sweep (plant-finder battery-sweep) launched:** full read of every base record's own job board where postings are "none found", "unknown" or "site not named"; nVent TRACHTE's three sites re-decided; relationship check on the six non-excluded "new" records; Winco (rule 2), Maysteel Germantown (rule 3) and Chillicothe (operating) status; missing coordinates for JTS Nampa, GTI Goodyear and Maysteel Germantown. After it merges, the profiling key is re-run and any base record that enters the top 40 is profiled.
- **Sweep merged (battery-sweep):** own job boards read in full. New counted postings: Fidelity Ocala Plant 1 (2; Steel Welder with hiring bonus, Aluminum Welder open 60+ days), Plant 2 (2), McGregor (3) on Fidelity's own Paylocity board (LocationName Plant 1/2/3); Phoenix Products Zoo Pkwy (4) and 8th St (3) tied by each iCIMS posting's JSON-LD streetAddress (Service Welder titles are repair welding; noted); Sea Box (1, JSON-LD street address). No welder roles: Maysteel Longmont, PSI Beloit and Darien (fabrication roles listed, not counted), Winco, GTI Phoenix/Goodyear/Wilmington, AVL, JTS Caldwell/Nampa, Simplex, Fabcon, Falcon; no board at Tramont, Pryco, Hardin, Coastline; blocked: Girtz, Kennedy, Pritchard Brown, Denyo, Com-Fab, Chillicothe.
  - nVent TRACHTE Oregon WI, Chattanooga and Houston -> base, lookalike (company states BESS enclosures and skid platforms; site ties inferred; Chattanooga and Houston weakest). Parent "nVent (nVent TRACHTE)"; Lectrus clause removed.
  - Relationship new -> lookalike: Generac Oshkosh, PowerSecure Durham, Falcon Structures, Kennedy (borderline: RE+ category only); Denyo stays new.
  - Excluded: Winco Le Center (rule 2, no enclosure/frame/tank welding shown; 3 MIG booths only), Maysteel Germantown (rule 3, "Data Center Manufacturing Hub").
  - Chillicothe Metal operating (EPA CAA status Operating, TRI reported for 2024, stormwater permit for a paint-building expansion to 2028).
- **Re-rank after the sweep:** twelve base records now sit in the top 40 by the profiling key (the six held plants excluded from profiling): Generac Oshkosh, nVent Houston, Chattanooga and Oregon, PowerSecure Durham, Simplex, Falcon Structures, Phoenix Products (both sites), Fidelity McGregor and Ocala Plants 1 and 2. They go to profilers F and G with fact-checkers R2-F and R2-G (as for the mining top-40 misses).
- **Profiler E merged + fact-check R2-E (4/94 = 4.3%; all four on Cordele pre-production status rows that overstated progress: "will refurbish" read as "being refurbished", a 2009 article dated 2010, an Operations Manager posting whose body says Batesville).** Scores: Yancey Barnesville 72 High (20/4/15/20/8/5), Yancey Cordele 71 High (20/4/15/12/15/5; profiled although pre-production because, unlike Kenosha and Belvidere, a live welder posting names the site), Wedlake Tulsa 68 Medium (20/0/15/20/8/5).
  - Yancey consistency ruling: the company-level line "custom power generation solutions" (c-yancey:production_type) earns part mix 15 at every Yancey plant and no confidence (added to no-confidence-claims.csv). Batesville 8 -> 15: 79 High.
  - Yancey's UKG "Posted on" date is a re-post stamp; the raw job data carries earlier first-posted dates (e.g. Barnesville WELDE004838 first posted 2025-10-20). Rows keep the displayed date; no 60+ days claim rests on either. Cordele labor stays 12.
  - normalise_scores.py: the material 4-test now also accepts a stated thin-sheet gauge (e.g. "14ga") in materials or part_size_fit, so the Power Pool Plus override is no longer needed.
- **Profilers F and G merged + fact-checks R2-F (2/116 = 1.7%) and R2-G (12/131 = 9.2%; strict reading 14/131 = 10.7%). Round 2 overall 18/341 = 5.3%.** R2-G's errors are all "quote does not support value": clauses copied from a sibling page into compound values, plans written as work under way (Fidelity McGregor "operations starting", Phoenix "construction from June 2025"), company products tagged stated at one site; five were older rows the profiler did not replace.
- **Rulings (2026-11-17):**
  - **Generac Oshkosh held as base** (rule 2 not shown: its postings say "fabrication of parts"; Generac's large-MW enclosures are Enercon's). **Winco Le Center re-ruled from excluded to held base** for the same reason: rule 2 excludes only when assembly-only is shown; when it is simply not shown, the plant is held (Clayton, Mosel).
  - **nVent TRACHTE Houston, Chattanooga and Oregon excluded under rule 3**, reversing the sweep's move to base: each site's own shown work is switchgear and e-house installation or steel substation buildings, and the BESS enclosure and skid line is stated only at company level. Kept as leads for v-datacenter-grid-prefab; profile rows removed. Rule written: company-level product lines decide relationship, not membership, when the site's own shown work is another vertical's.
  - Fidelity material 4 -> 0 at all three plants (neither aluminum-first nor thin sheet stated; both Steel and Aluminum Welder roles open): Ocala Plant 1 75, McGregor 75, Plant 2 68. Fidelity Plant 1 demand 15 kept (eight-acre Plant One expansion described by the CEO 2026-10-15). McGregor profiled although starting up (live welder postings name Plant 3; Cordele precedent).
  - Phoenix Products: Service Fabricators counted (posting text: operate welding and cutting systems, fit and assemble from prints); Service Welders are repair-worded and listed only; process 20 from their GMAW/FCAW requirements; scale 5 kept. Zoo Pkwy 75, 8th St 68.
  - Falcon material 20 kept (40 ft container generator enclosures; EK precedent): 56. PowerSecure Durham: campus accepted ("our Durham campus", buildings 0.67 km apart), labor 0 (temp-to-FTE conversion requisition): 41. Simplex scale 5 -> 0 (the "three locations in Springfield" line is undated and may predate a 2007 consolidation): 23.
  - c-fidelity:production_type and c-phoenix-products:production_type added to no-confidence-claims.csv.
- **Tool fix:** apply_factcheck.py wrote a corrected `:status` evidence value (a pre-production note) into Yancey Cordele's plants.csv status column. Restored to profiled; the tool no longer writes the status or id columns. No other plant was affected.
- **Battery storage now:** 115 records (incl. Sabre Bossier City, Gulf Island and Ultraquip from other verticals): 45 profiled (High 14, Medium 21, Low 10), 37 base, 33 excluded. Fact-check: round 1 3.6% (26/712), round 2 5.3% (18/341), base-record sample 3.3% (7/212). Miss rate 17.7% (11/62), upper bound 21.5%.

### Advisor consultation 16 (before marking battery storage done), 2026-11-17
- **Advice:** don't mark done yet. (1) rank_mining.py puts every OEM above every Tier 1 and misreads profiled posting wording; re-rank under CLAUDE.md step 5's written key (relationship bucket, then OEM and Tier 1 together, then open postings, headcount, sources). (2) Apply the nVent membership rule backwards (Panel Built, Modern Welding, Newberry Memphis, Sabre's battery tag) and reword the Oshkosh and Winco holds. (3) Line-check every High and Medium opening and bottleneck line after the rulings. (4) Give the summary its known limits. Non-blocking: recompute the miss denominator; EK confidence; the Oshkosh air permit; GTI Goodyear pin; the old-vertical RETAG candidates.
- **What changed:**
  - **Written-key re-rank:** contract fabricators (Robinson x3, Maysteel, Sea Box) fall below OEM and Tier 1 and stay out of the top 40. Three base records sit inside it: Global Power Components Milwaukee (1 counted posting), PSI Darien and Pritchard Brown (0 postings; inside the 40 on number of sources). They go to profiler H with fact-checker R2-H (workflow battery-final-wave), plus a status read of Generac Oshkosh's air permit. The other base records in the top 40 are the eight held plants.
  - **Membership rule applied backwards:** Panel Built Blairsville excluded (several separate facilities; this site's shown work is welded steel modular buildings; BESS line company-level). Sabre Bossier City's battery tag removed (BESS flyer names no plant; the site's shown work is poles and shelters); it stays profiled in poles. Kept, with reasons: Modern Welding Owensboro (the UL generator-base tank certificate is issued at this plant's PO box, a site-level tie); Newberry Memphis (two plants only, West Memphis is stated as round petroleum tanks, and generator base tanks are rectangular, so the rectangular-tank Memphis plant is the only place the stated Gen-Tank line can be made: a deduction, not a company-level guess).
  - Oshkosh and Winco prospect_test rows reworded: welding at the site is stated; rule 2 membership is what is not shown.
  - Line check R3-lines runs after profiler H.
  - **Miss rate recomputed: 11/60 = 18.3%.** Of the 52 pre-existing matched plants, 5 are not included battery records now (TAPP Houston, JRB Chattanooga, Caterpillar Griffin and Newberry West Memphis excluded; Caterpillar East Peoria is a mining record the matcher paired by city), so 47 + 2 matcher misses (Rehlko Mosel, Chillicothe) + 11 verified misses = 60. Upper bound 14/63 = 22.2%.
  - Not done this session: GTI Goodyear pin (no geocoder match for "W MC 85"); per-case review of the 9 far-off points; the ~30 old-vertical RETAG candidates printed by sweep_company_level.py (poles and ships; neither applied nor reviewed).

## 2026-11-17 Battery storage: profiler H, fact-check R2-H, line check R3 merged
- Profiler H (written-key re-rank): Global Power Components 51st St 65 Medium (20/0/15/12/8/10, conf 2); PSI Darien 40 Low (12/0/15/0/8/5); Pritchard Brown 27 Low (0/4/15/0/8/0). 92 rows added, 3 removed, 0 rejected.
- Fact-check R2-H: 8/77 = 10.4% (7 "quote does not support value": company overview text stated as one site's products at GPC, a plan written as current, an optional spec item written as "each"). No score moved. Round 2 total 26/418 = 6.2%.
- Line check R3 (every High and Medium opening line and bottleneck guess, 70 lines): 20/70 = 28.6%; 17/70 = 24.3% without three form-only fixes. 10 of the 20 were UKG "Posted on" re-post stamps read as posting dates (Yancey, United Alloy). All 20 rewritten; none changed a score. 1 unreachable (Generac Eagle; archive.org reset).
- Coordinator sweep from the line check: Yancey and United Alloy welder_postings now say "listed" with a re-post note (raw first-posted dates where evidence carries them); Von Ormy "about 130 days open" removed (two dates conflict; labor was already 12); Hennig 7 counted (Sub Welder Day closed 2026-11-17; labor 20 unchanged).
- Rulings: GPC labor stays 12 (Tester - Weld is repair on tested tanks, listed only, Phoenix precedent; Burnham trainee is a separate site 1.3 km away). GPC scale stays 10 on the inferred site headcount (1,200+ company, most operations at 51st St); no confidence from it. PSI demand stays 8 (expansion completion undated). Pritchard Brown stays profiled: its own spec states a welded steel floor and underframe and it has one facility; logged as a known limit.
- Generac Oshkosh air permit: not determined (DNR documents timed out); stays held.
- Leads not merged: PSI 1901 Gateway Blvd Beloit (UL tanks), MTL Manufacturing (PSI subsidiary, Beloit), GPC Burnham 4101 W Burnham St; PSI Beloit products value needs rewording (tanks moved to Gateway Blvd).
- Counts: 114 found, 80 included, 46 profiled (High 14, Medium 21, Low 11), 34 excluded. Miss rate 11/60 = 18.3% (upper bound 22.2%).

## 2026-11-17 Advisor consultation 17 (battery done-or-partial; line check over 10%)
- Advice: not done on this state. Consultation 16 made done conditional on a clean line check, and R3 came back at 28.6%; its 20 rewritten lines are unchecked. Run a confirming pass by other checkers (rewritten lines, profiler-H lines, the 22 lines of the 11 Low plants R3 did not cover, the hand-reworded posting fields) plus a sweep of R2-H's repeated kind (company Overview text stated as one site's products); done only if under 10% and no score moves, else partial.
- Done before the pass:
  - Drift script: its URL filter was always true, but all 23 reworded rows are UKG (ultipro) rows, so nothing to revert.
  - Generac Eagle opening line: the unsourced "base tanks and enclosures" clause dropped (checker's fallback line); row set to not_checked. Eagle's membership rests on the archived 2022 Generac page, read once by the profiler and unreachable since: a known limit.
  - Seguin opening line: UKG date given as "listed". Pritchard bottleneck: "each" corrected (the floor is optional in Spec 2130). PSI name descriptor trimmed.
  - The 28 corrected verdicts of R2-H and R3 all landed on rows with their exact source URL.
  - UKG sweep, all verticals: 26 plants carry ultipro evidence; 18 outside battery (poles 10, ships 3, mining 5) still say "posted" for UKG dates. A UKG stamp is later than the first posting, so it understates how long a role has been open and cannot inflate a 60+ day labor score; left for the next refresh, noted here.
  - GPC scale 10 kept: Fidelity's 5 rests on an unknown headcount, GPC's 10 on an inferred one (1,200+ employees, most operations at 51st St); consistent rule, no confidence from either.
- Confirming pass launched: R4-A and R4-B (45 lines), R4-C (9 posting fields, 25 job-posting product rows).

## 2026-11-17 Confirming pass R4 merged; advisor consultation 18; battery storage marked PARTIAL
- R4-A (23 lines) 4/23 = 17.4%; R4-B (21 lines) 6/21 = 28.6%; lines together 10/44 = 22.7%. R4-C (9 posting fields, 25 job-posting products rows) 4/61 = 6.6%. Round 4 pooled 14/105 = 13.3%. Corrections applied; none moved a score.
- Correction to the earlier sweep and to the report sent to the user: Hennig's Welder I - Sub Welder - Day Shift is live (R4-C); the count is 8, not 7.
- Advice (consultation 18): mark partial; another rewrite round will not fix it, since R4 corrected lines earlier checkers had rewritten and R3 had passed Union's "buildout" clause. Rulings:
  - Hennig: the consultation-15 basis (postings at the board address naming this record) was false: the counted postings carry no street address. The ledger has one Hennig record, so the tie is an inferred reading of the "Hennig Power, Machesney Park" label: points stay (72 High), labor and process lose confidence (5 -> 3; welder_postings and weld_processes added to no-confidence-claims.csv). Downside if the tie fails: 32 Low. GPC keeps its tie: its board location field names "51st Street".
  - Cordele labor stays 12: the raw 2026-06-30 date is only in a checker file, not on an evidence row (lead). Reasoning text fixed ("listed 2026-11-02, a UKG re-post stamp"). Confidence 5 -> 4 (products and production_type rows are division-level, R4-C).
  - R4-B sweeps (aggregator sources, expansion wording) on lines no checker had seen: EK bottleneck tense fixed (Plant 5 "will expand"); ASC, Fidelity Ocala, Generac Eagle and Yancey Batesville lines read as supported by stated rows.
  - Refresh lead: raw UKG first-posted dates can be earlier than the stamps, so they could raise labor scores (60+ days) in poles, ships and mining as well as lower nothing; check at the next refresh.
- verticals.csv: v-enclosures-battery-generator status partial, with the reason and the steps to reach done.
- Final battery counts: 114 found, 80 included, 46 profiled (High 14, Medium 21, Low 11), 34 excluded. Miss 18.3%.

## 2026-11-17 User request: OSHA file, assessment labels, state air permits, Chrome pass (user: yes to all four; no line into Path sales, so no back-test)
- Advisor consulted on the plan (order: labels, permit pilot, posting dates; OSHA and Chrome need the user).
- OSHA: osha.gov returns 403 from its CloudFront edge to this container (page and file URLs, plain and headless). Logged once (ground rule 6); not retried through other hosts. The user is asked to download the 2025 ITA summary and add it as data/osha_2025.csv.
- Chrome: no computer or Chrome extension is attached to this cloud session; the pass needs the user's machine. The posting-date part runs here instead through the job boards' own JSON (headless Playwright where needed).
- Labels (display only; evidence.csv keeps stated | inferred | unknown): build_map.py gives each inferred row a class. Assessment = tier, tier_secondary, lookalike_of, relationship lookalike/new, scores, confidence, opening_line, bottleneck_guess, exclusion_reason, part_size_fit, verticals, vertical scorecard fields; geocoded = Census or registry point; approximate location = centroid, no match or kept far point; process note = found_by. prospect_test, known_customer/customer_other_plant and plant status stay inferred facts (they assert welding, a Path customer, operation). Assessments show their basis (stated or inferred) from the claims their reasoning cites. Counts: 9,372 inferred rows = 4,941 assessments, 1,229 geocoded, 502 approximate, 395 process notes, 2,305 inferred facts (I had told the user "about 1,400"; the right figure is 2,305 because prospect_test, status and customer relationships stay facts). Stated-only mode hides exactly what it hid before (call list 212 in the smoke state; every tab equal on fresh load); smoke assertions added.
- Coordinator rule 2026-11-17 (job-board re-stamps; asked for by consultation 18): UKG and Paylocity show re-post stamps as "Posted on"; board dates are written "listed <date>" unless the raw first-posted date is read from the board JSON. A counted posting live today whose raw first-posted date is 60 days to 12 months old counts as open 60+ days (labor 20); a raw date over 12 months old marks a standing ad (open, 12, unless several postings or a bonus earn 20). An agent's raw-date reading scores only once it is on an evidence row and fact-checked.
- Launched: permit pilot (20 plants in TX, OH, WI: the 8 held battery plants' share and profiled plants whose welding rests only on inferred rows; 81 targets nationally) and the UKG raw-date pass (25 plants with UKG evidence, all verticals), each followed by a fact-checker (R5).

## 2026-11-17 Permit pilot and UKG raw-date pass merged
- UKG pass (25 plants, all verticals): 103 rows in, 97 replaced rows retired; R5-UKG 1/103 = 1.0% (0/79 stated). Raw first-posted dates now on stated rows. Score moves: Yancey Cordele labor 12 -> 20 (WELDE005744 first posted 2026-06-30, 140 days; re-stamp rule), 71 -> 79 High; Arcosa Traffic Structures Sumterville (poles, done vertical) labor 20 -> 0 (its only welder posting closed), 68 -> 48, still Medium, confidence 3 -> 2. Poles tier counts unchanged. Meyer Clinton 8 and Meyer Fort Worth 8 counted (up from 7 and 5); lines rewritten.
- Ruling: United Alloy Weld Youth Apprentice postings (a high-school student programme) are listed, not counted: not a production welder role.
- Permit pilot (TX 11, OH 5, WI 4): 7 hits, R5-PERMITS 1/15 = 6.7% (Klein quote is Klein's own NESHAP report filed in the TCEQ record, not the investigator's text; value corrected). Stated prospect_test rows for Sabre-FWT, Structural & Steel Products, Klein, MICA Kaufman (2009, worded as of the document date), Vessel Repair (2003, same), Generac Oshkosh (2019 Title V, Welding P16), Rehlko Mosel (2023, F42 welding operation). Stated materials for SSP (steel plate) and Klein (carbon and stainless steel); the old inferred rows retired.
  - FWT process 0 -> 20 on the stated 2021 PBR application (manual GMAW and SAW at the address): 21 -> 41 Low, confidence 0 -> 1.
  - Generac Oshkosh and Rehlko Mosel stay held: welding is now stated at both, but neither permit names enclosure, base-frame or tank welding (rule 2). Oshkosh's 2025 inventory reports zero welding throughput for 2024 and 2025 (no stable URL; not a row).
  - Rehlko Mosel city set to Mosel (permit address). Ohio permits list only permitted units, so welding was absent at all 5 Ohio sites: Ohio is low-yield.
  - Leads: KW East Bernard registry address CR 291 (ledger CR 1952); LSI Cincinnati permits at 10170 Alliance Rd (ledger 10000); DIS-TRAN plasma cutter permit 2026-02-13 (possible trigger); GARZO at ECA's Waller address.
- tools/fetch_page.py: a response starting with %PDF- is read as a PDF (Wisconsin serves permits as octet-stream).
- Decision: fan the permit search out to the other 61 targets (yield 7/20, every hit a stated welding-at-the-address row), with a checker per batch.
- Fix: a stray write_summary call (meant as a usage probe) rewrote ledger/audit/summary-v-poles-substation.json without its miss rate and limits in a2c74bc; restored from the previous commit (poles tier counts unchanged by today's rescoring). Map rebuilt; smoke passed.

## 2026-11-17 Permit fan-out merged (61 plants, 29 states)
- Batch results: PERMITS-1 (VA, SC, PA, KS, CA, WV, NY, AZ, TN, MD) 1/21 hit (NNS Goose Creek, SC general permit equipment summary: electric arc welding facility-wide); PERMITS-2 (IN, NC, MN, IL, LA, MI, MO, ND, SD) 4/20 (Corn Island, Nucor Towers & Structures, Valmont PiRod Plymouth, Construction Attachments Lenoir); PERMITS-3 (MS, IA, KY, FL, AL, OK, WY, UT, NE, OR) 6/20 (Syntron, Bollinger Pascagoula, Quality Mfg, PPI Pella, Musco, JamesBuilt). With the pilot: 18 of 81 targets now have welding stated at the address from a state air record.
- Fact-checks: R5-P1 1/1 (a permit-type clause not in the PDF; true per the SC listing, value corrected), R5-P2 1/15 = 6.7% (Corn Island "mild steel" was a grinding-wheel rating; corrected to steel plate), R5-P3 1/13 = 7.7% (PPI "EU 21" OCR error, EU 2l). Fan-out total 3/29 = 10.3%, all wording, none score-bearing.
- State systems: usable TX, WI, IN, NC, IA, MS (old host), KY, SC, NY (by DEC ID), FL (low yield for shipyards); blocked from this container VA DEQ (Akamai), KS KDHE (Cloudflare), PA eFACTS (TLS), MN MPCA documents (captcha), LA EDMS (image viewer), IL viewer, SCAQMD (503); WV documents need a sign-in (shared credentials not used: a sign-in under ground rule 5); AL files are scans (Master Boat names welding, unquotable without OCR). Ohio permits list only permitted units. Small shops without an EPA air ID rarely hit.
- Rulings:
  - Process 0 -> 20 on stated permit rows: Corn Island (95 FCAW stations; SMAW beside it is not TIG) 30 -> 50 Medium; Construction Attachments (MIG, NC DAQ inspection 2026-07-02) 36 -> 56 Medium; Nucor Towers & Structures (MCAW/GMAW and FCAW beside SAW; Title V application Aug 2026) 45 -> 65 Medium; Valmont PiRod Plymouth (47 MIG stations) 21 -> 41 Low.
  - JamesBuilt stays process 0: the Title V permit names GMAW and SMAW, but the tie of that permit to 390 Riverside Ln is inferred (permit says 476), so attribution earns no points (shared-city rule). Syntron stays 0 (no process named). Musco: the stated GMAW is aluminum (2013); steel-pole welding at Muscatine still unstated; process unchanged.
  - Valmont PiRod Plymouth address set to Plant 1, 1200 N Oak Rd (welding), Plant 2 office at 1545 Pidco Dr noted. Nucor Towers & Structures city set to New Ross (stated address 4129 East Ladoga Road); map point moved to New Ross village point (OSM; no Census match), approximate.
  - Superseded unknown/inferred process and material rows retired (8 rows) to ledger/audit/retired-evidence.csv.
  - Gulf Island Houma: ships tag removed (Sabre precedent). It is excluded from ships (reason kept) and profiled for battery only; with both tags it was counted as a profiled High ships plant. Ships summary counts refreshed: 217 found, 134 included, 47 profiled (High 18, Medium 16, Low 13), 83 excluded. Mining tiers refreshed (Construction Attachments to Medium).
- Smoke: the stated-only count on the call list fell 212 -> 207 because five values became stated (data, not labels); the assertion now only pins the count when HID_CALLS is given for a like-for-like build.

## 2026-11-17 OSHA ITA Form 300A 2025 data (user-supplied) and advisor consultation 19
- The user uploaded the OSHA 2025 300A summary as four JSON parts plus a brief (400,288 establishments, submissions through 2026-08-31; source file ITA_300A_Summary_Data_2025_through_08-31-2026_2.csv). Converted to data/osha_2025.csv (14 columns, all IDs unique; 70 MB, gitignored), with data/osha_2025_naics33.csv (NAICS 33, 2381, 4238; 40,665 rows; in git) and data/osha_2025_cited.csv (every cited record). The source hash in the brief could not be verified against the JSON conversion; said in every row's reasoning.
- Advisor consultation 19 (before writing rows): OSHA changes only the site-headcount half of scale; hold the multi-plant half as already scored (from current points: 0 -> 0/5, 10 -> 10/5, 5 -> which half from the old headcount, unclear to review). Auto-accept only with all gates: manufacturing NAICS, same street number and street name, the operating name shared ("former" names stripped; parent-only overlap and a differently named establishment go to review), one candidate each way, plausible values. Review queue: any lowering, small counts at possibly larger sites (all profiled matches under 100), and grade B on profiled plants. Commit an extract of cited records. Refresh summaries with the plants-only patch (never bare write_summary). Fix the stale Method and brief text.
- Matcher (tools/osha_match.py) results: auto 102 profiled, 161 base (47 excluded, unused); review 39 profiled. Errors the gates removed: Yancey Cordele -> Big Tex Cordele (former occupant), Deere Davenport -> Vonachen (contractor), Electric Boat -> NEmSI (contractor), Meyer Tulsa -> Arcosa Wind Towers (parent-only), Martin Tipton -> "Tipton Latham" (differently named establishment, to review).
- Applied (tools/osha_apply.py): 230 stated headcount rows (69 profiled at 100+, 161 base); 52 superseded "unknown" headcount rows retired. Scale raises on 59 profiled plants (0 -> 5 or 5 -> 10; none lowered). Tier moves: to High: Meyer Steele, Valmont El Dorado, Eastern Allanton, Keel Ladson, Rockland Bedford, Etnyre Oregon, Tomball Von Ormy, Freeman Batavia (68/67 -> 73/72); to Medium: J.H. Fletcher, Bobcat Litchfield, Super Steel, Klein Jacksonville, Syntron, PSI Darien. No-confidence entries removed for Werk-Brau and Bobcat Litchfield headcount (the claim now rests on an in-window stated row).
- Tiers now: poles High 11 / Medium 32 / Low 38; ships 20 / 14 / 13; mining 8 / 42 / 18; battery 16 / 20 / 10 (summaries' plant counts refreshed; miss rates and limits unchanged).
- Review queue (ledger/audit/osha-review-queue.json, 72 entries): 28 under 100, 30 review, 9 several candidates, 5 unclear half. Sent to a reviewer and a fact-checker next.
- AGENT_BRIEF.md and the Method page no longer say the OSHA file is absent.
- Re-rank after OSHA (advisor 19): tools/rank_for_profiling.py misread "318 (OSHA 300A, 2025 ...)" as 2025 (largest number) and posting dates as posting counts ("2026"), and counted "not checked"/"not found" text as one posting; fixed (first number; "<n> open/counted"; not/none/unknown/no = 0). Under the written key, base plants now in a top 40: ships Bollinger Amelia (643), Bollinger Lockport (600), Bollinger Houma (384), Sterling Shipyard Port Neches (265) (all entered on OSHA headcounts); battery Girtz Monticello (225) and JTS Nampa (155) (OSHA), plus Generac Oshkosh (held); mining Standard Iron Hartford x2 (2 undated postings, already in under the corrected key). So "top 40 fully profiled" no longer holds for ships, battery or mining; the eight are being profiled (profilers OSHA-SHIPS and OSHA-MIXED, fact-checkers R7).

## 2026-11-17 OSHA review merged; fact-check R6-OSHA and rulings
- Review (72 queued profiled plants): USE 58, PARTIAL 7 (inferred, no points: Meyer Tulsa = Arcosa Wind Towers establishment; EK Fall River three building records 91/54/55; PPI Pella 282 may cover all Pella sites; Philippi-Hagenbuch two partial records; Klein Ontario wholesale NAICS; Martin Tipton combined "Tipton Latham"; KW East Bernard record at CR 291), NONE 7. 17 scale raises (Valmont Tulsa, Meyer Hager City, Meyer Fort Worth, Keel Hollywood, Phoenix 8th St to High; PowerSecure Durham to Medium). The five "unclear half" plants: Hughes, Heartland, Senesco, Rhoads earned their 5 on the site half (stays 5, now on OSHA); Terex Durand on the multi half (raised to 10).
- R6-OSHA: 134 checked, 4 corrected = 3.0%; auto sample 3/40 = 7.5%; review file 1/94 = 1.1%. Repeated kind: the record is not the plant's own count (duplicated across two yards, the operating company, one building of a campus).
- Rulings: Gulf Copper Galveston scale 10 -> 5 (80 -> 75, High): its record duplicates Port Arthur's to the unit (Port Arthur base row also retagged inferred). Great Lakes Shipyard scale 5 -> 0 (35 -> 30): the 133 is The Great Lakes Towing Company. Werk-Brau headcount back on the no-confidence list (one building of the campus; 144 alone keeps 10). Campus sweep: Rockland Bedford (Weber Lane building of a two-address campus; 210 alone keeps 10) and Robinson De Pere (base) retagged inferred; Fecon's ledger record is Plant 1's address (180), stated stands; MEC, Eastern, Bollinger, Steiner and other same-city records are separate ledger plants. Harvard (record avenue 462nd vs 470th) and Hughes (inferred tie) headcount added to no-confidence, matching the six raises that cite an inferred site_attribution row. Ground Force address 6001 E Seltice Way (OSHA, FRS); point kept and labelled approximate (geocoder matches only W Seltice).
- Coordinator calls declined: no summing of building records (EK Fall River), no use of another establishment's record (Meyer Tulsa), no site use of a record that may cover several sites (PPI Pella).
- Leads: Fecon's "single production site" contradicts its four OSHA plant records in Lebanon; Sabre Conroe has two filings at its address (148, 199; both 100+); hours oddities at Kress, UIS, Fincantieri, Metalcraft Fall River (noted only); Phoenix 8th St still listed open on Ring Power's locator.
- Tiers now: poles 14/29/38, ships 21/13/13, mining 8/42/18, battery 17/20/9. data/osha_2025_cited.csv now holds all 299 cited records.

## 2026-11-17 Top-40 entrants after OSHA profiled (profilers OSHA-SHIPS, OSHA-MIXED; checks R7)
- Ships: Bollinger Lockport 77 High (conf 6; 8 counted welder/fitter postings at 8365 Hwy 308; Sep 2025 FRC award; process 12 under ships rule 1, part mix 8 one cutter class); Bollinger Houma 52 Medium (Arctic Security Cutter steel cut Apr 2026; Leaderman (Pipe) listed, not counted: directs and inspects, R4-C test); Bollinger Amelia 40 Low (scale 10 -> 5: OSHA record "Bollinger Amelia Operations" fails the name gate and may include the adjacent repair yards); Sterling Shipyard Port Neches 40 Low (May 2026 tug contract). R7-OSHA-SHIPS: stated 3/74 = 4.1%, lines 2/4 (Amelia "manual crews" premise unsourced; Houma "CEO" -> "president"), all rows 5/163 = 3.1%.
- Battery: JTS Nampa 80 High (conf 2; material 20 on the JTS template tank text, the Abilene ruling); Girtz Monticello 64 Medium (process 12, TIG rule; demand 15 on the Sep 2026 permit approval). Mining: Standard Iron Hartford: the only site-naming welder posting says "1055 W Sumner St or 1720 Innovation Way" and never says where a hire works. Ruling (consultation 18 precedent: a posting that cannot be assigned between two ledger plants is unknown for both): Sumner process and labor 0, 66 -> 26 Low, confidence 0; Innovation Way held as base (prospect test rests only on that posting; score, line and bottleneck rows retired; Caterpillar Clayton precedent). R7-OSHA-MIXED: stated 11/78 = 14.1% (Helgesen brand-level products/production_type rows retagged inferred x6; judgements inside stated posting rows x3; group name not on page x2), lines 2/8; all rows 15/172 = 8.7%. Over 10% on stated rows: the errors are retags of company-level text, none score-bearing after the Standard Iron ruling.
- Amelia check found the matcher's parent-name path let an "operations" establishment through; the sweep in R6 covered the campus and duplicate patterns; Amelia is the only profiled case where the establishment carries an operating word the plant lacks (the others name the yard).
- Re-rank (written key): ships and mining top 40 fully profiled again; battery's only unprofiled top-40 plant is Generac Oshkosh (held). Tiers: ships 22/14/15 (51 profiled), battery 18/21/9 (48), mining 8/42/19 (69), poles 14/29/38 (81).
- Leads: Bollinger Raceland (4535 LA-308; office roles only), Girtz Legrand acquisition (Jun 2026) not yet a triggers row, Bollinger board dates are re-stamps (shipfitter roles first published 2024-08 to 2025-10).

## 2026-11-17 User: complete both partials before moving on; advisor consultation 20 (finish lines)
- User: "The two Partials need to be completed before moving forward. Pushback if you disagree." Coordinator agrees; finish lines set now so done cannot drift.
- **Battery done when:** every profiled plant's opening line and bottleneck guess is rewritten under constrained composition (each clause from one stated site-level row with that row's date; postings as "listed <date>", no live counts; the source's own verb for expansions; company facts worded company-wide), passes tools/validate_lines.py (new: cited claims exist and are stated, every number and date in the line is on a cited row, banned words, closing "you" question), and a same-day independent line check of all High and Medium text lines is 10% or less with no score moves (rate on text lines only; lines set to "unknown" reported separately). One attempt; if it fails, back to the user. Before the validator, 42 of 78 current High/Medium lines failed it.
- **Mining done when:** one OSHA-driven closure pass (NAICS 333120, 333131, 333922, 332313 establishments not in the ledger; base records only with a sourced in-definition product at the site: no bulk-adding on NAICS) and one blind re-audit by two new list-auditors with new methods (C: state directories and product-by-state search; D: dealer line cards, OEM supplier lists, trademarks, news), no OSHA or NAICS lists, same miss formula as R2: verified miss rate 20% or less; then re-rank and profile any top-40 entrant, fact-check under 10%, the same line test as battery, and review the unreviewed sweep_company_level.py candidates. **Stop rule:** one closure and one audit; if still over 20%, report the misses by size to the user and do not change MIN_HEADCOUNT or the definition.
- Diagnostic before the closure: 22 of the 46 verified R2 mining misses have an OSHA record of their own (NAICS spread across about ten codes; half under 40 employees), so OSHA closes about half the gap; directories carry the rest (auditors' angles).
- Both verticals still go through the advisor checkpoint before their status changes. Poles and ships were never held to the line test; noted for the user (not blocking).
- Done meanwhile: cross-vertical fact-check files (R5 permits and UKG dates, R6 OSHA, R7 entrants) were not counted in any vertical's audit section (write_summary globs per-vertical files only); tools/summary_cross.py now adds them as round 8 by plant vertical: battery 1/147 = 0.7%, mining 19/157 = 12.1% (mostly Standard Iron brand-level rows retagged), poles 1/137 = 0.7%, ships 11/205 = 5.4%; profiled_fact_checked now counts them. Map pins added for the 18 included plants without one (1 Census match, 17 approximate town points, labelled), incl. GTI Goodyear (its address does not geocode). Workflow battery-lines first launch failed at once (a constant missing in the script; no agent ran) and was relaunched.

## 2026-11-17 Battery lines rebuilt under constrained composition; line check R5
- Four line-writers rebuilt both lines for all 48 profiled battery plants (validator 0 failing in each file); 8 lines set to "unknown" (no stated site fact fits: EK Madison x2, General Industries bottleneck, Tesla Lathrop bottleneck, Taylor Richland bottleneck, Simplex, Modern Welding, Blue Star bottlenecks).
- Line check R5 (two checkers who wrote none of them, same day, R3/R4 error definitions): R5-A 0/45 (2 unreachable: Freeman Abilene, posting closed), R5-B 1/43 (Tesla Lathrop, a Low plant: "April 2025" month on no row; corrected to 2025). **Round 5: 1/88 = 1.1%; High and Medium 0/76 = 0.0%.** Under the 10% bar.
- Freeman Abilene: its only welder posting (req 24792, listed Sep 22, 2026) closed (404; gone from the IES API): welder_postings "none open", labor 12 -> 0, 59 -> 47 Medium; lines replaced with the checker's fallback built on the May 2026 Broadwind sale. This is a data refresh, not a line error (no line correction moved a score).
- tools/validate_lines.py now pools each cited row's retrieved_date (both writers reported the gap; "read November 2026" clauses are now proven by the tool). Run on the other verticals' High/Medium lines: mining 58/100 failing, poles 39/83, ships 26/72.
- Battery summary rewritten (round 5 label added; limits updated); cross-vertical round 8 re-attributed.

## 2026-11-17 Advisor consultation 21 (battery done checkpoint) and closeout: BATTERY STORAGE DONE
- Advice: battery can be marked done (round 5 met the bar; nothing reopens the miss rate or the facts), after: EK Madison lines (the only High/Medium plant blank; a customer's other plant) written the way L2/L4 wrote undated pages ("read November 2026") and checked by a non-author together with Freeman Abilene's checker-written fallback lines; Cordele production_type retagged; Hennig's posting field reworded to claim no live count; duplicate line rows checked; Maysteel Germantown pin checked; limits to state Freeman's refresh, unknown lines, JTS Nampa's template-text material, Girtz's permit-based demand, same-day posting snapshots; validator tightened so retrieved dates count only inside "read <date>" clauses.
- Done: line-writer L5 wrote EK Madison's two lines (validator 0 failing); line-checker R5-C: 0/4 (EK Madison x2, Freeman Abilene x2). Round 5 total 1/92 = 1.1%; High and Medium 0/80. Cordele production_type (QC Manager posting, division-level) retagged inferred. Hennig welder_postings reworded ("several ... the count moves day to day"; labor 20 unchanged). No duplicate line rows. Maysteel Germantown is excluded (no pin needed). Freeman line rows' produced_by corrected to the checker. Validator restricts read dates to "read <Month> [<day>,] <year>" clauses; battery 90 text lines, 0 failing.
- verticals.csv: v-enclosures-battery-generator status done, reason rewritten. Summary rewritten with full arguments, cross round re-attributed. Smoke: battery card and section now assert done and round 5's 1.1%.
- Battery final: 114 found, 80 included, 48 profiled (High 18 / Medium 21 / Low 9), 34 excluded. Miss 18.3%. Rounds: 3.6%, 6.2%, 28.6% and 22.7% (lines, superseded), 13.3% (round 4 pooled), 1.1% (round 5 lines), 0.7% (cross), base sample 3.3%.

## 2026-11-17 Mining closure 5 and blind audit R3: first results
- Closure 5 (OSHA 300A candidates not in the ledger): 5A (NAICS 333120 + 333131, 211 screened): 24 base (6 with welding stated, 3 fabrication stated, 16 with prospect_test unknown held as base under the Caterpillar Clayton / Pemberton precedent), 1 excluded (Somero Fort Myers HQ), 18 already in the ledger, 23 unverified, 144 triaged out. 5B (333922 conveyors, 202): 8 base. 5C (332313 plate work, 256): 2 base (Ottenweller Fort Wayne, Petersen Ogden), 1 already in the ledger, 127 triaged out, 19 unverified, **107 not attempted** (the shared web-search budget, 200 per turn across all agents, ran out). Merged: 35 base records, 516 evidence rows, 0 rejected.
- Coordinator call on 5A's 16 unknown-prospect records: kept as base with prospect_test unknown (Caterpillar Clayton precedent: an in-definition product at a manufacturing site, welding not shown); not profiled until welding is shown.
- Blind auditor R3-C (state directories, product-by-state search; 25 searches, not dry): 70 rows, 62 in definition; 43 matched ledger plants (40 included, 3 excluded); 19 unmatched: already in the ledger under another city or name (Solesbee's, Rockland, CAI/Gainwell), out of definition by the boundary rules (Crysteel, Rugby, Ox Bodies, Godwin: on-road dump bodies, v-truck-bodies; Panova: tractor loader attachments, agricultural), 11 to verify (Johnson Industries, DSI Underground Abingdon, Long-Airdox, Aggregate Processing, American Bin & Conveyor, Inertia, Custom Dredge Works, Allied-Gator, USA Breakers, Geith, MDS). Range before verification: 0/42 to 11/53 = 20.8%.
- Blind auditor R3-D got zero web searches (budget already spent by the closure agents) and built its list from recall; the file is set aside unread by the coordinator's comparison (scratchpad) and the auditor is rerun fresh: an infrastructure failure, not a second audit under the stop rule.
- Launched: verification of R3-C's 11, R3-D rerun, closure 5C remainder (107).
- R3-C verification: 4 verified misses (American Bin & Conveyor Burlington WI and Custom Dredge Works Topeka with welding shown; Johnson Industries Pikeville and Inertia Freeport with welding not shown), 4 unverified (DSI Underground, Allied-Gator, USA Breakers, Aggregate Processing: base, Pemberton-type), Long-Airdox and Geith not plants, MDS agricultural. R3-C alone: 4/46 = 8.7% (upper bound 8/50 = 16.0%). 5 base records merged.
- Closure 5C remainder (107 plate-work candidates): 2 base (Argo Brookfield WI, Precision Machine Eugene OR; both boundary calls noted), 89 triaged out. Merged.
- R3-D rerun (dealer line cards, buyer's-guide brand index, supplier awards, trademarks, news; 27 searches, not dry): 114 rows, 100 in definition (it kept on-road dump bodies and compact attachments in, flagged); 42 matched; 58 unmatched: 12 on-road dump-body makers (out: v-truck-bodies), about 16 ledger plants the matcher missed for want of a city, about 30 to verify (mostly skid-steer and excavator attachment makers). The auditor reported that fetch_page.py --check can return FOUND on a 403 error page whose text contains the string (it re-ran its checks requiring 2xx). Verification of all 46 non-dump-body rows launched.
- Tool fix (from R3-D's report): tools/fetch_page.py --check now refuses to report FOUND on an HTTP 4xx/5xx page (prints HTTP_ERROR, exit 2); tools/verify_ledger_quotes.py counts a quote found only on a page with status under 400. merge_inbox.py already treated status 400+ as unreachable. Earlier agent-run --check results could include error-page passes; a ledger-wide re-run of verify_ledger_quotes.py would measure it (not run yet).

## 2026-11-17 Mining blind audit R3: verified miss rate 14.9%
- R3-D verification (46 rows): 21 already in the ledger (matcher missed them for want of a city), 15 verified misses as written by the verifier, 8 unverified, 2 out of definition (Superior Fabrication Kincheloe, York-Seaway). 15 base records merged.
- Coordinator ruling: boundary rule 1 (the core welded product decides) puts the lifting-led makers (Cornerstone Brandon, Haugen Casselton, Star Fort Worth, Kenco Ligonier) in v-cranes-lifting and tractor-led Grouser West Fargo in v-agricultural-equipment (MDS and Panova precedent); set excluded with the reason. The verifier had kept them on secondary skid-steer lines. Hammersmith (Vail) Horton is a separate physical plant from Vail Holton: counted as a miss (one record per physical plant). Compact/skid-steer attachment makers (CID, Omni, Stinger, Top Dog, Quick Attach) counted as misses, as boundary rows were in R2.
- **Verified miss rate, R3 (two blind auditors with new methods, R2 formula: misses / (included plants found + verified misses); excluded plants found leave the count): 14/94 = 14.9%.** R3-C alone 4/46 = 8.7%; R3-D alone 10/67 = 14.9%. Sensitivity: counting the five lifting- and tractor-led makers as misses, 19/99 = 19.2%; upper bound if all 12 unverified rows were misses, 26/106 = 24.5% (most have dead sites or no stated manufacturing). Neither auditor reached a dry point (both stopped at their search budgets). Closure 5 supplied 3 of the 80 found plants; the R2 misses added on 2026-11-16 supplied more. History: 30.2% (first blind audit), 27.6% (R2), 14.9% (R3).
- Under the 20% bar. Next under the finish line: profile the two top-40 entrants (Kafka Mosinee rank 19, Laidig Mishawaka rank 38, both OSHA closure records), review the 64 mining rows sweep_company_level.py flags, rebuild all 69 profiled plants' lines under constrained composition, three independent line checks; then the advisor checkpoint.
- Ledger-wide quote re-check (tools/verify_ledger_quotes.py with the error-page fix): 9,132 quoted rows; found 8,050, found by browser 406, AISC snapshot 79, not found 597 (330 OSHA rows: osha.gov blocked; 267 other stated rows, mostly EPA FRS pages (63) and script-loaded or closed job boards). Two display fixes in build_map.py: OSHA-row quotes are matched field by field against the cited record in data/osha_2025_cited.csv (shown as "quote matches the OSHA 300A file record", counted with saved-copy matches; all 330 match) and the checker's stored quotes, cut to 160 characters before today, now match their full ledger quote by prefix (1,050 stated rows had read as unchecked for that reason). data/osha_2025_cited.csv rebuilt from every OSHA ID cited in the ledger (341). The checker now stores full quotes. Method page, stated rows now: 8,613 found on the live page, 394 matched to a saved copy, 125 not found (flagged red in the drawer), 131 unchecked.

## 2026-11-17 Mining finish work merged (entrants, sweep, lines)
- Entrants profiled (fact-check round 4: stated 0/22, lines 0/4, all rows 1/70): Kafka Mosinee 55 -> 43 Low after ruling (its careers-page ad, JSON-LD 2023-03-30, has Apply Now buttons that go to a generic Indeed company page: a static page line, not a posting on an applicant board, Mine Rite precedent; labor 12 -> 0); Laidig Mishawaka 52 Medium (confidence 4 -> 3: part mix cites an inferred site-attribution row).
- Company-level sweep (round 7, targeted, not a sample; check file renamed so it is not read as a sampled round): 64 flagged rows, 22 confirmed (the page names the site), 41 retagged inferred (company or two-site pages), 1 corrected but stated (CMI Waverly product sentence). No score or confidence moved. 8 plants.csv fields prefixed "company-level; site split not stated".
- Lines: six writers rebuilt all 69 profiled plants' lines (entrants' lines by the profiler), validator 0 failing; 4 lines set to "unknown" (Tabor Princeton, Klein Ontario, Bobcat Bismarck, Ground Force bottlenecks). Line check round 6 (three checkers who wrote none): R6-A 0/46, R6-B 2/45 (Derrick qualifier, Liebherr expansion clause on no row; corrected), R6-C 0/43; **2/134 = 1.5%; High and Medium 1/100**; 3 unreachable (postings closed today: Rockland Fitter Fabricator, Virnig Robotic Welder): fallback lines applied (Virnig bottleneck "unknown").
- Data refresh rulings (not line errors): Rockland Bedford labor 20 -> 12 (one posting left; 73 -> 65, High -> Medium); Virnig Rice labor 12 -> 0 (58 -> 46); Mellott Warfordsburg labor 20 -> 12 (its 2026-06-19 date is a batch re-list of five ADP requisitions within 50 minutes and the text says "Updated 12/26/24": a standing ad; the re-stamp rule now read as applying to ADP too) (60 -> 52); Schwing posting field 5 -> 2 open (labor 20 unchanged); McLanahan date worded "listed" (UKG stamp); Standard Iron Sumner lines rebuilt on its stated posting row only (validator 0 failing).
- Validator over all mining lines: 137 text lines, 0 failing. Summary rewritten (miss 14.9%, rounds 4/6/7 labelled, limits updated; status still partial pending the advisor checkpoint). Mining: 520 found, 403 included, 71 profiled (High 7 / Medium 44 / Low 20), 117 excluded.

## 2026-11-17 Advisor consultation 22 (mining done checkpoint): not yet; closeout work
- Advice: lines and entrants pass; the miss rate passes on the agreed formula but its margin is five plants and the found side was never inspected; Standard Iron Sumner rests on the same two-address posting as the held Innovation Way; re-rank after today's posting changes; non-author check of the lines the coordinator applied; apply the Mellott (posting age) and Kafka (apply flow) rulings backwards; recompute limit counts from plants.csv; state round 8 with and without Standard Iron, the auditors' non-dry stops and scratchpad writes, the sweep's blind spot (pages cited by only one plant), that no checker sampled today's base records, and unknown lines by tier.
- Found-side inspection: all 85 matched auditor/ledger pairs listed and read. One wrong pair: R3-C's "Builtrite Handlers & Attachments, Two Harbors MN" was matched to LaBounty (Epiroc) in the same town, a different company; counted as a miss without verification (conservative). KPI-JCI credited once. Found and miss sets do not overlap. **Miss rate: 15/94 = 16.0%.** Five or more of the 12 unverified leads would have to be real misses to cross 20% (so no retry of the tool-failure cases was required under the advisor's four-or-fewer test).
- Standard Iron Sumner held as base (same two-address posting as Innovation Way; nothing distinguishes it); its score, line and bottleneck rows retired; welder_postings row reworded "not counted".
- Re-rank (written key) after the posting changes: no base plant in the mining top 40.
- Counts from plants.csv: closure 5 added 37 records (34 base, 2 profiled, 1 excluded; 19 base with prospect_test unknown); R3 verification added 20 (15 base, 5 excluded to other verticals; 11 base with prospect_test unknown). Profiled 70 (High 7 / Medium 44 / Low 19). Unknown lines: 5 bottleneck guesses (Low 4, Medium 1). Round 8 for mining: 19/157 = 12.1%; 5/71 = 7.0% without Standard Iron Hartford's two records.
- Launched check R9-closeout: posting-age rule on PHIL, Werk-Brau, Derrick, J.H. Fletcher; apply-flow rule on IROCK, Allied Systems; non-author check of the Rockland, Virnig, Derrick and Liebherr lines; battery Fidelity IndustryWeek trigger rows.
- R9-closeout (targeted, not a sample): J.H. Fletcher's 2026-08-08 ADP date is a re-post stamp of requisition 1000 (older than requisition 1002, first posted 2025-01-08): standing ad, labor 20 -> 12, 48 -> 40 Low. PHIL (JSON-LD and file stamp 2026-05-05), Werk-Brau (job IDs rise in date order) and Derrick (consecutive new requisitions) keep 20. Allied (own apply form) and IROCK (blanket "send applications to" instruction under current openings; coordinator call: counts) keep 12. Lines: Virnig opening question reworded (it assumed Fort Madison would weld attachments); Rockland, Derrick, Liebherr confirmed (Rockland's composing claims now include weld_processes). Battery Fidelity triggers: all three confirmed plant-level; Plant 1's demand 15 rests on the IndustryWeek row ("right here in Plant One"), so it stands. Werk-Brau posting field drift fixed. Mining lines: 135 text lines, 0 failing.

## 2026-11-17 Advisor consultation 23 (mining done checkpoint): MINING DONE under the written rule, both readings reported
- Advice: the boundary ruling is the whole margin. With Builtrite counted, the alternative reading (any stated skid-steer or excavator line keeps a plant in mining) gives 20/99 = 20.2%, 22/101 = 21.8% with MDS and Panova; the coordinator's earlier "19.2%, still under the bar" is retracted. The ruling must be applied to found plants too. Decision rule: both readings pass -> done; only the written rule passes -> done is defensible on the pre-research rule, but lead with both figures; neither -> stop rule.
- Found side read under the written rule (core product decides): the found compact-attachment makers (Berlon, Danuser, Worksaver, Virnig, Dymax, East, Solesbee's) are compact/skid-steer-led, as are the counted compact misses; no found plant is lifting-led or tractor-led, so no found plant leaves the count. Written rule: 15/94 = 16.0% (passes). Alternative reading: 20.2-21.8% (fails). Result: done on the written pre-research rule (boundary rule 2, set 2026-11-12), with both figures leading the summary and the reason. R2 counted compact attachment makers as misses, as R3 does.
- Fixed before the status change: battery's summary status field (written before verticals.csv changed) set to done; mining verticals.csv reason and status updated first, then the summary rewritten with full arguments (miss 16.0%, limits recomputed from plants.csv: 37 closure records, 19 + 11 base with prospect_test unknown, 70 profiled, Standard Iron held, Fletcher, IROCK and Werk-Brau sensitivities, Virnig checker-written line, unknown lines by tier, auditors not dry and their scratchpad writes, the sweep's two-plant blind spot, no sample of today's 57 records), cross round re-attributed (mining 22/175 = 12.6%; 8/89 = 9.0% without Standard Iron Hartford). Re-rank: no base plant in the mining top 40. Smoke: mining card and section assert done, 16.0%, 1.5%.
- Not done for other verticals (user's call): the posting-age and apply-flow rulings and the line test were applied to mining and battery only; poles and ships may hold re-listed ads and unchecked lines.
- Mining final: 520 found, 403 included, 70 profiled (High 7 / Medium 43 / Low 20), 117 excluded.

## 2026-11-17 User: complete the first verticals in their entirety; run the line test and posting rules on poles and ships before data-center prefab
- Scope set by the coordinator from the open items: (1) poles (81 profiled) and ships (51 profiled): rebuild every opening line and bottleneck guess under constrained composition (validator-gated; before: 39/83 poles and 26/72 ships High/Medium lines failed the validator) and four independent line checks (bar: 10% or less, no score moves from line errors); (2) the posting-age and apply-flow rulings applied to poles, ships and battery (9 plants holding labor 20 on one posting's age, 3 holding 12 on a careers-page ad); (3) a seeded sample (25 of 51) of mining's records added today; then summaries, smoke, map, and an advisor checkpoint for each done vertical whose figures move.
- Workflow poles-ships-completion launched (8 line-writers, postings checker R10, sample checker CS-R3, then 4 line-checkers).

## 2026-11-18 Container restart; completion work resumed
- The container restarted mid-workflow (poles-ships-completion). Survived on disk and committed: line-writer files P1-P5 (all 81 poles plants) and S1 (17 ships plants), each complete and validator-clean; postings check R10 and mining sample CS-R3 reports. Lost: line-writers S2 and S3 and all four line checks; relaunched as workflow poles-ships-completion-resume (S2, S3, then line checks PA, PB, SA, SB).
- R10 postings (poles, ships, battery; targeted): MaiCo Ellsworth's Welder ad has been on its Paycom board since 2023-01-05: standing ad, labor 20 -> 12, 88 -> 80 (High). Meyer Hager City, Universal Industrial Sales, V&S Schuler Canton (coordinator call: kept on the written rule; requisition order inferred, Werk-Brau precedent; 52 if it were a re-list), Keel Ladson, Trident, Conrad x2 keep 20 (real first-posted dates); Gulf Island keeps 20 (eight postings at once; its "posted" date reworded as a re-post stamp). Pelco, Western Utility Telecom and Girtz keep 12 (per-role apply forms or ATS links). Western Utility's recruiter ATS date (2026-04-24) would give 20; not applied (no merged row). R10: 4/43 corrected, 1 unreachable (a tallo.com row behind a sign-in wall).
- Mining sample CS-R3 (25 of the 51 records added 2026-11-17, seeded): 4/300 corrected = 1.3%, 5 unreachable (BROCK's Cloudflare-blocked sources). Corrections: BROCK tier_secondary, CMP Clear Lake site-attribution (home page does not say it manufactures there), Gill Rock Drill prospect test dated 2017, American Bin parent. Status note: Aggregate Processing's fabrication evidence is undated and probably about 2010 (kept base, not profiled).

## 2026-11-19 Poles and ships lines rebuilt; line checks R7 (PA, PB, SA; SB pending)
- The resume workflow wrote ships batches S2 and S3; line checks PA and PB (poles) and SA (ships S1+S2) finished; SB (ships S3) and the SA report-back hit the weekly usage limit. SA's file was complete on disk (34 plants, 64 text lines); SB rerun.
- All eight line files merged (removals first): 132 plants. Line checks: PA 0/56, PB 6/77 (premise questions presuming welding not stated at the site: Sovereign, Nello Spring Grove, Nello Westby, Ehresmann, LSI; DIS-TRAN publication date), SA 3/64 (Sterling, Bollinger Amelia, Master Boat wording). Poles so far 6/133 = 4.5% (High/Medium 0/35 in PA, 2.3% in PB); ships SA 3/64 = 4.7%. 9 unreachable lines (six Sabre/MICA lines resting on Tallo copies now behind a sign-in wall; Accurity x2): checker fallback lines applied, citations fixed for two; validator: poles 133 text lines, ships 97, 0 failing.
- Data refresh rulings from the checks: Nucor Brigham City labor 12 -> 0 (posting filled; 32 -> 20); PennFab Morrisville labor 12 -> 0 (its only listing names Ivyland and Morrisville, plant of hire not stated, Standard Iron precedent; 55 -> 43 Low); Accurity Owensboro labor 12 -> 0 (only copy behind a sign-in wall, own careers page gone; 67 -> 55). Kept: Valmont Columbus 20 (robot-titled role requires hands-on welding and a weld test: counted; two open at once); DSC Poplarville 20 (Fitter III added 2026-05-18 on a stated row, still listed; 50+ hour week); Sabre plants and Millerbernd 20 (roles still on own boards; their Tallo rows need own-board replacements: limit). Nichols Freeland's own-board JSON-LD date (2026-08-01) is on no row: no change (lead).

## 2026-11-19 Ships line check SB; advisor consultation 24 (ships miss rate 29.4% under the completion standard)
- SB (ships S3, 17 plants): 3/33 = 9.1% (High/Medium 3/26 = 11.5% for this batch): "said/reported in 2026" with a year the row does not carry as a publication date (EB Groton, EB Quonset), and a process list attached to more postings than its row (BAE Jacksonville). Applied. Ships R7 total 6/97 = 6.2% (High/Medium 3/72 = 4.2%); poles R7 total 6/133 = 4.5% (High/Medium 1/83 = 1.2%). Sweep for the repeated kind (year-only "said/reported in <year>" clauses across all four verticals): 4 remain, all on Low plants and all read by a line checker; no action.
- Ships was marked done on 2026-11-14 at a 29.4% miss rate (32/109, two blind auditors; advisor consultations 7-8). Under the user's "complete the first verticals in their entirety" and the 20% finish line mining and battery were held to, the coordinator consulted the advisor (CLAUDE.md: miss rate over 20%).
- Advice (consultation 24): hold ships to the mining finish line (one closure, one blind re-audit, same stop rule); do not ask the user first; leave its status until the audit returns and say so as its first limit. Ship an interim map now. Stage work in small committed workflows. Ships: OSHA diagnostic on the 32 R1 misses first; write the boundary reading (repair-only yards, aluminum boat builders, dredge builders, Tier 1 module shops) into the log before any result; auditors in their own workflow with methods R1 did not use, their own scratch folder, no OSHA or NAICS lists; read every matched pair; compute the alternative reading before reporting; also a fresh seeded base-record sample (R1's was 13.0%), the 73 drift-flagged rows, and Westport Orange's status. Poles: a non-author check of the 21 lines changed after the checks; own-board evidence rows for the Sabre plants' and Millerbernd's postings (labor 20 currently rests on a checker's reading); Valmont Columbus row update (the robot-titled role is now counted; log the 58 downside); re-rank; summary with full arguments; Tallo as a source failure; smoke update. Mining and battery: summary refresh for R10 and the new sample.
- Interim map: plant counts refreshed in all summaries, ships summary carries the re-measuring note as its first limit, cross rounds re-attributed, built, smoke passed, republished.
