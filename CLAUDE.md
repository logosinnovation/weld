# Path Prospect Map

A national map of every US plant that could use Path Robotics' autonomous welding, organised by vertical and supply-chain tier. Every fact must trace to a quoted source. It is an outside pitch to Path's sales team (SDRs, account executives) and leadership, so it must hold up to "where did this come from, and why should I trust it?"

These rules apply to the main session (the coordinator) and to every subagent.

## Folder layout
- `ledger/verticals.csv` one row per vertical: definition, status (candidate | accepted | rejected | partial | done), scorecard fields, rank, reason
- `ledger/plants.csv` one row per physical plant; status = base | profiled | excluded
- `ledger/links.csv` supplier relationships: from_id, to_id, what_is_supplied, claim_id
- `ledger/evidence.csv` one row per claim (format below)
- `ledger/run_log.md` dated entries: decisions, source failures, counts, weight changes, audit results
- `ledger/inbox/` subagent output files, merged by the coordinator
- `ledger/audit/` fact-check and list-audit reports
- `data/osha_2025.csv` optional. OSHA national 2025 summary. Use establishment_name, company_name, street_address, city, state, zip_code, naics_code, industry_description, annual_average_employees. No county column. Ignore its size column.
- `map/index.html` the built map

## Coordinator: how a run works
The main session coordinates. It does not do the research itself.
1. Read `ledger/` first. Never redo finished work.
2. If no vertical is accepted, run `vertical-planner` (Stage A).
3. Take the next vertical: `FIRST_VERTICAL`, then by rank. One vertical per session.
4. `plant-finder` builds the plant list and base records (Stages B-C). Split by company group and run several in parallel when the vertical is large.
5. Rank included plants for profiling: customer_other_plant and lookalike first, then OEM and Tier 1, then open welder postings, headcount, number of sources. Give the top `FULL_PROFILES_PER_VERTICAL` to `plant-profiler` agents, about 10 plants each, in parallel (Stages D-E).
6. `fact-checker` and `list-auditor` run after profiling (Stage F). They never take part in research.
7. `map-builder` rebuilds the map from the whole ledger (Stage G).
8. Final message: vertical completed; plants found, included, profiled; High/Medium/Low split; ten highest-scoring plants, one line each; fact error rate and miss rate; any weight changes; sources that failed; which vertical is next.

Merging: subagents never edit the ledger files. Each writes its results to `ledger/inbox/<agent>-<label>.json`. The coordinator validates and merges them into the ledger, then commits locally with a message naming the stage. Push only when the user asks.

Each subagent starts with no memory of the session. Every delegation message must carry the vertical's definition, the specific plants or companies assigned, and the output file name.

## Advisor checkpoints
Consult the advisor at these points and nowhere routine:
- before accepting or rejecting a vertical
- before changing score weights after the back-test
- when a vertical's miss rate is over 20% or its fact error rate is over 10%
- before marking a vertical done
Log each consultation and what changed in `run_log.md`.

## Settings
- FIRST_VERTICAL: Poles and substation steel
- FULL_PROFILES_PER_VERTICAL: 40
- RECENCY_MONTHS: 24
- MIN_HEADCOUNT: none

## Ground rules
1. Every value shown on the map has a row in `evidence.csv`.
2. Never invent a plant, relationship, process, certification, date or number. Not found = "unknown".
3. "Stated" means the source text says it. A bottleneck is always "inferred" unless the company says it outright. Industry alone never sets a weld process or a tier.
4. Business-level facts only. No personal emails, personal phone numbers or home addresses.
5. Browsing: no sign-ins, no LinkedIn automation (public search snippets are fine), no contacting businesses, no forms except site search boxes. Use a browser only for sites that block normal page fetches.
6. If a tool or source fails, log it once and continue. No single source is required.
7. Keep excluded plants and rejected verticals in the ledger with the reason.
8. The map always ships. If time or context runs low, stop research, mark the vertical "partial", and go to audit and map.

## Evidence row format
claim_id (plant or vertical id + ":" + field), value, tag (stated | inferred | unknown), quote (exact source text, up to 300 characters), source_url, source_type (company site | job posting | news | government file | certification list | trade association | other), retrieved_date, archive_url (save the page to a web archive when possible; else blank), reasoning (inferred claims only), produced_by (agent name), verified (not_checked | confirmed | corrected).

