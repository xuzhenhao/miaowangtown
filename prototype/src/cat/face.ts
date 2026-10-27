import {
  BufferGeometry,
  CanvasTexture,
  Mesh,
  MeshBasicMaterial,
  NearestFilter,
  PlaneGeometry,
  Quaternion,
  SRGBColorSpace,
  Vector3,
} from 'three';
import { headPos, muzzlePos, partByName, partNormal } from './parts';
import { SHAPE_KEYS, type ShapeParams } from './shape';
import type { CatSkeleton } from './skeleton';
import type { PetDNA } from './dna';
import type { FaceAnchorsMap } from './loadBaseGlb';

/**
 * 脸部 = 手绘像素贴图集 + 贴在头骨上的小面片（灵动翡翠大眼 + 粉鼻嘴 + 像素白胡须）。
 * 表情靠切换贴图格子，而不是网格形变，所以神态在像素尺度下始终清晰。
 * 当使用 Blender `cat_base.glb` 母版时，五官面片位置从 glTF extras 导出的 `faceAnchors` 读取，
 * 并在形态键变化时按对应顶点的 MorphTarget 位移自动修正锚点位置。
 */

export const EYE_STATES = ['open', 'closed', 'happy', 'sleepy', 'surprised'] as const;
export type EyeState = (typeof EYE_STATES)[number];
export const MOUTH_STATES = ['closed', 'open', 'tongue'] as const;
export type MouthState = (typeof MOUTH_STATES)[number];

function scaleHex(hex: string, factor: number): string {
  const h = hex.replace('#', '');
  const r = Math.min(255, Math.max(0, Math.round(parseInt(h.slice(0, 2), 16) * factor)));
  const g = Math.min(255, Math.max(0, Math.round(parseInt(h.slice(2, 4), 16) * factor)));
  const b = Math.min(255, Math.max(0, Math.round(parseInt(h.slice(4, 6), 16) * factor)));
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}

// k=眼线描边 r=深翠外虹膜环 i=翡翠主虹膜 g=下沿亮翠月牙 p=竖瞳 w=纯白高光 .=透明
const EYE_ART: Record<EyeState, string[]> = {
  open: [
    '..............',
    '...kkkkkkkk...',
    '..kkkkkkkkkk..',
    '.krrriiiirrrk.',
    '.krwwiiiiiirk.',
    '.krwwippppiik.',
    '.kriippppppik.',
    '.kriippppppik.',
    '.kriiippppiik.',
    '.krrggippigwk.',
    '..krrgggggrk..',
    '...kkkkkkkk...',
    '..............',
    '..............',
  ],
  closed: [
    '..............',
    '..............',
    '..............',
    '..............',
    '..............',
    '..............',
    '.kk........kk.',
    '..kkkkkkkkkk..',
    '..............',
    '..............',
    '..............',
    '..............',
    '..............',
    '..............',
  ],
  happy: [
    '..............',
    '..............',
    '..............',
    '..............',
    '...kkkkkkkk...',
    '..kk......kk..',
    '.kk........kk.',
    '..............',
    '..............',
    '..............',
    '..............',
    '..............',
    '..............',
    '..............',
  ],
  sleepy: [
    '..............',
    '..............',
    '..............',
    '..............',
    '.kkkkkkkkkkkk.',
    '.kriippppppik.',
    '.kriippppppik.',
    '.krrggippigwk.',
    '..krrgggggrk..',
    '...kkkkkkkk...',
    '..............',
    '..............',
    '..............',
    '..............',
  ],
  surprised: [
    '..............',
    '...kkkkkkkk...',
    '..krrrrrrrrk..',
    '.kriippppppik.',
    '.krpwppppppik.',
    '.krppppppppik.',
    '.krppppppppik.',
    '.krpppppppwik.',
    '.krggppppggik.',
    '..krrrrrrrrk..',
    '...kkkkkkkk...',
    '..............',
    '..............',
    '..............',
  ],
};

