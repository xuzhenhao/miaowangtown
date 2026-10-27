import { CanvasTexture, NearestFilter, SRGBColorSpace, Vector3 } from 'three';
import { ATLAS_SIZE, PARTS, partNormal, texelToParam, type PartDef } from './parts';
import { NEUTRAL_SHAPE } from './shape';
import type { Marking, MarkingFilter, PetDNA } from './dna';

type RGB = [number, number, number];

function hexToRgb(hex: string): RGB {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
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

interface Sample {
  part: PartDef;
  s: number;
  t: number;
  p: Vector3;
  n: Vector3;
}

function passFilter(f: MarkingFilter, x: Sample): boolean {
  if (f.parts && !f.parts.includes(x.part.name)) return false;
  const { p } = x;
  if (f.minX !== undefined && p.x < f.minX) return false;
  if (f.maxX !== undefined && p.x > f.maxX) return false;
  if (f.minY !== undefined && p.y < f.minY) return false;
  if (f.maxY !== undefined && p.y > f.maxY) return false;
  if (f.minZ !== undefined && p.z < f.minZ) return false;
  if (f.maxZ !== undefined && p.z > f.maxZ) return false;
  return true;
}

function hits(m: Marking, x: Sample): boolean {
  if (!passFilter(m, x)) return false;
  const jitter = (m.noise ?? 0) * fbm(x.p, m.noiseScale ?? 9);
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
      const coord = x.p[m.axis] + jitter * 0.08;
      const phase = Math.sin(coord * m.frequency * Math.PI * 2);
      return phase > 1 - 2 * m.width;
    }
  }
}

function isInnerEar(x: Sample): boolean {
  if (x.part.name !== 'earL' && x.part.name !== 'earR') return false;
  const th = (x.s - 0.5) * Math.PI * 2;
  return Math.abs(th) < 0.85 && x.t > 0.12 && x.t < 0.8;
}

function nearest(c: RGB, palette: RGB[]): RGB {
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

/** 把 3D 空间描述的印记烘焙到母版非镜像 UV 图集上 */
export function bakeCoat(dna: PetDNA, canvas: HTMLCanvasElement) {
  canvas.width = ATLAS_SIZE;
  canvas.height = ATLAS_SIZE;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(ATLAS_SIZE, ATLAS_SIZE);
  const base = hexToRgb(dna.coat.base);
  const markings = dna.coat.markings ?? [];
  const markRgb = markings.map((m) => hexToRgb(m.color));
  const innerEar = hexToRgb(dna.earInner ?? '#d9958f');
  const sample: Sample = { part: PARTS[0], s: 0, t: 0, p: new Vector3(), n: new Vector3() };

  for (let i = 0; i < img.data.length; i += 4) {
    img.data.set([...base, 255], i);
  }

  for (const part of PARTS) {
    const [rx, ry, rw, rh] = part.rect;
    for (let py = ry; py < ry + rh; py++) {
      for (let px = rx; px < rx + rw; px++) {
        const [s, t] = texelToParam(part, px, py);
        sample.part = part;
        sample.s = s;
        sample.t = t;
        part.pos(s, t, NEUTRAL_SHAPE, sample.p);
        partNormal(part, s, t, NEUTRAL_SHAPE, sample.n);
        let c: RGB = base;
        markings.forEach((m, mi) => {
          if (hits(m, sample)) c = markRgb[mi];
        });
        if (isInnerEar(sample)) c = innerEar;
        img.data.set([...c, 255], (py * ATLAS_SIZE + px) * 4);
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
    const c = nearest([img.data[i], img.data[i + 1], img.data[i + 2]], pal);
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
