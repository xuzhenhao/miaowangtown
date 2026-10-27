import { CatmullRomCurve3, Vector3 } from 'three';
import type { ShapeParams } from './shape';

/**
 * 母版猫由参数化部件组成。每个部件把 (s, t) ∈ [0,1]² 映射到静止姿态下的模型空间坐标，
 * 并在印记图集里独占一个矩形区域（UV 不镜像，左右部件各有各的区域）。
 * 坐标系：地面 y=0，猫朝 +Z，猫自身左侧为 +X。
 */

export const ATLAS_SIZE = 512;
const TAU = Math.PI * 2;

export type Weights = Array<[string, number]>;

export interface PartDef {
  name: string;
  /** 图集矩形 [x, y, w, h]，单位像素，y 自上而下 */
  rect: [number, number, number, number];
  /** true 时 t 沿图集横向、s 沿纵向（尾巴这种细长部件） */
  transposeUV?: boolean;
  segS: number;
  segT: number;
  pos(s: number, t: number, k: ShapeParams, out: Vector3): Vector3;
  core(s: number, t: number, k: ShapeParams, out: Vector3): Vector3;
  weights(s: number, t: number, p: Vector3): Weights;
}

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** 沿一维坐标在若干「骨骼满权重点」之间线性混合 */
export function chainWeights(v: number, stops: Array<[string, number]>): Weights {
  if (v <= stops[0][1]) return [[stops[0][0], 1]];
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, va] = stops[i];
    const [b, vb] = stops[i + 1];
    if (v <= vb) {
      const f = (v - va) / (vb - va);
      return [
        [a, 1 - f],
        [b, f],
      ];
    }
  }
  return [[stops[stops.length - 1][0], 1]];
}

// ---------------------------------------------------------------- 头

export const HEAD_CENTER = new Vector3(0, 0.92, 0.55);

export function headPos(s: number, t: number, k: ShapeParams, out: Vector3): Vector3 {
  const th = (s - 0.5) * TAU;
  const ph = t * Math.PI;
  const dx = Math.sin(ph) * Math.sin(th);
  const dy = Math.cos(ph);
  const dz = Math.sin(ph) * Math.cos(th);
  const rx = 0.36 * (1 + 0.1 * k.headRound);
  const ry = 0.32 * (1 - 0.04 * k.headRound);
  const rz = 0.31;
  const cheek =
    (0.05 + 0.13 * k.cheekFluff) * clamp((0.35 - dy) / 0.9, 0, 1) * Math.abs(Math.sin(th)) * Math.sin(ph);
  const face = dz > 0 ? 1 - 0.1 * dz * dz : 1;
  return out.set(HEAD_CENTER.x + dx * rx * (1 + cheek), HEAD_CENTER.y + dy * ry, HEAD_CENTER.z + dz * rz * face);
}

const head: PartDef = {
  name: 'head',
  rect: [0, 0, 256, 128],
  segS: 44,
  segT: 26,
  pos: headPos,
  core: (_s, _t, _k, out) => out.copy(HEAD_CENTER),
  weights: () => [['head', 1]],
};

// ---------------------------------------------------------------- 嘴套

export const MUZZLE_CENTER = new Vector3(0, 0.83, 0.8);

export function muzzlePos(s: number, t: number, k: ShapeParams, out: Vector3): Vector3 {
  const th = (s - 0.5) * TAU;
  const ph = t * Math.PI;
  const dx = Math.sin(ph) * Math.sin(th);
  const dy = Math.cos(ph);
  const dz = Math.sin(ph) * Math.cos(th);
  const m = k.muzzleSize;
  return out.set(
    MUZZLE_CENTER.x + dx * (0.13 + 0.03 * m),
    MUZZLE_CENTER.y + dy * (0.08 + 0.012 * m),
    MUZZLE_CENTER.z + dz * (0.075 + 0.02 * m),
  );
}

