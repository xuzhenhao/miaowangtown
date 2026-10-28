import { chromium } from '/workspace/cattown/node_modules/playwright/index.mjs';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const PORT = 5456;
const OUT = '/workspace/miaowangtown/docs/validation/innerscene_miemie_v1';
const vite = spawn('npx', ['vite', '--port', String(PORT), '--strictPort', '--host', '127.0.0.1'], {
  cwd: '/workspace/miaowangtown/prototype',
  stdio: ['ignore', 'pipe', 'pipe'],
});
let viteLog = '';
vite.stderr.on('data', (d) => { viteLog += d; });
vite.stdout.on('data', (d) => { viteLog += d; });
await new Promise((resolve, reject) => {
  const t = setTimeout(() => reject(new Error('vite timeout\n' + viteLog.slice(-800))), 60000);
  const on = (d) => { if (String(d).includes(String(PORT))) { clearTimeout(t); resolve(); } };
  vite.stdout.on('data', on); vite.stderr.on('data', on);
});

const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 })).newPage();
page.on('console', (msg) => {
  const t = msg.text();
  if (/error|Error|fail|印记|提取|source/i.test(t)) console.log('CONSOLE', msg.type(), t.slice(0, 240));
});
page.on('pageerror', (e) => console.log('PAGEERROR', e.message));

async function gotoBase(opts) {
  const { yaw = 20, pitch = 12, zoom = 3.6, action = 'idle', faceProj = 0 } = opts;
  await page.goto(
    `http://127.0.0.1:${PORT}/?pet=mimi&action=${action}&zoom=${zoom}&scale=1&pitch=${pitch}&yaw=${yaw}&heading=0&ui=1&lock=1&faceProj=${faceProj}&hd2d=0&x=0&z=0`,
    { waitUntil: 'networkidle', timeout: 90000 },
  );
  return page.waitForFunction(() => {
    const a = window.actor;
    if (!a?.dna || !a?.cat) return null;
    return {
      source: a.cat.source,
      verts: a.cat.mesh?.geometry?.attributes?.position?.count || null,
      morphs: a.cat.mesh?.morphTargetDictionary || null,
      markings: a.dna?.coat?.markings?.length || 0,
    };
  }, null, { timeout: 60000 }).then((h) => h.jsonValue());
}

async function isolateAndRender({ advance = 0.05, steps = 30, pitch, yaw, zoom, focusY = 0.55 }) {
  await page.evaluate(({ advance, steps, pitch, yaw, zoom, focusY }) => {
    const follow = document.getElementById('follow');
    if (follow) follow.checked = false;
    const panel = document.getElementById('panel');
    if (panel) panel.style.visibility = 'hidden';
    const catRoot = window.actor.group;
    window.town.scene.traverse((obj) => {
      let p = obj, under = false;
      while (p) { if (p === catRoot) { under = true; break; } p = p.parent; }
      if (under) return;
      if (obj !== window.town.scene && (obj.isMesh || obj.isGroup || obj.isPoints)) obj.visible = false;
    });
    window.town.scene.traverse((obj) => { if (obj.isLight) obj.visible = true; });
    catRoot.traverse((o) => { o.visible = true; });
    if (window.pipeline.renderer?.setClearColor) window.pipeline.renderer.setClearColor(0x3a322c, 1);
    catRoot.position.set(0, 0, 0);
    window.actor.heading = 0;
    window.pipeline.viewHeight = zoom;
    window.pipeline.pitchDeg = pitch;
    window.pipeline.yawDeg = yaw;
    window.pipeline.pixelScale = 1;
    window.pipeline.tiltShift = false;
    window.pipeline.bloom = false;
    window.pipeline.vignette = false;
    window.pipeline.outline = true;
    window.pipeline.focus.set(0, focusY, 0);
    window.pipeline.resize();
    if (window.setLock) window.setLock(catRoot.position.clone(), 0, false);
    for (let i = 0; i < 10; i++) window.stepSimulation(0.02);
    if (advance > 0) for (let i = 0; i < steps; i++) window.stepSimulation(advance / steps);
    window.pipeline.focus.set(0, focusY, 0);
    if (window.setLock) window.setLock(catRoot.position.clone(), window.actor.heading, true);
    window.pipeline.render(window.town.scene);
  }, { advance, steps, pitch, yaw, zoom, focusY });
  await page.waitForTimeout(80);
}

