// Smoke test for map/index.html: node tools/smoke_map.js  (needs playwright). Exits 1 on any failure.
const {chromium} = require('playwright');
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
const SHOTS = process.env.SHOTS || '/tmp/claude-0/-home-user-weld/15c8b7fa-2833-5efe-87c1-28b9533d13eb/scratchpad/map-two-verticals';
fs.mkdirSync(SHOTS, {recursive: true});
function csvRows(f){ // minimal RFC4180 parser
  const t = fs.readFileSync(f, 'utf8'); const rows = []; let r = [], c = '', q = false;
  for (let i = 0; i < t.length; i++) { const ch = t[i];
    if (q) { if (ch === '"') { if (t[i+1] === '"') { c += '"'; i++; } else q = false; } else c += ch; }
    else if (ch === '"') q = true; else if (ch === ',') { r.push(c); c = ''; }
    else if (ch === '\n') { r.push(c); rows.push(r); r = []; c = ''; } else if (ch !== '\r') c += ch; }
  if (c || r.length) { r.push(c); rows.push(r); }
  const h = rows.shift(); return rows.filter(x => x.length === h.length).map(x => Object.fromEntries(h.map((k, i) => [k, x[i]])));
}
const plants = csvRows(path.join(ROOT, 'ledger/plants.csv'));
const verts = csvRows(path.join(ROOT, 'ledger/verticals.csv'));
const PV = 'v-poles-substation', SV = 'v-shipbuilding-naval';
const profiledOf = v => plants.filter(p => p.status === 'profiled' && p.verticals.split(/\s*[;,|]\s*/).includes(v)).length;
const sumOf = v => JSON.parse(fs.readFileSync(path.join(ROOT, `ledger/audit/summary-${v}.json`), 'utf8'));
const shipsProfiled = profiledOf(SV), polesProfiled = profiledOf(PV);
const fails = [];
const check = (ok, msg) => { if (!ok) { fails.push(msg); console.log('FAIL', msg); } else console.log('ok  ', msg); };