const muzzle: PartDef = {
  name: 'muzzle',
  rect: [256, 0, 128, 64],
  segS: 28,
  segT: 14,
  pos: muzzlePos,
  core: (_s, _t, _k, out) => out.copy(MUZZLE_CENTER),
  weights: () => [['head', 1]],
};

// ---------------------------------------------------------------- 脖子

const NECK_A = new Vector3(0, 0.58, 0.26);
const NECK_B = new Vector3(0, 0.86, 0.5);
const NECK_D = NECK_B.clone().sub(NECK_A).normalize();
const NECK_U = new Vector3(1, 0, 0);
const NECK_W = new Vector3().crossVectors(NECK_U, NECK_D).normalize();

const neck: PartDef = {
  name: 'neck',
  rect: [384, 0, 128, 64],
  segS: 20,
  segT: 6,
  pos(s, t, k, out) {
    const th = (s - 0.5) * TAU;
    const r = 0.16 * (1 + 0.12 * k.weight) * (1 + 0.15 * k.cheekFluff * t);
    out.copy(NECK_A).lerp(NECK_B, t);
    return out.addScaledVector(NECK_U, Math.sin(th) * r).addScaledVector(NECK_W, Math.cos(th) * r);
  },
  core: (_s, t, _k, out) => out.copy(NECK_A).lerp(NECK_B, t),
  weights: (_s, t) =>
    chainWeights(t, [
      ['chest', 0.1],
      ['neck', 0.5],
      ['head', 0.9],
    ]),
};

// ---------------------------------------------------------------- 身体

export const BODY_CENTER = new Vector3(0, 0.52, 0);

function bodyPos(s: number, t: number, k: ShapeParams, out: Vector3): Vector3 {
  const ph = t * Math.PI;
  const zc = -Math.cos(ph);
  const r = Math.sin(ph);
  const th = (s - 0.5) * TAU;
  const taper = 1 + 0.06 * zc;
  const rx = 0.29 * (1 + 0.22 * k.weight);
  const ry = 0.27 * (1 + 0.12 * k.weight);
  const X = Math.sin(th) * r * rx * taper;
  let Y = Math.cos(th) * r * ry * taper;
  if (Y < 0) Y *= 1 + 0.35 * k.weight;
  return out.set(X, BODY_CENTER.y + Y, zc * 0.48);
}

const body: PartDef = {
  name: 'body',
  rect: [0, 128, 256, 192],
  segS: 36,
  segT: 28,
  pos: bodyPos,
  core: (_s, t, _k, out) => out.set(0, BODY_CENTER.y, -Math.cos(t * Math.PI) * 0.48 * 0.6),
  weights: (_s, _t, p) =>
    chainWeights(p.z, [
      ['hips', -0.22],
      ['spine', 0.05],
      ['chest', 0.28],
    ]),
};

// ---------------------------------------------------------------- 腿

export interface LegSpec {
  name: string;
  x: number;
  z: number;
  front: boolean;
  bones: [string, string, string, string]; // parent, upper, lower, paw
  rect: [number, number, number, number];
}

const LEG_TOP = 0.52;
export const PAW_Y = 0.075;
const PAW_R = 0.075;

function legRadius(y: number, front: boolean): number {
  const rUpper = front ? 0.085 : 0.1;
  const rLower = 0.064;
  if (y >= 0.3) return rUpper;
  if (y > 0.16) return lerp(rLower, rUpper, (y - 0.16) / 0.14);
  return lerp(PAW_R, rLower, clamp((y - PAW_Y) / (0.16 - PAW_Y), 0, 1));
}

