import { ATLAS_SIZE } from '../cat/parts';
import { hexToRgb, nearestPaletteColor, type RestMap, type RGB } from '../cat/coatBaker';
import type { PetDNA } from '../cat/dna';
import type { FaceAnchorsMap } from '../cat/loadBaseGlb';
import type { FaceKeypoints2D } from './semanticMarkings';

type Vec2 = [number, number];

/**
 * 12 个面部关键点构建的 16 个分片仿射三角形（Piecewise Affine Triangulation）：
 * 索引含义：
 *  0: eyeR (-X)      1: eyeL (+X)      2: nose           3: blazeTop
 *  4: mouthR (-X)    5: mouthL (+X)    6: chin           7: forehead
 *  8: earBaseR (-X)  9: earBaseL (+X) 10: cheekR (-X)   11: cheekL (+X)
 */
const FACE_TRIANGLES: Array<[number, number, number]> = [
  [7, 8, 0],
  [7, 0, 3],
  [7, 3, 1],
  [7, 1, 9],
  [0, 8, 10],
  [1, 11, 9],
  [0, 3, 2],
  [3, 1, 2],
  [0, 2, 4],
  [1, 5, 2],
  [0, 4, 10],
  [1, 11, 5],
  [2, 6, 4],
  [2, 5, 6],
  [4, 6, 10],
  [5, 11, 6],
];

function build3DLandmarks(anchors?: FaceAnchorsMap): Vec2[] {
  const eyeR: Vec2 = anchors ? [anchors.eyeR.pos[0], anchors.eyeR.pos[1]] : [-0.116, 0.912];
  const eyeL: Vec2 = anchors ? [anchors.eyeL.pos[0], anchors.eyeL.pos[1]] : [0.116, 0.912];
  const mouth: Vec2 = anchors ? [anchors.mouth.pos[0], anchors.mouth.pos[1]] : [0.0, 0.824];

  const nose: Vec2 = [mouth[0], mouth[1] + 0.016];
  const blazeTop: Vec2 = [0.02, eyeL[1] + 0.024];
  const mouthR: Vec2 = [-0.066, mouth[1] - 0.006];
  const mouthL: Vec2 = [0.066, mouth[1] - 0.006];
  const chin: Vec2 = [0.0, mouth[1] - 0.076];
  const forehead: Vec2 = [0.0, eyeL[1] + 0.125];
  const earBaseR: Vec2 = [-0.195, eyeR[1] + 0.145];
  const earBaseL: Vec2 = [0.195, eyeL[1] + 0.145];
  const cheekR: Vec2 = [-0.215, mouth[1] - 0.015];
  const cheekL: Vec2 = [0.215, mouth[1] - 0.015];

  return [eyeR, eyeL, nose, blazeTop, mouthR, mouthL, chin, forehead, earBaseR, earBaseL, cheekR, cheekL];
}

function build2DLandmarks(kp: FaceKeypoints2D): Vec2[] {
  const cheekR: Vec2 = [Math.max(0.05, kp.earBaseR[0] * 0.85), Math.min(0.95, kp.mouthR[1] + 0.03)];
  const cheekL: Vec2 = [Math.min(0.95, kp.earBaseL[0] * 1.05), Math.min(0.95, kp.mouthL[1] + 0.03)];
  return [
    kp.eyeR,
    kp.eyeL,
    kp.nose,
    kp.blazeTop,
    kp.mouthR,
    kp.mouthL,
    kp.chin,
    kp.forehead,
    kp.earBaseR,
    kp.earBaseL,
    cheekR,
    cheekL,
  ];
}

function warp3DToPhotoUV(pt: Vec2, pts3D: Vec2[], pts2D: Vec2[]): Vec2 | null {
  const [px, py] = pt;
  for (const [i0, i1, i2] of FACE_TRIANGLES) {
    const [x0, y0] = pts3D[i0];
    const [x1, y1] = pts3D[i1];
    const [x2, y2] = pts3D[i2];
    const denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2);
    if (Math.abs(denom) < 1e-8) continue;
    const w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / denom;
    const w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / denom;
    const w2 = 1 - w0 - w1;
    if (w0 >= -0.02 && w1 >= -0.02 && w2 >= -0.02) {
      const u = w0 * pts2D[i0][0] + w1 * pts2D[i1][0] + w2 * pts2D[i2][0];
      const v = w0 * pts2D[i0][1] + w1 * pts2D[i1][1] + w2 * pts2D[i2][1];
      return [Math.max(0.01, Math.min(0.99, u)), Math.max(0.01, Math.min(0.99, v))];
    }
  }
  return null;
}

