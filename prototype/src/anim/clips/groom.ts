import { cycle, pose, sin, type ClipDef } from '../clipDsl';
import { SIT, SIT_HIPS } from './poses';

/** 坐姿抬右前爪舔爪，一个循环舔 3 下 */
export const groom: ClipDef = {
  name: 'groom',
  label: '舔毛',
  duration: 2.4,
  loop: true,
  lookWeight: 0,
  tailSway: 3,
  keys: cycle(2.4, 18, (ph) => {
    const lick = sin(ph * 3);
    return {
      pose: pose(SIT, {
        shoulderR: [-45, 12, 0],
        elbowR: [105, 0, 0],
        fpawR: [40 + lick * 6, 0, 0],
        neck: [26, -14, 0],
        head: [24 + lick * 8, -18, -10],
      }),
      hips: SIT_HIPS,
    };
  }),
  face: [
    { t: 0, eyes: 'closed', mouth: 'tongue' },
    { t: 0.4, mouth: 'closed' },
    { t: 0.8, mouth: 'tongue' },
    { t: 1.2, mouth: 'closed' },
    { t: 1.6, mouth: 'tongue' },
    { t: 2.0, mouth: 'closed' },
  ],
};
