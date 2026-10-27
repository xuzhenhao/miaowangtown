import {
  BufferGeometry,
  Float32BufferAttribute,
  Uint16BufferAttribute,
  Uint32BufferAttribute,
  Vector3,
} from 'three';
import { BONE_NAMES, createSkeleton, type BoneName, type CatSkeleton } from './skeleton';
import { SHAPE_KEYS } from './shape';

export interface FaceAnchor {
  vertexIndex: number;
  pos: [number, number, number];
  normal: [number, number, number];
}

export type FaceAnchorsMap = Record<'eyeL' | 'eyeR' | 'mouth' | 'whiskerL' | 'whiskerR', FaceAnchor>;

export interface LoadedBaseGlb {
  geo: BufferGeometry;
  sk: CatSkeleton;
  anchors: FaceAnchorsMap;
  bonePositions: Partial<Record<BoneName, Vector3>>;
}

interface GltfAccessor {
  bufferView?: number;
  byteOffset?: number;
  componentType: number;
  count: number;
  type: 'SCALAR' | 'VEC2' | 'VEC3' | 'VEC4' | 'MAT4';
  sparse?: {
    count: number;
    indices: { bufferView: number; byteOffset?: number; componentType: number };
    values: { bufferView: number; byteOffset?: number };
  };
}

interface GltfBufferView {
  buffer: number;
  byteOffset?: number;
  byteLength: number;
  byteStride?: number;
}

interface GltfNode {
  name?: string;
  mesh?: number;
  skin?: number;
  children?: number[];
  translation?: [number, number, number];
  rotation?: [number, number, number, number];
  scale?: [number, number, number];
  extras?: Record<string, unknown>;
}

interface GltfJson {
  accessors: GltfAccessor[];
  bufferViews: GltfBufferView[];
  meshes: Array<{
    name?: string;
    extras?: { faceAnchors?: string; targetNames?: string[] };
    primitives: Array<{
      attributes: Record<string, number>;
      indices?: number;
      targets?: Array<Record<string, number>>;
    }>;
  }>;
  nodes: GltfNode[];
  skins?: Array<{
    joints: number[];
    inverseBindMatrices?: number;
  }>;
}

const TYPE_COUNTS: Record<GltfAccessor['type'], number> = {
  SCALAR: 1,
  VEC2: 2,
  VEC3: 3,
  VEC4: 4,
  MAT4: 16,
};

function readAccessorAsFloat32(gltf: GltfJson, bin: DataView, accIdx: number): Float32Array {
  const acc = gltf.accessors[accIdx];
  const comps = TYPE_COUNTS[acc.type];
  const out = new Float32Array(acc.count * comps);
  if (acc.bufferView !== undefined) {
    const bv = gltf.bufferViews[acc.bufferView!];
    const baseOffset = (bv.byteOffset ?? 0) + (acc.byteOffset ?? 0);
    const stride = bv.byteStride ?? comps * 4;
    for (let i = 0; i < acc.count; i++) {
      const rowOff = baseOffset + i * stride;
      for (let c = 0; c < comps; c++) {
        out[i * comps + c] = bin.getFloat32(rowOff + c * 4, true);
      }
    }
  }
  if (acc.sparse) {
    const { count, indices, values } = acc.sparse;
    const idxBv = gltf.bufferViews[indices.bufferView];
    const idxOff = (idxBv.byteOffset ?? 0) + (indices.byteOffset ?? 0);
    const idxBpe = indices.componentType === 5121 ? 1 : indices.componentType === 5123 ? 2 : 4;
    const valBv = gltf.bufferViews[values.bufferView];
    const valOff = (valBv.byteOffset ?? 0) + (values.byteOffset ?? 0);
    for (let s = 0; s < count; s++) {
      const io = idxOff + s * idxBpe;
      const targetIdx =
        idxBpe === 1 ? bin.getUint8(io) : idxBpe === 2 ? bin.getUint16(io, true) : bin.getUint32(io, true);
      const vo = valOff + s * comps * 4;
      for (let c = 0; c < comps; c++) {
        out[targetIdx * comps + c] = bin.getFloat32(vo + c * 4, true);
      }
    }
  }
  return out;
}

