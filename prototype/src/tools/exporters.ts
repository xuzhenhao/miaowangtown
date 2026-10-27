import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import type { CatActor } from '../cat/catActor';

function download(blob: Blob, filename: string) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/** 导出当前印记贴图，放进 public/pets/ 并在 DNA 里填 coat.texture 即可替代 markings */
export function exportCoatPng(actor: CatActor) {
  actor.coatCanvas.toBlob((b) => b && download(b, `${actor.dna?.id ?? 'cat'}_coat.png`), 'image/png');
}

/** 母版猫（网格 + 骨骼 + 形态键 + 全部动作）-> GLB，可导入 Blender 精修后替换 */
export function buildBaseGlb(actor: CatActor): Promise<ArrayBuffer> {
  return new GLTFExporter().parseAsync(actor.cat.mesh, { binary: true, animations: actor.clips }) as Promise<ArrayBuffer>;
}

export async function exportBaseGlb(actor: CatActor) {
  const glb = await buildBaseGlb(actor);
  download(new Blob([glb], { type: 'model/gltf-binary' }), 'cat_base.glb');
}
