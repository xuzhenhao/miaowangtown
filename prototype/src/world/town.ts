import {
  BoxGeometry,
  CanvasTexture,
  Color,
  CylinderGeometry,
  DirectionalLight,
  Group,
  HemisphereLight,
  IcosahedronGeometry,
  Mesh,
  MeshBasicMaterial,
  MeshToonMaterial,
  NearestFilter,
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

function pixelTex(canvas: HTMLCanvasElement, repeatX = 1, repeatY = 1): CanvasTexture {
  const tex = new CanvasTexture(canvas);
  tex.magFilter = NearestFilter;
  tex.minFilter = NearestFilter;
  tex.generateMipmaps = false;
  tex.colorSpace = SRGBColorSpace;
  if (repeatX > 1 || repeatY > 1) {
    tex.wrapS = RepeatWrapping;
    tex.wrapT = RepeatWrapping;
    tex.repeat.set(repeatX, repeatY);
  }
  return tex;
}

/** 古镇青石板街面贴图（含石板砖缝、河岸青苔、桥头石阶与暖色落叶点缀） */
function makeCobbleStreetTexture(): CanvasTexture {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(size, size);
  const r = rand(42);

  const slates = [
    [116, 114, 106],
    [104, 103, 96],
    [126, 122, 112],
    [94, 94, 88],
    [134, 128, 116],
  ];
  const mortar = [58, 56, 52];
  const moss = [
    [76, 102, 64],
    [64, 88, 54],
    [92, 116, 74],
  ];

  const toWorld = (px: number) => (px / size) * GROUND - GROUND / 2;

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const wx = toWorld(x);
      const wz = toWorld(y);
      const n = r();

      // 错缝青石板网格
      const row = Math.floor((wz + 11) * 3.2);
      const colOffset = (row & 1) * 0.45;
      const gx = (wx + 11) * 2.2 + colOffset;
      const gz = (wz + 11) * 3.2;
      const fx = gx - Math.floor(gx);
      const fz = gz - Math.floor(gz);
      const cellHash = ((Math.floor(gx) * 73856093) ^ (Math.floor(gz) * 19349663)) >>> 0;

      let c = slates[cellHash % slates.length];
      // 砖块内部颗粒微差
      const grain = (n - 0.5) * 12;
      c = [
        Math.max(0, Math.min(255, Math.round(c[0] + grain))),
        Math.max(0, Math.min(255, Math.round(c[1] + grain))),
        Math.max(0, Math.min(255, Math.round(c[2] + grain))),
      ];

      // 砖缝与高光倒角
      const isJoint = fx < 0.07 || fz < 0.08;
      const isBevel = !isJoint && (fx < 0.13 || fz < 0.14);
      if (isJoint) {
        c = mortar;
      } else if (isBevel) {
        c = [Math.min(255, c[0] + 14), Math.min(255, c[1] + 13), Math.min(255, c[2] + 10)];
      }

      // 河岸边缘与建筑墙根青苔渗透
      const canalDist = Math.abs(Math.abs(wx) - 1.55);
      if ((canalDist < 0.48 && isJoint) || (canalDist < 0.28 && n < 0.42)) {
        c = moss[cellHash % moss.length];
      }
      if (Math.abs(wx) > 5.2 && n < 0.35) {
        c = moss[(cellHash + 1) % moss.length];
      }

      // 客栈门前与桥头广场暖色石板铺装
      const bridgePlaza = Math.hypot(wx * 0.7, wz - 0.35);
      if (bridgePlaza < 2.9 && !isJoint) {
        c = [Math.min(255, c[0] + 12), Math.min(255, c[1] + 9), Math.min(255, c[2] + 4)];
      }

      // 零星花瓣与暖秋落叶点缀
      if (n > 0.9965 && Math.abs(wx) > 1.6) {
        c = n > 0.9982 ? [242, 182, 192] : [228, 174, 96];
      }

      img.data.set([c[0], c[1], c[2], 255], (y * size + x) * 4);
    }
  }
  ctx.putImageData(img, 0, 0);
  return pixelTex(canvas);
}

/** 桥面与石阶精细青石条纹贴图 */
function makeBridgeDeckTexture(): CanvasTexture {
  const w = 128;
  const h = 128;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(108);

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const slabX = Math.floor(x / 8);
      const slabY = Math.floor((y + (slabX & 1) * 10) / 16);
      const hash = ((slabX * 31) ^ (slabY * 17)) & 3;
      const base = [
        [142, 138, 126],
        [130, 126, 115],
        [150, 145, 132],
        [122, 119, 109],
      ][hash];
      const joint = x % 8 === 0 || (y + (slabX & 1) * 10) % 16 === 0;
      const edgeMoss = (y < 14 || y > h - 15) && (joint || r() < 0.38);
      const centerWear = Math.abs(y - h / 2) < 34 ? 10 : 0;
      const noise = Math.round((r() - 0.5) * 10);
      let c = [base[0] + centerWear + noise, base[1] + centerWear + noise, base[2] + centerWear + noise];
      if (joint) c = [64, 62, 56];
      if (edgeMoss) c = [78, 104, 66];
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return pixelTex(canvas);
}

