import { Raycaster, type Camera, type Vector2 } from 'three';
import { ATLAS_SIZE, PARTS } from '../cat/parts';
import type { CatActor } from '../cat/catActor';

/** 直接在 3D 猫身上画印记：射线命中 UV -> 写入印记图集对应纹素（限定在命中部件的区域内） */
export class CoatPainter {
  color = '#f3eee4';
  brush = 2;
  private ray = new Raycaster();

  constructor(private actor: CatActor) {}

  pick(ndc: Vector2, camera: Camera) {
    const mesh = this.actor.cat.mesh;
    mesh.computeBoundingSphere();
    this.ray.setFromCamera(ndc, camera);
    return this.ray.intersectObject(mesh, false)[0] ?? null;
  }

  paintAt(ndc: Vector2, camera: Camera): boolean {
    const hit = this.pick(ndc, camera);
    if (!hit?.uv) return false;
    const px = Math.floor(hit.uv.x * ATLAS_SIZE);
    const py = Math.floor((1 - hit.uv.y) * ATLAS_SIZE);
    const part = PARTS.find(({ rect: [x, y, w, h] }) => px >= x && px < x + w && py >= y && py < y + h);
    if (!part) return false;
    const [rx, ry, rw, rh] = part.rect;
    const ctx = this.actor.coatCanvas.getContext('2d')!;
    ctx.fillStyle = this.color;
    const half = Math.floor(this.brush / 2);
    for (let y = py - half; y < py - half + this.brush; y++) {
      for (let x = px - half; x < px - half + this.brush; x++) {
        if (x < rx || x >= rx + rw || y < ry || y >= ry + rh) continue;
        ctx.fillRect(x, y, 1, 1);
      }
    }
    this.actor.coatTexture.needsUpdate = true;
    return true;
  }
}
