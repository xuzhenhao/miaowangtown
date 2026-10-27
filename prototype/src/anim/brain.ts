import { Vector3 } from 'three';
import { CLIPS, clipDef } from './clips';

export interface BrainHost {
  readonly position: Vector3;
  heading: number;
  play(name: string): void;
}

export interface WorldNav {
  randomTarget(from: Vector3): Vector3;
}

const DURATION: Record<string, [number, number]> = {
  idle: [3, 6],
  sit: [6, 12],
  loaf: [9, 16],
  groom: [4.8, 7.2],
  belly: [6, 11],
};

/**
 * 闲逛状态机：性格 = 各状态的权重。
 * 同一套动作库，不同权重就是不同性格（懒猫 loaf 高，好动的猫 walk 高）。
 */
export class Brain {
  state = 'idle';
  private until = 3;
  private target: Vector3 | null = null;
  private time = 0;
  private forced = false;
  private hold = false;
  personality: Record<string, number> = { idle: 1 };
  speed = 0;
  turnRate = 0;

  constructor(private host: BrainHost, private nav: WorldNav) {}

  setPersonality(p: Record<string, number>) {
    this.personality = p;
  }

  /** UI 指定动作：hold=true 时循环动作持续保持（walk 到达一个路点后会自动续走下一个路点） */
  force(name: string, hold = false) {
    this.forced = true;
    this.hold = hold;
    this.enter(name);
    if (hold && clipDef(name).loop && name !== 'walk') this.until = Infinity;
  }

  release() {
    this.forced = false;
    this.hold = false;
    this.until = this.time;
  }

  private pickNext(): string {
    const prev = this.state;
    if ((prev === 'loaf' || prev === 'sit') && CLIPS.some((c) => c.name === 'stretch') && Math.random() < 0.4) {
      return 'stretch';
    }
    const entries = Object.entries(this.personality).filter(
      ([k, w]) => w > 0 && k !== prev && CLIPS.some((c) => c.name === k),
    );
    const total = entries.reduce((a, [, w]) => a + w, 0);
    let r = Math.random() * total;
    for (const [k, w] of entries) {
      if ((r -= w) <= 0) return k;
    }
    return 'idle';
  }

  private enter(name: string) {
    this.state = name;
    const def = clipDef(name);
    if (name === 'walk') {
      this.target = this.nav.randomTarget(this.host.position);
      this.until = this.time + 25;
    } else {
      this.target = null;
      const [a, b] = DURATION[name] ?? [def.duration - 0.2, def.duration - 0.2];
      this.until = this.time + (this.forced && def.loop ? 8 : a + Math.random() * (b - a));
    }
    this.host.play(name);
  }

  update(dt: number) {
    this.time += dt;
    this.speed = 0;
    this.turnRate = 0;

    if (this.state === 'walk' && this.target) {
      const to = this.target.clone().sub(this.host.position);
      to.y = 0;
      const dist = to.length();
      if (dist < 0.14) {
        if (this.forced && this.hold) {
          this.target = this.nav.randomTarget(this.host.position);
          this.until = this.time + 25;
        } else {
          this.until = this.time;
        }
      } else {
        const want = Math.atan2(to.x, to.z);
        let diff = want - this.host.heading;
        diff = Math.atan2(Math.sin(diff), Math.cos(diff));
        const turn = Math.sign(diff) * Math.min(Math.abs(diff), 3.6 * dt);
        this.host.heading += turn;
        this.turnRate = dt > 1e-4 ? turn / dt : 0;
        const align = Math.max(0.55, Math.cos(diff));
        this.speed = clipDef('walk').speed! * align;
        const step = Math.min(dist, this.speed * dt);
        this.host.position.x += Math.sin(this.host.heading) * step;
        this.host.position.z += Math.cos(this.host.heading) * step;
      }
    }

    if (this.time >= this.until) {
      if (this.forced && this.hold && this.state === 'walk') {
        this.target = this.nav.randomTarget(this.host.position);
        this.until = this.time + 25;
      } else {
        this.forced = false;
        this.hold = false;
        this.enter(this.pickNext());
      }
    }
  }
}
