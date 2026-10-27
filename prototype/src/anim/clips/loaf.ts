import { cycle, pose, sin, type ClipDef } from '../clipDsl';
import { LOAF, LOAF_HIPS } from './poses';

export const loaf: ClipDef = {
  name: 'loaf',
  label: '揣手手',
  duration: 4,
  loop: true,
  lookWeight: 0.5,
  tailSway: 3,
  keys: cycle(4, 8, (ph) => {
    const b = sin(ph);
    return {
      pose: pose(LOAF, {
        chest: [-b * 1.5, 0, 0],
        head: [4 + b * 2, 0, 0],
      }),
      hips: [LOAF_HIPS[0], LOAF_HIPS[1] + b * 0.004, LOAF_HIPS[2]],
    };
  }),
  face: [
    { t: 0, eyes: 'sleepy' },
    { t: 2.6, eyes: 'closed' },
    { t: 3.4, eyes: 'sleepy' },
  ],
};
