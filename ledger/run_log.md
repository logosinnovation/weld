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
