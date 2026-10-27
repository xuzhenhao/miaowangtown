import {
  CanvasTexture,
  Color,
  CylinderGeometry,
  DirectionalLight,
  HemisphereLight,
  IcosahedronGeometry,
  Mesh,
  MeshToonMaterial,
  NearestFilter,
  PlaneGeometry,
  BoxGeometry,
  SRGBColorSpace,
  Scene,
  TorusGeometry,
  Vector3,
  type BufferGeometry,
  type Texture,
} from 'three';
import type { WorldNav } from '../anim/brain';

const GROUND = 16;
const TEX_PER_UNIT = 48;

function rand(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function groundTexture(): CanvasTexture {
  const size = GROUND * TEX_PER_UNIT;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(size, size);
  const r = rand(7);
  const greens = [
    [118, 168, 82],
    [104, 154, 74],
    [132, 180, 90],
  ];
  const dirt = [
    [196, 164, 118],
    [184, 150, 106],
  ];
  const stone = [
    [206, 196, 178],
    [190, 180, 162],
  ];
  const toWorld = (px: number) => (px / TEX_PER_UNIT) - GROUND / 2;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const wx = toWorld(x);
      const wz = toWorld(y);
      const n = r();
      let c = greens[n < 0.7 ? 0 : n < 0.88 ? 1 : 2];
      const pathX = Math.sin(wz * 0.5) * 1.2 + 2.2;
      if (Math.abs(wx - pathX) < 0.55 + Math.sin(wz * 3.1) * 0.06) c = dirt[n < 0.8 ? 0 : 1];
      const plaza = Math.hypot(wx + 0.2, wz - 0.4);
      if (plaza < 1.9) {
        const tile = (Math.floor(wx * 3) + Math.floor(wz * 3)) & 1;
        c = stone[tile];
        if (plaza > 1.8) c = [160, 150, 134];
      }
      if (n > 0.9975 && plaza > 2.1) c = [[236, 228, 120], [240, 170, 190], [250, 250, 245]][Math.floor(r() * 3)];
      img.data.set([c[0], c[1], c[2], 255], (y * size + x) * 4);
    }
  }
  ctx.putImageData(img, 0, 0);
  const tex = new CanvasTexture(canvas);
  tex.magFilter = NearestFilter;
  tex.minFilter = NearestFilter;
  tex.generateMipmaps = false;
  tex.colorSpace = SRGBColorSpace;
  return tex;
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
  private toon: (hex: string) => MeshToonMaterial;

  constructor(gradientMap: Texture) {
    this.scene.background = new Color('#a9d4e8');
    this.toon = (hex) => new MeshToonMaterial({ color: hex, gradientMap });

    this.scene.add(new HemisphereLight('#fff4e0', '#9a9a7a', 0.85));
    this.sun = new DirectionalLight('#fff1d6', 2.8);
    this.sun.position.set(5, 9, 6);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(1024, 1024);
    const sc = this.sun.shadow.camera;
    sc.left = sc.bottom = -9;
    sc.right = sc.top = 9;
    sc.near = 1;
    sc.far = 30;
    this.sun.shadow.bias = -0.0008;
    this.scene.add(this.sun, this.sun.target);

    const ground = new Mesh(
      new PlaneGeometry(GROUND, GROUND),
      new MeshToonMaterial({ map: groundTexture(), gradientMap }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);

    this.house(-4.2, -4.2);
    [
      [-5.5, 1.5, 1.1],
      [4.8, -3.8, 1.3],
      [5.6, 3.5, 1.0],
      [-2.2, 5.2, 0.9],
      [-6.2, -1.2, 0.8],
    ].forEach(([x, z, s]) => this.tree(x, z, s));
    this.fence();
    this.catBed(1.3, -1.6);
    this.bowl(-2.2, -2.2);
    this.pot(-1.7, 1.9, '#e88a9a');
    this.pot(1.6, 2.2, '#f2d36b');
  }

  private add(geo: BufferGeometry, hex: string, x: number, y: number, z: number) {
    const m = new Mesh(geo, this.toon(hex));
    m.position.set(x, y, z);
    m.castShadow = true;
    m.receiveShadow = true;
    this.scene.add(m);
    return m;
  }

  private house(x: number, z: number) {
    this.add(new BoxGeometry(3, 2, 2.6), '#f3e6cc', x, 1, z);
    const roof = this.add(new CylinderGeometry(1.75, 1.75, 3.3, 3, 1), '#c0634c', x, 2.4, z);
    roof.rotation.z = Math.PI / 2;
    roof.rotation.x = -Math.PI / 2;
    roof.scale.set(1, 1, 0.6);
    this.add(new BoxGeometry(0.7, 1.2, 0.1), '#8a5a3c', x + 0.4, 0.6, z + 1.31);
    this.add(new BoxGeometry(0.6, 0.5, 0.1), '#9fd0e6', x - 0.8, 1.2, z + 1.31);
    this.obstacles.push({ x, z, r: 2.2 });
  }

  private tree(x: number, z: number, s: number) {
    this.add(new CylinderGeometry(0.12 * s, 0.16 * s, 1.2 * s, 6), '#8a6243', x, 0.6 * s, z);
    const leaf = new IcosahedronGeometry(0.75 * s, 0);
    this.add(leaf, '#5f9b52', x, 1.45 * s, z);
    this.add(new IcosahedronGeometry(0.55 * s, 0), '#74b35f', x + 0.2 * s, 1.95 * s, z + 0.1 * s);
    this.obstacles.push({ x, z, r: 0.7 * s });
  }

  private fence() {
    for (let i = 0; i < 9; i++) {
      const x = -1 + i * 0.6;
      this.add(new BoxGeometry(0.1, 0.55, 0.1), '#e9dcc0', x, 0.27, -5.6);
    }
    this.add(new BoxGeometry(5, 0.08, 0.06), '#e9dcc0', 1.4, 0.4, -5.6);
    this.add(new BoxGeometry(5, 0.08, 0.06), '#e9dcc0', 1.4, 0.18, -5.6);
  }

  private catBed(x: number, z: number) {
    const ring = this.add(new TorusGeometry(0.42, 0.13, 6, 14), '#d98a7a', x, 0.12, z);
    ring.rotation.x = -Math.PI / 2;
    this.add(new CylinderGeometry(0.4, 0.4, 0.08, 14), '#f4d6c8', x, 0.05, z);
  }

  private bowl(x: number, z: number) {
    this.add(new CylinderGeometry(0.2, 0.15, 0.12, 10), '#5e8fc4', x, 0.06, z);
    this.add(new CylinderGeometry(0.16, 0.16, 0.02, 10), '#b87b4b', x, 0.12, z);
  }

  private pot(x: number, z: number, flower: string) {
    this.add(new CylinderGeometry(0.2, 0.15, 0.3, 8), '#c4774f', x, 0.15, z);
    this.add(new IcosahedronGeometry(0.2, 0), '#6aa85a', x, 0.42, z);
    this.add(new IcosahedronGeometry(0.09, 0), flower, x + 0.06, 0.58, z + 0.06);
    this.obstacles.push({ x, z, r: 0.3 });
  }

  walkable(p: Vector3) {
    if (Math.hypot(p.x, p.z) > 5.2) return false;
    return this.obstacles.every((o) => Math.hypot(p.x - o.x, p.z - o.z) > o.r + 0.35);
  }

  randomTarget(from: Vector3): Vector3 {
    for (let i = 0; i < 40; i++) {
      const a = Math.random() * Math.PI * 2;
      const d = 1.2 + Math.random() * 2.5;
      const p = new Vector3(from.x + Math.sin(a) * d, 0, from.z + Math.cos(a) * d);
      if (this.walkable(p) && this.clearLine(from, p)) return p;
    }
    return new Vector3(0, 0, 0.4);
  }

  private clearLine(a: Vector3, b: Vector3) {
    for (let t = 0.1; t <= 1; t += 0.1) {
      if (!this.walkable(a.clone().lerp(b, t))) return false;
    }
    return true;
  }
}
