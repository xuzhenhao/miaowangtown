export const SHAPE_KEYS = ['headRound', 'weight', 'earSize', 'tailFluff', 'cheekFluff', 'muzzleSize'] as const;
export type ShapeKey = (typeof SHAPE_KEYS)[number];
export type ShapeParams = Record<ShapeKey, number>;

export const NEUTRAL_SHAPE: ShapeParams = {
  headRound: 0,
  weight: 0,
  earSize: 0,
  tailFluff: 0,
  cheekFluff: 0,
  muzzleSize: 0,
};

export function shapeWith(key: ShapeKey, value: number): ShapeParams {
  return { ...NEUTRAL_SHAPE, [key]: value };
}
