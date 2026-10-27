import { Raycaster, type Camera, type Vector2 } from 'three';
import { ATLAS_SIZE, PARTS } from '../cat/parts';
import type { CatActor } from '../cat/catActor';

/**
 * 直接在 3D 猫身上画印记：
 * 射线命中 UV -> 从 `RestMap` 查询命中纹素的部件编号 `partId`，并将笔刷裁切限定在同一部件内。
 */
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
    if (px < 0 || px >= ATLAS_SIZE || py < 0 || py >= ATLAS_SIZE) return false;

    const restMap = this.actor.restMap;
    const centerIdx = py * ATLAS_SIZE + px;
    const targetPartId = restMap.partId[centerIdx];
    const fallbackPart = PARTS.find(({ rect: [x, y, w, h] }) => px >= x && px < x + w && py >= y && py < y + h);
    if (targetPartId < 0 && !fallbackPart) return false;

    const ctx = this.actor.coatCanvas.getContext('2d')!;
    ctx.fillStyle = this.color;
    const half = Math.floor(this.brush / 2);
    for (let y = py - half; y < py - half + this.brush; y++) {
      for (let x = px - half; x < px - half + this.brush; x++) {
        if (x < 0 || x >= ATLAS_SIZE || y < 0 || y >= ATLAS_SIZE) continue;
        if (targetPartId >= 0) {
          if (restMap.partId[y * ATLAS_SIZE + x] !== targetPartId) continue;
        } else if (fallbackPart) {
          const [rx, ry, rw, rh] = fallbackPart.rect;
          if (x < rx || x >= rx + rw || y < ry || y >= ry + rh) continue;
        }
        ctx.fillRect(x, y, 1, 1);
      }
    }
    this.actor.coatTexture.needsUpdate = true;
    return true;
  }
}
