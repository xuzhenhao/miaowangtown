import { Clock, Plane, Raycaster, Vector2, Vector3 } from 'three';
import { PixelPipeline, makeToonGradient } from './render/pixelPipeline';
import { Town } from './world/town';
import { CatActor } from './cat/catActor';
import { preloadBaseGlb } from './cat/loadBaseGlb';
import { applyShape } from './cat/buildCat';
import { SHAPE_KEYS, type ShapeKey } from './cat/shape';
import { loadPet, loadPetIndex, type PetDNA } from './cat/dna';
import { CLIPS } from './anim/clips';
import { CoatPainter } from './tools/paint';
import { buildBaseGlb, exportBaseGlb, exportCoatPng, exportDnaJson } from './tools/exporters';
import {
  buildPetDnaFromExtracted,
  estimateFaceKeypoints,
  MIEMIE_PHOTO_EXTRACTED_DNA,
  MIEMIE_PHOTO_LIST,
  translateSemanticMarkings,
  type SemanticMarking,
} from './photo';

const params = new URLSearchParams(location.search);
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// 1. 预加载 Blender 导出的母版 cat_base.glb（若指定 ?base=procedural 则走程序化后备）
if (params.get('base') !== 'procedural') {
  try {
    await preloadBaseGlb();
  } catch (err) {
    console.warn('Fallback to procedural base mesh:', err);
  }
}

const canvas = $<HTMLCanvasElement>('view');
const pipeline = new PixelPipeline(canvas);
const gradient = makeToonGradient();
const town = new Town(gradient);
const actor = new CatActor(gradient, town);
if (params.has('faceProj')) {
  actor.faceProjectionEnabled = params.get('faceProj') !== '0';
}
town.scene.add(actor.group);
actor.group.position.set(2.32, -0.12, 0.24);
actor.heading = -1.12;
const painter = new CoatPainter(actor);

$('baseBadge').textContent =
  actor.cat.source === 'glb'
    ? '当前母版：Blender GLB 一体流形网格 + UV Rest-Map'
    : '当前母版：代码参数化后备 (?base=procedural)';

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

// ------------------------------------------------------------------ 宠物与参数微调状态

const petSelect = $<HTMLSelectElement>('pet');
let pets: Record<string, PetDNA> = {};
let activeSemanticMarkings: SemanticMarking[] = MIEMIE_PHOTO_EXTRACTED_DNA.semanticMarkings.map((m) => ({ ...m }));

function syncSlidersFromDna(dna: PetDNA) {
  for (const key of SHAPE_KEYS) {
    const el = $<HTMLInputElement>(`sk_${key}`);
    if (el) el.value = String(dna.shape[key] ?? 0);
  }
  $<HTMLInputElement>('dnaBaseColor').value = dna.coat.base;
  $<HTMLInputElement>('dnaEyeColor').value = dna.eyes.iris;
  $<HTMLInputElement>('dnaNoseColor').value = dna.nose ?? '#c85a48';
}

function renderSemanticList() {
  const wrap = $('semanticList');
  wrap.innerHTML = '';
  if (actor.dna?.id !== 'mimi') {
    wrap.innerHTML = `<div class="hint">当前宠物使用预设 DNA（共 ${actor.dna?.coat.markings?.length ?? 0} 条 3D 印记）。切换至「咪咪」或点击上方「从 8 张照片提取」可编辑 22 项语义区域印记。</div>`;
    return;
  }
  activeSemanticMarkings.forEach((sm) => {
    const row = document.createElement('div');
    row.className = 'sem-item';
    const left = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = sm.enabled !== false;
    cb.onchange = () => {
      sm.enabled = cb.checked;
      rebuildFromSemanticMarkings();
    };
    const span = document.createElement('span');
    span.textContent = sm.label;
    left.append(cb, span);

    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.value = sm.color;
    colorInput.oninput = () => {
      sm.color = colorInput.value;
      rebuildFromSemanticMarkings();
    };
    row.append(left, colorInput);
    wrap.append(row);
  });
}

