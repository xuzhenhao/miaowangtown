import { cycle, pose, sin, type ClipDef } from '../clipDsl';
import { TAIL_RELAXED } from './poses';

export const idle: ClipDef = {
  name: 'idle',
  label: '待机呼吸',
  duration: 3.2,
  loop: true,
  lookWeight: 1,
  tailSway: 9,
  keys: cycle(3.2, 12, (ph) => {
    const b = sin(ph);
    return {
      pose: pose(TAIL_RELAXED, {
        spine: [b * 1.2, 0, 0],
        chest: [-b * 2, 0, 0],
        neck: [b * 1.5, 0, 0],
        head: [-b * 2, 0, 0],
      }),
      hips: [0, b * 0.004, 0],
    };
  }),
};
