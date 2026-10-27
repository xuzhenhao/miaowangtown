import { cycle, pose, sin, type ClipDef } from '../clipDsl';
import { SIT, SIT_HIPS } from './poses';

export const sit: ClipDef = {
  name: 'sit',
  label: '坐下',
  duration: 3,
  loop: true,
  lookWeight: 1,
  tailSway: 4,
  keys: cycle(3, 8, (ph) => {
    const b = sin(ph);
    return {
      pose: pose(SIT, {
        chest: [-5 - b * 1.5, 0, 0],
        head: [18 - b * 1.5, 0, 0],
      }),
      hips: SIT_HIPS,
    };
  }),
};