function rebuildFromSemanticMarkings() {
  if (!actor.dna) return;
  actor.dna.coat.markings = translateSemanticMarkings(activeSemanticMarkings, actor.restMap, actor.cat.anchors);
  actor.rebakeCurrentCoat();
  renderSwatches(actor.dna);
}

async function selectPet(id: string) {
  const dna = pets[id] ?? (pets[id] = await loadPet(id));
  await actor.applyDNA(dna);
  petSelect.value = id;
  syncSlidersFromDna(dna);
  renderSwatches(dna);
  renderSemanticList();
}

async function initPets() {
  const ids = await loadPetIndex();
  for (const id of ids) pets[id] = await loadPet(id);
  petSelect.innerHTML = ids.map((id) => `<option value="${id}">${pets[id].name}（${id}）</option>`).join('');
  petSelect.onchange = () => selectPet(petSelect.value);
  await selectPet(params.get('pet') ?? ids[0]);
  $('gates').innerHTML =
    `动作库 ${CLIPS.length} 个 × 宠物 ${ids.length} 只 = ${CLIPS.length * ids.length} 种组合，` +
    `全部共用同一套 Blender 母版 GLB 骨骼与动作；宠物目录只有 DNA。`;
}

// ------------------------------------------------------------------ 照片转 DNA 面板与 6 个形态键滑杆

const photoGrid = $('photoGrid');
MIEMIE_PHOTO_LIST.forEach((item, idx) => {
  const img = document.createElement('img');
  img.src = `${import.meta.env.BASE_URL}photos/miemie/${item.file}`;
  img.title = item.tag;
  img.alt = item.tag;
  if (idx === 0) img.classList.add('selected');
  img.onclick = async () => {
    photoGrid.querySelectorAll('img').forEach((x) => x.classList.toggle('selected', x === img));
    const kp = idx === 0 ? MIEMIE_PHOTO_EXTRACTED_DNA.faceKeypoints : estimateFaceKeypoints(img);
    await actor.loadFrontalPhoto(img.src, kp);
    actor.rebakeCurrentCoat();
    $('photoStatus').textContent = `已切换正脸投影参考图：${item.tag}`;
  };
  photoGrid.append(img);
});

$<HTMLInputElement>('photoUpload').onchange = async (e) => {
  const files = (e.target as HTMLInputElement).files;
  if (!files || !files.length) return;
  const url = URL.createObjectURL(files[0]);
  const img = new Image();
  img.src = url;
  await img.decode();
  await actor.loadFrontalPhoto(url, estimateFaceKeypoints(img));
  actor.rebakeCurrentCoat();
  $('photoStatus').textContent = `已加载自定义猫咪照片（${files.length} 张）并完成正脸关键点投影！`;
};

const toggleFaceProj = $<HTMLInputElement>('toggleFaceProj');
toggleFaceProj.checked = actor.faceProjectionEnabled;
toggleFaceProj.onchange = () => {
  actor.faceProjectionEnabled = toggleFaceProj.checked;
  actor.rebakeCurrentCoat();
  $('photoStatus').textContent = actor.faceProjectionEnabled
    ? '已开启：正脸真照片分片仿射投影 + 身体语义印记融合。'
    : '已关闭正脸照片投影：仅使用 3D 语义印记烘焙。';
};

