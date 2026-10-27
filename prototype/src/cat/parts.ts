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
      if (a === b) return [[a, 1]];
      const f = (v - va) / (vb - va);
      return [
        [a, 1 - f],
        [b, f],
      ];
    }
  }
  return [[stops[stops.length - 1][0], 1]];
}

// ---------------------------------------------------------------- 头（上窄下饱满、自然融合口鼻与婴儿肥脸颊）

export const HEAD_CENTER = new Vector3(0, 0.9, 0.54);

export function headPos(s: number, t: number, k: ShapeParams, out: Vector3): Vector3 {
  const th = (s - 0.5) * TAU;
  const ph = t * Math.PI;
  const dx = Math.sin(ph) * Math.sin(th);
  const dy = Math.cos(ph);
  const dz = Math.sin(ph) * Math.cos(th);

  // 娇俏猫科头骨比例：告别扁宽充气球，额顶微收、双颊饱满、下颌秀气
  const rx = 0.285 * (1 + 0.08 * k.headRound);
  const ry = 0.275 * (1 - 0.02 * k.headRound);
  const rz = 0.282;

  const crownTaper = dy > 0.2 ? 1 - 0.11 * clamp((dy - 0.2) / 0.8, 0, 1) : 1;
  const chinTaper = dy < -0.35 ? 1 - 0.22 * clamp((-0.35 - dy) / 0.65, 0, 1) : 1;
  const cheekBell = Math.exp(-(((dy + 0.14) / 0.36) ** 2));
  const cheek =
    (0.06 + 0.11 * k.cheekFluff) *
    cheekBell *
    Math.pow(Math.abs(Math.sin(th)), 0.85) *
    Math.sin(ph);

  // 面部正前下侧自然向口鼻过渡，消除嘴套孤立球感
  const snoutBlend =
    dz > 0.25 && dy < 0.08 && dy > -0.72
      ? 0.045 * clamp((dz - 0.25) / 0.75, 0, 1) * Math.exp(-(((dy + 0.26) / 0.32) ** 2))
      : 0;
  const faceFlatten = dz > 0 ? 1 - 0.06 * dz * dz : 0.96;

  return out.set(
    HEAD_CENTER.x + dx * rx * crownTaper * chinTaper * (1 + cheek),
    HEAD_CENTER.y + dy * ry,
    HEAD_CENTER.z + dz * rz * faceFlatten + snoutBlend,
  );
}

const head: PartDef = {
  name: 'head',
  rect: [0, 0, 256, 128],
  segS: 48,
  segT: 28,
  pos: headPos,
  core: (_s, _t, _k, out) => out.copy(HEAD_CENTER),
  weights: () => [['head', 1]],
};

// ---------------------------------------------------------------- 嘴套（平滑嵌入式猫口鼻垫，消除球体切缝）

export const MUZZLE_CENTER = new Vector3(0, 0.825, 0.742);

