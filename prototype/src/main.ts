import { Clock, Plane, Raycaster, Vector2, Vector3 } from 'three';
import { PixelPipeline, makeToonGradient } from './render/pixelPipeline';
import { Town } from './world/town';
import { CatActor } from './cat/catActor';
import { loadPet, loadPetIndex, type PetDNA } from './cat/dna';
import { bakeCoat } from './cat/coatBaker';
import { CLIPS } from './anim/clips';
import { CoatPainter } from './tools/paint';
import { exportBaseGlb, exportCoatPng } from './tools/exporters';

const params = new URLSearchParams(location.search);
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const canvas = $<HTMLCanvasElement>('view');
const pipeline = new PixelPipeline(canvas);
const gradient = makeToonGradient();
const town = new Town(gradient);
const actor = new CatActor(gradient, town);
town.scene.add(actor.group);
actor.group.position.set(0, 0, 0.4);
const painter = new CoatPainter(actor);

pipeline.pixelScale = Number(params.get('scale') ?? 3);
pipeline.viewHeight = Number(params.get('zoom') ?? 5.2);
pipeline.yawDeg = Number(params.get('yaw') ?? 0);
pipeline.pitchDeg = Number(params.get('pitch') ?? 32);
pipeline.resize();
if (params.get('ui') === '0') $('panel').classList.add('hidden');
if (params.has('heading')) actor.heading = Number(params.get('heading'));

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
if (params.get('action')) {
  actor.brain.force(params.get('action')!, true);
  const idx = CLIPS.findIndex((c) => c.name === params.get('action'));
  markAction(actionsRow.querySelectorAll('button')[idx + 1] as HTMLButtonElement);
}

// ------------------------------------------------------------------ 画风

const scale = $<HTMLInputElement>('scale');
const zoom = $<HTMLInputElement>('zoom');
scale.value = String(pipeline.pixelScale);
zoom.value = String(pipeline.viewHeight);
scale.oninput = () => {
  pipeline.pixelScale = Number(scale.value);
  pipeline.resize();
};
zoom.oninput = () => (pipeline.viewHeight = Number(zoom.value));
$<HTMLInputElement>('outline').onchange = (e) => (pipeline.outline = (e.target as HTMLInputElement).checked);
$<HTMLInputElement>('posterize').onchange = (e) => (pipeline.posterize = (e.target as HTMLInputElement).checked);
const follow = $<HTMLInputElement>('follow');

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
pipeline.focus.copy(actor.group.position).add(new Vector3(0, 0.5, 0));

function frame() {
  const dt = Math.min(clock.getDelta(), 1 / 20);
  actor.update(dt);
  if (follow.checked) {
    focusTarget.copy(actor.group.position).add(new Vector3(0, 0.5, 0));
    pipeline.focus.lerp(focusTarget, 1 - Math.exp(-3 * dt));
  }
  town.sun.position.copy(pipeline.focus).add(new Vector3(5, 9, 6));
  town.sun.target.position.copy(pipeline.focus);
  pipeline.render(town.scene);
  const d = actor.dna;
  $('status').textContent = d
    ? `${d.name} · 状态：${CLIPS.find((c) => c.name === actor.brain.state)?.label} · 表情：${actor.expression.eyes}/${actor.expression.mouth}`
    : '加载中…';
  requestAnimationFrame(frame);
}

initPets().then(() => requestAnimationFrame(frame));
Object.assign(window, { actor, pipeline, town });
