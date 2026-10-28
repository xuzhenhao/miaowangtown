import { chromium } from '/workspace/cattown/node_modules/playwright/index.mjs';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const PORT = 5462;
const OUT = '/workspace/miaowangtown/docs/validation/innerscene_miemie_v2';
const PUB = '/workspace/miaowangtown/prototype/public/base';
const BACKUP = path.join(OUT, 'smoke_backup');
const V1 = '/workspace/miaowangtown/docs/validation/innerscene_miemie_v1';

function sha(p) {
  return createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

fs.mkdirSync(BACKUP, { recursive: true });
const prodBefore = {
  glb: sha(path.join(PUB, 'cat_base.glb')),
  bones: sha(path.join(PUB, 'bones.json')),
  assets: sha('/workspace/miaowangtown/assets/cat_base.glb'),
};
fs.writeFileSync(path.join(OUT, 'prod_sha_before.json'), JSON.stringify(prodBefore, null, 2));
fs.copyFileSync(path.join(PUB, 'cat_base.glb'), path.join(BACKUP, 'cat_base.glb'));
fs.copyFileSync(path.join(PUB, 'bones.json'), path.join(BACKUP, 'bones.json'));
if (fs.existsSync('/workspace/miaowangtown/prototype/public/pets/mimi.json')) {
  fs.copyFileSync('/workspace/miaowangtown/prototype/public/pets/mimi.json', path.join(BACKUP, 'mimi.json'));
}

// swap
fs.copyFileSync(path.join(OUT, 'cat_base.glb'), path.join(PUB, 'cat_base.glb'));
fs.copyFileSync(path.join(OUT, 'bones.json'), path.join(PUB, 'bones.json'));
console.log('SWAPPED public/base <- v2');

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
  if (/error|Error|fail|印记|提取|anchor|face/i.test(t)) console.log('CONSOLE', msg.type(), t.slice(0, 260));
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
      markings: a.dna?.coat?.markings?.length || 0,
      anchors: a.face?.anchors ? {
        eyeL: a.face.anchors.eyeL?.pos,
        eyeR: a.face.anchors.eyeR?.pos,
        mouth: a.face.anchors.mouth?.pos,
      } : null,
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

async function applyPhotoDnaAndBoostMuzzle(eye = '#8FB369', nose = '#C85A48') {
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

  // denser yin-yang muzzle: boost caramel on cat-right (-X), keep left shallow
  const boostInfo = await page.evaluate(({ eye, nose }) => {
    if (!window.actor?.dna) return { ok: false };
    window.actor.dna.eyes.iris = eye;
    window.actor.dna.nose = nose;
    window.actor.face.applyColors(window.actor.dna);

    const mouth = window.actor.face?.anchors?.mouth?.pos || [0, 0.68, 0.66];
    const eyeL = window.actor.face?.anchors?.eyeL?.pos || [0.08, 0.77, 0.62];
    const boxes = window.actor.restMap?.partBoxes || [];
    const muzzleBox = boxes.find((b) => b.name === 'muzzle');
    const muzzleMaxZ = muzzleBox ? muzzleBox.max.z : mouth[2];

    const denser = [
      // large caramel pad on cat-right muzzle (-X)
      {
        type: 'blob', color: '#c68b59',
        center: [-0.055, mouth[1] + 0.01, muzzleMaxZ - 0.015],
        radius: [0.095, 0.072, 0.095],
        maxX: -0.002, minY: mouth[1] - 0.055, noise: 0.05,
        parts: ['muzzle', 'head'],
      },
      // caramel up toward nose bridge (right)
      {
        type: 'blob', color: '#b87948',
        center: [-0.028, mouth[1] + 0.055, muzzleMaxZ - 0.02],
        radius: [0.048, 0.05, 0.08],
        maxX: 0.004, minY: mouth[1] + 0.01,
        parts: ['muzzle', 'head'],
      },
      // deeper caramel cheek edge
      {
        type: 'blob', color: '#a86d3e',
        center: [-0.078, mouth[1] - 0.005, muzzleMaxZ - 0.03],
        radius: [0.04, 0.045, 0.07],
        maxX: -0.03,
        parts: ['muzzle', 'head'],
      },
      // whisker dots
      {
        type: 'blob', color: '#4a3325',
        center: [-0.05, mouth[1] - 0.005, muzzleMaxZ],
        radius: [0.012, 0.01, 0.03], parts: ['muzzle'],
      },
      {
        type: 'blob', color: '#4a3325',
        center: [-0.072, mouth[1] - 0.015, muzzleMaxZ - 0.008],
        radius: [0.011, 0.009, 0.03], parts: ['muzzle'],
      },
      // reinforce left blaze white so contrast stays yin-yang
      {
        type: 'blob', color: '#f6f3ec',
        center: [0.022, eyeL[1] + 0.015, muzzleMaxZ - 0.025],
        radius: [0.04, 0.07, 0.08],
        minX: -0.008, parts: ['head', 'muzzle'],
      },
      // left lip shallow apricot only
      {
        type: 'blob', color: '#dca675',
        center: [0.05, mouth[1] - 0.035, muzzleMaxZ - 0.01],
        radius: [0.045, 0.016, 0.06],
        minX: 0.012, minY: mouth[1] - 0.05, maxY: mouth[1] - 0.015,
        parts: ['muzzle'],
      },
    ];
    window.actor.dna.coat.markings = [...(window.actor.dna.coat.markings || []), ...denser];
    window.actor.faceProjectionEnabled = false;
    window.actor.rebakeCurrentCoat();
    return {
      ok: true,
      markings: window.actor.dna.coat.markings.length,
      mouth, eyeL,
      muzzleMaxZ,
      status: document.getElementById('photoStatus')?.textContent || '',
    };
  }, { eye, nose });
  return boostInfo;
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

try {
  const info = await gotoBase({ yaw: 20, pitch: 10, zoom: 3.4, faceProj: 0 });
  console.log('LOADED', JSON.stringify(info));
  const dnaInfo = await applyPhotoDnaAndBoostMuzzle();
  console.log('DNA', JSON.stringify(dnaInfo));
  fs.writeFileSync(path.join(OUT, 'miemie_dna_runtime.json'), JSON.stringify(await page.evaluate(() => window.actor.dna), null, 2));

  // apply miemie shape defaults
  await page.evaluate(() => {
    const shape = { headRound: 0.55, weight: 0.36, earSize: 0.45, tailFluff: 0.38, cheekFluff: 0.62, muzzleSize: 0.52 };
    Object.assign(window.actor.dna.shape, shape);
    const mesh = window.actor.cat.mesh;
    const dict = mesh.morphTargetDictionary || {};
    const inf = mesh.morphTargetInfluences || [];
    for (const [k, v] of Object.entries(shape)) if (dict[k] !== undefined) inf[dict[k]] = v;
    window.actor.face.applyShape(window.actor.dna.shape);
  });

  await shot('idle_front.png', { yaw: 8, pitch: 8, zoom: 3.2, focusY: 0.62, advance: 0.04 });
  await shot('idle_front45.png', { yaw: 35, pitch: 10, zoom: 3.3, focusY: 0.58, advance: 0.04 });
  await shot('idle_side.png', { yaw: 88, pitch: 6, zoom: 3.6, focusY: 0.55, advance: 0.04 });
  await shot('idle_side_left.png', { yaw: -88, pitch: 6, zoom: 3.6, focusY: 0.55, advance: 0.04 });

  // muzzle closeups (face)
  await shot('muzzle_close_front.png', { yaw: 5, pitch: 5, zoom: 1.55, focusY: 0.72, advance: 0.02 });
  await shot('muzzle_close_front45.png', { yaw: 28, pitch: 6, zoom: 1.65, focusY: 0.71, advance: 0.02 });
  await shot('muzzle_close_right.png', { yaw: -40, pitch: 4, zoom: 1.7, focusY: 0.70, advance: 0.02 }); // show caramel (-X is cat right; camera from +X looks at -X side? yaw -40 shows right face)

  await page.evaluate(() => { try { window.actor.play('belly', 0); } catch (e) {} });
  await shot('belly_view.png', { yaw: 25, pitch: 58, zoom: 2.9, focusY: 0.32, advance: 1.0, steps: 48 });

  // walk / sit smoke
  await page.evaluate(() => { try { window.actor.play('idle', 0); } catch (e) {} });
  await shot('smoke_idle.png', { yaw: 35, pitch: 10, zoom: 3.4, focusY: 0.55, advance: 0.3, steps: 20 });
  await page.evaluate(() => { try { window.actor.play('walk', 0); } catch (e) {} });
  await shot('smoke_walk.png', { yaw: 55, pitch: 8, zoom: 3.5, focusY: 0.5, advance: 0.85, steps: 40 });
  await page.evaluate(() => { try { window.actor.play('sit', 0); } catch (e) {} });
  await shot('smoke_sit.png', { yaw: 40, pitch: 12, zoom: 3.3, focusY: 0.45, advance: 1.1, steps: 50 });

  await exportCoatAtlas();

  const meta = await page.evaluate(() => {
    const mesh = window.actor.cat.mesh;
    const face = window.actor.face;
    return {
      source: window.actor.cat.source,
      verts: mesh.geometry.attributes.position.count,
      markings: window.actor.dna.coat.markings.length,
      eyes: window.actor.dna.eyes,
      nose: window.actor.dna.nose,
      shape: window.actor.dna.shape,
      faceAnchors: face?.anchors ? {
        eyeL: { pos: [...(face.anchors.eyeL?.pos || [])], vertexIndex: face.anchors.eyeL?.vertexIndex },
        eyeR: { pos: [...(face.anchors.eyeR?.pos || [])], vertexIndex: face.anchors.eyeR?.vertexIndex },
        mouth: { pos: [...(face.anchors.mouth?.pos || [])], vertexIndex: face.anchors.mouth?.vertexIndex },
      } : null,
      eyeMeshPos: face?.eyes?.[0] ? {
        L: face.eyes[0].position.toArray(),
        R: face.eyes[1]?.position?.toArray?.(),
        mouth: face.mouth?.position?.toArray?.(),
      } : null,
      partBoxes: (window.actor.restMap?.partBoxes || []).map((b) => ({
        name: b.name,
        min: [+b.min.x.toFixed(3), +b.min.y.toFixed(3), +b.min.z.toFixed(3)],
        max: [+b.max.x.toFixed(3), +b.max.y.toFixed(3), +b.max.z.toFixed(3)],
      })),
    };
  });
  fs.writeFileSync(path.join(OUT, 'capture_meta.json'), JSON.stringify(meta, null, 2));
  console.log('META', JSON.stringify({ markings: meta.markings, anchors: meta.faceAnchors, eyeMeshPos: meta.eyeMeshPos }));
} finally {
  await browser.close().catch(() => {});
  vite.kill('SIGKILL');
  // restore production
  fs.copyFileSync(path.join(BACKUP, 'cat_base.glb'), path.join(PUB, 'cat_base.glb'));
  fs.copyFileSync(path.join(BACKUP, 'bones.json'), path.join(PUB, 'bones.json'));
  const prodAfter = {
    glb: sha(path.join(PUB, 'cat_base.glb')),
    bones: sha(path.join(PUB, 'bones.json')),
    assets: sha('/workspace/miaowangtown/assets/cat_base.glb'),
  };
  fs.writeFileSync(path.join(OUT, 'prod_sha_after.json'), JSON.stringify({ before: prodBefore, after: prodAfter, match: prodBefore.glb === prodAfter.glb && prodBefore.bones === prodAfter.bones }, null, 2));
  console.log('RESTORED production', prodBefore.glb === prodAfter.glb && prodBefore.bones === prodAfter.bones);
}
console.log('DONE capture');
