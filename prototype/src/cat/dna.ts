import { NEUTRAL_SHAPE, type ShapeParams } from './shape';

/** 印记的公共筛选条件：限定部件和模型空间范围（猫自身左侧为 +X） */
export interface MarkingFilter {
  parts?: string[];
  minX?: number;
  maxX?: number;
  minY?: number;
  maxY?: number;
  minZ?: number;
  maxZ?: number;
  /** 边缘不规则度 0..1 */
  noise?: number;
  noiseScale?: number;
}

export type Marking =
  | ({ type: 'blob'; color: string; center: [number, number, number]; radius: [number, number, number] } & MarkingFilter)
  | ({ type: 'underside'; color: string; threshold?: number } & MarkingFilter)
  | ({ type: 'stripes'; color: string; axis: 'x' | 'y' | 'z'; frequency: number; width: number } & MarkingFilter)
  | ({ type: 'part'; color: string } & MarkingFilter);

export interface PetDNA {
  id: string;
  name: string;
  shape: ShapeParams;
  coat: {
    /** 画好的印记贴图（256x256，按母版 UV 图集）。为空则用 markings 烘焙 */
    texture?: string | null;
    base: string;
    palette?: string[];
    markings?: Marking[];
  };
  earInner?: string;
  eyes: { iris: string; pupil?: string };
  nose?: string;
  personality: Record<string, number>;
}

export async function loadPetIndex(): Promise<string[]> {
  const res = await fetch(`${import.meta.env.BASE_URL}pets/index.json`);
  return (await res.json()).pets;
}

export async function loadPet(id: string): Promise<PetDNA> {
  const res = await fetch(`${import.meta.env.BASE_URL}pets/${id}.json`);
  const raw = await res.json();
  return { ...raw, shape: { ...NEUTRAL_SHAPE, ...raw.shape } };
}