export function muzzlePos(s: number, t: number, k: ShapeParams, out: Vector3): Vector3 {
  const th = (s - 0.5) * TAU;
  const ph = t * Math.PI;
  const dx = Math.sin(ph) * Math.sin(th);
  const dy = Math.cos(ph);
  const dz = Math.sin(ph) * Math.cos(th);
  const m = k.muzzleSize;
  // 两侧胡须垫微鼓，上下与后方平滑汇入面部
  const pad = 1 + 0.1 * Math.sin(2 * th) ** 2 * clamp(dy + 0.35, 0, 1);
  const chin = dy < -0.25 ? 1 - 0.18 * clamp((-0.25 - dy) / 0.75, 0, 1) : 1;
  const backTuck = dz < 0 ? 0.55 : 1;
  return out.set(
    MUZZLE_CENTER.x + dx * (0.132 + 0.022 * m) * pad * chin,
    MUZZLE_CENTER.y + dy * (0.078 + 0.01 * m),
    MUZZLE_CENTER.z + dz * (0.064 + 0.014 * m) * backTuck,
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

// ---------------------------------------------------------------- 脖子与胸脯围脖（无缝衔接头部与前胸）

const NECK_A = new Vector3(0, 0.55, 0.25);
const NECK_B = new Vector3(0, 0.85, 0.5);
const NECK_D = NECK_B.clone().sub(NECK_A).normalize();
const NECK_U = new Vector3(1, 0, 0);
const NECK_W = new Vector3().crossVectors(NECK_U, NECK_D).normalize();

const neck: PartDef = {
  name: 'neck',
  rect: [384, 0, 128, 64],
  segS: 24,
  segT: 10,
  pos(s, t, k, out) {
    const th = (s - 0.5) * TAU;
    const baseR = lerp(0.215, 0.168, t) * (1 + 0.1 * k.weight) * (1 + 0.1 * k.cheekFluff * t);
    const chestFluff = (1 - t) * 0.055 * Math.max(0, Math.cos(th));
    out.copy(NECK_A).lerp(NECK_B, t);
    return out
      .addScaledVector(NECK_U, Math.sin(th) * baseR * 0.94)
      .addScaledVector(NECK_W, Math.cos(th) * (baseR + chestFluff));
  },
  core: (_s, t, _k, out) => out.copy(NECK_A).lerp(NECK_B, t),
  weights: (_s, t) =>
    chainWeights(t, [
      ['chest', 0.12],
      ['neck', 0.52],
      ['head', 0.88],
    ]),
};

// ---------------------------------------------------------------- 身体（饱满白胸脯 + 流线微凹背脊 + 圆润臀部）

export const BODY_CENTER = new Vector3(0, 0.5, 0);

function bodyPos(s: number, t: number, k: ShapeParams, out: Vector3): Vector3 {
  const ph = t * Math.PI;
  const zc = -Math.cos(ph); // -1 为臀部，+1 为前胸
  const r = Math.sin(ph);
  const th = (s - 0.5) * TAU;

  // 猫科流线体态：肩胸挺拔、腰肋适中、臀部圆润
  const widthProfile = 1 - 0.08 * zc + 0.06 * Math.sin(ph);
  const heightProfile = 1 + 0.06 * Math.cos((zc - 0.15) * Math.PI * 0.8);
  const rx = 0.232 * (1 + 0.2 * k.weight) * widthProfile;
  const ry = 0.236 * (1 + 0.12 * k.weight) * heightProfile;

  const X = Math.sin(th) * r * rx;
  let Y = Math.cos(th) * r * ry;
  if (Y < 0) {
    // 腹部收腰与软肚皮曲线
    const waistTuck = zc < -0.1 && zc > -0.65 ? 0.92 : 1.0;
    Y *= (1 + 0.28 * k.weight) * waistTuck;
  }

  // 自然背脊线微弧与挺拔前胸脯
  const spineArc =
    0.026 * Math.exp(-(((zc - 0.48) / 0.38) ** 2)) +
    0.018 * Math.exp(-(((zc + 0.45) / 0.42) ** 2)) -
    0.014 * Math.exp(-((zc / 0.35) ** 2));
  const chestBibZ = zc > 0.3 && Y > -0.12 ? 0.045 * clamp((zc - 0.3) / 0.7, 0, 1) * r : 0;

  return out.set(X, BODY_CENTER.y + spineArc + Y, zc * 0.485 + chestBibZ);
}

const body: PartDef = {
  name: 'body',
  rect: [0, 128, 256, 192],
  segS: 40,
  segT: 32,
  pos: bodyPos,
  core: (_s, t, _k, out) => out.set(0, BODY_CENTER.y, -Math.cos(t * Math.PI) * 0.485 * 0.6),
  weights: (_s, _t, p) =>
    chainWeights(p.z, [
      ['hips', -0.22],
      ['spine', 0.05],
      ['chest', 0.28],
    ]),
};

// ---------------------------------------------------------------- 四肢与圆润猫爪（上粗下收 + 踝腕微折 + 饱满猫爪垫）

export interface LegSpec {
  name: string;
  x: number;
  z: number;
  front: boolean;
  bones: [string, string, string, string]; // parent, upper, lower, paw
  rect: [number, number, number, number];
}

const LEG_TOP = 0.56;
export const PAW_Y = 0.055;
const PAW_R = 0.068;

function legRadius(y: number, front: boolean): [number, number] {
  // 返回 [rx, rz]：后腿大腿股四头肌更宽厚，前腕/飞节纤细
  const rxUpper = front ? 0.086 : 0.105;
  const rzUpper = front ? 0.092 : 0.155;
  const rWrist = front ? 0.052 : 0.052;
  if (y >= 0.34) {
    const f = clamp((y - 0.34) / (LEG_TOP - 0.34), 0, 1);
    return [lerp(rxUpper * 0.88, rxUpper, f), lerp(rzUpper * 0.88, rzUpper, f)];
  }
  if (y > 0.15) {
    const f = (y - 0.15) / 0.19;
    return [lerp(rWrist, rxUpper * 0.88, f), lerp(rWrist * 1.04, rzUpper * 0.88, f)];
  }
  const f = clamp((y - PAW_Y) / (0.15 - PAW_Y), 0, 1);
  return [lerp(PAW_R * 0.98, rWrist, f), lerp(PAW_R * 1.18, rWrist * 1.04, f)];
}

/** Stage 1 趾行解剖轴线：返回绝对 z（与 build_base.py front_axis_z / hind_axis_z 一致） */
export function legAxisZ(y: number, front: boolean): number {
  if (front) {
    // 肩 0.33 → 肘 0.27@0.30 → 腕 0.31@0.11 → 掌 0.35
    if (y >= 0.3) return lerp(0.27, 0.33, clamp((y - 0.3) / (0.52 - 0.3), 0, 1));
    if (y >= 0.11) return lerp(0.31, 0.27, clamp((y - 0.11) / (0.3 - 0.11), 0, 1));
    return lerp(0.35, 0.31, clamp(y / 0.11, 0, 1));
  }
  // 髋 -0.22 → 膝 -0.15@0.33 → 飞节 -0.29@0.17 → 掌 -0.21
  if (y >= 0.33) return lerp(-0.15, -0.22, clamp((y - 0.33) / (0.52 - 0.33), 0, 1));
  if (y >= 0.17) return lerp(-0.29, -0.15, clamp((y - 0.17) / (0.33 - 0.17), 0, 1));
  return lerp(-0.21, -0.29, clamp(y / 0.17, 0, 1));
}

/** 相对基准 z 的偏置（兼容旧调用 / 调试）；新几何优先用 legAxisZ */
export function legZOffset(y: number, front: boolean): number {
  const base = front ? 0.31 : -0.23;
  return legAxisZ(y, front) - base;
}

function makeLeg(spec: LegSpec): PartDef {
  const tc = 0.8;
  return {
    name: spec.name,
    rect: spec.rect,
    segS: 18,
    segT: 22,
    pos(s, t, _k, out) {
      const th = (s - 0.5) * TAU;
      let y: number;
      let rx: number;
      let rz: number;
      if (t <= tc) {
        y = lerp(LEG_TOP, PAW_Y, t / tc);
        [rx, rz] = legRadius(y, spec.front);
      } else {
        const a = ((t - tc) / (1 - tc)) * (Math.PI / 2) * 0.92;
        y = PAW_Y - PAW_R * Math.sin(a) * 0.35;
        const c = Math.cos(a);
        const toe = 1 + 0.2 * Math.max(0, Math.cos(th)) * (1 - c);
        rx = PAW_R * 1.05 * c * toe;
        rz = PAW_R * 1.3 * c;
      }
      const lz = legAxisZ(y, spec.front);
      return out.set(spec.x + Math.sin(th) * rx, y, lz + Math.cos(th) * rz);
    },
    core(_s, t, _k, out) {
      const y = t <= tc ? lerp(LEG_TOP, PAW_Y, t / tc) : PAW_Y;
      return out.set(spec.x, y, legAxisZ(y, spec.front));
    },
    weights: (_s, _t, p) =>
      chainWeights(p.y, spec.front
        ? [
            [spec.bones[3], 0.055],
            [spec.bones[3], 0.095],
            [spec.bones[2], 0.13],
            [spec.bones[2], 0.275],
            [spec.bones[1], 0.32],
            [spec.bones[1], 0.455],
            [spec.bones[0], 0.51],
          ]
        : [
            [spec.bones[3], 0.06],
            [spec.bones[3], 0.145],
            [spec.bones[2], 0.185],
            [spec.bones[2], 0.305],
            [spec.bones[1], 0.35],
            [spec.bones[1], 0.47],
            [spec.bones[0], 0.52],
          ]),
  };
}

export const LEGS: LegSpec[] = [
  { name: 'fLegL', x: 0.145, z: 0.33, front: true, bones: ['chest', 'shoulderL', 'elbowL', 'fpawL'], rect: [256, 64, 64, 96] },
  { name: 'fLegR', x: -0.145, z: 0.33, front: true, bones: ['chest', 'shoulderR', 'elbowR', 'fpawR'], rect: [320, 64, 64, 96] },
  { name: 'hLegL', x: 0.155, z: -0.22, front: false, bones: ['hips', 'hipL', 'kneeL', 'hpawL'], rect: [384, 64, 64, 96] },
  { name: 'hLegR', x: -0.155, z: -0.22, front: false, bones: ['hips', 'hipR', 'kneeR', 'hpawR'], rect: [448, 64, 64, 96] },
];

// ---------------------------------------------------------------- 耳朵（挺拔饱满的三角猫耳，对标左图神态）

const EAR_THETA = 0.76;
const EAR_PHI = 0.23;

export function earBase(side: 1 | -1, k: ShapeParams, out = new Vector3()): Vector3 {
  return headPos(0.5 + (side * EAR_THETA) / TAU, EAR_PHI, k, out);
}

function makeEar(side: 1 | -1, rect: [number, number, number, number]): PartDef {
  const axis = new Vector3(side * 0.32, 1, 0.12).normalize();
  const f0 = new Vector3(0, 0, 1);
  const front = f0.clone().addScaledVector(axis, -axis.dot(f0)).normalize();
  const sideways = new Vector3().crossVectors(axis, front).normalize();
  const base = new Vector3();
  const boneName = side === 1 ? 'earL' : 'earR';
  return {
    name: side === 1 ? 'earL' : 'earR',
    rect,
    segS: 16,
    segT: 12,
    pos(s, t, k, out) {
      earBase(side, k, base);
      const rb = 0.125 * (1 + 0.2 * k.earSize);
      const h = 0.235 * (1 + 0.36 * k.earSize);
      const th = (s - 0.5) * TAU;
      const r = rb * Math.pow(1 - t, 0.88);
      // 耳廓正面微凹呈小勺状，凸显粉色内耳与深色外耳廓边
      const cup = Math.cos(th) > 0 ? 0.22 : 0.58;
      out.copy(base).addScaledVector(axis, -0.045 + t * (h + 0.045));
      return out.addScaledVector(sideways, Math.sin(th) * r).addScaledVector(front, Math.cos(th) * r * cup);
    },
    core(_s, t, k, out) {
      earBase(side, k, out);
      const h = 0.235 * (1 + 0.36 * k.earSize);
      return out.addScaledVector(axis, -0.045 + t * (h + 0.045) - 0.02);
    },
    weights: (_s, t) =>
      chainWeights(t, [
        ['head', 0.05],
        [boneName, 0.35],
      ]),
  };
}

// ---------------------------------------------------------------- 尾巴（自然修长 S 型微翘虎斑尾）

const TAIL_CURVE = new CatmullRomCurve3([
  new Vector3(0, 0.64, -0.44),
  new Vector3(0, 0.6, -0.56),
  new Vector3(0, 0.58, -0.68),
  new Vector3(0, 0.62, -0.8),
  new Vector3(0, 0.7, -0.88),
  new Vector3(0, 0.8, -0.93),
  new Vector3(0, 0.9, -0.95),
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
  segS: 14,
  segT: 32,
  pos(s, t, k, out) {
    const th = (s - 0.5) * TAU;
    TAIL_CURVE.getPointAt(t, out);
    TAIL_CURVE.getTangentAt(t, tailTan);
    tailW.crossVectors(TAIL_U, tailTan).normalize();
    const f = k.tailFluff;
    let r = (0.044 + 0.022 * f) * (1 + 0.22 * f * Math.sin(Math.PI * t)) * lerp(1, 0.72, t);
    if (t > 0.88) r *= Math.sqrt(Math.max(0, 1 - ((t - 0.88) / 0.12) ** 2));
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