function readAccessorAsUint16(gltf: GltfJson, bin: DataView, accIdx: number): Uint16Array {
  const acc = gltf.accessors[accIdx];
  const bv = gltf.bufferViews[acc.bufferView!];
  const comps = TYPE_COUNTS[acc.type];
  const bpe = acc.componentType === 5121 ? 1 : acc.componentType === 5123 ? 2 : 4;
  const baseOffset = (bv.byteOffset ?? 0) + (acc.byteOffset ?? 0);
  const stride = bv.byteStride ?? comps * bpe;
  const out = new Uint16Array(acc.count * comps);
  for (let i = 0; i < acc.count; i++) {
    const rowOff = baseOffset + i * stride;
    for (let c = 0; c < comps; c++) {
      const off = rowOff + c * bpe;
      out[i * comps + c] =
        bpe === 1 ? bin.getUint8(off) : bpe === 2 ? bin.getUint16(off, true) : bin.getUint32(off, true);
    }
  }
  return out;
}

function readIndices(gltf: GltfJson, bin: DataView, accIdx: number): Uint16Array | Uint32Array {
  const acc = gltf.accessors[accIdx];
  const bv = gltf.bufferViews[acc.bufferView!];
  const bpe = acc.componentType === 5121 ? 1 : acc.componentType === 5123 ? 2 : 4;
  const baseOffset = (bv.byteOffset ?? 0) + (acc.byteOffset ?? 0);
  const stride = bv.byteStride ?? bpe;
  const out = acc.count > 65535 || bpe === 4 ? new Uint32Array(acc.count) : new Uint16Array(acc.count);
  for (let i = 0; i < acc.count; i++) {
    const off = baseOffset + i * stride;
    out[i] = bpe === 1 ? bin.getUint8(off) : bpe === 2 ? bin.getUint16(off, true) : bin.getUint32(off, true);
  }
  return out;
}

/**
 * 解析 Blender 流水线导出的 `cat_base.glb`：
 * 1. 读取一体网格几何体、UV、`_PART` 部件标签、6 个形态键、脸部锚点；
 * 2. 只提取 GLB 骨骼节点的静止世界位置（忽略骨骼局部旋转，保持静止旋转恒为单位四元数 Identity）；
 * 3. 按骨骼名称把 GLB 的 `JOINTS_0` 蒙皮索引重映射到 `createSkeleton(positions)` 的骨骼顺序。
 */
