import {
  BufferGeometry,
  Float32BufferAttribute,
  Uint16BufferAttribute,
  Vector3,
  type Material,
  SkinnedMesh,
} from 'three';
import { ATLAS_SIZE, PARTS, paramToTexel, partNormal, type PartDef } from './parts';
import { NEUTRAL_SHAPE, SHAPE_KEYS, shapeWith, type ShapeParams } from './shape';
import { createSkeleton, type CatSkeleton } from './skeleton';

function gridCount(p: PartDef) {
  return (p.segS + 1) * (p.segT + 1);
}

function forEachVertex(cb: (part: PartDef, s: number, t: number, i: number) => void) {
  let i = 0;
  for (const part of PARTS) {
    for (let j = 0; j <= part.segT; j++) {
      for (let q = 0; q <= part.segS; q++) {
        cb(part, q / part.segS, j / part.segT, i++);
      }
    }
  }
}

function positions(k: ShapeParams, count: number): Float32Array {
  const arr = new Float32Array(count * 3);
  const v = new Vector3();
  forEachVertex((part, s, t, i) => {
    part.pos(s, t, k, v);
    arr[i * 3] = v.x;
    arr[i * 3 + 1] = v.y;
    arr[i * 3 + 2] = v.z;
  });
  return arr;
}

export function buildCatGeometry(sk: CatSkeleton): BufferGeometry {
  const count = PARTS.reduce((n, p) => n + gridCount(p), 0);
  const base = positions(NEUTRAL_SHAPE, count);
  const normal = new Float32Array(count * 3);
  const uv = new Float32Array(count * 2);
  const skinIndex = new Uint16Array(count * 4);
  const skinWeight = new Float32Array(count * 4);
  const n = new Vector3();
  const p = new Vector3();

  forEachVertex((part, s, t, i) => {
    partNormal(part, s, t, NEUTRAL_SHAPE, n);
    normal.set([n.x, n.y, n.z], i * 3);
    const [tu, tv] = paramToTexel(part, s, t);
    uv[i * 2] = tu / ATLAS_SIZE;
    uv[i * 2 + 1] = 1 - tv / ATLAS_SIZE;
    p.fromArray(base, i * 3);
    const w = part
      .weights(s, t, p)
      .filter(([, x]) => x > 1e-4)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
    const sum = w.reduce((a, [, x]) => a + x, 0);
    w.forEach(([bone, x], c) => {
      const idx = sk.index[bone];
      if (idx === undefined) throw new Error(`weight to unknown bone ${bone}`);
      skinIndex[i * 4 + c] = idx;
      skinWeight[i * 4 + c] = x / sum;
    });
  });

  const indices: number[] = [];
  let offset = 0;
  for (const part of PARTS) {
    const row = part.segS + 1;
    const start = indices.length;
    for (let j = 0; j < part.segT; j++) {
      for (let q = 0; q < part.segS; q++) {
        const a = offset + j * row + q;
        const b = a + 1;
        const c = a + row;
        const d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }
    // 统一绕序：让三角面朝向与法线一致（朝外）
    const tri = new Vector3();
    const e1 = new Vector3();
    const e2 = new Vector3();
    let score = 0;
    for (let f = start; f < indices.length; f += 3) {
      const [i0, i1, i2] = [indices[f], indices[f + 1], indices[f + 2]];
      const v0 = new Vector3().fromArray(base, i0 * 3);
      e1.fromArray(base, i1 * 3).sub(v0);
      e2.fromArray(base, i2 * 3).sub(v0);
      tri.crossVectors(e1, e2);
      if (tri.lengthSq() < 1e-12) continue;
      score += tri.dot(n.fromArray(normal, i0 * 3)) > 0 ? 1 : -1;
    }
    if (score < 0) {
      for (let f = start; f < indices.length; f += 3) {
        const tmp = indices[f + 1];
        indices[f + 1] = indices[f + 2];
        indices[f + 2] = tmp;
      }
    }
    offset += gridCount(part);
  }

  const geo = new BufferGeometry();
  geo.setAttribute('position', new Float32BufferAttribute(base, 3));
  geo.setAttribute('normal', new Float32BufferAttribute(normal, 3));
  geo.setAttribute('uv', new Float32BufferAttribute(uv, 2));
  geo.setAttribute('skinIndex', new Uint16BufferAttribute(skinIndex, 4));
  geo.setAttribute('skinWeight', new Float32BufferAttribute(skinWeight, 4));
  geo.setIndex(indices);

  // 形态键：每个体型参数取 1 时与中性体型的位移差
  geo.morphTargetsRelative = true;
  geo.morphAttributes.position = SHAPE_KEYS.map((key) => {
    const target = positions(shapeWith(key, 1), count);
    for (let i = 0; i < target.length; i++) target[i] -= base[i];
    const attr = new Float32BufferAttribute(target, 3);
    attr.name = key;
    return attr;
  });
  geo.computeBoundingSphere();
  return geo;
}

export interface CatMesh {
  mesh: SkinnedMesh;
  sk: CatSkeleton;
}

export function buildCatMesh(material: Material): CatMesh {
  const sk = createSkeleton();
  const geo = buildCatGeometry(sk);
  const mesh = new SkinnedMesh(geo, material);
  mesh.name = 'cat_base';
  mesh.add(sk.root);
  mesh.bind(sk.skeleton);
  mesh.updateMorphTargets();
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.frustumCulled = false;
  return { mesh, sk };
}

export function applyShape(mesh: SkinnedMesh, k: ShapeParams) {
  const dict = mesh.morphTargetDictionary!;
  const inf = mesh.morphTargetInfluences!;
  for (const key of SHAPE_KEYS) inf[dict[key]] = k[key];
}
