import { Clock, Plane, Raycaster, Vector2, Vector3 } from 'three';
import { PixelPipeline, makeToonGradient } from './render/pixelPipeline';
import { Town } from './world/town';
import { CatActor } from './cat/catActor';
import { loadPet, loadPetIndex, type PetDNA } from './cat/dna';
import { bakeCoat } from './cat/coatBaker';
import { CLIPS } from './anim/clips';
import { CoatPainter } from './tools/paint';
import { buildBaseGlb, exportBaseGlb, exportCoatPng } from './tools/exporters';

const params = new URLSearchParams(location.search);
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const canvas = $<HTMLCanvasElement>('view');
const pipeline = new PixelPipeline(canvas);
const gradient = makeToonGradient();
const town = new Town(gradient);
const actor = new CatActor(gradient, town);
town.scene.add(actor.group);
actor.group.position.set(2.32, -0.12, 0.24);
actor.heading = -1.12;
const painter = new CoatPainter(actor);

// 预设镜头配置（默认对标左图客栈门前下桥石阶机位 compare）
const preset = params.get('preset') ?? (params.has('zoom') ? null : 'compare');
if (preset === 'compare') {
  pipeline.viewHeight = 2.85;
  pipeline.pitchDeg = 30;
  pipeline.yawDeg = -14;
  pipeline.pixelScale = 3;
  actor.group.position.set(2.32, -0.12, 0.24);
  actor.heading = -1.12;
} else if (preset === 'town') {
  pipeline.viewHeight = 6.6;
  pipeline.pitchDeg = 30;
  pipeline.yawDeg = -16;
  pipeline.pixelScale = 2;
  actor.group.position.set(0, 0, 0.35);
} else if (preset === 'bridge') {
  pipeline.viewHeight = 4.0;
  pipeline.pitchDeg = 28;
  pipeline.yawDeg = -12;
  pipeline.pixelScale = 3;
  actor.group.position.set(0, 0, 0.35);
} else if (preset === 'closeup') {
  pipeline.viewHeight = 2.5;
  pipeline.pitchDeg = 24;
  pipeline.yawDeg = 0;
  pipeline.pixelScale = 3;
  actor.group.position.set(2.32, -0.12, 0.24);
  actor.heading = 0;
} else if (preset === 'belly') {
  pipeline.viewHeight = 2.5;
  pipeline.pitchDeg = 34;
  pipeline.yawDeg = 0;
  pipeline.pixelScale = 3;
  actor.group.position.set(2.32, -0.12, 0.24);
  actor.heading = 0;
} else {
  pipeline.viewHeight = 4.0;
  pipeline.pitchDeg = 28;
  pipeline.yawDeg = -12;
  pipeline.pixelScale = 3;
  actor.group.position.set(0, 0, 0.35);
}

if (params.has('scale')) pipeline.pixelScale = Number(params.get('scale'));
if (params.has('zoom')) pipeline.viewHeight = Number(params.get('zoom'));
if (params.has('pitch')) pipeline.pitchDeg = Number(params.get('pitch'));
if (params.has('yaw')) {
  pipeline.yawDeg = Number(params.get('yaw'));
} else if (!preset && pipeline.viewHeight <= 3.0) {
  pipeline.yawDeg = 0;
  actor.group.position.set(0, 0, 0.35);
}
if (params.get('hd2d') === '0') {
  pipeline.tiltShift = false;
  pipeline.bloom = false;
  pipeline.vignette = false;
}
if (params.has('tiltShift')) pipeline.tiltShift = params.get('tiltShift') !== '0';
if (params.has('bloom')) pipeline.bloom = params.get('bloom') !== '0';
if (params.has('vignette')) pipeline.vignette = params.get('vignette') !== '0';

pipeline.resize();
if (params.get('ui') === '0') $('panel').classList.add('hidden');
if (params.has('heading')) actor.heading = Number(params.get('heading'));
if (params.has('x')) actor.group.position.x = Number(params.get('x'));
if (params.has('z')) actor.group.position.z = Number(params.get('z'));
town.update(0, actor.group.position, actor.heading, actor.brain.state);

// ------------------------------------------------------------------ 宠物

const petSelect = $<HTMLSelectElement>('pet');
let pets: Record<string, PetDNA> = {};

async function selectPet(id: string) {
  const dna = pets[id] ?? (pets[id] = await loadPet(id));
  await actor.applyDNA(dna);
  petSelect.value = id;
  renderSwatches(dna);
}

async function initPets() {
  const ids = await loadPetIndex();
  for (const id of ids) pets[id] = await loadPet(id);
  petSelect.innerHTML = ids.map((id) => `<option value="${id}">${pets[id].name}（${id}）</option>`).join('');
  petSelect.onchange = () => selectPet(petSelect.value);
  await selectPet(params.get('pet') ?? ids[0]);
  $('gates').innerHTML =
    `动作库 ${CLIPS.length} 个 × 宠物 ${ids.length} 只 = ${CLIPS.length * ids.length} 种组合，` +
    `全部共用一套骨骼与动作；宠物目录只有 DNA。`;
}

