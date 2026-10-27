import { Bone, Skeleton, Vector3 } from 'three';
import { earBase, tailBonePoints } from './parts';
import { NEUTRAL_SHAPE } from './shape';

/** 母版骨骼。所有骨骼静止姿态的局部轴与世界轴对齐，动作数据直接写欧拉角。 */
export const BONE_NAMES = [
  'root',
  'hips',
  'spine',
  'chest',
  'neck',
  'head',
  'earL',
  'earR',
  'shoulderL',
  'elbowL',
  'fpawL',
  'shoulderR',
  'elbowR',
  'fpawR',
  'hipL',
  'kneeL',
  'hpawL',
  'hipR',
  'kneeR',
  'hpawR',
  'tail0',
  'tail1',
  'tail2',
  'tail3',
  'tail4',
  'tail5',
] as const;

export type BoneName = (typeof BONE_NAMES)[number];

/** 参与动作片段的骨骼（root 留给移动/朝向） */
export const ANIM_BONES = BONE_NAMES.filter((b) => b !== 'root') as Exclude<BoneName, 'root'>[];

interface BoneDef {
  name: BoneName;
  parent: BoneName | null;
  pos: Vector3;
}

function boneDefs(): BoneDef[] {
  const v = (x: number, y: number, z: number) => new Vector3(x, y, z);
  const tail = tailBonePoints();
  const defs: BoneDef[] = [
    { name: 'root', parent: null, pos: v(0, 0, 0) },
    { name: 'hips', parent: 'root', pos: v(0, 0.52, -0.22) },
    { name: 'spine', parent: 'hips', pos: v(0, 0.53, 0.05) },
    { name: 'chest', parent: 'spine', pos: v(0, 0.55, 0.28) },
    { name: 'neck', parent: 'chest', pos: v(0, 0.7, 0.4) },
    { name: 'head', parent: 'neck', pos: v(0, 0.9, 0.52) },
    { name: 'earL', parent: 'head', pos: earBase(1, NEUTRAL_SHAPE) },
    { name: 'earR', parent: 'head', pos: earBase(-1, NEUTRAL_SHAPE) },
  ];
  for (const [side, x] of [
    ['L', 0.16],
    ['R', -0.16],
  ] as const) {
    defs.push(
      { name: `shoulder${side}`, parent: 'chest', pos: v(x, 0.45, 0.3) },
      { name: `elbow${side}`, parent: `shoulder${side}`, pos: v(x, 0.25, 0.31) },
      { name: `fpaw${side}`, parent: `elbow${side}`, pos: v(x, 0.1, 0.32) },
    );
  }
  for (const [side, x] of [
    ['L', 0.17],
    ['R', -0.17],
  ] as const) {
    defs.push(
      { name: `hip${side}`, parent: 'hips', pos: v(x, 0.45, -0.24) },
      { name: `knee${side}`, parent: `hip${side}`, pos: v(x, 0.25, -0.23) },
      { name: `hpaw${side}`, parent: `knee${side}`, pos: v(x, 0.1, -0.22) },
    );
  }
  tail.forEach((p, i) => {
    defs.push({ name: `tail${i}` as BoneName, parent: i === 0 ? 'hips' : (`tail${i - 1}` as BoneName), pos: p });
  });
  return defs;
}

export interface CatSkeleton {
  skeleton: Skeleton;
  root: Bone;
  bones: Record<BoneName, Bone>;
  index: Record<string, number>;
  /** 静止姿态下的世界坐标 */
  restWorld: Record<BoneName, Vector3>;
  /** 静止姿态下的局部坐标（每帧复位用） */
  restLocal: Record<BoneName, Vector3>;
}

export function createSkeleton(): CatSkeleton {
  const defs = boneDefs();
  const bones = {} as Record<BoneName, Bone>;
  const restWorld = {} as Record<BoneName, Vector3>;
  const restLocal = {} as Record<BoneName, Vector3>;
  const index: Record<string, number> = {};
  const list: Bone[] = [];
  for (const d of defs) {
    const b = new Bone();
    b.name = d.name;
    const local = d.parent ? d.pos.clone().sub(restWorld[d.parent]) : d.pos.clone();
    b.position.copy(local);
    if (d.parent) bones[d.parent].add(b);
    bones[d.name] = b;
    restWorld[d.name] = d.pos.clone();
    restLocal[d.name] = local.clone();
    index[d.name] = list.length;
    list.push(b);
  }
  return { skeleton: new Skeleton(list), root: bones.root, bones, index, restWorld, restLocal };
}