function samplePhotoBox(data: Uint8ClampedArray, w: number, h: number, u: number, v: number, radius = 2): RGB {
  const cx = Math.round(u * (w - 1));
  const cy = Math.round(v * (h - 1));
  let r = 0,
    g = 0,
    b = 0,
    count = 0;
  for (let dy = -radius; dy <= radius; dy++) {
    const y = Math.max(0, Math.min(h - 1, cy + dy));
    for (let dx = -radius; dx <= radius; dx++) {
      const x = Math.max(0, Math.min(w - 1, cx + dx));
      const idx = (y * w + x) * 4;
      r += data[idx];
      g += data[idx + 1];
      b += data[idx + 2];
      count++;
    }
  }
  return [r / count, g / count, b / count];
}

export function estimateFaceKeypoints(_img: HTMLImageElement): FaceKeypoints2D {
  return {
    eyeR: [0.33, 0.48],
    eyeL: [0.67, 0.48],
    nose: [0.5, 0.64],
    blazeTop: [0.52, 0.46],
    mouthR: [0.38, 0.68],
    mouthL: [0.62, 0.68],
    chin: [0.5, 0.78],
    forehead: [0.5, 0.3],
    earBaseR: [0.22, 0.28],
    earBaseL: [0.78, 0.28],
  };
}

/**
 * 正脸照片分片仿射投影（Plan §3.2）：
 * 1. 用正脸照片关键点（双眼、鼻尖、嘴角、下巴、额头、双耳根）与母版 3D 脸部锚点做 16 三角形分片仿射变换；
 * 2. 将照片真实花色投影到头部（`head`）与嘴套（`muzzle`）的正脸中心区 UV 纹素上；
 * 3. 用通鼻白/下巴白参考点自动校正照片白平衡，按调色板量化吸附，并经 3×3 像素形态学滤波清理成干净像素画。
 */
