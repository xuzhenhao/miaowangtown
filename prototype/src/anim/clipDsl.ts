import {
  AnimationClip,
  Euler,
  KeyframeTrack,
  Quaternion,
  QuaternionKeyframeTrack,
  VectorKeyframeTrack,
} from 'three';
import { ANIM_BONES, type BoneName } from '../cat/skeleton';
import type { EyeState, MouthState } from '../cat/face';

/** 欧拉角，单位度。绕 X 正 = 低头/腿后摆，绕 Y 正 = 转向猫左侧，绕 Z 正 = 向猫右侧歪 */
export type Deg3 = [number, number, number];
export type AnimBone = Exclude<BoneName, 'root'>;
export type Pose = Partial<Record<AnimBone, Deg3>>;

export interface Key {
  t: number;
  pose?: Pose;
  /** hips 相对静止位置的位移 */
  hips?: [number, number, number];
}

export interface FaceKey {
  t: number;
  eyes?: EyeState;
  mouth?: MouthState;
}

export interface ClipDef {
  name: string;
  label: string;
  duration: number;
  loop: boolean;
  keys: Key[];
  face?: FaceKey[];
  /** 原地循环时对应的移动速度（单位/秒），用于步频匹配 */
  speed?: number;
  /** 程序化「看向」的权重 0..1 */
  lookWeight?: number;
  /** 尾巴随机摆动幅度（度） */
  tailSway?: number;
}

/** 把相位函数采样成关键帧，方便写循环动作 */
export function cycle(duration: number, samples: number, fn: (phase: number) => Omit<Key, 't'>): Key[] {
  const keys: Key[] = [];
  for (let i = 0; i <= samples; i++) {
    const ph = (i % samples) / samples;
    keys.push({ t: (i / samples) * duration, ...fn(ph) });
  }
  return keys;
}

/** 合并多个姿态，后者覆盖前者的同名骨骼 */
export function pose(...poses: Pose[]): Pose {
  return Object.assign({}, ...poses);
}

export const sin = (ph: number, off = 0) => Math.sin((ph + off) * Math.PI * 2);
export const cos = (ph: number, off = 0) => Math.cos((ph + off) * Math.PI * 2);

const D2R = Math.PI / 180;

export function buildClip(def: ClipDef, restHips: [number, number, number]): AnimationClip {
  const tracks: KeyframeTrack[] = [];
  const e = new Euler();
  const q = new Quaternion();
  for (const bone of ANIM_BONES) {
    const ks = def.keys.filter((k) => k.pose?.[bone]);
    const times: number[] = [];
    const values: number[] = [];
    if (!ks.length) {
      times.push(0, def.duration);
      values.push(0, 0, 0, 1, 0, 0, 0, 1);
    } else {
      for (const k of ks) {
        const [x, y, z] = k.pose![bone]!;
        q.setFromEuler(e.set(x * D2R, y * D2R, z * D2R, 'YXZ'));
        times.push(k.t);
        values.push(q.x, q.y, q.z, q.w);
      }
    }
    tracks.push(new QuaternionKeyframeTrack(`${bone}.quaternion`, times, values));
  }
  const hk = def.keys.filter((k) => k.hips);
  const ht = hk.length ? hk.map((k) => k.t) : [0, def.duration];
  const hv = hk.length
    ? hk.flatMap((k) => k.hips!.map((v, i) => v + restHips[i]))
    : [...restHips, ...restHips];
  tracks.push(new VectorKeyframeTrack('hips.position', ht, hv));
  return new AnimationClip(def.name, def.duration, tracks);
}

/** 取某个时刻生效的表情（最近一个不晚于 t 的关键帧） */
export function faceAt(def: ClipDef, t: number): { eyes?: EyeState; mouth?: MouthState } {
  const out: { eyes?: EyeState; mouth?: MouthState } = {};
  for (const k of def.face ?? []) {
    if (k.t > t) break;
    if (k.eyes) out.eyes = k.eyes;
    if (k.mouth) out.mouth = k.mouth;
  }
  return out;
}
