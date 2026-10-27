import type { Pose } from '../clipDsl';

/** 动作之间共享的基础姿态（只描述骨骼，与具体宠物无关） */

export const TAIL_RELAXED: Pose = {
  tail0: [-35, 0, 0],
  tail1: [-10, 0, 0],
  tail2: [5, 0, 0],
  tail3: [10, 0, 0],
  tail4: [10, 0, 0],
  tail5: [10, 0, 0],
};

export const SIT_HIPS: [number, number, number] = [0, -0.31, -0.03];

export const SIT: Pose = {
  hips: [-28, 0, 0],
  spine: [-5, 0, 0],
  chest: [-5, 0, 0],
  neck: [18, 0, 0],
  head: [18, 0, 0],
  shoulderL: [38, 0, 0],
  shoulderR: [38, 0, 0],
  elbowL: [0, 0, 0],
  elbowR: [0, 0, 0],
  fpawL: [0, 0, 0],
  fpawR: [0, 0, 0],
  hipL: [-62, -8, 0],
  hipR: [-62, 8, 0],
  kneeL: [150, 0, 0],
  kneeR: [150, 0, 0],
  hpawL: [-60, 0, 0],
  hpawR: [-60, 0, 0],
  tail0: [-38, 50, 0],
  tail1: [-5, 35, 0],
  tail2: [10, 30, 0],
  tail3: [10, 25, 0],
  tail4: [5, 20, 0],
  tail5: [0, 15, 0],
};

export const LOAF_HIPS: [number, number, number] = [0, -0.24, 0];

export const LOAF: Pose = {
  hips: [0, 0, 0],
  spine: [0, 0, 0],
  chest: [0, 0, 0],
  neck: [12, 0, 0],
  head: [4, 0, 0],
  shoulderL: [100, 0, 0],
  shoulderR: [100, 0, 0],
  elbowL: [-150, 0, 0],
  elbowR: [-150, 0, 0],
  fpawL: [50, 0, 0],
  fpawR: [50, 0, 0],
  hipL: [-80, 0, 0],
  hipR: [-80, 0, 0],
  kneeL: [160, 0, 0],
  kneeR: [160, 0, 0],
  hpawL: [-70, 0, 0],
  hpawR: [-70, 0, 0],
  tail0: [-55, 55, 0],
  tail1: [-10, 45, 0],
  tail2: [5, 45, 0],
  tail3: [5, 40, 0],
  tail4: [0, 35, 0],
  tail5: [0, 30, 0],
};
