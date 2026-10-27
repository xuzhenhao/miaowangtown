import { cos, cycle, pose, sin, type ClipDef, type Pose } from '../clipDsl';
import { TAIL_RELAXED } from './poses';

/**
 * 真实猫科四拍侧序步态（左后 0.0 -> 左前 0.25 -> 右后 0.50 -> 右前 0.75）：
 * - 采用平滑 C1 连续周期函数驱动支撑相（56%）与摆动相（44%），消除落爪/抬爪瞬间的角速度折角。
 * - 约定（见 clipDsl.ts）：绕 X 轴负角度（-X）= 向前迈步（+Z），绕 X 轴正角度（+X）= 向后蹬地（-Z）。
 * - 摆动相前半段屈腕/屈踝抬爪离地，后半段前臂/小腿完全向前伸展落爪，配合身体双倍频垂直起伏（bob）与尾尖S形随动。
 */
function leg(ph: number, off: number, front: boolean): [number, number, number] {
  const u = (((ph + off) % 1) + 1) % 1;
  // 用偏置相位映射将 56% 周期分给支撑相（0..0.5 π），44% 分给摆动相（0.5 π..π），全程 C1 平滑无折角
  const stanceRatio = 0.56;
  let theta: number;
  let liftEnv = 0;
  let reachEnv = 0;
  let stanceMid = 0;

  if (u < stanceRatio) {
    const s = u / stanceRatio; // 0 (前爪着地) -> 1 (后蹬离地)
    theta = s * Math.PI; // 0 -> π
    stanceMid = Math.sin(theta);
  } else {
    const w = (u - stanceRatio) / (1 - stanceRatio); // 0 (后蹬离地) -> 1 (前爪着地)
    theta = Math.PI + w * Math.PI; // π -> 2π
    // 抬爪屈肘/屈膝包络：在 w ≈ 0.38 达峰值，在 w -> 0 和 w -> 1 处导数均为 0（无突变折角）
    liftEnv = Math.pow(Math.sin(w * Math.PI), 1.35);
    reachEnv = Math.sin(Math.max(0, (w - 0.45) / 0.55) * Math.PI);
  }

  // -cos(theta)：在 u=0（着地）为 -1（最前伸），在 u=stanceRatio（离地）为 +1（最后蹬）
  const swing = -Math.cos(theta);

  if (front) {
    const upper = 29 * swing - 5 * liftEnv;
    const lower = 28 * liftEnv + 6 * stanceMid - 5 * reachEnv;
    const paw = -(upper + lower) * (1 - 0.55 * liftEnv) + 12 * liftEnv;
    return [upper, lower, paw];
  } else {
    const upper = 27 * swing - 6 * liftEnv;
    const lower = 25 * liftEnv + 7 * stanceMid + 4 * reachEnv;
    const paw = -(upper + lower) * (1 - 0.5 * liftEnv) - 8 * liftEnv;
    return [upper, lower, paw];
  }
}

export const walk: ClipDef = {
  name: 'walk',
  label: '走',
  duration: 0.84,
  loop: true,
  speed: 0.38,
  lookWeight: 0.5,
  tailSway: 12,
  keys: cycle(0.84, 24, (ph) => {
    const p: Pose = {};
    const setLeg = (upper: keyof Pose, lower: keyof Pose, paw: keyof Pose, off: number, front: boolean) => {
      const [a, b, c] = leg(ph, off, front);
      p[upper] = [a, 0, 0];
      p[lower] = [b, 0, 0];
      p[paw] = [c, 0, 0];
    };
    // 四拍侧序步态：左后(0.0) -> 左前(0.25) -> 右后(0.50) -> 右前(0.75)
    setLeg('hipL', 'kneeL', 'hpawL', 0, false);
    setLeg('shoulderL', 'elbowL', 'fpawL', 0.25, true);
    setLeg('hipR', 'kneeR', 'hpawR', 0.5, false);
    setLeg('shoulderR', 'elbowR', 'fpawR', 0.75, true);

    const bob = cos(ph * 2);
    const bobSin = sin(ph * 2);
    const sway = sin(ph);
    return {
      pose: pose(TAIL_RELAXED, p, {
        hips: [3.2 * bob, sway * 4.2, cos(ph) * 3.5],
        spine: [-2.6 * bob, sway * 3.0, -cos(ph) * 2.5],
        chest: [2.8 * bob, -sway * 3.8, -cos(ph) * 2.8],
        neck: [4.0 + cos(ph * 2, 0.12) * 3.8, sway * 2.0, 0],
        head: [-cos(ph * 2, 0.12) * 3.4, -sway * 2.2, 0],
        earL: [3.5 * bobSin, 0, 1.8 * sway],
        earR: [-3.5 * bobSin, 0, 1.8 * sway],
        tail0: [-24 + 6 * bobSin, sway * 12, 0],
        tail1: [12 + 4 * bob, sin(ph, -0.15) * 16, 0],
        tail2: [16, sin(ph, -0.3) * 20, 0],
        tail3: [18, sin(ph, -0.45) * 22, 0],
        tail4: [10, sin(ph, -0.6) * 24, 0],
      }),
      hips: [0.012 * sway, -0.028 * bob, 0],
    };
  }),
};