/** 河道石砌驳岸与拱桥石壁贴图 */
function makeStoneWallTexture(): CanvasTexture {
  const w = 128;
  const h = 64;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(77);

  for (let y = 0; y < h; y++) {
    const row = Math.floor(y / 10);
    for (let x = 0; x < w; x++) {
      const bx = (x + (row & 1) * 9) % 18;
      const by = y % 10;
      const isJoint = bx === 0 || by === 0;
      const n = Math.round((r() - 0.5) * 12);
      let c = isJoint ? [48, 50, 46] : [112 + n, 110 + n, 102 + n];
      if (!isJoint && by === 1) c = [132 + n, 128 + n, 118 + n];
      // 底部临水青苔暗化
      if (y > h - 18) {
        const m = (y - (h - 18)) / 18;
        c = [
          Math.round(c[0] * (1 - m * 0.45) + 38 * m),
          Math.round(c[1] * (1 - m * 0.3) + 68 * m),
          Math.round(c[2] * (1 - m * 0.45) + 44 * m),
        ];
      }
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return pixelTex(canvas, 3, 1);
}

/** 黛瓦屋顶像素贴图 */
function makeRoofTileTexture(): CanvasTexture {
  const w = 64;
  const h = 64;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(99);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const ridge = x % 6;
      const tileRow = y % 8;
      const n = Math.round((r() - 0.5) * 8);
      let c = ridge === 0 ? [34, 40, 48] : ridge <= 2 ? [62 + n, 70 + n, 80 + n] : [46 + n, 53 + n, 62 + n];
      if (tileRow === 0) c = [28, 33, 40];
      else if (tileRow === 1 && ridge > 0) c = [76 + n, 84 + n, 94 + n];
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return pixelTex(canvas, 2, 2);
}

/** 古建白墙与深木梁柱贴图 */
function makeTimberWallTexture(): CanvasTexture {
  const w = 64;
  const h = 64;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const r = rand(123);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const n = Math.round((r() - 0.5) * 8);
      const isFrame = x < 5 || x >= w - 5 || y < 5 || y >= h - 5 || (y > 42 && y < 46);
      const isSkirt = y >= 46;
      let c = [226 + n, 214 + n, 192 + n];
      if (isFrame) {
        c = [66 + n, 44 + n, 31 + n];
      } else if (isSkirt) {
        c = x % 4 === 0 ? [54, 36, 25] : [86 + n, 58 + n, 40 + n];
      }
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return pixelTex(canvas, 2, 1);
}

/** 暖黄透光雕花木窗贴图 */
function makeGlowingWindowTexture(): CanvasTexture {
  const w = 32;
  const h = 32;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const border = x < 3 || x >= w - 3 || y < 3 || y >= h - 3;
      const lattice = x === 15 || x === 16 || y === 15 || y === 16 || x % 8 === 0 || y % 8 === 0;
      if (border || lattice) {
        ctx.fillStyle = '#3b2418';
      } else {
        const dist = Math.hypot(x - 16, y - 16) / 18;
        const g = Math.round(215 - dist * 38);
        const b = Math.round(125 - dist * 45);
        ctx.fillStyle = `rgb(255,${g},${b})`;
      }
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return pixelTex(canvas);
}

/** 客栈门前蓝布招幌贴图 */
function makeBannerTexture(): CanvasTexture {
  const w = 32;
  const h = 64;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#2b4c73';
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = '#e8dcc4';
  ctx.fillRect(2, 2, w - 4, h - 4);
  ctx.fillStyle = '#335a86';
  ctx.fillRect(4, 4, w - 8, h - 8);
  // 中心菱形暖白底与古风纹理
  ctx.fillStyle = '#f2e8d4';
  for (let y = 16; y < 48; y++) {
    const span = 12 - Math.abs(y - 32) * 0.65;
    for (let x = 0; x < w; x++) {
      if (Math.abs(x - 16) < span) ctx.fillRect(x, y, 1, 1);
    }
  }
  ctx.fillStyle = '#274466';
  ctx.fillRect(14, 24, 4, 16);
  ctx.fillRect(11, 28, 10, 3);
  ctx.fillRect(11, 34, 10, 3);
  return pixelTex(canvas);
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
      ctx.fillStyle = stripe ? '#dfd1b4' : '#b85c44';
      if (y > h - 5) ctx.fillStyle = '#8c4230';
      ctx.fillRect(x, y, 1, 1);
    }
  }
  return pixelTex(canvas);
}

