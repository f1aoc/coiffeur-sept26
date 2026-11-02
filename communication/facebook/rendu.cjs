const { chromium } = require('playwright'); const fs = require('fs');
(async () => { const b = await chromium.launch(); const d = process.argv[2];
  for (const f of fs.readdirSync(d).filter((x) => x.endsWith('.html'))) {
    const [l, h] = fs.readFileSync(d + '/' + f, 'utf8').match(/data-taille="(\d+)x(\d+)"/).slice(1).map(Number);
    const p = await b.newPage({ viewport: { width: l, height: h } });
    await p.goto('file://' + d + '/' + f); await p.waitForTimeout(400);
    const debord = await p.evaluate(() => { const r = []; for (const e of document.querySelectorAll('h1, .sous, .zone, .bas')) { const b = e.getBoundingClientRect(); if (b.right > innerWidth + 1 || b.bottom > innerHeight + 1) r.push(e.className || e.tagName); } return r; });
    if (debord.length) console.log('DEBORDE', f, debord);
    await p.screenshot({ path: `${d}/${f.replace('.html', '')}.png` }); await p.close();
  }
  await b.close(); })();