// n=鼻头主色 h=鼻头高光 k=嘴线 m=口腔 t=舌头
const MOUTH_ART: Record<MouthState, string[]> = {
  closed: [
    '.............',
    '...nnnnnnn...',
    '....nhhhn....',
    '.....nnn.....',
    '......n......',
    '......k......',
    '..k...k...k..',
    '...kkk.kkk...',
    '.............',
    '.............',
  ],
  open: [
    '.............',
    '...nnnnnnn...',
    '....nhhhn....',
    '.....nnn.....',
    '......n......',
    '......k......',
    '....kkkkk....',
    '...kmmmmmk...',
    '....kkkkk....',
    '.............',
  ],
  tongue: [
    '.............',
    '...nnnnnnn...',
    '....nhhhn....',
    '.....nnn.....',
    '......n......',
    '......k......',
    '...kkk.kkk...',
    '....ttttt....',
    '....ttttt....',
    '.....ttt.....',
  ],
};

// 贴在脸颊表面的像素白胡须（两根纯白像素胡须 w 配深褐描边衬底 k，自然贴合脸颊不悬空）
const WHISKER_STATES = ['default'] as const;
type WhiskerState = (typeof WHISKER_STATES)[number];
const WHISKER_ART: Record<WhiskerState, string[]> = {
  default: [
    '............',
    '..kkkkkkkk..',
    '.wwwwwwwwww.',
    '..kkkkkkkk..',
    '............',
    '...kkkkkkk..',
    '..wwwwwwwww.',
    '...kkkkkkk..',
  ],
};

function drawAtlas<S extends string>(
  states: readonly S[],
  art: Record<S, string[]>,
  colors: Record<string, string>,
): HTMLCanvasElement {
  const w = art[states[0]][0].length;
  const h = art[states[0]].length;
  const canvas = document.createElement('canvas');
  canvas.width = w * states.length;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  states.forEach((st, ci) => {
    art[st].forEach((row, y) => {
      [...row].forEach((ch, x) => {
        if (ch === '.') return;
        ctx.fillStyle = colors[ch] ?? '#ff00ff';
        ctx.fillRect(ci * w + x, y, 1, 1);
      });
    });
  });
  return canvas;
}

function pixelTexture(canvas: HTMLCanvasElement, cells: number): CanvasTexture {
  const tex = new CanvasTexture(canvas);
  tex.magFilter = NearestFilter;
  tex.minFilter = NearestFilter;
  tex.generateMipmaps = false;
  tex.colorSpace = SRGBColorSpace;
  tex.repeat.set(1 / cells, 1);
  return tex;
}

const EYE_THETA = 0.42;
const EYE_PHI = 0.47;
const EYE_SIZE = 0.176;
const MOUTH_W = 0.156;
const MOUTH_PHI = 0.43;
const WHISKER_W = 0.145;
const WHISKER_H = (WHISKER_W * 8) / 12;
const DECAL_LIFT = 0.012;

export class FaceRig {
  readonly eyeMat = new MeshBasicMaterial({ alphaTest: 0.5, polygonOffset: true, polygonOffsetFactor: -2 });
  readonly mouthMat = new MeshBasicMaterial({ alphaTest: 0.5, polygonOffset: true, polygonOffsetFactor: -2 });
  readonly whiskerMat = new MeshBasicMaterial({
    alphaTest: 0.5,
    polygonOffset: true,
    polygonOffsetFactor: -2,
  });
  readonly eyes: [Mesh, Mesh];
  readonly mouth: Mesh;
  readonly whiskers: [Mesh, Mesh];
  eyeState: EyeState = 'open';
  mouthState: MouthState = 'closed';

