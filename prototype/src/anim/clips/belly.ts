import { cycle, pose, sin, type ClipDef, type Pose } from '../clipDsl';

/**
 * 第 7 个动作：翻肚皮撒娇（仰躺露肚皮）。
 * 四肢自然向两侧舒展开，完全不遮挡腹部正中央，所有宠物直接复用。
 */
const BELLY_BASE: Pose = {
  hips: [6, 0, 154],
  spine: [4, 0, 4],
  chest: [8, 0, 6],
  neck: [16, 10, -10],
  head: [24, 16, -14],
  shoulderL: [-22, 0, -52],
  elbowL: [82, 0, 0],
  fpawL: [28, 0, 0],
  shoulderR: [-22, 0, 56],
  elbowR: [78, 0, 0],
  fpawR: [26, 0, 0],
  hipL: [28, 0, -50],
  kneeL: [64, 0, 0],
  hpawL: [-24, 0, 0],
  hipR: [28, 0, 52],
  kneeR: [64, 0, 0],
  hpawR: [-24, 0, 0],
  tail0: [28, 18, 0],
  tail1: [12, 14, 0],
  tail2: [6, 12, 0],
  tail3: [4, 10, 0],
  tail4: [2, 8, 0],
  tail5: [0, 6, 0],
};

export const belly: ClipDef = {
  name: 'belly',
  label: '翻肚皮',
  duration: 3.6,
  loop: true,
  lookWeight: 0,
  tailSway: 5,
  keys: cycle(3.6, 16, (ph) => {
    const w = sin(ph);
    const p = sin(ph * 2);
    return {
      pose: pose(BELLY_BASE, {
        hips: [6, 0, 154 + w * 4],
        head: [24 + p * 3, 16 + w * 5, -14 - w * 4],
        shoulderL: [-22 + p * 6, 0, -52],
        shoulderR: [-22 - p * 6, 0, 56],
        fpawL: [28 + p * 8, 0, 0],
        fpawR: [26 - p * 8, 0, 0],
        tail0: [28, 18 + w * 12, 0],
        tail1: [12, 14 + w * 10, 0],
      }),
      hips: [0, -0.22 + p * 0.004, 0],
    };
  }),
  face: [
    { t: 0, eyes: 'happy', mouth: 'closed' },
    { t: 1.4, eyes: 'happy', mouth: 'open' },
    { t: 2.2, eyes: 'happy', mouth: 'closed' },
  ],
};