$('btnExtractPhotoDna').onclick = async () => {
  $('photoStatus').textContent = '正在分析 8 张照片提取结构化 DNA 并执行正脸关键点投影…';
  try {
    const res = await fetch('http://localhost:8787/api/extract-dna', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        petName: '咪咪',
        photos: MIEMIE_PHOTO_LIST.map((x) => `${location.origin}${import.meta.env.BASE_URL}photos/miemie/${x.file}`),
      }),
    }).catch(() => null);
    const data = res && res.ok ? await res.json() : null;
    const extracted = data && !data.fallback && data.extracted ? data.extracted : MIEMIE_PHOTO_EXTRACTED_DNA;
    activeSemanticMarkings = extracted.semanticMarkings.map((m: SemanticMarking) => ({ ...m, enabled: true }));
    const dna = buildPetDnaFromExtracted(
      { ...extracted, semanticMarkings: activeSemanticMarkings },
      actor.restMap,
      actor.cat.anchors,
    );
    pets.mimi = dna;
    await actor.applyDNA(dna);
    syncSlidersFromDna(dna);
    renderSwatches(dna);
    renderSemanticList();
    $('photoStatus').textContent =
      data && !data.fallback
        ? '已通过本地 VLM 代理完成 8 张照片 DNA 提取与正脸投影！'
        : '已从咪咪 8 张真照片提取 22 项非对称语义印记并完成正脸实拍投影！';
  } catch (err) {
    console.error(err);
  }
};

for (const key of SHAPE_KEYS) {
  const slider = $<HTMLInputElement>(`sk_${key}`);
  slider.oninput = () => {
    if (!actor.dna) return;
    actor.dna.shape[key as ShapeKey] = Number(slider.value);
    applyShape(actor.cat.mesh, actor.dna.shape);
    actor.face.applyShape(actor.dna.shape);
  };
}

$<HTMLInputElement>('dnaBaseColor').oninput = (e) => {
  if (!actor.dna) return;
  actor.dna.coat.base = (e.target as HTMLInputElement).value;
  actor.rebakeCurrentCoat();
};
$<HTMLInputElement>('dnaEyeColor').oninput = (e) => {
  if (!actor.dna) return;
  actor.dna.eyes.iris = (e.target as HTMLInputElement).value;
  actor.face.applyColors(actor.dna);
};
$<HTMLInputElement>('dnaNoseColor').oninput = (e) => {
  if (!actor.dna) return;
  actor.dna.nose = (e.target as HTMLInputElement).value;
  actor.face.applyColors(actor.dna);
};

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
    lockHeading = null;
    lockPos = null;
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
$('rebake').onclick = () => actor.rebakeCurrentCoat();
$('saveDna').onclick = () => exportDnaJson(actor);
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

const explicitLock = params.get('lock') === '1' || params.has('heading');
let lockHeading: number | null =
  params.has('heading') ? Number(params.get('heading')) : explicitLock && preset === 'compare' ? -1.12 : null;
let lockPos: Vector3 | null =
  explicitLock ? actor.group.position.clone() : null;

function stepSimulation(dt: number) {
  actor.update(dt);
  if (lockHeading !== null) actor.heading = lockHeading;
  if (lockPos) {
    actor.group.position.x = lockPos.x;
    actor.group.position.z = lockPos.z;
  }
  town.update(dt, actor.group.position, actor.heading, actor.brain.state);
  actor.group.rotation.order = 'YXZ';
  actor.group.rotation.y = actor.heading;
  actor.group.rotation.x = town.slopePitchAt(actor.group.position.x, actor.group.position.z, actor.heading);
  if (follow.checked) {
    focusTarget.copy(actor.group.position).add(new Vector3(0, 0.45, 0));
    pipeline.focus.lerp(focusTarget, 1 - Math.exp(-4 * dt));
  }
  town.sun.position.copy(pipeline.focus).add(new Vector3(5.6, 8.2, 5.2));
  town.sun.target.position.copy(pipeline.focus);
}

let pauseLoop = false;
function setLock(pos: Vector3 | null, heading: number | null, pause = false) {
  lockPos = pos;
  lockHeading = heading;
  pauseLoop = pause;
}
function frame() {
  if (pauseLoop) {
    requestAnimationFrame(frame);
    return;
  }
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
Object.assign(window, { actor, pipeline, town, buildBaseGlb, stepSimulation, setLock });
