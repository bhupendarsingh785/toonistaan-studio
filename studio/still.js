// node still.js scene.html episode.json t out.png [W H]
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
(async () => { const [scene, epf, t, out, w, h] = process.argv.slice(2); const ep = JSON.parse(fs.readFileSync(epf));
  const W = +(w || 540), H = +(h || 960);
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: W, height: H } }); p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto('file://' + path.resolve(scene));
  const d = await p.evaluate(([e, w, h, t]) => { setup(e, w, h); drawFrame(t); return document.getElementById('c').toDataURL('image/png'); }, [ep, W, H, +t]);
  fs.writeFileSync(out, Buffer.from(d.split(',')[1], 'base64')); await b.close(); console.log('ok', out); })();