async function applyPhotoDna(eye = '#8FB369', nose = '#C85A48') {
  await page.evaluate(() => {
    const panel = document.getElementById('panel');
    if (panel) { panel.style.display = ''; panel.style.visibility = 'visible'; }
  });
  await page.click('#btnExtractPhotoDna', { force: true, timeout: 15000 });
  await page.waitForFunction(() => {
    const t = document.getElementById('photoStatus')?.textContent || '';
    return /提取|投影|DNA|失败|完成|印记/.test(t);
  }, null, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(500);
  await page.evaluate(({ eye, nose }) => {
    if (!window.actor?.dna) return;
    window.actor.dna.eyes.iris = eye;
    window.actor.dna.nose = nose;
    window.actor.face.applyColors(window.actor.dna);
    // disable face projection for geometry honesty on new Rest base (markings still semantic)
    window.actor.faceProjectionEnabled = false;
    window.actor.rebakeCurrentCoat();
  }, { eye, nose });
  return page.evaluate(() => ({
    name: window.actor.dna?.name,
    markings: window.actor.dna?.coat?.markings?.length,
    eye: window.actor.dna?.eyes?.iris,
    nose: window.actor.dna?.nose,
    shape: window.actor.dna?.shape,
    status: document.getElementById('photoStatus')?.textContent || '',
  }));
}

async function shot(name, cam) {
  await isolateAndRender(cam);
  await page.locator('#view').screenshot({ path: path.join(OUT, name) });
  console.log('SHOT', name);
}

async function exportCoatAtlas() {
  const dataUrl = await page.evaluate(() => window.actor?.coatCanvas?.toDataURL('image/png') || null);
  if (!dataUrl) { console.log('NO_COAT_CANVAS'); return; }
  fs.writeFileSync(path.join(OUT, 'coat_atlas_512.png'), Buffer.from(dataUrl.replace(/^data:image\/png;base64,/, ''), 'base64'));
  console.log('COAT_ATLAS ok');
}

async function setShape(partial) {
  await page.evaluate((partial) => {
    const dna = window.actor.dna;
    const mesh = window.actor.cat.mesh;
    Object.assign(dna.shape, partial);
    const dict = mesh.morphTargetDictionary;
    const inf = mesh.morphTargetInfluences;
    for (const [k, v] of Object.entries(partial)) {
      if (dict[k] !== undefined) inf[dict[k]] = v;
    }
    window.actor.face.applyShape(dna.shape);
    window.pipeline.render(window.town.scene);
  }, partial);
}

const info = await gotoBase({ yaw: 20, pitch: 10, zoom: 3.4, faceProj: 0 });
console.log('LOADED', info);
const dnaInfo = await applyPhotoDna();
console.log('DNA', dnaInfo);
fs.writeFileSync(path.join(OUT, 'miemie_dna_runtime.json'), JSON.stringify(await page.evaluate(() => window.actor.dna), null, 2));

await shot('idle_front.png', { yaw: 8, pitch: 8, zoom: 3.2, focusY: 0.62, advance: 0.04 });
await shot('idle_front45.png', { yaw: 35, pitch: 10, zoom: 3.3, focusY: 0.58, advance: 0.04 });
await shot('idle_side.png', { yaw: 88, pitch: 6, zoom: 3.6, focusY: 0.55, advance: 0.04 });
await shot('idle_side_left.png', { yaw: -88, pitch: 6, zoom: 3.6, focusY: 0.55, advance: 0.04 });

await page.evaluate(() => { try { window.actor.play('belly', 0); } catch (e) {} });
await shot('belly_view.png', { yaw: 25, pitch: 58, zoom: 2.9, focusY: 0.32, advance: 1.0, steps: 48 });

await page.evaluate(() => { try { window.actor.play('idle', 0); } catch (e) {} });
await isolateAndRender({ yaw: 28, pitch: 10, zoom: 3.3, focusY: 0.6, advance: 0.04 });

for (const { key, values } of [
  { key: 'headRound', values: [0.0, 0.55, 1.0] },
  { key: 'weight', values: [0.0, 0.36, 1.0] },
  { key: 'earSize', values: [0.0, 0.45, 1.0] },
]) {
  for (const v of values) {
    await setShape({
      headRound: 0.55, weight: 0.36, earSize: 0.45,
      tailFluff: 0.38, cheekFluff: 0.62, muzzleSize: 0.52,
      [key]: v,
    });
    await page.waitForTimeout(40);
    const fname = `dna_${key}_${String(v).replace('.', 'p')}.png`;
    await page.locator('#view').screenshot({ path: path.join(OUT, fname) });
    console.log('DNA_SHOT', fname);
  }
}

await exportCoatAtlas();
const meta = await page.evaluate(() => {
  const mesh = window.actor.cat.mesh;
  const inf = mesh.morphTargetInfluences || [];
  const dict = mesh.morphTargetDictionary || {};
  return {
    source: window.actor.cat.source,
    verts: mesh.geometry.attributes.position.count,
    markings: window.actor.dna.coat.markings.length,
    eyes: window.actor.dna.eyes,
    nose: window.actor.dna.nose,
    shape: window.actor.dna.shape,
    morphDict: dict,
    partBoxes: (window.actor.restMap?.partBoxes || []).map((b) => ({
      name: b.name,
      min: [+b.min.x.toFixed(3), +b.min.y.toFixed(3), +b.min.z.toFixed(3)],
      max: [+b.max.x.toFixed(3), +b.max.y.toFixed(3), +b.max.z.toFixed(3)],
    })),
  };
});
fs.writeFileSync(path.join(OUT, 'capture_meta.json'), JSON.stringify(meta, null, 2));
console.log('META markings', meta.markings, 'eye', meta.eyes, 'nose', meta.nose);

await browser.close();
vite.kill('SIGKILL');
console.log('DONE');