export function parseBaseGlb(buffer: ArrayBuffer): LoadedBaseGlb {
  const view = new DataView(buffer);
  const magic = view.getUint32(0, true);
  if (magic !== 0x46546c67) {
    throw new Error('Invalid GLB magic header');
  }
  const jsonLen = view.getUint32(12, true);
  const jsonText = new TextDecoder().decode(new Uint8Array(buffer, 20, jsonLen));
  const gltf: GltfJson = JSON.parse(jsonText);
  const binStart = 20 + jsonLen + 8;
  const bin = new DataView(buffer, binStart);

  // 1. 解析节点树，累加关节静止世界坐标（忽略关节旋转）
  const parentMap = new Map<number, number>();
  gltf.nodes.forEach((node, idx) => {
    node.children?.forEach((ch) => parentMap.set(ch, idx));
  });

  const worldPosOfNode = (idx: number): Vector3 => {
    const acc = new Vector3();
    let cur: number | undefined = idx;
    while (cur !== undefined) {
      const n = gltf.nodes[cur];
      if (n.translation) {
        acc.x += n.translation[0];
        acc.y += n.translation[1];
        acc.z += n.translation[2];
      }
      cur = parentMap.get(cur);
    }
    return acc;
  };

  const boneSet = new Set<string>(BONE_NAMES);
  const bonePositions: Partial<Record<BoneName, Vector3>> = {};
  gltf.nodes.forEach((node, idx) => {
    if (node.name && boneSet.has(node.name)) {
      bonePositions[node.name as BoneName] = worldPosOfNode(idx);
    }
  });

  const sk = createSkeleton(bonePositions);

  // 2. 读取网格与属性
  const meshDef = gltf.meshes[0];
  const prim = meshDef.primitives[0];
  const pos = readAccessorAsFloat32(gltf, bin, prim.attributes.POSITION);
  const norm = readAccessorAsFloat32(gltf, bin, prim.attributes.NORMAL);
  const rawUv = readAccessorAsFloat32(gltf, bin, prim.attributes.TEXCOORD_0);
  // glTF UV 原点在左上角 (v_gltf = py / ATLAS_SIZE)，Three.js CanvasTexture 默认 flipY=true，因此翻回 v = 1 - v_gltf
  const uv = new Float32Array(rawUv.length);
  for (let i = 0; i < rawUv.length; i += 2) {
    uv[i] = rawUv[i];
    uv[i + 1] = 1 - rawUv[i + 1];
  }

  const partAttrIdx = prim.attributes._PART;
  const partArr =
    partAttrIdx !== undefined ? readAccessorAsFloat32(gltf, bin, partAttrIdx) : new Float32Array(pos.length / 3);

  // 3. 按骨骼名称把 GLB 的 JOINTS_0 索引重映射到 sk.index[boneName]
  const rawJoints = readAccessorAsUint16(gltf, bin, prim.attributes.JOINTS_0);
  const skinWeights = readAccessorAsFloat32(gltf, bin, prim.attributes.WEIGHTS_0);
  const skinJoints = gltf.skins?.[0]?.joints ?? [];
  const jointRemap = skinJoints.map((nodeIdx) => {
    const bname = gltf.nodes[nodeIdx]?.name ?? 'root';
    return sk.index[bname] ?? 0;
  });

  const skinIndex = new Uint16Array(rawJoints.length);
  for (let i = 0; i < rawJoints.length; i++) {
    skinIndex[i] = jointRemap[rawJoints[i]] ?? 0;
  }

  const geo = new BufferGeometry();
  geo.setAttribute('position', new Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new Float32BufferAttribute(norm, 3));
  geo.setAttribute('uv', new Float32BufferAttribute(uv, 2));
  geo.setAttribute('_PART', new Float32BufferAttribute(partArr, 1));
  geo.setAttribute('skinIndex', new Uint16BufferAttribute(skinIndex, 4));
  geo.setAttribute('skinWeight', new Float32BufferAttribute(skinWeights, 4));

  if (prim.indices !== undefined) {
    const idxArr = readIndices(gltf, bin, prim.indices);
    geo.setIndex(
      idxArr instanceof Uint32Array ? new Uint32BufferAttribute(idxArr, 1) : new Uint16BufferAttribute(idxArr, 1),
    );
  }

  // 4. 读取 6 个形态键 (MorphTargets: glTF targets 存储的就是相对 Basis 的位移差 delta)
  geo.morphTargetsRelative = true;
  const targetNames = meshDef.extras?.targetNames ?? [...SHAPE_KEYS];
  if (prim.targets && prim.targets.length > 0) {
    const morphMap = new Map<string, Float32BufferAttribute>();
    prim.targets.forEach((t, ti) => {
      if (t.POSITION !== undefined) {
        const delta = readAccessorAsFloat32(gltf, bin, t.POSITION);
        const name = targetNames[ti] ?? SHAPE_KEYS[ti] ?? `target_${ti}`;
        const attr = new Float32BufferAttribute(delta, 3);
        attr.name = name;
        morphMap.set(name, attr);
      }
    });
    geo.morphAttributes.position = SHAPE_KEYS.map((key) => {
      const found = morphMap.get(key);
      if (found) return found;
      const empty = new Float32BufferAttribute(new Float32Array(pos.length), 3);
      empty.name = key;
      return empty;
    });
  }

  geo.computeBoundingSphere();

  // 5. 解析脸部锚点 (extras.faceAnchors)
  let rawAnchorsJson = meshDef.extras?.faceAnchors;
  if (!rawAnchorsJson) {
    const nodeWithExtras = gltf.nodes.find((n) => n.extras?.faceAnchors);
    rawAnchorsJson = nodeWithExtras?.extras?.faceAnchors as string | undefined;
  }
  const anchors: FaceAnchorsMap = rawAnchorsJson
    ? JSON.parse(rawAnchorsJson)
    : {
        eyeL: { vertexIndex: 0, pos: [0.114, 0.88, 0.774], normal: [0.3, 0.04, 0.953] },
        eyeR: { vertexIndex: 0, pos: [-0.114, 0.88, 0.774], normal: [-0.3, 0.04, 0.953] },
        mouth: { vertexIndex: 0, pos: [0, 0.828, 0.804], normal: [0, 0.02, 1] },
        whiskerL: { vertexIndex: 0, pos: [0.184, 0.812, 0.708], normal: [0.64, -0.04, 0.767] },
        whiskerR: { vertexIndex: 0, pos: [-0.184, 0.812, 0.708], normal: [-0.64, -0.04, 0.767] },
      };

  return { geo, sk, anchors, bonePositions };
}

let cachedGlbBuffer: ArrayBuffer | null = null;

export async function preloadBaseGlb(url = `${import.meta.env.BASE_URL}base/cat_base.glb`): Promise<ArrayBuffer> {
  if (cachedGlbBuffer) return cachedGlbBuffer;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch base GLB: ${res.status}`);
  cachedGlbBuffer = await res.arrayBuffer();
  return cachedGlbBuffer;
}

export function getCachedBaseGlb(): LoadedBaseGlb | null {
  if (!cachedGlbBuffer) return null;
  return parseBaseGlb(cachedGlbBuffer);
}
