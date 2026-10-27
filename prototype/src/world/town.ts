import {
  BoxGeometry,
  CanvasTexture,
  Color,
  CylinderGeometry,
  DirectionalLight,
  DoubleSide,
  Group,
  HemisphereLight,
  LinearFilter,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  PointLight,
  RepeatWrapping,
  SRGBColorSpace,
  Scene,
  SphereGeometry,
  TorusGeometry,
  Vector3,
  type BufferGeometry,
  type Material,
  type Texture,
} from 'three';
import type { WorldNav } from '../anim/brain';

const GROUND = 22;

function rand(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function hdTex(canvas: HTMLCanvasElement, repeatX = 1, repeatY = 1): CanvasTexture {
  const tex = new CanvasTexture(canvas);
  tex.magFilter = LinearFilter;
  tex.minFilter = LinearFilter;
  tex.generateMipmaps = true;
  tex.colorSpace = SRGBColorSpace;
  if (repeatX > 1 || repeatY > 1) {
    tex.wrapS = RepeatWrapping;
    tex.wrapT = RepeatWrapping;
    tex.repeat.set(repeatX, repeatY);
  }
  return tex;
}

/** 古镇高清青石板街面贴图（对标左图沉稳暖暗青灰石板 + 深色砖缝 + 局部暖光受光感） */
function makeCobbleStreetTexture(): CanvasTexture {
  const size = 1024;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(size, size);
  const r = rand(42);

  const slates = [
    [82, 78, 72],
    [74, 71, 66],
    [90, 85, 78],
    [68, 66, 61],
    [96, 90, 82],
  ];
  const mortar = [36, 33, 30];
  const moss = [
    [54, 72, 46],
    [46, 62, 40],
  ];

  const toWorld = (px: number) => (px / size) * GROUND - GROUND / 2;

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const wx = toWorld(x);
      const wz = toWorld(y);
      const n = r();

      // 错缝青石板网格（高密度细腻石砖）
      const row = Math.floor((wz + 11) * 4.8);
      const colOffset = (row & 1) * 0.48;
      const gx = (wx + 11) * 3.4 + colOffset;
      const gz = (wz + 11) * 4.8;
      const fx = gx - Math.floor(gx);
      const fz = gz - Math.floor(gz);
      const cellHash = ((Math.floor(gx) * 73856093) ^ (Math.floor(gz) * 19349663)) >>> 0;

      let c = slates[cellHash % slates.length];
      const grain = (n - 0.5) * 10;
      c = [
        Math.max(0, Math.min(255, Math.round(c[0] + grain))),
        Math.max(0, Math.min(255, Math.round(c[1] + grain))),
        Math.max(0, Math.min(255, Math.round(c[2] + grain))),
      ];

      // 细腻深色砖缝与微高光倒角
      const isJoint = fx < 0.065 || fz < 0.075;
      const isBevel = !isJoint && (fx < 0.12 || fz < 0.13);
      if (isJoint) {
        c = mortar;
      } else if (isBevel) {
        c = [Math.min(255, c[0] + 10), Math.min(255, c[1] + 9), Math.min(255, c[2] + 7)];
      }

      // 河岸边缘青苔微渗
      const canalDist = Math.abs(Math.abs(wx) - 1.5);
      if ((canalDist < 0.35 && isJoint) || (canalDist < 0.18 && n < 0.35)) {
        c = moss[cellHash % moss.length];
      }

      img.data.set([c[0], c[1], c[2], 255], (y * size + x) * 4);
    }
  }
  ctx.putImageData(img, 0, 0);
  return hdTex(canvas);
}

/** 石桥桥面与阶梯温润暖灰条石贴图 */
function makeBridgeDeckTexture(): CanvasTexture {
  const w = 256;
  const h = 256;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(108);

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const slabX = Math.floor(x / 16);
      const slabY = Math.floor((y + (slabX & 1) * 20) / 32);
      const hash = ((slabX * 31) ^ (slabY * 17)) & 3;
      const base = [
        [124, 114, 100],
        [114, 105, 92],
        [132, 121, 106],
        [108, 99, 87],
      ][hash];
      const joint = x % 16 < 2 || (y + (slabX & 1) * 20) % 32 < 2;
      const bevel = !joint && (x % 16 === 2 || (y + (slabX & 1) * 20) % 32 === 2);
      const noise = Math.round((r() - 0.5) * 8);
      let c = [base[0] + noise, base[1] + noise, base[2] + noise];
      if (joint) c = [48, 44, 39];
      else if (bevel) c = [c[0] + 12, c[1] + 11, c[2] + 9];
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return hdTex(canvas);
}