## Path reference
Capabilities (Path's site and sales material):
- Process: MIG/MAG (GMAW). Fillet, butt, bevel/groove and structural welds, including multi-pass adaptive fill. Quality claim: AWS D1.1.
- Materials: carbon and stainless steel. Path claims aluminum; treat it as unconfirmed.
- Part size: an older Path sales sheet lists the large cell at 8-72 in diameter, up to 65 ft long, 10,500 lb, and a small-part cell at up to 36 in and 50 lb. A 2026 analyst report says cells handle up to 60 ft long, 15 ft wide, 55,000 lb. Record which limit a plant's parts fit.
- Rove: a walking welding robot for work too large to move into a cell. 50 units ship in 2027.
- Best fit: many part types, part-to-part variation, imperfect fit-up. Weak fit: high-volume identical parts already on fixed robots.

How Path sells: Robots-as-a-Service with no upfront cost; a factory acceptance test on the customer's own parts; enterprise accounts with senior buyers; growth by expanding inside existing customers.

Verticals and parts Path names: defense and aerospace (ship, tank and submarine hulls, naval components, armored panels and vehicles, vehicle frames, weapon mounts); utility and energy (utility poles, traffic poles, substations, battery storage); data centers (structural frames, e-houses, cooling units, server racks); heavy industry (mining equipment, industrial buckets, heavy trailers, chassis frames, boom assemblies, excavator and loader arms, hydraulic tanks).

Customers reported. Confirm each from a primary source before relying on it:
- Path's own material: HII, Saronic, LAD Services (barges), TYCROP (mobile power chassis), Millerbernd and Nello (poles)
- Press: Lockheed Martin
- One analyst report: Valmont, Mine Rite, AMSi, Cheetah Manufacturing, Schenck Process
- 2022-23 coverage: Hutchens Industries, Ameritex

## Definitions
Prospect test (all three): the plant welds in-house; welding is a core production step; it welds carbon or stainless steel (aluminum-first plants are kept and noted). Failing plants stay in the ledger as excluded, with the reason.

Tiers:
- OEM: sells a finished product under its own name
- Tier 1: supplies welded assemblies directly to OEMs
- Tier 2: supplies components or sub-weldments to Tier 1s
- Contract fabricator: builds to customer drawings across customers and sectors
- Tier 3: materials and processing only; usually fails the prospect test
Give a secondary tier where two apply.

Relationship: known_customer; customer_other_plant (same parent, not reported as converted); lookalike (name the customer it resembles and why); new.

## Scoring (profiled plants, 0-100)
Points come only from evidence; an unknown component scores 0. Use the weights in `run_log.md` if the back-test changed them.
- Process fit, 20: MIG or flux-core on production weldments 20; mixed with TIG 12; mostly TIG or spot 4
- Material and part fit, 20: steel parts within a cell's limits 20; too big to move but suited to Rove 12; aluminum-first or thin sheet 4
- Part mix, 15: many part types or custom work 15; mixed 8; high-volume identical parts 0
- Labor pain, 20: welder postings open 60+ days, several at once, or a sign-on bonus or mandatory overtime 20; any open welder posting 12; none found 0
- Demand and triggers, 15: a plant-level trigger within RECENCY_MONTHS 15; only the vertical's demand outlook 8
- Scale, 10: multi-plant parent and 100+ employees at the site 10; one of the two 5
Tier: High 70+, Medium 45-69, Low under 45. Confidence = how many of the six components rest on stated evidence (0-6). Store each component's points with the claim_ids behind them.

## plants.csv columns
id, status, name, parent_company, address, city, state, county_fips, lat, lon, website, verticals, products, tier, tier_secondary, relationship, lookalike_of, headcount, found_by, exclusion_reason, weld_processes, materials, certifications, part_size_fit, production_type, existing_robots, welder_postings, triggers, bottleneck_guess, opening_line, score_total, score_tier, confidence, score_process, score_material_part, score_part_mix, score_labor, score_demand, score_scale, last_checked
