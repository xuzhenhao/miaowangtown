import { cos, cycle, pose, sin, type ClipDef, type Pose } from '../clipDsl';
import { TAIL_RELAXED } from './poses';

/** 猫的侧序步态：左后 -> 左前 -> 右后 -> 右前，各差 1/4 周期 */
function leg(ph: number, off: number, front: boolean): [number, number, number] {
  const swing = (front ? 22 : 24) * -sin(ph, off);
  const lift = Math.max(0, cos(ph, off));
  return [swing, lift * (front ? 38 : 30), lift * 25];
}

export const walk: ClipDef = {
  name: 'walk',
  label: '走',
  duration: 0.9,
  loop: true,
  speed: 0.31,
  lookWeight: 0.5,
  tailSway: 10,
  keys: cycle(0.9, 16, (ph) => {
    const p: Pose = {};
    const setLeg = (upper: keyof Pose, lower: keyof Pose, paw: keyof Pose, off: number, front: boolean) => {
      const [a, b, c] = leg(ph, off, front);
      p[upper] = [a, 0, 0];
      p[lower] = [b, 0, 0];
      p[paw] = [c, 0, 0];
    };
    setLeg('hipL', 'kneeL', 'hpawL', 0, false);
    setLeg('shoulderL', 'elbowL', 'fpawL', 0.25, true);
    setLeg('hipR', 'kneeR', 'hpawR', 0.5, false);
    setLeg('shoulderR', 'elbowR', 'fpawR', 0.75, true);
    return {
      pose: pose(TAIL_RELAXED, p, {
        spine: [0, sin(ph) * 3, sin(ph) * 2],
        chest: [0, -sin(ph) * 3, 0],
        neck: [4 + cos(ph, 0.1) * 1.5, 0, 0],
        head: [-cos(ph * 2) * 2, -sin(ph) * 2, 0],
        tail0: [-25, 0, 0],
      }),
      hips: [0, 0.012 * cos(ph * 2), 0],
    };
  }),
};