/** 河道石砌驳岸与拱桥石壁贴图 */
function makeStoneWallTexture(): CanvasTexture {
  const w = 256;
  const h = 128;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(77);

  for (let y = 0; y < h; y++) {
    const row = Math.floor(y / 16);
    for (let x = 0; x < w; x++) {
      const bx = (x + (row & 1) * 18) % 36;
      const by = y % 16;
      const isJoint = bx < 2 || by < 2;
      const n = Math.round((r() - 0.5) * 10);
      let c = isJoint ? [42, 40, 36] : [102 + n, 96 + n, 86 + n];
      if (!isJoint && by === 2) c = [118 + n, 111 + n, 100 + n];
      if (y > h - 28) {
        const m = (y - (h - 28)) / 28;
        c = [
          Math.round(c[0] * (1 - m * 0.45) + 34 * m),
          Math.round(c[1] * (1 - m * 0.3) + 58 * m),
          Math.round(c[2] * (1 - m * 0.45) + 38 * m),
        ];
      }
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return hdTex(canvas, 2, 1);
}

/** 黛瓦屋顶贴图 */
function makeRoofTileTexture(): CanvasTexture {
  const w = 128;
  const h = 128;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(99);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const ridge = x % 8;
      const tileRow = y % 10;
      const n = Math.round((r() - 0.5) * 6);
      let c = ridge === 0 ? [32, 36, 42] : ridge <= 3 ? [54 + n, 60 + n, 68 + n] : [42 + n, 47 + n, 54 + n];
      if (tileRow === 0) c = [24, 28, 34];
      else if (tileRow === 1 && ridge > 0) c = [66 + n, 72 + n, 80 + n];
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return hdTex(canvas, 2, 2);
}

/** 深胡桃木与暖褐木构墙面贴图（还原左图沉稳古建木色） */
function makeDarkTimberWallTexture(): CanvasTexture {
  const w = 128;
  const h = 128;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(123);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const n = Math.round((r() - 0.5) * 6);
      const isFrame = x < 8 || x >= w - 8 || y < 8 || y >= h - 8 || (y > 68 && y < 74);
      const plank = x % 8 === 0;
      let c = [76 + n, 54 + n, 38 + n];
      if (isFrame) {
        c = [46 + n, 31 + n, 21 + n];
      } else if (plank) {
        c = [58 + n, 40 + n, 28 + n];
      }
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return hdTex(canvas, 2, 1);
}

/** 左图同款：客栈正门三联深蓝布门帘（Noren，中央饰白色圆徽） */
function makeIndigoNorenTexture(): CanvasTexture {
  const w = 192;
  const h = 96;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(305);

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      // 三联分缝（x=64, x=128 处留出垂直微缝）
      const slit = (Math.abs(x - 64) <= 2 || Math.abs(x - 128) <= 2) && y > 14;
      if (slit) {
        ctx.fillStyle = '#140e0a';
        ctx.fillRect(x, y, 1, 1);
        continue;
      }
      // 布料自然垂褶与织物纹理
      const panelX = (x % 64) / 64;
      const fold = Math.sin(panelX * Math.PI * 2) * 8;
      const weave = ((x + y) & 1) * 3 + (r() - 0.5) * 4;
      const topShadow = y < 10 ? -12 : 0;
      const cr = Math.max(18, Math.min(85, Math.round(32 + fold * 0.6 + weave + topShadow)));
      const cg = Math.max(30, Math.min(115, Math.round(52 + fold * 0.8 + weave + topShadow)));
      const cb = Math.max(58, Math.min(165, Math.round(98 + fold * 1.1 + weave + topShadow)));
      ctx.fillStyle = `rgb(${cr},${cg},${cb})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }

  // 中央联绘制左图标志性的白色古风圆徽纹章
  const cx = 96;
  const cy = 50;
  ctx.strokeStyle = '#d8e0ec';
  ctx.lineWidth = 3.2;
  ctx.beginPath();
  ctx.arc(cx, cy, 20, 0, Math.PI * 2);
  ctx.stroke();

  ctx.lineWidth = 2.0;
  ctx.beginPath();
  ctx.arc(cx, cy, 13, 0, Math.PI * 2);
  ctx.stroke();

  // 圆徽内部古风篆纹/花瓣纹
  for (let a = 0; a < 4; a++) {
    const ang = (a * Math.PI) / 2;
    const px = cx + Math.cos(ang) * 7;
    const py = cy + Math.sin(ang) * 7;
    ctx.beginPath();
    ctx.arc(px, py, 4.5, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.fillStyle = '#d8e0ec';
  ctx.fillRect(cx - 8, cy - 1.5, 16, 3);
  ctx.fillRect(cx - 1.5, cy - 8, 3, 16);

  return hdTex(canvas);
}

/** 左图同款：客栈深木色格栅拉门贴图 */
function makeLatticeDoorTexture(): CanvasTexture {
  const w = 128;
  const h = 160;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#241810';
  ctx.fillRect(0, 0, w, h);

  // 左右两扇门框
  for (let leaf = 0; leaf < 2; leaf++) {
    const lx = leaf * 64;
    ctx.fillStyle = '#483020';
    ctx.fillRect(lx + 2, 2, 60, h - 4);
    // 上半部木格窗芯（暖暗内透）
    ctx.fillStyle = '#362417';
    ctx.fillRect(lx + 7, 10, 50, 86);
    // 细木格栅条
    ctx.fillStyle = '#5c3d28';
    for (let gx = 7; gx <= 57; gx += 10) {
      ctx.fillRect(lx + gx, 10, 2, 86);
    }
    for (let gy = 10; gy <= 96; gy += 12) {
      ctx.fillRect(lx + 7, gy, 50, 2);
    }
    // 腰板与下半部裙板
    ctx.fillStyle = '#563925';
    ctx.fillRect(lx + 6, 100, 52, 14);
    ctx.fillStyle = '#3c2719';
    ctx.fillRect(lx + 7, 118, 50, 34);
    for (let px = 12; px < 55; px += 8) {
      ctx.fillStyle = '#2d1d12';
      ctx.fillRect(lx + px, 118, 1, 34);
    }
  }
  return hdTex(canvas);
}

/** 暖黄透光雕花木窗贴图 */
function makeGlowingWindowTexture(): CanvasTexture {
  const w = 64;
  const h = 64;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const border = x < 5 || x >= w - 5 || y < 5 || y >= h - 5;
      const lattice = Math.abs(x - 32) <= 1 || Math.abs(y - 32) <= 1 || x % 12 === 0 || y % 12 === 0;
      if (border || lattice) {
        ctx.fillStyle = '#2e1c12';
      } else {
        const dist = Math.hypot(x - 32, y - 32) / 36;
        const g = Math.round(196 - dist * 42);
        const b = Math.round(108 - dist * 45);
        ctx.fillStyle = `rgb(245,${g},${b})`;
      }
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return hdTex(canvas);
}

/** 左图右侧木格陈列橱窗贴图 */
function makeShopShelfWindowTexture(): CanvasTexture {
  const w = 96;
  const h = 96;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#1c130d';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#4e3524';
  ctx.lineWidth = 4;
  ctx.strokeRect(2, 2, w - 4, h - 4);
  // 多宝格层板与小器皿剪影
  for (let row = 1; row <= 4; row++) {
    const y = row * 19;
    ctx.fillStyle = '#4a3222';
    ctx.fillRect(4, y, w - 8, 3);
    for (let col = 1; col <= 4; col++) {
      const x = col * 19;
      ctx.fillRect(x, 4, 2, h - 8);
      ctx.fillStyle = (row + col) & 1 ? '#6e5239' : '#58422f';
      ctx.fillRect(x - 11, y - 9, 7, 8);
      ctx.fillStyle = '#4a3222';
    }
  }
  return hdTex(canvas);
}

/** 街市摊位条纹布篷贴图 */
function makeAwningTexture(): CanvasTexture {
  const w = 64;
  const h = 64;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const stripe = Math.floor(x / 8) & 1;
      ctx.fillStyle = stripe ? '#c8baa0' : '#964a36';
      if (y > h - 5) ctx.fillStyle = '#6e3426';
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return hdTex(canvas);
}

/** 猫咪脚下柔和接地软阴影贴图 */
function makeContactShadowTexture(): CanvasTexture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createRadialGradient(size / 2, size / 2, size * 0.08, size / 2, size / 2, size * 0.48);
  grad.addColorStop(0, 'rgba(18, 12, 8, 0.52)');
  grad.addColorStop(0.55, 'rgba(18, 12, 8, 0.28)');
  grad.addColorStop(1, 'rgba(18, 12, 8, 0.0)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  return hdTex(canvas);
}

export interface Obstacle {
  x: number;
  z: number;
  r: number;
}

export class Town implements WorldNav {
  readonly scene = new Scene();
  readonly sun: DirectionalLight;
  readonly obstacles: Obstacle[] = [];
  readonly contactShadow: Mesh;
  private std: (hex: string, map?: Texture, roughness?: number) => MeshStandardMaterial;
  private waterCanvas: HTMLCanvasElement;
  private waterTex: CanvasTexture;
  private waterTime = 0;
  private wallMat: MeshStandardMaterial;
  private roofMat: MeshStandardMaterial;
  private timberWallMat: MeshStandardMaterial;
  private bridgeDeckMat: MeshStandardMaterial;
  private windowMat: MeshBasicMaterial;
  private lanternLights: PointLight[] = [];

  constructor(_gradientMap: Texture) {
    // 江南古镇暮色暖暗背景
    this.scene.background = new Color('#211d1a');
    this.std = (hex, map, roughness = 0.86) =>
      new MeshStandardMaterial({ color: hex, map, roughness, metalness: 0.04 });

    this.wallMat = this.std('#b8b0a2', makeStoneWallTexture(), 0.88);
    this.roofMat = this.std('#9ca4ae', makeRoofTileTexture(), 0.78);
    this.timberWallMat = this.std('#d8c8b4', makeDarkTimberWallTexture(), 0.82);
    this.bridgeDeckMat = this.std('#d2c8b8', makeBridgeDeckTexture(), 0.85);
    this.windowMat = new MeshBasicMaterial({ map: makeGlowingWindowTexture() });

    // 1. 电影感斜向暖阳 + 温润天光（复刻左图沉稳石板暗部与暖黄灯笼光感）
    this.scene.add(new HemisphereLight('#ffdca8', '#383432', 0.95));
    this.sun = new DirectionalLight('#ffdf9e', 2.45);
    this.sun.position.set(5.6, 8.2, 5.2);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.radius = 2.2;
    const sc = this.sun.shadow.camera;
    sc.left = sc.bottom = -10.5;
    sc.right = sc.top = 10.5;
    sc.near = 1;
    sc.far = 34;
    this.sun.shadow.bias = -0.0005;
    this.scene.add(this.sun, this.sun.target);

    // 2. 纵向穿城水道与两岸高清青石板街面
    this.waterCanvas = document.createElement('canvas');
    this.waterCanvas.width = 128;
    this.waterCanvas.height = 256;
    this.waterTex = hdTex(this.waterCanvas);
    this.drawWaterCanvas(0);

    this.buildCanalAndBanks();
    this.buildArchedStoneBridge();
    this.buildReferenceInnCourtyard();
    this.buildLeftSideMarketAndCourtyard();
    this.buildGreeneryAndProps();

    // 3. 猫咪脚下柔和接地软阴影
    const shadowGeo = new PlaneGeometry(0.86, 1.05);
    shadowGeo.rotateX(-Math.PI / 2);
    this.contactShadow = new Mesh(
      shadowGeo,
      new MeshBasicMaterial({
        map: makeContactShadowTexture(),
        transparent: true,
        depthWrite: false,
        polygonOffset: true,
        polygonOffsetFactor: -1,
      }),
    );
    this.contactShadow.position.set(0, 0.006, 0.35);
    this.contactShadow.renderOrder = 1;
    this.scene.add(this.contactShadow);
  }

  /** 根据世界坐标 (x, z) 计算可行走表面高度（石拱桥中心 y=0.0，向两岸台阶过渡至 y=-0.12） */
  heightAt(x: number, z: number): number {
    if (z >= -0.78 && z <= 1.48 && Math.abs(x) <= 1.85) {
      const t = Math.min(1, Math.abs(x) / 1.85);
      return -0.12 * t * t;
    }
    return -0.12;
  }

  /** 动态更新水面波光与猫咪脚下接地软阴影 */
  update(dt: number, catPos?: Vector3, catHeading = 0, catState = 'idle') {
    this.waterTime += dt;
    this.drawWaterCanvas(this.waterTime);
    this.waterTex.needsUpdate = true;

    this.lanternLights.forEach((l, i) => {
      l.intensity = 2.2 + Math.sin(this.waterTime * 3.0 + i * 1.3) * 0.16;
    });

    if (catPos) {
      const groundY = this.heightAt(catPos.x, catPos.z);
      catPos.y = groundY;
      this.contactShadow.position.set(catPos.x, groundY + 0.006, catPos.z);
      this.contactShadow.rotation.y = catHeading;
      if (catState === 'sit') {
        this.contactShadow.scale.set(0.8, 1, 0.76);
      } else if (catState === 'belly' || catState === 'loaf') {
        this.contactShadow.scale.set(1.02, 1, 1.02);
      } else {
        this.contactShadow.scale.set(0.85, 1, 1.0);
      }
    }
  }

  /** 绘制动态碧绿波光水面 */
  private drawWaterCanvas(t: number) {
    const w = this.waterCanvas.width;
    const h = this.waterCanvas.height;
    const ctx = this.waterCanvas.getContext('2d')!;
    const img = ctx.createImageData(w, h);

    for (let y = 0; y < h; y++) {
      const wz = (y / h) * GROUND - GROUND / 2;
      for (let x = 0; x < w; x++) {
        const wx = (x / w - 0.5) * 2.9;
        const bankDist = 1.45 - Math.abs(wx);

        let r = 32;
        let g = 68;
        let b = 60;

        if (bankDist < 0.35) {
          r = 20;
          g = 44;
          b = 40;
        } else if (bankDist < 0.65) {
          r = 26;
          g = 56;
          b = 50;
        }

        const underBridge = wz > -0.88 && wz < 1.58;
        if (underBridge) {
          r = Math.round(r * 0.5);
          g = Math.round(g * 0.52);
          b = Math.round(b * 0.54);
        }

        if (wx > 0.2 && !underBridge && Math.abs(wz - 0.2) < 4.5) {
          const waveX = Math.sin(y * 0.55 + t * 4.0) * 0.14;
          const lanternGlow = Math.max(0, 1 - Math.abs(wx - (0.88 + waveX)) * 2.5);
          const band = (Math.sin(y * 0.85 - t * 2.8) + 1) * 0.5;
          const k = lanternGlow * (0.3 + 0.4 * band);
          r = Math.min(255, Math.round(r + 170 * k));
          g = Math.min(255, Math.round(g + 92 * k));
          b = Math.min(255, Math.round(b + 24 * k));
        }

        if (!underBridge && bankDist > 0.16) {
          const wave1 = Math.sin(x * 0.45 + y * 0.32 - t * 2.6);
          const wave2 = Math.cos(x * 0.35 - y * 0.5 + t * 2.0);
          const ripple = wave1 * wave2;
          if (ripple > 0.7) {
            r = 224;
            g = 218;
            b = 172;
          } else if (ripple > 0.42) {
            r = Math.min(255, r + 42);
            g = Math.min(255, g + 62);
            b = Math.min(255, b + 48);
          }
        }

        const idx = (y * w + x) * 4;
        img.data[idx] = r;
        img.data[idx + 1] = g;
        img.data[idx + 2] = b;
        img.data[idx + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
  }

  private add(geo: BufferGeometry, hexOrMat: string | Material, x: number, y: number, z: number) {
    const mat = typeof hexOrMat === 'string' ? this.std(hexOrMat) : hexOrMat;
    const m = new Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = true;
    m.receiveShadow = true;
    this.scene.add(m);
    return m;
  }

  /** 建造纵向穿城河道与两岸高清青石板长街 */
  private buildCanalAndBanks() {
    const cobbleMat = this.std('#d8d2c8', makeCobbleStreetTexture(), 0.88);

    const bankW = (GROUND - 2.9) / 2;
    const leftBank = new Mesh(new PlaneGeometry(bankW, GROUND), cobbleMat);
    leftBank.rotation.x = -Math.PI / 2;
    leftBank.position.set(-(1.45 + bankW / 2), -0.12, 0);
    leftBank.receiveShadow = true;
    this.scene.add(leftBank);

    const rightBank = new Mesh(new PlaneGeometry(bankW, GROUND), cobbleMat);
    rightBank.rotation.x = -Math.PI / 2;
    rightBank.position.set(1.45 + bankW / 2, -0.12, 0);
    rightBank.receiveShadow = true;
    this.scene.add(rightBank);

    const waterMesh = new Mesh(new PlaneGeometry(2.96, GROUND), this.std('#ffffff', this.waterTex, 0.35));
    waterMesh.rotation.x = -Math.PI / 2;
    waterMesh.position.set(0, -0.44, 0);
    waterMesh.receiveShadow = true;
    this.scene.add(waterMesh);

    for (const side of [-1, 1]) {
      const wallX = side * 1.5;
      this.add(new BoxGeometry(0.18, 0.56, GROUND), this.wallMat, wallX, -0.36, 0);
      this.add(new BoxGeometry(0.24, 0.08, 9.2), '#787166', wallX, -0.08, -5.5);
      if (side === 1) {
        this.add(new BoxGeometry(0.24, 0.08, 9.5), '#787166', wallX, -0.08, 6.2);
      } else {
        this.add(new BoxGeometry(0.24, 0.08, 6.4), '#787166', wallX, -0.08, 6.6);
      }

      const zPosts = side === -1 ? [-5.2, -3.8, -2.4, -1.2, 3.5, 4.9] : [-5.2, -3.8, -2.4, -1.2, 1.9, 3.3, 4.7];
      for (const pz of zPosts) {
        this.add(new BoxGeometry(0.16, 0.42, 0.16), '#847c70', side * 1.52, 0.1, pz);
        this.add(new BoxGeometry(0.2, 0.07, 0.2), '#968d80', side * 1.52, 0.33, pz);
      }
      this.add(new BoxGeometry(0.08, 0.07, 4.1), '#7a7368', side * 1.52, 0.22, -3.2);
      this.add(new BoxGeometry(0.08, 0.12, 4.1), '#686258', side * 1.52, 0.04, -3.2);
      if (side === 1) {
        this.add(new BoxGeometry(0.08, 0.07, 2.9), '#7a7368', side * 1.52, 0.22, 3.3);
        this.add(new BoxGeometry(0.08, 0.12, 2.9), '#686258', side * 1.52, 0.04, 3.3);
      }
    }

    for (let i = 0; i < 4; i++) {
      this.add(new BoxGeometry(0.22, 0.1, 1.25), this.bridgeDeckMat, -2.05 + i * 0.2, -0.14 - i * 0.08, 2.5);
    }
  }

  /**
   * 建造横跨河道中央的青石拱桥与下桥石阶（东侧引桥台阶直接对标左图左侧石桥阶梯构图！）
   */
  private buildArchedStoneBridge() {
    const zCenter = 0.38;
    const bridgeW = 2.08;
    const segments = 9;
    const span = 3.2;
    const segLen = span / segments;

    for (let i = 0; i < segments; i++) {
      const x = -span / 2 + (i + 0.5) * segLen;
      const topY = this.heightAt(x, zCenter);
      const archBottomY = -0.36 - 0.16 * (x / (span / 2)) ** 2;
      const thickness = Math.max(0.14, topY - archBottomY);
      const deck = this.add(
        new BoxGeometry(segLen + 0.03, thickness, bridgeW),
        this.bridgeDeckMat,
        x,
        topY - thickness / 2,
        zCenter,
      );
      deck.rotation.z = (-2 * -0.12 * x) / (1.85 * 1.85);
    }

    // 东侧与西侧桥头多级青石阶梯 + 阶梯侧护墙（还原左图左侧層疊下桥石阶与栏杆）
    for (const side of [-1, 1]) {
      for (let s = 0; s < 5; s++) {
        const sx = side * (1.28 + s * 0.155);
        const sy = 0.02 - s * 0.034;
        this.add(new BoxGeometry(0.17, 0.09, bridgeW - 0.12), this.bridgeDeckMat, sx, sy, zCenter);
      }
      // 阶梯两侧斜坡护栏压石与桥头望柱（对标左图左侧石阶护栏）
      for (const sz of [zCenter - bridgeW / 2 + 0.08, zCenter + bridgeW / 2 - 0.08]) {
        const rampRail = this.add(new BoxGeometry(0.92, 0.28, 0.14), '#80776a', side * 1.56, 0.08, sz);
        rampRail.rotation.z = -side * 0.22;
        const rampCap = this.add(new BoxGeometry(0.96, 0.06, 0.18), '#968c7d', side * 1.56, 0.24, sz);
        rampCap.rotation.z = -side * 0.22;
        this.add(new BoxGeometry(0.18, 0.34, 0.18), '#8a8072', side * 1.96, 0.02, sz);
        this.add(new BoxGeometry(0.22, 0.06, 0.22), '#9e9485', side * 1.96, 0.21, sz);
      }
    }

    // 北侧雕花青石桥栏（z = -0.62）
    const northZ = -0.62;
    for (const px of [-1.42, -0.85, -0.28, 0.28, 0.85, 1.42]) {
      const py = this.heightAt(px, zCenter);
      this.add(new BoxGeometry(0.16, 0.42, 0.16), '#8c8375', px, py + 0.2, northZ);
      this.add(new BoxGeometry(0.21, 0.07, 0.21), '#a29889', px, py + 0.42, northZ);
    }
    for (let i = 0; i < 5; i++) {
      const rx = -1.14 + i * 0.57;
      const ry = this.heightAt(rx, zCenter);
      this.add(new BoxGeometry(0.5, 0.07, 0.09), '#887f72', rx, ry + 0.32, northZ);
      this.add(new BoxGeometry(0.48, 0.18, 0.07), '#726a5f', rx, ry + 0.15, northZ);
    }

    // 南侧桥沿与桥头石望柱（z = +1.38）
    const southZ = 1.38;
    for (const px of [-1.42, -0.95, 0.95, 1.42]) {
      const py = this.heightAt(px, zCenter);
      this.add(new BoxGeometry(0.16, 0.38, 0.16), '#8c8375', px, py + 0.17, southZ);
      this.add(new BoxGeometry(0.21, 0.07, 0.21), '#a29889', px, py + 0.38, southZ);
    }
    this.add(new BoxGeometry(1.85, 0.07, 0.12), '#847b6e', 0, 0.02, southZ);
  }

  /**
   * 1:1 还原左图（01M5Y43048AD1CA1YXZA3MK8QW.png）的客栈门前庭院与前景石栏绿植：
   * - 位于东侧下桥广场（猫咪站在 x=2.32, z=0.22）：
   * - 猫身后（z = -0.45，朝 +Z 面向广场与镜头）：
   *   1) 两级浅灰青石门阶（x=2.36, z=-0.20）
   *   2) 深木色格栅双开门（x=2.36, z=-0.42）
   *   3) 三联深蓝布门帘（带白色圆徽，x=2.36, y=1.18, z=-0.32）
   *   4) 左右门柱悬挂两盏暖橙木框灯笼（x=1.78 与 x=2.94, y=1.12, z=-0.26）
   *   5) 门右侧：多宝格木陈列窗 + 浅褐竖幡 + 两个贴红封签的深青绿陶酒坛（x=3.22, 3.52）
   * - 猫身前下方（前景 x=2.46, z=0.92）：
   *   青石护栏围合的方形绿植花坛，内栽浓密深绿灌木丛！
   */
  private buildReferenceInnCourtyard() {
    // 一、猫身后的客栈正门立面（朝 +Z 面向下桥青石广场）
    const doorX = 2.36;
    const wallZ = -0.52;

    // 客栈主体深木墙体与二层黛瓦屋檐
    this.add(new BoxGeometry(3.4, 2.25, 2.2), this.timberWallMat, 2.85, 0.96, wallZ - 1.05);
    this.buildPitchedRoof(2.85, 2.05, wallZ - 1.0, 3.8, 2.8, 0.68);

    // 门前两级浅灰青石门阶（左图红框正上方猫咪脚边的两层石阶）
    this.add(new BoxGeometry(1.26, 0.08, 0.42), '#7e7a72', doorX, -0.08, wallZ + 0.28);
    this.add(new BoxGeometry(1.14, 0.08, 0.26), '#8c877e', doorX, -0.01, wallZ + 0.18);

    // 门廊四根深胡桃木立柱与横梁
    for (const px of [1.72, 3.0, 3.95]) {
      this.add(new CylinderGeometry(0.065, 0.072, 1.95, 10), '#322015', px, 0.82, wallZ + 0.08);
    }
    this.add(new BoxGeometry(2.5, 0.11, 0.16), '#382417', 2.84, 1.56, wallZ + 0.1);
    this.add(new BoxGeometry(1.36, 0.09, 0.14), '#3d281a', doorX, 1.42, wallZ + 0.12);

    // 客栈深木色格栅双开门
    const doorMesh = new Mesh(
      new PlaneGeometry(1.16, 1.48),
      this.std('#ffffff', makeLatticeDoorTexture(), 0.78),
    );
    doorMesh.position.set(doorX, 0.68, wallZ + 0.06);
    doorMesh.receiveShadow = true;
    this.scene.add(doorMesh);

    // 三联深蓝布门帘（Noren，中央白色圆徽，微向前倾垂挂于门楣下）
    const noren = new Mesh(
      new PlaneGeometry(1.18, 0.56),
      new MeshStandardMaterial({ map: makeIndigoNorenTexture(), roughness: 0.9, side: DoubleSide }),
    );
    noren.position.set(doorX, 1.18, wallZ + 0.16);
    noren.rotation.x = 0.05;
    noren.castShadow = true;
    noren.receiveShadow = true;
    this.scene.add(noren);

    // 门帘左右两侧悬挂的暖黄六角木框灯笼（完全对应左图门帘两侧的暖光灯笼）
    this.warmBoxLantern(1.76, 1.12, wallZ + 0.22, true);
    this.warmBoxLantern(2.96, 1.12, wallZ + 0.22, true);

    // 门右侧：多宝格木格陈列窗 + 浅褐竖招幌 + 两个贴红封签的深青绿陶瓮
    const shelfWin = new Mesh(
      new PlaneGeometry(0.76, 0.78),
      this.std('#ffffff', makeShopShelfWindowTexture(), 0.8),
    );
    shelfWin.position.set(3.48, 0.78, wallZ + 0.07);
    this.scene.add(shelfWin);
    this.add(new BoxGeometry(0.84, 0.07, 0.14), '#442c1d', 3.48, 0.38, wallZ + 0.1);

    // 右上浅褐布幡
    const signBanner = new Mesh(
      new PlaneGeometry(0.42, 0.62),
      this.std('#967856', undefined, 0.9),
    );
    signBanner.position.set(3.38, 1.45, wallZ + 0.24);
    signBanner.castShadow = true;
    this.scene.add(signBanner);

    // 门右下方两只深橄榄绿陶酒坛（带红色方块封贴）
    this.ceramicWineJar(3.22, wallZ + 0.28);
    this.ceramicWineJar(3.54, wallZ + 0.32);

    // 二、猫身前下方的青石护栏绿植花坛（1:1 复刻左图红框下方的石栏灌木丛！）
    this.buildForegroundStonePlanter(2.44, 1.32);

    // 东侧远端侧翼楼阁（丰富广角视野）
    this.add(new BoxGeometry(2.6, 2.4, 3.2), this.timberWallMat, 5.1, 1.05, 0.8);
    this.buildPitchedRoof(5.1, 2.25, 0.8, 3.0, 3.6, 0.75);
    this.obstacles.push({ x: 2.85, z: -1.4, r: 1.5 });
    this.obstacles.push({ x: 2.44, z: 1.32, r: 0.72 });
    this.obstacles.push({ x: 5.1, z: 0.8, r: 1.8 });
  }

  /** 左图同款：木框暖黄发光灯笼 */
  private warmBoxLantern(x: number, y: number, z: number, addLight: boolean) {
    // 挂杆与上下深木灯盖
    this.add(new CylinderGeometry(0.015, 0.015, 0.22, 6), '#2a1a10', x, y + 0.22, z);
    this.add(new CylinderGeometry(0.12, 0.14, 0.05, 6), '#2a1a10', x, y + 0.14, z);
    this.add(new CylinderGeometry(0.11, 0.09, 0.04, 6), '#2a1a10', x, y - 0.14, z);

    // 暖琥珀色发光灯芯
    const core = new Mesh(
      new CylinderGeometry(0.105, 0.095, 0.24, 6),
      new MeshBasicMaterial({ color: '#ffae42' }),
    );
    core.position.set(x, y, z);
    this.scene.add(core);

    // 细木立棱
    for (let i = 0; i < 6; i++) {
      const a = (i * Math.PI) / 3;
      const rx = x + Math.cos(a) * 0.105;
      const rz = z + Math.sin(a) * 0.105;
      this.add(new CylinderGeometry(0.008, 0.008, 0.25, 4), '#2a1a10', rx, y, rz);
    }

    if (addLight) {
      const light = new PointLight('#ff9e38', 2.2, 5.2, 1.4);
      light.position.set(x, y - 0.08, z + 0.18);
      this.scene.add(light);
      this.lanternLights.push(light);
    }
  }

  /** 左图门右侧深青绿陶瓮（配红封条） */
  private ceramicWineJar(x: number, z: number) {
    const y0 = -0.12;
    const jar = this.add(new CylinderGeometry(0.11, 0.12, 0.34, 12), '#333d2c', x, y0 + 0.17, z);
    jar.scale.set(1.08, 1, 1.08);
    this.add(new CylinderGeometry(0.085, 0.105, 0.05, 12), '#252c20', x, y0 + 0.35, z);
    // 红色封签
    const label = new Mesh(new PlaneGeometry(0.08, 0.08), new MeshBasicMaterial({ color: '#9e2e24' }));
    label.position.set(x, y0 + 0.19, z + 0.125);
    label.rotation.z = Math.PI / 4;
    this.scene.add(label);
  }

  /** 左图红框正下方：青石望柱护栏围合的绿植灌木花坛 */
  private buildForegroundStonePlanter(cx: number, cz: number) {
    const y0 = -0.12;
    const w = 1.24;
    const d = 0.78;
    const stoneMat = this.std('#7d8286', undefined, 0.84);
    const capMat = this.std('#92979b', undefined, 0.8);

    // 四角青石望柱与柱头压石
    const corners: [number, number][] = [
      [cx - w / 2, cz - d / 2],
      [cx + w / 2, cz - d / 2],
      [cx - w / 2, cz + d / 2],
      [cx + w / 2, cz + d / 2],
    ];
    for (const [px, pz] of corners) {
      this.add(new BoxGeometry(0.17, 0.38, 0.17), stoneMat, px, y0 + 0.19, pz);
      this.add(new BoxGeometry(0.21, 0.06, 0.21), capMat, px, y0 + 0.4, pz);
    }

    // 前后左右青石上下横梁与竖向石栏板
    for (const sz of [-d / 2, d / 2]) {
      this.add(new BoxGeometry(w, 0.065, 0.09), capMat, cx, y0 + 0.33, cz + sz);
      this.add(new BoxGeometry(w, 0.08, 0.11), stoneMat, cx, y0 + 0.08, cz + sz);
      for (let i = -2; i <= 2; i++) {
        this.add(new BoxGeometry(0.07, 0.2, 0.06), stoneMat, cx + i * 0.2, y0 + 0.2, cz + sz);
      }
    }
    for (const sx of [-w / 2, w / 2]) {
      this.add(new BoxGeometry(0.09, 0.065, d), capMat, cx + sx, y0 + 0.33, cz);
      this.add(new BoxGeometry(0.11, 0.08, d), stoneMat, cx + sx, y0 + 0.08, cz);
    }

    // 花坛内部丰茂的多层次深绿叶片灌木丛（自然圆润簇状，告别低多边形棱角球）
    const leafColors = ['#26381e', '#324826', '#3e5830', '#4a6638'];
    const r = rand(808);
    for (let i = 0; i < 28; i++) {
      const bx = cx + (r() - 0.5) * (w - 0.18);
      const bz = cz + (r() - 0.5) * (d - 0.12);
      const by = y0 + 0.16 + r() * 0.24;
      const rad = 0.11 + r() * 0.09;
      const col = leafColors[i % leafColors.length];
      const bush = this.add(new SphereGeometry(rad, 10, 8), this.std(col, undefined, 0.9), bx, by, bz);
      bush.scale.set(1.15, 0.88, 1.08);
    }
  }

  /** 建造古风黛瓦双坡屋顶与飞檐 */
  private buildPitchedRoof(x: number, y: number, z: number, widthX: number, lengthZ: number, height: number) {
    const halfW = widthX / 2;
    const slopeLen = Math.hypot(halfW, height) + 0.18;
    const angle = Math.atan2(height, halfW);

    const leftSlope = this.add(
      new BoxGeometry(slopeLen, 0.14, lengthZ),
      this.roofMat,
      x - halfW * 0.48,
      y + height * 0.48,
      z,
    );
    leftSlope.rotation.z = angle;

    const rightSlope = this.add(
      new BoxGeometry(slopeLen, 0.14, lengthZ),
      this.roofMat,
      x + halfW * 0.48,
      y + height * 0.48,
      z,
    );
    rightSlope.rotation.z = -angle;

    this.add(new BoxGeometry(0.24, 0.2, lengthZ + 0.28), '#262d34', x, y + height + 0.04, z);
  }

  /** 建造左侧街市木摊位与徽派古宅 */
  private buildLeftSideMarketAndCourtyard() {
    const hx = -4.65;
    const hz = -3.65;
    this.add(new BoxGeometry(3.4, 2.2, 3.1), this.timberWallMat, hx, 0.98, hz);
    this.buildPitchedRoof(hx, 2.1, hz, 3.8, 3.5, 0.82);
    const win = new Mesh(new PlaneGeometry(0.82, 0.68), this.windowMat);
    win.rotation.y = Math.PI / 2;
    win.position.set(hx + 1.71, 1.15, hz + 0.3);
    this.scene.add(win);
    this.warmBoxLantern(hx + 1.85, 1.72, hz + 1.25, true);
    this.obstacles.push({ x: hx, z: hz, r: 2.3 });

    this.marketStall(-2.85, -0.55);
    this.marketStall(-3.35, 2.35);
  }

  private marketStall(x: number, z: number) {
    const g = new Group();
    g.position.set(x, -0.12, z);
    this.scene.add(g);

    const addPart = (geo: BufferGeometry, matOrHex: string | Material, px: number, py: number, pz: number) => {
      const m = new Mesh(geo, typeof matOrHex === 'string' ? this.std(matOrHex) : matOrHex);
      m.position.set(px, py, pz);
      m.castShadow = true;
      m.receiveShadow = true;
      g.add(m);
      return m;
    };

    addPart(new BoxGeometry(0.95, 0.62, 1.55), '#5e3c26', 0, 0.31, 0);
    addPart(new BoxGeometry(1.04, 0.07, 1.64), '#784e32', 0, 0.64, 0);
    for (const px of [-0.42, 0.42]) {
      for (const pz of [-0.7, 0.7]) {
        addPart(new CylinderGeometry(0.04, 0.04, 1.55, 8), '#42291a', px, 0.78, pz);
      }
    }
    const awning = addPart(
      new BoxGeometry(1.28, 0.06, 1.78),
      this.std('#ffffff', makeAwningTexture(), 0.88),
      0.06,
      1.52,
      0,
    );
    awning.rotation.z = -0.22;

    addPart(new CylinderGeometry(0.18, 0.16, 0.42, 10), '#6e462c', 0.56, 0.21, 0.68);
    addPart(new CylinderGeometry(0.16, 0.12, 0.34, 10), '#7a422e', 0.52, 0.17, -0.72);

    this.obstacles.push({ x, z, r: 0.95 });
  }

  private buildGreeneryAndProps() {
    this.stoneLantern(-1.82, -1.08);
    this.tree(-5.4, 0.85, 1.25, '#344e2a', '#486838');
    this.tree(-2.35, -2.25, 0.92, '#2e4624', '#426034');
    this.tree(2.35, -4.35, 1.15, '#324c28', '#466436');
    this.tree(5.45, 3.65, 1.05, '#2e4624', '#405c32');
    this.tree(-5.2, 4.1, 1.0, '#344e2a', '#486838');

    this.catBed(-2.05, 0.42);
    this.bowl(-2.05, 0.92);
  }

  private stoneLantern(x: number, z: number) {
    const y0 = -0.12;
    this.add(new BoxGeometry(0.34, 0.12, 0.34), '#7a7468', x, y0 + 0.06, z);
    this.add(new CylinderGeometry(0.08, 0.1, 0.46, 8), '#888276', x, y0 + 0.35, z);
    this.add(new BoxGeometry(0.28, 0.08, 0.28), '#948e82', x, y0 + 0.6, z);
    const chamber = new Mesh(new BoxGeometry(0.18, 0.2, 0.18), new MeshBasicMaterial({ color: '#ffcf70' }));
    chamber.position.set(x, y0 + 0.74, z);
    this.scene.add(chamber);
    const cap = this.add(new CylinderGeometry(0.06, 0.28, 0.18, 4), '#646056', x, y0 + 0.92, z);
    cap.rotation.y = Math.PI / 4;
    this.obstacles.push({ x, z, r: 0.32 });
  }

  private tree(x: number, z: number, s: number, darkLeaf: string, midLeaf: string) {
    const y0 = -0.12;
    this.add(new CylinderGeometry(0.13 * s, 0.19 * s, 1.35 * s, 8), '#4a3020', x, y0 + 0.65 * s, z);
    this.add(new SphereGeometry(0.8 * s, 12, 10), darkLeaf, x, y0 + 1.55 * s, z);
    this.add(new SphereGeometry(0.6 * s, 12, 10), midLeaf, x + 0.24 * s, y0 + 1.96 * s, z + 0.15 * s);
    this.add(new SphereGeometry(0.52 * s, 12, 10), midLeaf, x - 0.26 * s, y0 + 1.76 * s, z - 0.18 * s);
    this.obstacles.push({ x, z, r: 0.68 * s });
  }

  private catBed(x: number, z: number) {
    const y0 = -0.12;
    const ring = this.add(new TorusGeometry(0.36, 0.1, 8, 16), '#b86858', x, y0 + 0.1, z);
    ring.rotation.x = -Math.PI / 2;
    this.add(new CylinderGeometry(0.34, 0.34, 0.08, 16), '#e2c8b6', x, y0 + 0.05, z);
  }

  private bowl(x: number, z: number) {
    const y0 = -0.12;
    this.add(new CylinderGeometry(0.16, 0.13, 0.1, 12), '#4e78a0', x, y0 + 0.05, z);
    this.add(new CylinderGeometry(0.13, 0.13, 0.02, 12), '#a86e3e', x, y0 + 0.1, z);
  }

  /** 判断坐标 p 是否在石桥桥面或两岸青石街道可行走区 */
  walkable(p: Vector3) {
    if (Math.abs(p.x) > 4.4 || Math.abs(p.z) > 4.4) return false;
    const onBridge = p.z >= -0.42 && p.z <= 1.15 && Math.abs(p.x) <= 1.85;
    const inCanal = Math.abs(p.x) < 1.72;
    if (inCanal && !onBridge) return false;
    return this.obstacles.every((o) => Math.hypot(p.x - o.x, p.z - o.z) > o.r + 0.3);
  }

  randomTarget(from: Vector3): Vector3 {
    for (let i = 0; i < 48; i++) {
      const a = Math.random() * Math.PI * 2;
      const d = 1.0 + Math.random() * 2.4;
      const p = new Vector3(from.x + Math.sin(a) * d, 0, from.z + Math.cos(a) * d);
      if (this.walkable(p) && this.clearLine(from, p)) {
        p.y = this.heightAt(p.x, p.z);
        return p;
      }
    }
    return new Vector3(2.32, -0.12, 0.24);
  }

  private clearLine(a: Vector3, b: Vector3) {
    for (let t = 0.1; t <= 1; t += 0.1) {
      if (!this.walkable(a.clone().lerp(b, t))) return false;
    }
    return true;
  }
}