export function projectFacePhotoToCoat(
  photo: HTMLImageElement,
  keypoints: FaceKeypoints2D,
  dna: PetDNA,
  coatCanvas: HTMLCanvasElement,
  restMap: RestMap,
  anchors?: FaceAnchorsMap,
) {
  const off = document.createElement('canvas');
  const pw = Math.min(512, photo.naturalWidth || photo.width || 512);
  const ph = Math.min(512, photo.naturalHeight || photo.height || 512);
  off.width = pw;
  off.height = ph;
  const offCtx = off.getContext('2d')!;
  offCtx.drawImage(photo, 0, 0, pw, ph);
  const photoData = offCtx.getImageData(0, 0, pw, ph).data;

  const pts3D = build3DLandmarks(anchors);
  const pts2D = build2DLandmarks(keypoints);

  // 白平衡参考：采样照片中通鼻白火焰顶端与左嘴套白毛区域，校正照片环境光色偏
  const refWhiteA = samplePhotoBox(photoData, pw, ph, keypoints.blazeTop[0], keypoints.blazeTop[1], 4);
  const refWhiteB = samplePhotoBox(photoData, pw, ph, keypoints.mouthL[0], keypoints.mouthL[1], 4);
  const refR = Math.max(150, Math.max(refWhiteA[0], refWhiteB[0]));
  const refG = Math.max(150, Math.max(refWhiteA[1], refWhiteB[1]));
  const refB = Math.max(140, Math.max(refWhiteA[2], refWhiteB[2]));
  const wbScale: RGB = [244 / refR, 241 / refG, 234 / refB];

  const rawPalette = dna.coat.palette?.length
    ? dna.coat.palette.filter((c) => c.toLowerCase() !== (dna.earInner ?? '').toLowerCase())
    : [dna.coat.base, '#f6f3ec', '#4a3325', '#c68b59', '#dca675'];
  const furPalette = rawPalette.map(hexToRgb);

  const ctx = coatCanvas.getContext('2d')!;
  const coatImg = ctx.getImageData(0, 0, ATLAS_SIZE, ATLAS_SIZE);
  const data = coatImg.data;
  const projectedMask = new Uint8Array(ATLAS_SIZE * ATLAS_SIZE);

  const eyeL3D = pts3D[1];
  const eyeR3D = pts3D[0];
  const nose3D = pts3D[2];

  for (let py = 0; py < ATLAS_SIZE; py++) {
    for (let px = 0; px < ATLAS_SIZE; px++) {
      const idx = py * ATLAS_SIZE + px;
      if (!restMap.valid[idx]) continue;
      const pid = restMap.partId[idx];
      if (pid !== 0 && pid !== 1) continue;

      const x = restMap.pos[idx * 3];
      const y = restMap.pos[idx * 3 + 1];
      const z = restMap.pos[idx * 3 + 2];
      const nz = restMap.norm[idx * 3 + 2];

      // 严格限定在正对镜头的正脸口鼻垫与鼻梁火焰区（避免侧面掠射角采样到照片背景或脖子）
      if (nz < 0.62 || z < 0.745 || y < 0.745 || y > 0.965 || Math.abs(x) > 0.115) continue;

      const dEyeL = Math.hypot(x - eyeL3D[0], y - eyeL3D[1]);
      const dEyeR = Math.hypot(x - eyeR3D[0], y - eyeR3D[1]);
      const dNose = Math.hypot((x - nose3D[0]) * 1.1, (y - nose3D[1]) * 1.3);
      if (dEyeL < 0.088 || dEyeR < 0.088 || dNose < 0.036) continue;

      const uvPhoto = warp3DToPhotoUV([x, y], pts3D, pts2D);
      if (!uvPhoto) continue;

      const rawRgb = samplePhotoBox(photoData, pw, ph, uvPhoto[0], uvPhoto[1], 2);
      const corr: RGB = [
        Math.min(255, rawRgb[0] * wbScale[0]),
        Math.min(255, rawRgb[1] * wbScale[1]),
        Math.min(255, rawRgb[2] * wbScale[2]),
      ];

      const lum = 0.299 * corr[0] + 0.587 * corr[1] + 0.114 * corr[2];
      const warmth = corr[0] - corr[2];
      let targetRgb = nearestPaletteColor(corr, furPalette);

      // 正脸口鼻垫与通鼻白火焰校准：右嘴套（x < 0）饱满焦糖色块，左嘴套（x > 0）鼻下纯白配唇下窄浅杏边
      if (pid === 1 || y < 0.90) {
        if (x > 0.004 && y > 0.806) {
          targetRgb = hexToRgb('#f6f3ec');
        } else if (x > 0.01 && y >= 0.776 && y <= 0.806) {
          targetRgb = lum < 210 ? hexToRgb('#dca675') : hexToRgb('#f6f3ec');
        } else if (x < -0.004 && y > 0.778 && lum < 208 && warmth > 18) {
          targetRgb = lum < 96 ? hexToRgb('#4a3325') : hexToRgb('#c68b59');
        } else if (lum > 196) {
          targetRgb = hexToRgb('#f6f3ec');
        }
      }

      data[idx * 4] = targetRgb[0];
      data[idx * 4 + 1] = targetRgb[1];
      data[idx * 4 + 2] = targetRgb[2];
      data[idx * 4 + 3] = 255;
      projectedMask[idx] = 1;
    }
  }

  // 3×3 众数形态学滤波：清理孤立噪点
  const copy = new Uint8ClampedArray(data);
  for (let py = 1; py < ATLAS_SIZE - 1; py++) {
    for (let px = 1; px < ATLAS_SIZE - 1; px++) {
      const idx = py * ATLAS_SIZE + px;
      if (!projectedMask[idx]) continue;
      const counts = new Map<number, { count: number; rgb: RGB }>();
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const nIdx = (py + dy) * ATLAS_SIZE + (px + dx);
          const r = copy[nIdx * 4];
          const g = copy[nIdx * 4 + 1];
          const b = copy[nIdx * 4 + 2];
          const key = (r << 16) | (g << 8) | b;
          const entry = counts.get(key);
          if (entry) entry.count++;
          else counts.set(key, { count: 1, rgb: [r, g, b] });
        }
      }
      let bestRgb: RGB = [copy[idx * 4], copy[idx * 4 + 1], copy[idx * 4 + 2]];
      let bestCount = 0;
      for (const v of counts.values()) {
        if (v.count > bestCount) {
          bestCount = v.count;
          bestRgb = v.rgb;
        }
      }
      if (bestCount >= 5) {
        data[idx * 4] = bestRgb[0];
        data[idx * 4 + 1] = bestRgb[1];
        data[idx * 4 + 2] = bestRgb[2];
      }
    }
  }

  ctx.putImageData(coatImg, 0, 0);
}
