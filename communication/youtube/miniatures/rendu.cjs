const { chromium } = require('playwright'); const fs = require('fs');
(async () => { const b = await chromium.launch(); const d = process.argv[2];
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  for (const f of fs.readdirSync(d).filter((x) => x.endsWith('.html'))) {
    await p.goto('file://' + d + '/' + f); await p.waitForTimeout(400);
    const deborde = await p.evaluate(() => { const h = document.querySelector('h1').getBoundingClientRect(); const c = document.querySelector('.capture').getBoundingClientRect(); return [Math.round(h.bottom), Math.round(h.right), Math.round(c.left)]; });
    console.log(f, 'h1 bas/droite', deborde.slice(0, 2), 'capture gauche', deborde[2]);
    await p.screenshot({ path: `${d}/vorelik-miniature-${f.replace('.html', '')}.jpg`, type: 'jpeg', quality: 92 });
  }
  await b.close(); })();