async function run(label, ctxOpts, full) {
  const b = await chromium.launch(); const ctx = await b.newContext(ctxOpts); const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push('pageerror ' + e.message)); p.on('console', m => { if (m.type() === 'error') errs.push('console ' + m.text()); });
  p.on('request', r => { if (!/^(file|data|blob):/.test(r.url()) && !/cdnjs\.cloudflare\.com/.test(r.url())) errs.push('request ' + r.url()); });
  await p.goto('file://' + ROOT + '/map/index.html'); await p.waitForTimeout(1200);
  const tab = async (name) => { await p.locator('#tabs button', {hasText: name}).first().click(); await p.waitForTimeout(500); };
  const text = sel => p.locator(sel).first().innerText();
  const shot = n => p.screenshot({path: path.join(SHOTS, `${label}-${n}.png`), fullPage: false});
  if (!full) { await tab('Method'); await shot('method'); await tab('Vertical ranking'); await shot('ranking'); check(errs.length === 0, `${label}: no console errors/requests ${JSON.stringify(errs.slice(0,3))}`); await b.close(); return; }

  // header and ranking
  const head = await text('#stats');
  check(/Verticals done/.test(head) && /Plants profiled/.test(head), `${label}: header stats`);
  await tab('Vertical ranking');
  const pc = await text('#vc-' + PV), sc = await text('#vc-' + SV);
  check(pc.includes('done') && pc.includes(String(polesProfiled)) && !/29\.4%|7\.3%/.test(pc), `${label}: poles card (done, ${polesProfiled} profiled, no ships figures)`);
  check(sc.includes('done') && sc.includes(String(shipsProfiled)) && !/13\.8%|11\.8%|19\.4%/.test(sc), `${label}: ships card (done, ${shipsProfiled} profiled, no poles figures)`);
  check(/Latest audit summary \(ledger\/audit\/summary-v-poles-substation\.json\)/.test(pc) && /13\.8%/.test(pc), `${label}: poles card audit line`);
  check(/Latest audit summary \(ledger\/audit\/summary-v-shipbuilding-naval\.json\)/.test(sc) && /29\.4%/.test(sc) && /7\.3%/.test(sc) && /6\.1%/.test(sc), `${label}: ships card audit line`);
  await shot('ranking');

  // map: vertical filter, tier filter, state click, search
  await tab('Plant map');
  const vsel = p.locator('#fbar-map select[data-f="vert"]');
  await vsel.selectOption(SV); await p.waitForTimeout(400);
  const dotsShips = await p.locator('#v-map svg circle').count();
  await vsel.selectOption(PV); await p.waitForTimeout(400);
  const dotsPoles = await p.locator('#v-map svg circle').count();
  check(dotsShips > 50 && dotsPoles > 50 && dotsShips !== dotsPoles, `${label}: map vertical filter (ships ${dotsShips} dots, poles ${dotsPoles})`);
  await vsel.selectOption(SV); await p.waitForTimeout(300);
  const tsel = p.locator('#fbar-map select[data-f="tier"]'); if (await tsel.count()) { const o = await tsel.locator('option').allTextContents(); if (o.length > 1) { await tsel.selectOption({index: 1}); await p.waitForTimeout(300); await tsel.selectOption({index: 0}); } }
  await p.locator('#v-map path.state, #v-map .state').first().click({force: true}).catch(() => {}); await p.waitForTimeout(400);
  await shot('map-ships');
  await p.fill('#q', 'saronic'); await p.waitForTimeout(500);
  check(/saronic/i.test(await text('#v-map')), `${label}: name search finds Saronic on map view`);
  await p.fill('#q', ''); await p.waitForTimeout(300);
  await vsel.selectOption('');

  // supply chain: a maker whose list has a company-level node
  await tab('Supply chain');
  const opts = await p.locator('#makerSel option').evaluateAll(os => os.map(o => ({v: o.value, t: o.textContent})));
  let sawCompany = false, sawNoBroken = true;
  for (const o of opts.filter(o => /link/.test(o.t))) {
    await p.selectOption('#makerSel', o.v); await p.waitForTimeout(250);
    const t = await text('#sclist'); if (/Electric Boat/.test(t) && /company/i.test(t)) { sawCompany = true; await shot('supply-company-node'); break; }
  }
  check(sawCompany, `${label}: supply chain shows a company node (Electric Boat) for a ships link`);
  const poleMaker = opts.find(o => /link/.test(o.t) && /Arcosa|Nucor|Meyer|Steel Structures/i.test(o.v));
  if (poleMaker) { await p.selectOption('#makerSel', poleMaker.v); await p.waitForTimeout(300); check(/Evidence for this link/.test(await text('#sclist')), `${label}: poles maker link evidence button`); }

  // call list
  await tab('Call list');
  const callTxt = await text('#v-calls');
  check(/Existing Path accounts/.test(callTxt), `${label}: call list has existing Path accounts block`);
  const exBlock = await p.evaluate(() => { const el = [...document.querySelectorAll('#calllist .blockh')].find(x => /Existing Path/.test(x.textContent)); let t = ''; let n = el && el.nextElementSibling; while (n && !n.classList.contains('blockh')) { t += n.innerText + '\n'; n = n.nextElementSibling; } return t; });
  check(/NNS|Newport News|Ingalls/i.test(exBlock) && /Saronic/.test(exBlock) && /LAD/.test(exBlock), `${label}: existing-account block lists HII, Saronic, LAD plants`);
  check(/customer_other_plant|other plant/i.test(exBlock) || /Path customer/.test(exBlock), `${label}: path status badges shown`);
  const nAll = (await p.locator('#calllist .crow:not(.hd)').count());
  await p.locator('#live').check(); await p.waitForTimeout(400);
  const nLive = (await p.locator('#calllist .crow:not(.hd)').count());
  check(nLive > 0 && nLive < nAll, `${label}: live trigger only toggle (${nLive} of ${nAll})`);
  await p.locator('#live').uncheck();
  await shot('calls');
  await p.locator('#v-calls select[data-f="vert"]').selectOption(SV); await p.waitForTimeout(400);
  const shipRows = await p.locator('#calllist .crow:not(.hd)').count();
  check(shipRows === shipsProfiled, `${label}: ships call list rows ${shipRows} = ${shipsProfiled} profiled`);
  await p.locator('#v-calls select[data-f="vert"]').selectOption('');

  // pre-production badges
  await p.fill('#q', 'Hadrian'); await tab('Plant map'); await p.waitForTimeout(400);
  for (const nm of ['Hadrian', 'New Pacific', 'Port Alpha']) {
    await p.fill('#q', nm); await p.waitForTimeout(400);
    const hit = await p.evaluate((nm) => { const b = [...document.querySelectorAll('#v-map [data-plant]')].find(x => x.textContent.includes(nm)); return b ? b.getAttribute('data-plant') : null; }, nm);
    if (!hit) { check(false, `${label}: found ${nm} in map list`); continue; }
    await p.locator('#v-map [data-plant="' + hit + '"]').first().click(); await p.waitForTimeout(500);
    const pt = await text('#profile');
    check(/Pre-production plant|New or converting plant/.test(pt), `${label}: ${nm} profile carries a pre-production badge`);
    if (nm === 'Hadrian') { check(/not yet profiled/i.test(pt), `${label}: base plant says not yet profiled`); await shot('profile-preprod'); }
    await p.keyboard.press('Escape'); await p.waitForTimeout(200);
  }
  await p.fill('#q', ''); await p.waitForTimeout(300);

  // profiles + evidence drawers: HII, Saronic Franklin, one poles plant
  await tab('Call list');
  const profs = [['Newport News Shipbuilding (main', /customer_other_plant|other plant/i], ['Saronic', /known_customer|known customer/i], ['LAD', /customer_other_plant|other plant/i]];
  let drawers = 0;
  for (const [nm, relRe] of profs) {
    await p.fill('#q', nm); await p.waitForTimeout(400);
    const btn = p.locator('#calllist button[data-plant]', {hasText: nm}).first();
    if (!(await btn.count())) { check(false, `${label}: call list has ${nm}`); continue; }
    await btn.click(); await p.waitForTimeout(500);
    const pt = await text('#profile');
    check(/Opening line|opening line/i.test(pt) && /Confidence|confidence/.test(pt) && /Existing Path account/.test(pt), `${label}: profile ${nm} (score, confidence, opening line, Path account banner)`);
    const ev = p.locator('#profile [data-claim]').first(); await ev.click(); await p.waitForTimeout(400);
    const dt = await text('#drawer'); drawers++;
    check(/source/i.test(dt) && /retrieved|Retrieved/.test(dt) && /verified|Verified/i.test(dt), `${label}: evidence drawer opened from ${nm}`);
    if (drawers === 1) await shot('drawer');
    await p.keyboard.press('Escape'); await p.waitForTimeout(150); await p.keyboard.press('Escape'); await p.waitForTimeout(200);
    if (nm.startsWith('Saronic')) await shot('profile-saronic');
  }
  await p.fill('#q', 'Millerbernd'); await p.waitForTimeout(400);
  const pb = p.locator('#calllist button[data-plant]').first(); await pb.click(); await p.waitForTimeout(400);
  check(/Existing Path account/.test(await text('#profile')), `${label}: poles plant profile opens`);
  await p.keyboard.press('Escape'); await p.fill('#q', ''); await p.waitForTimeout(300);

  // ceiling / unknowns banner on a Low ships plant
  await p.locator('#v-calls select[data-f="vert"]').selectOption(SV);
  await p.locator('#v-calls select[data-f="stier"], #v-calls select[data-f="score"]').first().selectOption('Low').catch(() => {}); await p.waitForTimeout(400);
  const lowBtn = p.locator('#calllist button[data-plant]').first();
  if (await lowBtn.count()) { await lowBtn.click(); await p.waitForTimeout(400); check(/unknown|Unknown|ceiling/.test(await text('#profile')), `${label}: ships profile shows unknowns/ceiling text`); await p.keyboard.press('Escape'); }
  await p.locator('#v-calls select[data-f="vert"]').selectOption('');

  // CSV download
  const [dl] = await Promise.all([p.waitForEvent('download'), p.locator('#csv').click()]);
  const csv = fs.readFileSync(await dl.path(), 'utf8');
  check(csv.split('\n').length > 10 && /account,path_status/.test(csv.split('\n')[0]), `${label}: CSV download (${csv.split('\n').length - 1} lines)`);
  // stated-only toggle
  const st = p.locator('#stated'); if (await st.count()) { await st.check(); await p.waitForTimeout(300); await st.uncheck(); }

  // method: per-vertical sections
  await tab('Method'); await shot('method-top');
  const mt = await text('#v-method');
  const ps = await text('#audit-' + PV), ss = await text('#audit-' + SV);
  const P_ = sumOf(PV), S_ = sumOf(SV);
  check(P_.status === 'done' && S_.status === 'done', `${label}: summary files status done / done`);
  check(['11.8%', '19.4%', '8.2%', '8.9%', '13.8%'].every(x => ps.includes(x)) && ps.includes('done') && ps.includes(String(polesProfiled)), `${label}: poles section shows rounds 11.8/19.4/8.2/8.9, miss 13.8, done, ${polesProfiled} profiled`);
  check(!/29\.4%|7\.3%|Electric Boat|v-shipbuilding/.test(ps), `${label}: poles section has no ships figures`);
  check(ss.includes('7.3%') && ss.includes('29.4%') && ss.includes('6.1%') && ss.includes('done') && ss.includes(String(shipsProfiled)), `${label}: ships section shows round 1 7.3%, miss 29.4%, round 2 6.1%, done, ${shipsProfiled} profiled`);
  check(!/11\.8%|19\.4%|8\.9%|13\.8%|fact-check-v-poles/.test(ss), `${label}: ships section has no poles figures or poles checker files`);
  check(/fact-check-v-shipbuilding-naval|-A|-B|-C/.test(ss) && /v-shipbuilding-naval-A|\bA\b/.test(ss), `${label}: ships per-checker detail present`);
  const shipsPerChecker = await p.locator('#audit-' + SV + ' table tbody tr').count();
  check(shipsPerChecker >= 4, `${label}: ships round table has 3 checkers + total (${shipsPerChecker} rows)`);
  const stale = ['every included plant is profiled', '27.5%', '5/64', 'ledger/audit/summary.json', 'Pole makers rarely'].filter(s => (mt + head + callTxt).includes(s));
  check(stale.length === 0, `${label}: no stale text ${JSON.stringify(stale)}`);
  await shot('method-ships');
  check(errs.length === 0, `${label}: no console errors or runtime requests ${JSON.stringify(errs.slice(0, 3))}`);
  await b.close();
}
(async () => {
  await run('desktop-1440', {viewport: {width: 1440, height: 900}}, true);
  await run('phone-390', {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true}, false);
  await run('dark-1440', {viewport: {width: 1440, height: 900}, colorScheme: 'dark'}, false);
  console.log(fails.length ? 'SMOKE FAILED: ' + fails.length : 'SMOKE PASSED');
  process.exit(fails.length ? 1 : 0);
})();
