import type { ClipDef } from '../clipDsl';
import { idle } from './idle';
import { walk } from './walk';
import { sit } from './sit';
import { loaf } from './loaf';
import { groom } from './groom';
import { stretch } from './stretch';
import { belly } from './belly';

/** 动作库：新增动作 = 新增一个文件 + 在这里注册一行，不碰任何宠物资源 */
export const CLIPS: ClipDef[] = [idle, walk, sit, loaf, groom, stretch, belly];

export function clipDef(name: string): ClipDef {
  const c = CLIPS.find((x) => x.name === name);
  if (!c) throw new Error(`unknown clip ${name}`);
  return c;
}
