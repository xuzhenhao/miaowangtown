import { BufferGeometry, CanvasTexture, NearestFilter, SRGBColorSpace, Vector3 } from 'three';
import { ATLAS_SIZE, PARTS, partNormal, texelToParam, type PartDef } from './parts';
import { NEUTRAL_SHAPE } from './shape';
import type { Marking, MarkingFilter, PetDNA } from './dna';

export type RGB = [number, number, number];

export function hexToRgb(hex: string): RGB {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

export function rgbToHex(rgb: RGB): string {
  return `#${rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('')}`;
}

function hash3(x: number, y: number, z: number): number {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(z, 1274126177);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

function valueNoise(x: number, y: number, z: number): number {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const zi = Math.floor(z);
  const f = (v: number) => v * v * (3 - 2 * v);
  const u = f(x - xi);
  const v = f(y - yi);
  const w = f(z - zi);
  const L = (a: number, b: number, t: number) => a + (b - a) * t;
  const c = (dx: number, dy: number, dz: number) => hash3(xi + dx, yi + dy, zi + dz);
  return L(
    L(L(c(0, 0, 0), c(1, 0, 0), u), L(c(0, 1, 0), c(1, 1, 0), u), v),
    L(L(c(0, 0, 1), c(1, 0, 1), u), L(c(0, 1, 1), c(1, 1, 1), u), v),
    w,
  );
}

/** -1..1 的分形噪声 */
function fbm(p: Vector3, scale: number): number {
  const a = valueNoise(p.x * scale, p.y * scale, p.z * scale);
  const b = valueNoise(p.x * scale * 2.1 + 17, p.y * scale * 2.1 + 3, p.z * scale * 2.1 + 9);
  return (a * 0.65 + b * 0.35) * 2 - 1;
}

export interface PartBox {
  id: number;
  name: string;
  min: Vector3;
  max: Vector3;
  center: Vector3;
  size: Vector3;
}

/**
 * UV 静止姿态位置图（Rest-Map）：
 * 在 UV 空间光栅化母版 GLB 网格的所有三角形，记录每个纹素的静止 3D 位置、法线与部件编号 `_PART`。
 * 印记烘焙与画笔裁切直接查询此表，从而与底层模型是 Blender/AI 网格还是参数化曲面完全解耦。
 */
export interface RestMap {
  size: number;
  valid: Uint8Array;
  partId: Int8Array;
  pos: Float32Array;
  norm: Float32Array;
  partBoxes: PartBox[];
}

export function buildRestMap(geo: BufferGeometry, size = ATLAS_SIZE): RestMap {
  const valid = new Uint8Array(size * size);
  const partId = new Int8Array(size * size).fill(-1);
  const pos = new Float32Array(size * size * 3);
  const norm = new Float32Array(size * size * 3);

  const posAttr = geo.getAttribute('position');
  const normAttr = geo.getAttribute('normal');
  const uvAttr = geo.getAttribute('uv');
  const partAttr = geo.getAttribute('_PART');
  const indexAttr = geo.getIndex();

  // 1. 统计每个部件的 3D 包围盒（供语义印记自动计算区域中心）
  const partBoxes: PartBox[] = PARTS.map((p, id) => ({
    id,
    name: p.name,
    min: new Vector3(Infinity, Infinity, Infinity),
    max: new Vector3(-Infinity, -Infinity, -Infinity),
    center: new Vector3(),
    size: new Vector3(),
  }));

  for (let vi = 0; vi < posAttr.count; vi++) {
    const pid = partAttr ? Math.max(0, Math.min(PARTS.length - 1, Math.round(partAttr.getX(vi)))) : 0;
    const vx = posAttr.getX(vi);
    const vy = posAttr.getY(vi);
    const vz = posAttr.getZ(vi);
    const box = partBoxes[pid];
    if (box) {
      box.min.min(new Vector3(vx, vy, vz));
      box.max.max(new Vector3(vx, vy, vz));
    }
  }
  for (const box of partBoxes) {
    if (!Number.isFinite(box.min.x)) {
      box.min.set(-0.2, 0, -0.2);
      box.max.set(0.2, 1, 0.2);
    }
    box.center.addVectors(box.min, box.max).multiplyScalar(0.5);
    box.size.subVectors(box.max, box.min);
  }

  // 2. 在 UV 空间光栅化全部三角形
  const triCount = indexAttr ? indexAttr.count / 3 : posAttr.count / 3;
  for (let t = 0; t < triCount; t++) {
    const i0 = indexAttr ? indexAttr.getX(t * 3) : t * 3;
    const i1 = indexAttr ? indexAttr.getX(t * 3 + 1) : t * 3 + 1;
    const i2 = indexAttr ? indexAttr.getX(t * 3 + 2) : t * 3 + 2;

    const u0 = uvAttr.getX(i0) * size;
    const v0 = (1 - uvAttr.getY(i0)) * size;
    const u1 = uvAttr.getX(i1) * size;
    const v1 = (1 - uvAttr.getY(i1)) * size;
    const u2 = uvAttr.getX(i2) * size;
    const v2 = (1 - uvAttr.getY(i2)) * size;

    const minX = Math.max(0, Math.floor(Math.min(u0, u1, u2) - 0.5));
    const maxX = Math.min(size - 1, Math.ceil(Math.max(u0, u1, u2) + 0.5));
    const minY = Math.max(0, Math.floor(Math.min(v0, v1, v2) - 0.5));
    const maxY = Math.min(size - 1, Math.ceil(Math.max(v0, v1, v2) + 0.5));

    const denom = (v1 - v2) * (u0 - u2) + (u2 - u1) * (v0 - v2);
    if (Math.abs(denom) < 1e-8) continue;
    const invDenom = 1 / denom;

    const pid = partAttr ? Math.max(0, Math.min(PARTS.length - 1, Math.round(partAttr.getX(i0)))) : 0;

    const p0x = posAttr.getX(i0), p0y = posAttr.getY(i0), p0z = posAttr.getZ(i0);
    const p1x = posAttr.getX(i1), p1y = posAttr.getY(i1), p1z = posAttr.getZ(i1);
    const p2x = posAttr.getX(i2), p2y = posAttr.getY(i2), p2z = posAttr.getZ(i2);

    const n0x = normAttr.getX(i0), n0y = normAttr.getY(i0), n0z = normAttr.getZ(i0);
    const n1x = normAttr.getX(i1), n1y = normAttr.getY(i1), n1z = normAttr.getZ(i1);
    const n2x = normAttr.getX(i2), n2y = normAttr.getY(i2), n2z = normAttr.getZ(i2);

    for (let py = minY; py <= maxY; py++) {
      const cy = py + 0.5;
      for (let px = minX; px <= maxX; px++) {
        const cx = px + 0.5;
        let w0 = ((v1 - v2) * (cx - u2) + (u2 - u1) * (cy - v2)) * invDenom;
        let w1 = ((v2 - v0) * (cx - u2) + (u0 - u2) * (cy - v2)) * invDenom;
        let w2 = 1 - w0 - w1;
        if (w0 < -0.02 || w1 < -0.02 || w2 < -0.02) continue;
        w0 = Math.max(0, w0);
        w1 = Math.max(0, w1);
        w2 = Math.max(0, w2);
        const wSum = w0 + w1 + w2 || 1;
        w0 /= wSum;
        w1 /= wSum;
        w2 /= wSum;

        const idx = py * size + px;
        valid[idx] = 1;
        partId[idx] = pid;
        pos[idx * 3] = w0 * p0x + w1 * p1x + w2 * p2x;
        pos[idx * 3 + 1] = w0 * p0y + w1 * p1y + w2 * p2y;
        pos[idx * 3 + 2] = w0 * p0z + w1 * p1z + w2 * p2z;

        const nx = w0 * n0x + w1 * n1x + w2 * n2x;
        const ny = w0 * n0y + w1 * n1y + w2 * n2y;
        const nz = w0 * n0z + w1 * n1z + w2 * n2z;
        const nLen = Math.hypot(nx, ny, nz) || 1;
        norm[idx * 3] = nx / nLen;
        norm[idx * 3 + 1] = ny / nLen;
        norm[idx * 3 + 2] = nz / nLen;
      }
    }
  }

  // 3. UV 岛边缘 4 轮膨胀填充，消除三角面接缝或岛边界采样黑边
  const dirs = [
    [-1, 0],
    [1, 0],
    [0, -1],
    [0, 1],
    [-1, -1],
    [1, -1],
    [-1, 1],
    [1, 1],
  ];
  for (let pass = 0; pass < 4; pass++) {
    const nextValid = new Uint8Array(valid);
    for (let py = 0; py < size; py++) {
      for (let px = 0; px < size; px++) {
        const idx = py * size + px;
        if (valid[idx]) continue;
        let sx = 0, sy = 0, sz = 0;
        let snx = 0, sny = 0, snz = 0;
        let pid = -1;
        let count = 0;
        for (const [dx, dy] of dirs) {
          const nx = px + dx;
          const ny = py + dy;
          if (nx < 0 || nx >= size || ny < 0 || ny >= size) continue;
          const nIdx = ny * size + nx;
          if (valid[nIdx]) {
            sx += pos[nIdx * 3];
            sy += pos[nIdx * 3 + 1];
            sz += pos[nIdx * 3 + 2];
            snx += norm[nIdx * 3];
            sny += norm[nIdx * 3 + 1];
            snz += norm[nIdx * 3 + 2];
            pid = partId[nIdx];
            count++;
          }
        }
        if (count > 0) {
          nextValid[idx] = 1;
          partId[idx] = pid;
          pos[idx * 3] = sx / count;
          pos[idx * 3 + 1] = sy / count;
          pos[idx * 3 + 2] = sz / count;
          const nl = Math.hypot(snx, sny, snz) || 1;
          norm[idx * 3] = snx / nl;
          norm[idx * 3 + 1] = sny / nl;
          norm[idx * 3 + 2] = snz / nl;
        }
      }
    }
    valid.set(nextValid);
  }

  // 4. 对部件矩形内仍未覆盖的极角边缘纹素，用参数曲面兜底填满，确保整块矩形 100% 无空洞
  const tmpP = new Vector3();
  const tmpN = new Vector3();
  PARTS.forEach((part, pid) => {
    const [rx, ry, rw, rh] = part.rect;
    for (let py = ry; py < ry + rh; py++) {
      for (let px = rx; px < rx + rw; px++) {
        const idx = py * size + px;
        if (valid[idx]) continue;
        const [s, t] = texelToParam(part, px, py);
        part.pos(s, t, NEUTRAL_SHAPE, tmpP);
        partNormal(part, s, t, NEUTRAL_SHAPE, tmpN);
        valid[idx] = 1;
        partId[idx] = pid;
        pos[idx * 3] = tmpP.x;
        pos[idx * 3 + 1] = tmpP.y;
        pos[idx * 3 + 2] = tmpP.z;
        norm[idx * 3] = tmpN.x;
        norm[idx * 3 + 1] = tmpN.y;
        norm[idx * 3 + 2] = tmpN.z;
      }
    }
  });

  return { size, valid, partId, pos, norm, partBoxes };
}

interface Sample {
  part: PartDef;
  s: number;
  t: number;
  px: number;
  py: number;
  p: Vector3;
  n: Vector3;
}

/** 像素级毛流阶梯抖动（Pixel Fur Dithering）：让色块与虎斑边界呈现手绘像素毛簇感而非平滑几何切线 */
function furDither(px: number, py: number): number {
  const bayer = (((px & 1) << 1) | (py & 1)) / 3 - 0.5;
  const tooth = (((px * 3 + py * 5) & 3) / 3 - 0.5) * 0.6;
  return (bayer * 0.65 + tooth * 0.35) * 0.045;
}

function passFilter(f: MarkingFilter, x: Sample): boolean {
  if (f.parts && !f.parts.includes(x.part.name)) return false;
  const { p } = x;
  const d = furDither(x.px, x.py) * 0.25;
  if (f.minX !== undefined && p.x < f.minX + d) return false;
  if (f.maxX !== undefined && p.x > f.maxX + d) return false;
  if (f.minY !== undefined && p.y < f.minY + d) return false;
  if (f.maxY !== undefined && p.y > f.maxY + d) return false;
  if (f.minZ !== undefined && p.z < f.minZ + d) return false;
  if (f.maxZ !== undefined && p.z > f.maxZ + d) return false;
  return true;
}

function hits(m: Marking, x: Sample): boolean {
  if (!passFilter(m, x)) return false;
  const dither = furDither(x.px, x.py);
  const jitter = (m.noise ?? 0) * fbm(x.p, m.noiseScale ?? 9) + dither;
  switch (m.type) {
    case 'part':
      return true;
    case 'blob': {
      const dx = (x.p.x - m.center[0]) / m.radius[0];
      const dy = (x.p.y - m.center[1]) / m.radius[1];
      const dz = (x.p.z - m.center[2]) / m.radius[2];
      return Math.sqrt(dx * dx + dy * dy + dz * dz) < 1 + jitter;
    }
    case 'underside':
      return x.n.y < (m.threshold ?? -0.35) + jitter;
    case 'stripes': {
      let coord = x.p[m.axis] + jitter * 0.075;
      // 躯干虎斑顺着肋骨自然向后下弯弧（复刻左图手绘虎斑走势）
      if (x.part.name === 'body' && m.axis === 'z') {
        coord -= (0.62 - x.p.y) * 0.22;
      }
      const phase = Math.sin(coord * m.frequency * Math.PI * 2);
      return phase > 1 - 2 * m.width;
    }
  }
}

function isInnerEar(x: Sample): boolean {
  if (x.part.name !== 'earL' && x.part.name !== 'earR') return false;
  const th = (x.s - 0.5) * Math.PI * 2;
  return Math.abs(th) < 0.78 && x.t > 0.12 && x.t < 0.78;
}

/** 耳尖与外耳廓深色包边（凸显挺拔猫耳轮廓与粉色内耳对比） */
function isEarRim(x: Sample): boolean {
  if (x.part.name !== 'earL' && x.part.name !== 'earR') return false;
  const th = (x.s - 0.5) * Math.PI * 2;
  if (x.t >= 0.8) return true;
  return Math.abs(th) >= 0.78 && Math.abs(th) <= 1.32 && x.t > 0.18;
}

export function nearestPaletteColor(c: RGB, palette: RGB[]): RGB {
  let best = palette[0];
  let bd = Infinity;
  for (const q of palette) {
    const d = (c[0] - q[0]) ** 2 + (c[1] - q[1]) ** 2 + (c[2] - q[2]) ** 2;
    if (d < bd) {
      bd = d;
      best = q;
    }
  }
  return best;
}

/**
 * 把 3D 空间描述的印记烘焙到母版非镜像 UV 图集上：
 * - 优先使用从母版 GLB 光栅化生成的 `RestMap`（每个纹素的静止 3D 位置、法线与 `_PART` 编号）；
 * - 若未传入 `RestMap`，自动回退到参数化曲面采样。
 */
export function bakeCoat(dna: PetDNA, canvas: HTMLCanvasElement, restMap?: RestMap) {
  canvas.width = ATLAS_SIZE;
  canvas.height = ATLAS_SIZE;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(ATLAS_SIZE, ATLAS_SIZE);
  const base = hexToRgb(dna.coat.base);
  const markings = dna.coat.markings ?? [];
  const markRgb = markings.map((m) => hexToRgb(m.color));
  const innerEar = hexToRgb(dna.earInner ?? '#d9958f');
  const earRim: RGB = [
    Math.max(24, Math.round(base[0] * 0.42)),
    Math.max(18, Math.round(base[1] * 0.4)),
    Math.max(14, Math.round(base[2] * 0.38)),
  ];
  const sample: Sample = { part: PARTS[0], s: 0, t: 0, px: 0, py: 0, p: new Vector3(), n: new Vector3() };

  for (let i = 0; i < img.data.length; i += 4) {
    img.data.set([...base, 255], i);
  }

  if (restMap) {
    const size = restMap.size;
    for (let py = 0; py < size; py++) {
      for (let px = 0; px < size; px++) {
        const idx = py * size + px;
        if (!restMap.valid[idx]) continue;
        const pid = restMap.partId[idx];
        const part = PARTS[pid] ?? PARTS[0];
        const [s, t] = texelToParam(part, px, py);
        sample.part = part;
        sample.s = s;
        sample.t = t;
        sample.px = px;
        sample.py = py;
        sample.p.set(restMap.pos[idx * 3], restMap.pos[idx * 3 + 1], restMap.pos[idx * 3 + 2]);
        sample.n.set(restMap.norm[idx * 3], restMap.norm[idx * 3 + 1], restMap.norm[idx * 3 + 2]);

        let c: RGB = base;
        markings.forEach((m, mi) => {
          if (hits(m, sample)) c = markRgb[mi];
        });
        if (isEarRim(sample)) c = earRim;
        if (isInnerEar(sample)) c = innerEar;
        img.data.set([...c, 255], idx * 4);
      }
    }
  } else {
    for (const part of PARTS) {
      const [rx, ry, rw, rh] = part.rect;
      for (let py = ry; py < ry + rh; py++) {
        for (let px = rx; px < rx + rw; px++) {
          const [s, t] = texelToParam(part, px, py);
          sample.part = part;
          sample.s = s;
          sample.t = t;
          sample.px = px;
          sample.py = py;
          part.pos(s, t, NEUTRAL_SHAPE, sample.p);
          partNormal(part, s, t, NEUTRAL_SHAPE, sample.n);
          let c: RGB = base;
          markings.forEach((m, mi) => {
            if (hits(m, sample)) c = markRgb[mi];
          });
          if (isEarRim(sample)) c = earRim;
          if (isInnerEar(sample)) c = innerEar;
          img.data.set([...c, 255], (py * ATLAS_SIZE + px) * 4);
        }
      }
    }
  }

  ctx.putImageData(img, 0, 0);
}

/** 把任意图片（手绘 PNG）吸附到调色板，保证是干净的像素画 */
export function snapToPalette(canvas: HTMLCanvasElement, palette: string[]) {
  if (!palette.length) return;
  const pal = palette.map(hexToRgb);
  const ctx = canvas.getContext('2d')!;
  const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < img.data.length; i += 4) {
    const c = nearestPaletteColor([img.data[i], img.data[i + 1], img.data[i + 2]], pal);
    img.data.set(c, i);
    img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}

export async function loadCoatImage(url: string, canvas: HTMLCanvasElement) {
  const img = new Image();
  img.src = url;
  await img.decode();
  canvas.width = ATLAS_SIZE;
  canvas.height = ATLAS_SIZE;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(img, 0, 0, ATLAS_SIZE, ATLAS_SIZE);
}

export function makeCoatTexture(canvas: HTMLCanvasElement): CanvasTexture {
  const tex = new CanvasTexture(canvas);
  tex.magFilter = NearestFilter;
  tex.minFilter = NearestFilter;
  tex.generateMipmaps = false;
  tex.colorSpace = SRGBColorSpace;
  return tex;
}
