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