function makeLeg(spec: LegSpec): PartDef {
  const tc = 0.82;
  return {
    name: spec.name,
    rect: spec.rect,
    segS: 14,
    segT: 16,
    pos(s, t, _k, out) {
      const th = (s - 0.5) * TAU;
      let y: number;
      let r: number;
      if (t <= tc) {
        y = lerp(LEG_TOP, PAW_Y, t / tc);
        r = legRadius(y, spec.front);
      } else {
        const a = ((t - tc) / (1 - tc)) * (Math.PI / 2);
        y = PAW_Y - PAW_R * Math.sin(a);
        r = PAW_R * Math.cos(a);
      }
      const pawness = clamp((0.16 - y) / 0.08, 0, 1);
      const zScale = 1 + 0.3 * pawness;
      return out.set(spec.x + Math.sin(th) * r, y, spec.z + 0.02 * pawness + Math.cos(th) * r * zScale);
    },
    core(_s, t, _k, out) {
      const y = t <= tc ? lerp(LEG_TOP, PAW_Y, t / tc) : PAW_Y;
      return out.set(spec.x, y, spec.z);
    },
    weights: (_s, _t, p) =>
      chainWeights(p.y, [
        [spec.bones[3], 0.1],
        [spec.bones[2], 0.22],
        [spec.bones[1], 0.36],
        [spec.bones[0], 0.56],
      ]),
  };
}

export const LEGS: LegSpec[] = [
  { name: 'fLegL', x: 0.16, z: 0.31, front: true, bones: ['chest', 'shoulderL', 'elbowL', 'fpawL'], rect: [256, 64, 64, 96] },
  { name: 'fLegR', x: -0.16, z: 0.31, front: true, bones: ['chest', 'shoulderR', 'elbowR', 'fpawR'], rect: [320, 64, 64, 96] },
  { name: 'hLegL', x: 0.17, z: -0.23, front: false, bones: ['hips', 'hipL', 'kneeL', 'hpawL'], rect: [384, 64, 64, 96] },
  { name: 'hLegR', x: -0.17, z: -0.23, front: false, bones: ['hips', 'hipR', 'kneeR', 'hpawR'], rect: [448, 64, 64, 96] },
];

// ---------------------------------------------------------------- 耳朵

const EAR_THETA = 0.95;
const EAR_PHI = 0.2;

export function earBase(side: 1 | -1, k: ShapeParams, out = new Vector3()): Vector3 {
  return headPos(0.5 + (side * EAR_THETA) / TAU, EAR_PHI, k, out);
}

function makeEar(side: 1 | -1, rect: [number, number, number, number]): PartDef {
  const axis = new Vector3(side * 0.5, 1, 0.08).normalize();
  const f0 = new Vector3(0, 0, 1);
  const front = f0.clone().addScaledVector(axis, -axis.dot(f0)).normalize();
  const sideways = new Vector3().crossVectors(axis, front).normalize();
  const base = new Vector3();
  const boneName = side === 1 ? 'earL' : 'earR';
  return {
    name: side === 1 ? 'earL' : 'earR',
    rect,
    segS: 12,
    segT: 8,
    pos(s, t, k, out) {
      earBase(side, k, base);
      const rb = 0.105 * (1 + 0.25 * k.earSize);
      const h = 0.17 * (1 + 0.45 * k.earSize);
      const th = (s - 0.5) * TAU;
      const r = rb * Math.pow(1 - t, 0.85);
      out.copy(base).addScaledVector(axis, -0.04 + t * (h + 0.04));
      return out.addScaledVector(sideways, Math.sin(th) * r).addScaledVector(front, Math.cos(th) * r * 0.45);
    },
    core(_s, t, k, out) {
      earBase(side, k, out);
      const h = 0.17 * (1 + 0.45 * k.earSize);
      return out.addScaledVector(axis, -0.04 + t * (h + 0.04) - 0.02);
    },
    weights: (_s, t) =>
      chainWeights(t, [
        ['head', 0.05],
        [boneName, 0.35],
      ]),
  };
}

// ---------------------------------------------------------------- 尾巴

const TAIL_CURVE = new CatmullRomCurve3([
  new Vector3(0, 0.56, -0.42),
  new Vector3(0, 0.6, -0.56),
  new Vector3(0, 0.68, -0.68),
  new Vector3(0, 0.8, -0.76),
  new Vector3(0, 0.94, -0.79),
  new Vector3(0, 1.07, -0.77),
  new Vector3(0, 1.17, -0.71),
]);
export const TAIL_BONE_T = [0.04, 0.2, 0.36, 0.52, 0.68, 0.84];