  constructor(
    private sk: CatSkeleton,
    private anchors?: FaceAnchorsMap,
    private geo?: BufferGeometry,
  ) {
    const eyeGeo = new PlaneGeometry(EYE_SIZE, EYE_SIZE);
    const mouthGeo = new PlaneGeometry(MOUTH_W, (MOUTH_W * 10) / 13);
    const whiskerGeoL = new PlaneGeometry(WHISKER_W, WHISKER_H);
    const whiskerGeoR = new PlaneGeometry(WHISKER_W, WHISKER_H);
    const uvR = whiskerGeoR.attributes.uv;
    for (let i = 0; i < uvR.count; i++) {
      uvR.setX(i, 1 - uvR.getX(i));
    }
    this.eyes = [new Mesh(eyeGeo, this.eyeMat), new Mesh(eyeGeo, this.eyeMat)];
    this.mouth = new Mesh(mouthGeo, this.mouthMat);
    this.whiskers = [new Mesh(whiskerGeoL, this.whiskerMat), new Mesh(whiskerGeoR, this.whiskerMat)];
    for (const m of [...this.eyes, this.mouth, ...this.whiskers]) sk.bones.head.add(m);
  }

  private vertexMorphDelta(vi: number, k: ShapeParams, out = new Vector3()): Vector3 {
    out.set(0, 0, 0);
    const morphs = this.geo?.morphAttributes.position;
    if (!morphs) return out;
    SHAPE_KEYS.forEach((key, ki) => {
      const weight = k[key] ?? 0;
      const attr = morphs[ki];
      if (!attr || Math.abs(weight) < 1e-5 || vi >= attr.count) return;
      out.x += attr.getX(vi) * weight;
      out.y += attr.getY(vi) * weight;
      out.z += attr.getZ(vi) * weight;
    });
    return out;
  }

  applyColors(dna: PetDNA) {
    const outline = '#1b110b';
    const iris = dna.eyes.iris;
    const irisRim = scaleHex(iris, 0.58);
    const irisGlow = scaleHex(iris, 1.24);
    const nose = dna.nose ?? '#c85a48';
    const noseHighlight = scaleHex(nose, 1.2);
    this.eyeMat.map?.dispose();
    this.mouthMat.map?.dispose();
    this.whiskerMat.map?.dispose();
    this.eyeMat.map = pixelTexture(
      drawAtlas(EYE_STATES, EYE_ART, {
        k: outline,
        r: irisRim,
        i: iris,
        g: irisGlow,
        p: dna.eyes.pupil ?? '#151e12',
        w: '#ffffff',
      }),
      EYE_STATES.length,
    );
    this.mouthMat.map = pixelTexture(
      drawAtlas(MOUTH_STATES, MOUTH_ART, {
        k: outline,
        n: nose,
        h: noseHighlight,
        m: '#5a2626',
        t: '#e57d8e',
      }),
      MOUTH_STATES.length,
    );
    this.whiskerMat.map = pixelTexture(
      drawAtlas(WHISKER_STATES, WHISKER_ART, {
        w: '#ffffff',
        k: '#231710',
      }),
      1,
    );
    this.eyeMat.needsUpdate = true;
    this.mouthMat.needsUpdate = true;
    this.whiskerMat.needsUpdate = true;
    this.setEyes(this.eyeState);
    this.setMouth(this.mouthState);
  }

