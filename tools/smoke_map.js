const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage();const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
await p.goto('file:///home/user/weld/map/index.html');await p.waitForTimeout(1500);
let t=await p.evaluate(()=>document.body.innerText);try{await p.getByRole('tab',{name:/Method/i}).first().click({timeout:3000})}catch(e){try{await p.getByText(/^Method/).first().click({timeout:3000})}catch(e2){console.log('no method tab')}};await p.waitForTimeout(800);t+=await p.evaluate(()=>document.body.innerText);
console.log('errors',errs.length,errs.slice(0,3));console.log((()=>{const need=['81','8.9%','8.2%','13.8%','35.6%','Round 5','done'];const bad=need.filter(s=>!t.includes(s));const stale=['every included plant is profiled','27.5%','5/64'].filter(s=>t.includes(s));return 'missing:'+JSON.stringify(bad)+' stale:'+JSON.stringify(stale)})());await b.close();})();
