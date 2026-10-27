import { pose, type ClipDef, type Pose } from '../clipDsl';
import { TAIL_RELAXED } from './poses';

/** 第 6 个动作：伸懒腰。后加的动作，所有宠物直接可用，不需要任何宠物专属资源。 */
const BOW: Pose = pose(TAIL_RELAXED, {
  hips: [22, 0, 0],
  spine: [6, 0, 0],
  chest: [4, 0, 0],
  neck: [-30, 0, 0],
  head: [-22, 0, 0],
  shoulderL: [-90, 0, 0],
  shoulderR: [-90, 0, 0],
  elbowL: [-5, 0, 0],
  elbowR: [-5, 0, 0],
  fpawL: [25, 0, 0],
  fpawR: [25, 0, 0],
  hipL: [-18, 0, 0],
  hipR: [-18, 0, 0],
  kneeL: [-4, 0, 0],
  kneeR: [-4, 0, 0],
  tail0: [30, 0, 0],
  tail1: [5, 0, 0],
});

const REST: Pose = pose(TAIL_RELAXED, {});

export const stretch: ClipDef = {
  name: 'stretch',
  label: '伸懒腰',
  duration: 3.4,
  loop: false,
  lookWeight: 0,
  tailSway: 2,
  keys: [
    { t: 0, pose: REST, hips: [0, 0, 0] },
    { t: 0.9, pose: BOW, hips: [0, -0.12, -0.08] },
    { t: 2.3, pose: BOW, hips: [0, -0.13, -0.09] },
    { t: 3.4, pose: REST, hips: [0, 0, 0] },
  ],
  face: [
    { t: 0, eyes: 'open', mouth: 'closed' },
    { t: 0.7, eyes: 'closed', mouth: 'open' },
    { t: 2.3, eyes: 'happy', mouth: 'closed' },
    { t: 3.0, eyes: 'open' },
  ],
};