  /**
   * 体型变化后重新把面片贴到头/嘴套表面：
   * - 若加载自 Blender GLB 母版，直接读取 `faceAnchors` 并叠加对应顶点的形态键（MorphTargets）位移；
   * - 若为程序化后备模式，回退到参数曲面求值。
   */
  applyShape(k: ShapeParams) {
    const headRest = this.sk.restWorld.head;
    const p = new Vector3();
    const n = new Vector3();
    const q = new Quaternion();
    const zAxis = new Vector3(0, 0, 1);

    if (this.anchors) {
      const dL = this.vertexMorphDelta(this.anchors.eyeL.vertexIndex, k, new Vector3());
      const dR = this.vertexMorphDelta(this.anchors.eyeR.vertexIndex, k, new Vector3());
      const eyeDx = 0.5 * (Math.abs(dL.x) + Math.abs(dR.x));
      const eyeDy = 0.5 * (dL.y + dR.y);
      const eyeDz = 0.5 * (dL.z + dR.z);

      (
        [
          ['eyeL', 1, 0],
          ['eyeR', -1, 1],
        ] as const
      ).forEach(([key, side, i]) => {
        const a = this.anchors![key];
        p.fromArray(a.pos).add(new Vector3(side * eyeDx, eyeDy, eyeDz));
        n.fromArray(a.normal).normalize();
        const eye = this.eyes[i];
        eye.position.copy(p).addScaledVector(n, DECAL_LIFT).sub(headRest);
        eye.quaternion.copy(q.setFromUnitVectors(zAxis, n));
      });

      const wDL = this.vertexMorphDelta(this.anchors.whiskerL.vertexIndex, k, new Vector3());
      const wDR = this.vertexMorphDelta(this.anchors.whiskerR.vertexIndex, k, new Vector3());
      const wDx = 0.5 * (Math.abs(wDL.x) + Math.abs(wDR.x));
      const wDy = 0.5 * (wDL.y + wDR.y);
      const wDz = 0.5 * (wDL.z + wDR.z);

      (
        [
          ['whiskerL', 1, 0],
          ['whiskerR', -1, 1],
        ] as const
      ).forEach(([key, side, i]) => {
        const a = this.anchors![key];
        p.fromArray(a.pos).add(new Vector3(side * wDx, wDy, wDz));
        n.fromArray(a.normal).normalize();
        const whisker = this.whiskers[i];
        whisker.position.copy(p).addScaledVector(n, DECAL_LIFT * 1.1).sub(headRest);
        whisker.quaternion.copy(q.setFromUnitVectors(zAxis, n));
      });

      const mA = this.anchors.mouth;
      const mD = this.vertexMorphDelta(mA.vertexIndex, k, new Vector3());
      p.fromArray(mA.pos).add(new Vector3(0, mD.y, mD.z));
      n.fromArray(mA.normal).normalize();
      this.mouth.position.copy(p).addScaledVector(n, DECAL_LIFT).sub(headRest);
      this.mouth.quaternion.copy(q.setFromUnitVectors(zAxis, n));
      return;
    }

    const headPart = partByName('head');
    const muzzlePart = partByName('muzzle');

    [1, -1].forEach((side, i) => {
      const s = 0.5 + (side * EYE_THETA) / (Math.PI * 2);
      headPos(s, EYE_PHI, k, p);
      partNormal(headPart, s, EYE_PHI, k, n);
      n.lerp(new Vector3(side * 0.22, 0.04, 0.96).normalize(), 0.35).normalize();
      const eye = this.eyes[i];
      eye.position.copy(p).addScaledVector(n, DECAL_LIFT).sub(headRest);
      eye.quaternion.copy(q.setFromUnitVectors(zAxis, n));

      const ws = 0.5 + (side * 0.78) / (Math.PI * 2);
      headPos(ws, 0.62, k, p);
      partNormal(headPart, ws, 0.62, k, n);
      n.lerp(new Vector3(side * 0.65, -0.04, 0.76).normalize(), 0.5).normalize();
      const whisker = this.whiskers[i];
      whisker.position.copy(p).addScaledVector(n, DECAL_LIFT * 1.1).sub(headRest);
      whisker.quaternion.copy(q.setFromUnitVectors(zAxis, n));
    });

    muzzlePos(0.5, MOUTH_PHI, k, p);
    partNormal(muzzlePart, 0.5, MOUTH_PHI, k, n);
    n.lerp(new Vector3(0, 0, 1), 0.55).normalize();
    this.mouth.position.copy(p).addScaledVector(n, DECAL_LIFT).sub(headRest);
    this.mouth.quaternion.copy(q.setFromUnitVectors(zAxis, n));
  }

  setEyes(state: EyeState) {
    this.eyeState = state;
    if (this.eyeMat.map) this.eyeMat.map.offset.x = EYE_STATES.indexOf(state) / EYE_STATES.length;
  }

  setMouth(state: MouthState) {
    this.mouthState = state;
    if (this.mouthMat.map) this.mouthMat.map.offset.x = MOUTH_STATES.indexOf(state) / MOUTH_STATES.length;
  }
}