// ------------------------------------------------------------------ 动作

const actionsRow = $('actions');
const autoBtn = document.createElement('button');
autoBtn.textContent = '自动闲逛';
autoBtn.onclick = () => {
  lockHeading = null;
  lockPos = null;
  actor.brain.release();
  markAction(autoBtn);
};
actionsRow.append(autoBtn);
for (const def of CLIPS) {
  const b = document.createElement('button');
  b.textContent = def.label;
  b.onclick = () => {
    actor.brain.force(def.name, true);
    markAction(b);
  };
  actionsRow.append(b);
}
function markAction(btn: HTMLButtonElement) {
  actionsRow.querySelectorAll('button').forEach((x) => x.classList.toggle('active', x === btn));
}
markAction(autoBtn);
const initialAction =
  params.get('action') ??
  (preset === 'compare' ? 'walk' : preset === 'closeup' ? 'sit' : preset === 'belly' ? 'belly' : null);
if (initialAction) {
  actor.brain.force(initialAction, true);
  const idx = CLIPS.findIndex((c) => c.name === initialAction);
  if (idx >= 0) markAction(actionsRow.querySelectorAll('button')[idx + 1] as HTMLButtonElement);
}

// ------------------------------------------------------------------ 画风与 HD-2D 控制

const scale = $<HTMLInputElement>('scale');
const zoom = $<HTMLInputElement>('zoom');
const tiltShiftEl = $<HTMLInputElement>('tiltShift');
const bloomEl = $<HTMLInputElement>('bloom');
const vignetteEl = $<HTMLInputElement>('vignette');
const outlineEl = $<HTMLInputElement>('outline');
const posterizeEl = $<HTMLInputElement>('posterize');
const follow = $<HTMLInputElement>('follow');

scale.value = String(pipeline.pixelScale);
zoom.value = String(pipeline.viewHeight);
tiltShiftEl.checked = pipeline.tiltShift;
bloomEl.checked = pipeline.bloom;
vignetteEl.checked = pipeline.vignette;
outlineEl.checked = pipeline.outline;
posterizeEl.checked = pipeline.posterize;

scale.oninput = () => {
  pipeline.pixelScale = Number(scale.value);
  pipeline.resize();
};
zoom.oninput = () => (pipeline.viewHeight = Number(zoom.value));
tiltShiftEl.onchange = () => (pipeline.tiltShift = tiltShiftEl.checked);
bloomEl.onchange = () => (pipeline.bloom = bloomEl.checked);
vignetteEl.onchange = () => (pipeline.vignette = vignetteEl.checked);
outlineEl.onchange = () => (pipeline.outline = outlineEl.checked);
posterizeEl.onchange = () => (pipeline.posterize = posterizeEl.checked);

const presetButtons = [$('presetCompare'), $('presetBridge'), $('presetCloseup'), $('presetTown')];
function applyPreset(name: 'compare' | 'bridge' | 'closeup' | 'town', btn: HTMLElement) {
  presetButtons.forEach((b) => b.classList.toggle('active', b === btn));
  if (name === 'compare') {
    pipeline.viewHeight = 2.85;
    pipeline.pitchDeg = 30;
    pipeline.yawDeg = -14;
    pipeline.pixelScale = 3;
    actor.group.position.set(2.32, -0.12, 0.24);
    actor.heading = -1.12;
    lockHeading = -1.12;
    lockPos = actor.group.position.clone();
    actor.brain.force('walk', true);
    const idx = CLIPS.findIndex((c) => c.name === 'walk');
    if (idx >= 0) markAction(actionsRow.querySelectorAll('button')[idx + 1] as HTMLButtonElement);
  } else if (name === 'bridge') {
    pipeline.viewHeight = 4.0;
    pipeline.pitchDeg = 28;
    pipeline.yawDeg = -12;
    pipeline.pixelScale = 3;
    actor.group.position.set(0, 0, 0.35);
    actor.heading = -0.55;
    lockHeading = null;
    lockPos = null;
    actor.brain.release();
    markAction(autoBtn);
  } else if (name === 'closeup') {
    pipeline.viewHeight = 2.5;
    pipeline.pitchDeg = 24;
    pipeline.yawDeg = 0;
    pipeline.pixelScale = 3;
    actor.group.position.set(2.32, -0.12, 0.24);
    actor.heading = 0;
    lockHeading = 0;
    lockPos = actor.group.position.clone();
    actor.brain.force('sit', true);
    const idx = CLIPS.findIndex((c) => c.name === 'sit');
    if (idx >= 0) markAction(actionsRow.querySelectorAll('button')[idx + 1] as HTMLButtonElement);
  } else {
    pipeline.viewHeight = 6.6;
    pipeline.pitchDeg = 30;
    pipeline.yawDeg = -16;
    pipeline.pixelScale = 2;
    actor.group.position.set(0, 0, 0.35);
    lockHeading = null;
    lockPos = null;
    actor.brain.release();
    markAction(autoBtn);
  }
  scale.value = String(pipeline.pixelScale);
  zoom.value = String(pipeline.viewHeight);
  pipeline.resize();
  pipeline.focus.copy(actor.group.position).add(new Vector3(0, 0.45, 0));
}
$('presetCompare').onclick = () => applyPreset('compare', $('presetCompare'));
$('presetBridge').onclick = () => applyPreset('bridge', $('presetBridge'));
$('presetCloseup').onclick = () => applyPreset('closeup', $('presetCloseup'));
$('presetTown').onclick = () => applyPreset('town', $('presetTown'));