/** 猫咪脚下柔和深暖褐像素接地阴影贴图（解决浮空感，不写深度不触发描边） */
function makeContactShadowTexture(): CanvasTexture {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(size, size);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const nx = (x - size / 2 + 0.5) / (size / 2);
      const ny = (y - size / 2 + 0.5) / (size / 2);
      const d = Math.hypot(nx, ny);
      // 柔和分阶像素软阴影
      let alpha = 0;
      if (d < 0.38) alpha = 0.54;
      else if (d < 0.62) alpha = 0.36;
      else if (d < 0.82) alpha = 0.18;
      else if (d < 0.96) alpha = 0.07;
      const idx = (y * size + x) * 4;
      img.data[idx] = 26;
      img.data[idx + 1] = 16;
      img.data[idx + 2] = 12;
      img.data[idx + 3] = Math.round(alpha * 255);
    }
  }
  ctx.putImageData(img, 0, 0);
  return pixelTex(canvas);
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
  private toon: (hex: string, map?: Texture) => MeshToonMaterial;
  private waterCanvas: HTMLCanvasElement;
  private waterTex: CanvasTexture;
  private waterTime = 0;
  private wallMat: MeshToonMaterial;
  private roofMat: MeshToonMaterial;
  private timberWallMat: MeshToonMaterial;
  private bridgeDeckMat: MeshToonMaterial;
  private windowMat: MeshBasicMaterial;
  private lanternLights: PointLight[] = [];

  constructor(gradientMap: Texture) {
    // 暮色暖金深邃背景色（配合四角暗角与暖阳，贴合 HD-2D 氛围）
    this.scene.background = new Color('#26323c');
    this.toon = (hex, map) => new MeshToonMaterial({ color: hex, map, gradientMap });

    this.wallMat = new MeshToonMaterial({ color: '#d8d2c5', map: makeStoneWallTexture(), gradientMap });
    this.roofMat = new MeshToonMaterial({ color: '#c8d0d8', map: makeRoofTileTexture(), gradientMap });
    this.timberWallMat = new MeshToonMaterial({ color: '#fff8ec', map: makeTimberWallTexture(), gradientMap });
    this.bridgeDeckMat = new MeshToonMaterial({ color: '#e6e0d2', map: makeBridgeDeckTexture(), gradientMap });
    this.windowMat = new MeshBasicMaterial({ map: makeGlowingWindowTexture() });

    // 1. 戏剧性斜射暖阳 + 冷暖对比天光（右上斜射拉出修长街景与石桥投影）
    this.scene.add(new HemisphereLight('#ffe6be', '#3e3a4c', 0.88));
    this.sun = new DirectionalLight('#ffdf9e', 3.15);
    this.sun.position.set(6.8, 8.6, 4.8);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const sc = this.sun.shadow.camera;
    sc.left = sc.bottom = -10.5;
    sc.right = sc.top = 10.5;
    sc.near = 1;
    sc.far = 34;
    this.sun.shadow.bias = -0.0006;
    this.scene.add(this.sun, this.sun.target);

    // 2. 纵向穿城水道（x ∈ [-1.45, 1.45]）与两岸青石板街面
    this.waterCanvas = document.createElement('canvas');
    this.waterCanvas.width = 96;
    this.waterCanvas.height = 256;
    this.waterTex = pixelTex(this.waterCanvas);
    this.drawWaterCanvas(0);

    this.buildCanalAndBanks(gradientMap);
    this.buildArchedStoneBridge();
    this.buildRightSideInn();
    this.buildLeftSideMarketAndCourtyard();
    this.buildGreeneryAndProps();

    // 3. 猫咪脚下接地软阴影贴片（跟随猫咪位置与姿态缩放）
    const shadowGeo = new PlaneGeometry(0.95, 1.18);
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
    this.contactShadow.position.set(0, 0.008, 0.35);
    this.contactShadow.renderOrder = 1;
    this.scene.add(this.contactShadow);
  }

  /** 根据世界坐标 (x, z) 计算可行走表面高度（石拱桥中心 y=0.0，向两岸缓坡过渡至 y=-0.12） */
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

    // 灯笼微光呼吸感
    this.lanternLights.forEach((l, i) => {
      l.intensity = 1.9 + Math.sin(this.waterTime * 3.2 + i * 1.3) * 0.2;
    });

    if (catPos) {
      const groundY = this.heightAt(catPos.x, catPos.z);
      catPos.y = groundY;
      this.contactShadow.position.set(catPos.x, groundY + 0.008, catPos.z);
      this.contactShadow.rotation.y = catHeading;
      if (catState === 'sit') {
        this.contactShadow.scale.set(0.82, 1, 0.78);
      } else if (catState === 'belly' || catState === 'loaf') {
        this.contactShadow.scale.set(1.06, 1, 1.05);
      } else {
        this.contactShadow.scale.set(0.88, 1, 1.04);
      }
    }
  }

  /** 绘制动态像素波光水面（翡翠冷调水底 + 岸边屋影 + 红灯笼暖金倒影 + 粼粼波光与落花） */
  private drawWaterCanvas(t: number) {
    const w = this.waterCanvas.width;
    const h = this.waterCanvas.height;
    const ctx = this.waterCanvas.getContext('2d')!;
    const img = ctx.createImageData(w, h);

    for (let y = 0; y < h; y++) {
      const wz = (y / h) * GROUND - GROUND / 2;
      for (let x = 0; x < w; x++) {
        const wx = ((x / w) - 0.5) * 2.9;
        const bankDist = 1.45 - Math.abs(wx);

        // 基础翡翠碧水色阶
        let r = 34;
        let g = 74;
        let b = 68;

        // 河岸石壁暗部倒影
        if (bankDist < 0.35) {
          r = 22;
          g = 48;
          b = 46;
        } else if (bankDist < 0.65) {
          r = 28;
          g = 62;
          b = 58;
        }

        // 中央青石拱桥桥洞深色投影（wz ∈ [-0.85, 1.55]）
        const underBridge = wz > -0.88 && wz < 1.58;
        if (underBridge) {
          r = Math.round(r * 0.52);
          g = Math.round(g * 0.55);
          b = Math.round(b * 0.58);
        }

        // 右侧客栈红灯笼在水面的暖金橘色波纹倒影
        if (wx > 0.25 && !underBridge && Math.abs(wz + 0.5) < 4.2) {
          const waveX = Math.sin(y * 0.55 + t * 4.2) * 0.14;
          const lanternGlow = Math.max(0, 1 - Math.abs(wx - (0.88 + waveX)) * 2.6);
          const band = (Math.sin(y * 0.85 - t * 3.0) + 1) * 0.5;
          const k = lanternGlow * (0.35 + 0.45 * band);
          r = Math.min(255, Math.round(r + 185 * k));
          g = Math.min(255, Math.round(g + 96 * k));
          b = Math.min(255, Math.round(b + 24 * k));
        }

        // 动态像素波纹与阳光碎金高光（八方旅人标志性水面闪烁颗粒）
        if (!underBridge && bankDist > 0.2) {
          const wave1 = Math.sin(x * 0.48 + y * 0.32 - t * 2.8);
          const wave2 = Math.cos(x * 0.35 - y * 0.52 + t * 2.1);
          const ripple = wave1 * wave2;
          if (ripple > 0.72 && (y % 3 === 0)) {
            // 暖金阳光波峰高光
            r = 232;
            g = 226;
            b = 178;
          } else if (ripple > 0.46 && (y % 2 === 0)) {
            // 浅翠水波纹理
            r = Math.min(255, r + 46);
            g = Math.min(255, g + 68);
            b = Math.min(255, b + 54);
          }
        }

        // 缓慢漂流的花瓣与浮萍
        const driftY = (y - Math.floor(t * 6) + h * 10) % h;
        const petalHash = ((x * 37 + driftY * 91) ^ (driftY * 13)) % 997;
        if (!underBridge && bankDist > 0.3 && petalHash === 1) {
          r = 246;
          g = 186;
          b = 198;
        } else if (!underBridge && bankDist < 0.45 && petalHash === 2) {
          r = 78;
          g = 128;
          b = 76;
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
    const mat = typeof hexOrMat === 'string' ? this.toon(hexOrMat) : hexOrMat;
    const m = new Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = true;
    m.receiveShadow = true;
    this.scene.add(m);
    return m;
  }

  /** 建造纵向穿城河道、动态水面、两岸青石板长街、亲水石阶与石栏杆 */
  private buildCanalAndBanks(gradientMap: Texture) {
    const cobbleMat = new MeshToonMaterial({ map: makeCobbleStreetTexture(), gradientMap });

    // 左岸与右岸青石板街道地面（y = -0.12，中间留出 x ∈ [-1.45, 1.45] 的河道）
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

    // 河床暗石底与动态波光水面（y = -0.44）
    const waterMesh = new Mesh(
      new PlaneGeometry(2.96, GROUND),
      new MeshToonMaterial({ map: this.waterTex, gradientMap }),
    );
    waterMesh.rotation.x = -Math.PI / 2;
    waterMesh.position.set(0, -0.44, 0);
    waterMesh.receiveShadow = true;
    this.scene.add(waterMesh);

    // 两岸厚重青石驳岸石壁与压顶条石
    for (const side of [-1, 1]) {
      const wallX = side * 1.5;
      this.add(new BoxGeometry(0.18, 0.56, GROUND), this.wallMat, wallX, -0.36, 0);
      // 压顶青石板条（留出左岸亲水石阶缺口）
      this.add(new BoxGeometry(0.24, 0.08, 9.2), '#8d897e', wallX, -0.08, -5.5);
      if (side === 1) {
        this.add(new BoxGeometry(0.24, 0.08, 9.5), '#8d897e', wallX, -0.08, 6.2);
      } else {
        this.add(new BoxGeometry(0.24, 0.08, 6.4), '#8d897e', wallX, -0.08, 6.6);
      }

      // 河岸石柱护栏（避开中央石桥 z ∈ [-0.9, 1.6] 与左岸亲水石阶 z ∈ [1.7, 3.3]）
      const zPosts = side === -1 ? [-5.2, -3.8, -2.4, -1.2, 3.5, 4.9] : [-5.2, -3.8, -2.4, -1.2, 1.9, 3.3, 4.7];
      for (const pz of zPosts) {
        this.add(new BoxGeometry(0.16, 0.42, 0.16), '#9e9a8e', side * 1.52, 0.1, pz);
        this.add(new BoxGeometry(0.2, 0.07, 0.2), '#b5b0a2', side * 1.52, 0.33, pz);
      }
      // 护栏横梁
      this.add(new BoxGeometry(0.08, 0.07, 4.1), '#949084', side * 1.52, 0.22, -3.2);
      this.add(new BoxGeometry(0.08, 0.12, 4.1), '#7f7b70', side * 1.52, 0.04, -3.2);
      if (side === 1) {
        this.add(new BoxGeometry(0.08, 0.07, 2.9), '#949084', side * 1.52, 0.22, 3.3);
        this.add(new BoxGeometry(0.08, 0.12, 2.9), '#7f7b70', side * 1.52, 0.04, 3.3);
      }
    }

    // 左岸亲水青石台阶（x ∈ [-2.2, -1.35], z ∈ [1.85, 3.15]）
    for (let i = 0; i < 4; i++) {
      this.add(
        new BoxGeometry(0.22, 0.1, 1.25),
        this.bridgeDeckMat,
        -2.05 + i * 0.2,
        -0.14 - i * 0.08,
        2.5,
      );
    }
  }

  /**
   * 建造横跨河道中央的青石拱桥（x ∈ [-1.85, 1.85], z ∈ [-0.72, 1.48]）
   * - 桥心顶面位于 y = 0.0，猫咪在 (0, 0, 0.35) 处稳立于石桥正中央。
   * - 北侧（猫身后 z = -0.66）为完整雕花青石栏杆与望柱；
   * - 南侧（猫身前 z = +1.42）中央采用低矮青石桥沿（高 0.08），两侧配石望柱，确保正面特写绝不遮挡猫爪！
   */
  private buildArchedStoneBridge() {
    const zCenter = 0.38;
    const bridgeW = 2.16;
    const segments = 9;
    const span = 3.5;
    const segLen = span / segments;

    // 分段微拱桥面与拱券侧壁
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

    // 东西桥头引桥石阶
    for (const side of [-1, 1]) {
      for (let s = 0; s < 3; s++) {
        const sx = side * (1.58 + s * 0.18);
        const sy = -0.05 - s * 0.035;
        this.add(new BoxGeometry(0.2, 0.08, bridgeW - 0.1), this.bridgeDeckMat, sx, sy, zCenter);
      }
    }

    // 北侧完整雕花青石桥栏（猫背后 z = -0.64）
    const northZ = -0.64;
    for (const px of [-1.68, -1.02, -0.34, 0.34, 1.02, 1.68]) {
      const py = this.heightAt(px, zCenter);
      this.add(new BoxGeometry(0.17, 0.44, 0.17), '#a5a093', px, py + 0.2, northZ);
      this.add(new BoxGeometry(0.22, 0.08, 0.22), '#bcb6a8', px, py + 0.44, northZ);
      this.add(new SphereGeometry(0.075, 6, 6), '#c6c0b2', px, py + 0.51, northZ);
    }
    for (let i = 0; i < 5; i++) {
      const rx = -1.35 + i * 0.675;
      const ry = this.heightAt(rx, zCenter);
      this.add(new BoxGeometry(0.56, 0.07, 0.09), '#9d988b', rx, ry + 0.33, northZ);
      this.add(new BoxGeometry(0.54, 0.18, 0.07), '#848074', rx, ry + 0.16, northZ);
    }

    // 南侧桥沿与桥头石望柱（z = +1.40，中央为低矮压边石条，绝不挡正面镜头）
    const southZ = 1.4;
    for (const px of [-1.68, -1.12, 1.12, 1.68]) {
      const py = this.heightAt(px, zCenter);
      this.add(new BoxGeometry(0.17, 0.4, 0.17), '#a5a093', px, py + 0.18, southZ);
      this.add(new BoxGeometry(0.22, 0.07, 0.22), '#bcb6a8', px, py + 0.4, southZ);
    }
    this.add(new BoxGeometry(0.44, 0.22, 0.08), '#8a8679', -1.4, -0.02, southZ);
    this.add(new BoxGeometry(0.44, 0.22, 0.08), '#8a8679', 1.4, -0.02, southZ);
    this.add(new BoxGeometry(2.1, 0.07, 0.12), '#969184', 0, 0.02, southZ);
  }

  /** 建造右侧双层古风木质客栈/茶楼、飞檐黛瓦、透光雕花窗、蓝布招幌与暖红灯笼 */
  private buildRightSideInn() {
    const ix = 4.45;
    const iz = -1.85;

    // 青石台基
    this.add(new BoxGeometry(3.8, 0.28, 6.2), this.wallMat, ix, -0.02, iz);

    // 一层主体木骨白墙与外挑木廊柱
    this.add(new BoxGeometry(3.1, 1.85, 5.4), this.timberWallMat, ix + 0.25, 0.95, iz);
    for (const pz of [-4.2, -2.7, -1.2, 0.3]) {
      this.add(new CylinderGeometry(0.085, 0.095, 1.85, 8), '#4a2e1f', 2.48, 0.92, pz);
    }
    // 一层客栈门厅暖光内景与门槛
    this.add(new BoxGeometry(0.12, 1.35, 1.15), '#382216', 2.78, 0.72, -1.2);
    const doorGlow = new Mesh(new PlaneGeometry(0.95, 1.18), this.windowMat);
    doorGlow.rotation.y = -Math.PI / 2;
    doorGlow.position.set(2.71, 0.72, -1.2);
    this.scene.add(doorGlow);

    // 一层两侧透光雕花木窗
    for (const wz of [-3.15, -0.15]) {
      const wMesh = new Mesh(new PlaneGeometry(0.85, 0.72), this.windowMat);
      wMesh.rotation.y = -Math.PI / 2;
      wMesh.position.set(2.78, 1.05, wz);
      this.scene.add(wMesh);
    }

    // 一层飞檐坡屋顶（腰檐）
    this.buildPitchedRoof(ix, 1.92, iz, 4.1, 6.0, 0.65);

    // 二层楼阁主体、木质挑廊护栏与三扇暖光木窗
    this.add(new BoxGeometry(2.75, 1.48, 4.7), this.timberWallMat, ix + 0.3, 2.72, iz);
    this.add(new BoxGeometry(0.12, 0.42, 4.75), '#523424', 2.78, 2.18, iz);
    for (const wz of [-2.95, -1.75, -0.55]) {
      const wMesh = new Mesh(new PlaneGeometry(0.78, 0.68), this.windowMat);
      wMesh.rotation.y = -Math.PI / 2;
      wMesh.position.set(3.0, 2.82, wz);
      this.scene.add(wMesh);
    }

    // 二层主屋顶（黛瓦歇山顶 + 脊兽翘角）
    this.buildPitchedRoof(ix + 0.2, 3.55, iz, 3.65, 5.4, 0.95);

    // 门前蓝布招幌/酒旗（对标参考图右侧客栈蓝底招幌）
    this.add(new CylinderGeometry(0.045, 0.055, 2.15, 6), '#4a2e1f', 2.32, 0.95, 0.55);
    this.add(new BoxGeometry(0.65, 0.06, 0.06), '#4a2e1f', 2.06, 1.92, 0.55);
    const banner = new Mesh(
      new PlaneGeometry(0.46, 0.92),
      new MeshToonMaterial({ map: makeBannerTexture(), side: 2 }),
    );
    banner.rotation.y = -Math.PI / 5;
    banner.position.set(1.96, 1.4, 0.55);
    banner.castShadow = true;
    this.scene.add(banner);

    // 屋檐下悬挂的红灯笼与暖橙点光源
    const lanternPositions: [number, number, number, boolean][] = [
      [2.42, 1.62, -3.8, false],
      [2.42, 1.62, -2.35, true],
      [2.42, 1.62, -0.75, true],
      [2.42, 1.62, 0.65, false],
      [2.62, 3.22, -2.6, false],
      [2.62, 3.22, -1.0, false],
    ];
    for (const [lx, ly, lz, withLight] of lanternPositions) {
      this.hangingLantern(lx, ly, lz, withLight);
    }

    // 客栈临河茶座木桌与木凳
    this.teaTable(2.35, 2.35);
    this.obstacles.push({ x: ix, z: iz, r: 2.6 });
    this.obstacles.push({ x: 2.35, z: 2.35, r: 0.65 });
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

    // 屋脊与两端飞檐翘角
    this.add(new BoxGeometry(0.24, 0.2, lengthZ + 0.28), '#262d34', x, y + height + 0.04, z);
    for (const sz of [-1, 1]) {
      this.add(
        new BoxGeometry(0.28, 0.18, 0.24),
        '#2c343c',
        x - halfW + 0.05,
        y + 0.12,
        z + sz * (lengthZ / 2),
      );
    }
  }

  /** 建造悬挂发光红灯笼 */
  private hangingLantern(x: number, y: number, z: number, addLight: boolean) {
    this.add(new CylinderGeometry(0.015, 0.015, 0.22, 6), '#3a2418', x, y + 0.18, z);
    this.add(new CylinderGeometry(0.11, 0.11, 0.04, 8), '#3a2418', x, y + 0.11, z);
    const body = new Mesh(
      new SphereGeometry(0.15, 10, 8),
      new MeshBasicMaterial({ color: '#ff642e' }),
    );
    body.scale.set(0.92, 1.15, 0.92);
    body.position.set(x, y, z);
    this.scene.add(body);
    this.add(new CylinderGeometry(0.09, 0.09, 0.04, 8), '#3a2418', x, y - 0.12, z);

    if (addLight) {
      const light = new PointLight('#ff9638', 1.9, 6.2, 1.5);
      light.position.set(x - 0.25, y - 0.1, z);
      this.scene.add(light);
      this.lanternLights.push(light);
    }
  }

  /** 建造左侧街市木摊位、徽派古宅与错落台阶 */
  private buildLeftSideMarketAndCourtyard() {
    // 左后方古宅院落（马头墙 + 黛瓦 + 暖光花窗）
    const hx = -4.65;
    const hz = -3.65;
    this.add(new BoxGeometry(3.4, 2.2, 3.1), this.timberWallMat, hx, 0.98, hz);
    this.buildPitchedRoof(hx, 2.1, hz, 3.8, 3.5, 0.82);
    // 两侧马头墙阶梯山墙
    for (const sz of [-1.62, 1.62]) {
      this.add(new BoxGeometry(3.5, 0.35, 0.18), '#dfd3be', hx, 2.25, hz + sz);
      this.add(new BoxGeometry(2.1, 0.35, 0.18), '#dfd3be', hx, 2.58, hz + sz);
      this.add(new BoxGeometry(3.58, 0.07, 0.24), '#2f3740', hx, 2.44, hz + sz);
      this.add(new BoxGeometry(2.18, 0.07, 0.24), '#2f3740', hx, 2.77, hz + sz);
    }
    const win = new Mesh(new PlaneGeometry(0.82, 0.68), this.windowMat);
    win.rotation.y = Math.PI / 2;
    win.position.set(hx + 1.71, 1.15, hz + 0.3);
    this.scene.add(win);
    this.hangingLantern(hx + 1.85, 1.72, hz + 1.25, true);
    this.obstacles.push({ x: hx, z: hz, r: 2.3 });

    // 左侧街市摊位 1（靠桥头北侧：条纹布篷 + 木柜台 + 陶罐木桶）
    this.marketStall(-2.85, -0.55);
    // 左侧街市摊位 2（南侧街角茶果摊）
    this.marketStall(-3.35, 2.35);
  }

  /** 街市木摊位（木柱、条纹布篷、柜台、木桶与陶罐） */
  private marketStall(x: number, z: number) {
    const g = new Group();
    g.position.set(x, -0.12, z);
    this.scene.add(g);

    const addPart = (geo: BufferGeometry, matOrHex: string | Material, px: number, py: number, pz: number) => {
      const m = new Mesh(geo, typeof matOrHex === 'string' ? this.toon(matOrHex) : matOrHex);
      m.position.set(px, py, pz);
      m.castShadow = true;
      m.receiveShadow = true;
      g.add(m);
      return m;
    };

    // 木柜台与四根立柱
    addPart(new BoxGeometry(0.95, 0.62, 1.55), '#7a4e32', 0, 0.31, 0);
    addPart(new BoxGeometry(1.04, 0.07, 1.64), '#9c6844', 0, 0.64, 0);
    for (const px of [-0.42, 0.42]) {
      for (const pz of [-0.7, 0.7]) {
        addPart(new CylinderGeometry(0.04, 0.04, 1.55, 6), '#543522', px, 0.78, pz);
      }
    }
    // 倾斜条纹布篷
    const awning = addPart(
      new BoxGeometry(1.28, 0.06, 1.78),
      new MeshToonMaterial({ map: makeAwningTexture() }),
      0.06,
      1.52,
      0,
    );
    awning.rotation.z = -0.22;

    // 柜台上的青瓷罐与暖橙柑橘篮
    addPart(new CylinderGeometry(0.11, 0.13, 0.24, 8), '#6b8e88', 0.1, 0.78, -0.35);
    addPart(new BoxGeometry(0.32, 0.1, 0.38), '#b58452', 0.08, 0.72, 0.28);
    addPart(new SphereGeometry(0.08, 6, 6), '#e8883a', 0.06, 0.8, 0.24);
    addPart(new SphereGeometry(0.075, 6, 6), '#f09c42', 0.14, 0.79, 0.35);

    // 摊位旁木桶与陶瓮
    addPart(new CylinderGeometry(0.18, 0.16, 0.42, 8), '#8a5a38', 0.56, 0.21, 0.68);
    addPart(new CylinderGeometry(0.16, 0.12, 0.34, 8), '#9e563c', 0.52, 0.17, -0.72);

    this.obstacles.push({ x, z, r: 0.95 });
  }

  private teaTable(x: number, z: number) {
    this.add(new BoxGeometry(0.72, 0.07, 0.72), '#7d5034', x, 0.42, z);
    this.add(new CylinderGeometry(0.07, 0.09, 0.52, 6), '#5a3824', x, 0.16, z);
    this.add(new CylinderGeometry(0.07, 0.06, 0.12, 8), '#d8cbb8', x - 0.12, 0.51, z - 0.08);
    this.add(new CylinderGeometry(0.045, 0.04, 0.08, 8), '#e6dec8', x + 0.14, 0.49, z + 0.1);
    for (const [sx, sz] of [
      [-0.52, 0],
      [0.52, 0],
    ]) {
      this.add(new CylinderGeometry(0.14, 0.12, 0.28, 8), '#6c442b', x + sx, 0.04, z + sz);
    }
  }

  /** 布置古树、桥头石灯笼、猫咪软垫、食盆与花坛盆景 */
  private buildGreeneryAndProps() {
    // 东西桥头古风石灯笼
    this.stoneLantern(-1.82, -1.08);
    this.stoneLantern(1.82, -1.08);

    // 苍翠古树与金秋/粉樱点缀树冠（右上与左上枝叶构成前景/背景框景）
    this.tree(-5.4, 0.85, 1.25, '#588248', '#789e58', '#e6a8b2');
    this.tree(-2.35, -2.25, 0.92, '#4e7640', '#6d9452', '#dca068');
    this.tree(2.35, -4.35, 1.15, '#527a44', '#729854', '#e4b268');
    this.tree(5.45, 3.65, 1.05, '#4c743e', '#688e4e', '#e8a6b0');
    this.tree(-5.2, 4.1, 1.0, '#568046', '#749c56');

    // 猫咪软垫、食盆与桥畔盆景（放在阳光充足的桥头青石小广场）
    this.catBed(2.05, 0.42);
    this.bowl(-2.05, 0.62);
    this.pot(-1.88, 1.48, '#eb8c9c');
    this.pot(1.92, 1.48, '#f2cc68');
  }

  private stoneLantern(x: number, z: number) {
    const y0 = -0.12;
    this.add(new BoxGeometry(0.34, 0.12, 0.34), '#8a8679', x, y0 + 0.06, z);
    this.add(new CylinderGeometry(0.08, 0.1, 0.46, 6), '#9a9688', x, y0 + 0.35, z);
    this.add(new BoxGeometry(0.28, 0.08, 0.28), '#a6a294', x, y0 + 0.6, z);
    // 暖光灯室
    const chamber = new Mesh(
      new BoxGeometry(0.18, 0.2, 0.18),
      new MeshBasicMaterial({ color: '#ffcf70' }),
    );
    chamber.position.set(x, y0 + 0.74, z);
    this.scene.add(chamber);
    // 伞盖与宝顶
    const cap = this.add(new CylinderGeometry(0.06, 0.28, 0.18, 4), '#727066', x, y0 + 0.92, z);
    cap.rotation.y = Math.PI / 4;
    this.add(new SphereGeometry(0.055, 6, 6), '#8a8679', x, y0 + 1.04, z);
    this.obstacles.push({ x, z, r: 0.32 });
  }

  private tree(x: number, z: number, s: number, darkLeaf: string, midLeaf: string, accentLeaf?: string) {
    const y0 = -0.12;
    this.add(new CylinderGeometry(0.13 * s, 0.19 * s, 1.35 * s, 6), '#5a3c28', x, y0 + 0.65 * s, z);
    this.add(new IcosahedronGeometry(0.82 * s, 1), darkLeaf, x, y0 + 1.55 * s, z);
    this.add(new IcosahedronGeometry(0.62 * s, 1), midLeaf, x + 0.24 * s, y0 + 1.98 * s, z + 0.15 * s);
    this.add(new IcosahedronGeometry(0.54 * s, 1), midLeaf, x - 0.26 * s, y0 + 1.78 * s, z - 0.18 * s);
    if (accentLeaf) {
      this.add(new IcosahedronGeometry(0.38 * s, 0), accentLeaf, x + 0.18 * s, y0 + 2.22 * s, z + 0.22 * s);
    }
    this.obstacles.push({ x, z, r: 0.68 * s });
  }

  private catBed(x: number, z: number) {
    const y0 = -0.12;
    const ring = this.add(new TorusGeometry(0.38, 0.11, 6, 14), '#d47c6a', x, y0 + 0.11, z);
    ring.rotation.x = -Math.PI / 2;
    this.add(new CylinderGeometry(0.36, 0.36, 0.08, 14), '#f4d8c6', x, y0 + 0.05, z);
  }

  private bowl(x: number, z: number) {
    const y0 = -0.12;
    this.add(new CylinderGeometry(0.18, 0.14, 0.11, 10), '#5888b8', x, y0 + 0.06, z);
    this.add(new CylinderGeometry(0.14, 0.14, 0.02, 10), '#c2824c', x, y0 + 0.11, z);
  }

  private pot(x: number, z: number, flower: string) {
    const y0 = -0.12;
    this.add(new CylinderGeometry(0.2, 0.15, 0.28, 8), '#b86c46', x, y0 + 0.14, z);
    this.add(new IcosahedronGeometry(0.2, 0), '#5e964e', x, y0 + 0.38, z);
    this.add(new IcosahedronGeometry(0.09, 0), flower, x + 0.06, y0 + 0.52, z + 0.06);
    this.obstacles.push({ x, z, r: 0.28 });
  }

  /** 判断坐标 p 是否在石桥桥面或两岸青石街道可行走区（禁止落入河道水面） */
  walkable(p: Vector3) {
    if (Math.abs(p.x) > 4.6 || Math.abs(p.z) > 4.6) return false;
    const onBridge = p.z >= -0.42 && p.z <= 1.15 && Math.abs(p.x) <= 1.75;
    const inCanal = Math.abs(p.x) < 1.72;
    if (inCanal && !onBridge) return false;
    return this.obstacles.every((o) => Math.hypot(p.x - o.x, p.z - o.z) > o.r + 0.32);
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
    return new Vector3(0, 0, 0.35);
  }

  private clearLine(a: Vector3, b: Vector3) {
    for (let t = 0.1; t <= 1; t += 0.1) {
      if (!this.walkable(a.clone().lerp(b, t))) return false;
    }
    return true;
  }
}
