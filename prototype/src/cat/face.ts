import {
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
import type { ShapeParams } from './shape';
import type { CatSkeleton } from './skeleton';
import type { PetDNA } from './dna';

/**
 * 脸部 = 手绘像素贴图集 + 贴在头骨上的小面片。
 * 表情靠切换贴图格子，而不是网格形变，所以神态在像素尺度下始终清晰。
 */

export const EYE_STATES = ['open', 'closed', 'happy', 'sleepy', 'surprised'] as const;
export type EyeState = (typeof EYE_STATES)[number];
export const MOUTH_STATES = ['closed', 'open', 'tongue'] as const;
export type MouthState = (typeof MOUTH_STATES)[number];

// k=描边 i=虹膜 p=瞳孔 w=高光 .=透明
const EYE_ART: Record<EyeState, string[]> = {
  open: [
    '..........',
    '...kkkk...',
    '..kiiiik..',
    '.kiipiiik.',
    '.kiwppiik.',
    '.kiippiik.',
    '.kiippiik.',
    '..kiipik..',
    '...kkkk...',
    '..........',
  ],
  closed: [
    '..........',
    '..........',
    '..........',
    '..........',
    '..........',
    '.k......k.',
    '..kkkkkk..',
    '..........',
    '..........',
    '..........',
  ],
  happy: [
    '..........',
    '..........',
    '..........',
    '...kkkk...',
    '..k....k..',
    '.k......k.',
    '..........',
    '..........',
    '..........',
    '..........',
  ],
  sleepy: [
    '..........',
    '..........',
    '..........',
    '.kkkkkkkk.',
    '.kiippiik.',
    '.kiippiik.',
    '..kiipik..',
    '...kkkk...',
    '..........',
    '..........',
  ],
  surprised: [
    '...kkkk...',
    '..kiiiik..',
    '.kipppiik.',
    '.kpwpppik.',
    '.kpppppik.',
    '.kpppppik.',
    '.kipppiik.',
    '..kiiiik..',
    '...kkkk...',
    '..........',
  ],
};

// n=鼻子 k=线条 m=口腔 t=舌头
const MOUTH_ART: Record<MouthState, string[]> = {
  closed: [
    '...........',
    '...nnnnn...',
    '....nnn....',
    '.....k.....',
    '..k..k..k..',
    '...kk.kk...',
    '...........',
    '...........',
  ],
  open: [
    '...........',
    '...nnnnn...',
    '....nnn....',
    '.....k.....',
    '...kkkkk...',
    '...kmmmk...',
    '....kkk....',
    '...........',
  ],
  tongue: [
    '...........',
    '...nnnnn...',
    '....nnn....',
    '.....k.....',
    '...kk.kk...',
    '....ttt....',
    '....ttt....',
    '.....t.....',
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
const EYE_PHI = 0.45;
const EYE_SIZE = 0.15;
const MOUTH_W = 0.165;
const MOUTH_PHI = 0.4;
const DECAL_LIFT = 0.012;

export class FaceRig {
  readonly eyeMat = new MeshBasicMaterial({ alphaTest: 0.5, polygonOffset: true, polygonOffsetFactor: -2 });
  readonly mouthMat = new MeshBasicMaterial({ alphaTest: 0.5, polygonOffset: true, polygonOffsetFactor: -2 });
  readonly eyes: [Mesh, Mesh];
  readonly mouth: Mesh;
  eyeState: EyeState = 'open';
  mouthState: MouthState = 'closed';

  constructor(private sk: CatSkeleton) {
    const eyeGeo = new PlaneGeometry(EYE_SIZE, EYE_SIZE);
    const mouthGeo = new PlaneGeometry(MOUTH_W, (MOUTH_W * 8) / 11);
    this.eyes = [new Mesh(eyeGeo, this.eyeMat), new Mesh(eyeGeo, this.eyeMat)];
    this.mouth = new Mesh(mouthGeo, this.mouthMat);
    for (const m of [...this.eyes, this.mouth]) sk.bones.head.add(m);
  }

  applyColors(dna: PetDNA) {
    const outline = '#2a1d16';
    this.eyeMat.map?.dispose();
    this.mouthMat.map?.dispose();
    this.eyeMat.map = pixelTexture(
      drawAtlas(EYE_STATES, EYE_ART, { k: outline, i: dna.eyes.iris, p: dna.eyes.pupil ?? '#1a120e', w: '#ffffff' }),
      EYE_STATES.length,
    );
    this.mouthMat.map = pixelTexture(
      drawAtlas(MOUTH_STATES, MOUTH_ART, { k: outline, n: dna.nose ?? '#d98c8c', m: '#5a2626', t: '#e57d8e' }),
      MOUTH_STATES.length,
    );
    this.eyeMat.needsUpdate = true;
    this.mouthMat.needsUpdate = true;
    this.setEyes(this.eyeState);
    this.setMouth(this.mouthState);
  }

  /** 体型变化后重新把面片贴到头/嘴套表面 */
  applyShape(k: ShapeParams) {
    const headRest = this.sk.restWorld.head;
    const headPart = partByName('head');
    const muzzlePart = partByName('muzzle');
    const p = new Vector3();
    const n = new Vector3();
    const q = new Quaternion();
    const zAxis = new Vector3(0, 0, 1);
    [1, -1].forEach((side, i) => {
      const s = 0.5 + (side * EYE_THETA) / (Math.PI * 2);
      headPos(s, EYE_PHI, k, p);
      partNormal(headPart, s, EYE_PHI, k, n);
      const eye = this.eyes[i];
      eye.position.copy(p).addScaledVector(n, DECAL_LIFT).sub(headRest);
      eye.quaternion.copy(q.setFromUnitVectors(zAxis, n));
    });
    muzzlePos(0.5, MOUTH_PHI, k, p);
    partNormal(muzzlePart, 0.5, MOUTH_PHI, k, n);
    n.lerp(new Vector3(0, 0, 1), 0.5).normalize();
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