// ------------------------------------------------------------------ 印记

let painting = false;
const paintBtn = $('paint');
paintBtn.onclick = () => {
  painting = !painting;
  paintBtn.classList.toggle('active', painting);
  canvas.classList.toggle('painting', painting);
};
$<HTMLInputElement>('brush').oninput = (e) => (painter.brush = Number((e.target as HTMLInputElement).value));
$<HTMLInputElement>('color').oninput = (e) => (painter.color = (e.target as HTMLInputElement).value);
$('rebake').onclick = () => {
  if (!actor.dna) return;
  bakeCoat(actor.dna, actor.coatCanvas);
  actor.coatTexture.needsUpdate = true;
};
$('savePng').onclick = () => exportCoatPng(actor);
$('saveGlb').onclick = () => exportBaseGlb(actor);
actor.coatCanvas.id = 'coat';
$('coatWrap').append(actor.coatCanvas);

function renderSwatches(dna: PetDNA) {
  const wrap = $('swatches');
  const colors = [...new Set([dna.coat.base, ...(dna.coat.palette ?? []), ...(dna.coat.markings ?? []).map((m) => m.color)])];
  wrap.innerHTML = '';
  for (const c of colors) {
    const s = document.createElement('span');
    s.style.background = c;
    s.onclick = () => {
      painter.color = c;
      $<HTMLInputElement>('color').value = c;
      wrap.querySelectorAll('span').forEach((x) => x.classList.toggle('active', x === s));
    };
    wrap.append(s);
  }
}

// ------------------------------------------------------------------ 交互

const ndc = new Vector2();
const ray = new Raycaster();
const lookPlane = new Plane(new Vector3(0, 1, 0), -0.6);
let pointerDown = false;

canvas.addEventListener('pointermove', (e) => {
  pipeline.screenToNdc(e.clientX, e.clientY, ndc);
  ray.setFromCamera(ndc, pipeline.camera);
  const hit = new Vector3();
  if (ray.ray.intersectPlane(lookPlane, hit)) actor.lookTarget = hit;
  if (painting && pointerDown) painter.paintAt(ndc, pipeline.camera);
});
canvas.addEventListener('pointerdown', (e) => {
  pointerDown = true;
  pipeline.screenToNdc(e.clientX, e.clientY, ndc);
  if (painting) painter.paintAt(ndc, pipeline.camera);
  else if (painter.pick(ndc, pipeline.camera)) actor.procedural.pet();
});
window.addEventListener('pointerup', () => (pointerDown = false));
canvas.addEventListener('pointerleave', () => (actor.lookTarget = null));
window.addEventListener('resize', () => pipeline.resize());

// ------------------------------------------------------------------ 主循环

const clock = new Clock();
const focusTarget = new Vector3();
pipeline.focus.copy(actor.group.position).add(new Vector3(0, 0.45, 0));

let lockHeading: number | null =
  params.has('heading') ? Number(params.get('heading')) : preset === 'compare' ? -1.12 : null;
let lockPos: Vector3 | null =
  lockHeading !== null && (initialAction === 'walk' || preset === 'compare') ? actor.group.position.clone() : null;

function stepSimulation(dt: number) {
  actor.update(dt);
  if (lockHeading !== null) actor.heading = lockHeading;
  if (lockPos) {
    actor.group.position.x = lockPos.x;
    actor.group.position.z = lockPos.z;
    actor.group.rotation.y = actor.heading;
  }
  town.update(dt, actor.group.position, actor.heading, actor.brain.state);
  if (follow.checked) {
    focusTarget.copy(actor.group.position).add(new Vector3(0, 0.45, 0));
    pipeline.focus.lerp(focusTarget, 1 - Math.exp(-4 * dt));
  }
  town.sun.position.copy(pipeline.focus).add(new Vector3(5.6, 8.2, 5.2));
  town.sun.target.position.copy(pipeline.focus);
}

function frame() {
  const dt = Math.min(clock.getDelta(), 1 / 20);
  stepSimulation(dt);
  pipeline.render(town.scene);
  const d = actor.dna;
  $('status').textContent = d
    ? `${d.name} · 状态：${CLIPS.find((c) => c.name === actor.brain.state)?.label} · 表情：${actor.expression.eyes}/${actor.expression.mouth}`
    : '加载中…';
  requestAnimationFrame(frame);
}

initPets().then(() => requestAnimationFrame(frame));
Object.assign(window, { actor, pipeline, town, buildBaseGlb, stepSimulation });