export function tailBonePoints(): Vector3[] {
  return TAIL_BONE_T.map((t) => TAIL_CURVE.getPointAt(t));
}

const tailStops: Array<[string, number]> = [['hips', 0]];
TAIL_BONE_T.forEach((t, i) => {
  const next = TAIL_BONE_T[i + 1] ?? 1;
  tailStops.push([`tail${i}`, (t + next) / 2]);
});

const TAIL_U = new Vector3(1, 0, 0);
const tailTan = new Vector3();
const tailW = new Vector3();

const tail: PartDef = {
  name: 'tail',
  rect: [0, 320, 256, 64],
  transposeUV: true,
  segS: 12,
  segT: 30,
  pos(s, t, k, out) {
    const th = (s - 0.5) * TAU;
    TAIL_CURVE.getPointAt(t, out);
    TAIL_CURVE.getTangentAt(t, tailTan);
    tailW.crossVectors(TAIL_U, tailTan).normalize();
    const f = k.tailFluff;
    let r = (0.05 + 0.03 * f) * (1 + 0.3 * f * Math.sin(Math.PI * t)) * lerp(1, 0.75, t);
    if (t > 0.9) r *= Math.sqrt(Math.max(0, 1 - ((t - 0.9) / 0.1) ** 2));
    return out.addScaledVector(TAIL_U, Math.sin(th) * r).addScaledVector(tailW, Math.cos(th) * r);
  },
  core: (_s, t, _k, out) => TAIL_CURVE.getPointAt(Math.min(t, 0.97), out),
  weights: (_s, t) => chainWeights(t, tailStops),
};

// ----------------------------------------------------------------

export const PARTS: PartDef[] = [
  head,
  muzzle,
  neck,
  body,
  ...LEGS.map(makeLeg),
  makeEar(1, [256, 160, 64, 64]),
  makeEar(-1, [320, 160, 64, 64]),
  tail,
];

export function partByName(name: string): PartDef {
  const p = PARTS.find((x) => x.name === name);
  if (!p) throw new Error(`unknown part ${name}`);
  return p;
}

/** 部件参数 -> 图集纹素坐标（像素，连续值，纹素中心对齐） */
export function paramToTexel(part: PartDef, s: number, t: number): [number, number] {
  const [x, y, w, h] = part.rect;
  const a = part.transposeUV ? t : s;
  const b = part.transposeUV ? s : t;
  return [x + 0.5 + a * (w - 1), y + 0.5 + b * (h - 1)];
}

/** 图集纹素 -> 部件参数（paramToTexel 的逆） */
export function texelToParam(part: PartDef, px: number, py: number): [number, number] {
  const [x, y, w, h] = part.rect;
  const a = (px - x) / (w - 1);
  const b = (py - y) / (h - 1);
  return part.transposeUV ? [b, a] : [a, b];
}

const _a = new Vector3();
const _b = new Vector3();
const _c = new Vector3();
const _d = new Vector3();

/** 数值法求部件表面法线，极点处退化时用 (点 - 核心) 方向 */
export function partNormal(part: PartDef, s: number, t: number, k: ShapeParams, out: Vector3): Vector3 {
  const e = 1e-3;
  part.pos(Math.min(1, s + e), t, k, _a);
  part.pos(Math.max(0, s - e), t, k, _b);
  part.pos(s, Math.min(1, t + e), k, _c);
  part.pos(s, Math.max(0, t - e), k, _d);
  const ds = _a.sub(_b);
  const dt = _c.sub(_d);
  out.crossVectors(ds, dt);
  part.pos(s, t, k, _b);
  part.core(s, t, k, _d);
  const radial = _b.sub(_d);
  if (out.lengthSq() < 1e-14) return out.copy(radial).normalize();
  out.normalize();
  if (out.dot(radial) < 0) out.negate();
  return out;
}
