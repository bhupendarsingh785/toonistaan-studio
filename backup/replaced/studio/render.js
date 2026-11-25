// Frame-by-frame renderer: node render.js scenes/rampur.html episode.json out/frames
// Scene page must define window.setup(episode, W, H) and window.drawFrame(tSeconds) on a <canvas id="c">.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [scene, epFile, outDir] = process.argv.slice(2);
  const ep = JSON.parse(fs.readFileSync(epFile, 'utf8'));
  const [W, H] = ep.size || [1080, 1920]; const fps = ep.fps || 30; const total = Math.round(ep.duration * fps);
  fs.mkdirSync(outDir, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] }); const p = await b.newPage({ viewport: { width: W, height: H } });
  await p.goto('file://' + path.resolve(scene));
  await p.evaluate(([e, w, h]) => window.setup(e, w, h), [ep, W, H]);
  for (let i = 0; i < total; i++) {
    const data = await p.evaluate(t => { window.drawFrame(t); return document.getElementById('c').toDataURL('image/png'); }, i / fps);
    fs.writeFileSync(path.join(outDir, `f${String(i).padStart(5, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
    if (i % fps === 0) process.stdout.write(`\r🎞️  ${Math.round(100 * i / total)}%`);
  }
  await b.close(); console.log(`\r✅ ${total} frames -> ${outDir}`);
})();
