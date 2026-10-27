import { Euler, Quaternion, Vector3, type Object3D } from 'three';
import type { BoneName } from '../cat/skeleton';
import type { Bone } from 'three';

const D2R = Math.PI / 180;
const _e = new Euler();
const _q = new Quaternion();

function addRot(bone: Bone, xDeg: number, yDeg: number, zDeg: number) {
  _q.setFromEuler(_e.set(xDeg * D2R, yDeg * D2R, zDeg * D2R, 'YXZ'));
  bone.quaternion.multiply(_q);
}

interface Spring {
  v: number;
  x: number;
}

export interface ProceduralInput {
  /** 看向目标（世界坐标），null 表示不看 */
  lookTarget: Vector3 | null;
  lookWeight: number;
  tailSway: number;
  /** 身体绕 Y 的角速度（弧度/秒），驱动尾巴甩动 */
  turnRate: number;
  speed: number;
}

/**
 * 程序化层：叠加在任何动作之上，零美术成本地让猫「活」起来。
 * 看向 / 尾巴弹簧 / 呼吸 / 耳朵抖动 / 眨眼 / 被摸时歪头。
 */
export class Procedural {
  private lookYaw = 0;
  private lookPitch = 0;
  private lookW = 0;
  private tailYaw: Spring[] = Array.from({ length: 6 }, () => ({ v: 0, x: 0 }));
  private tailPitch: Spring[] = Array.from({ length: 6 }, () => ({ v: 0, x: 0 }));
  private ear = { L: 0, R: 0 };
  private nextTwitch = 2;
  private nextBlink = 2.5;
  private blinkUntil = 0;
  private happyUntil = 0;
  private tilt = 0;
  time = 0;

  get blinking() {
    return this.time < this.blinkUntil;
  }

  get happyLeft() {
    return Math.max(0, this.happyUntil - this.time);
  }

  pet(duration = 1.8) {
    this.happyUntil = this.time + duration;
  }

  apply(dt: number, bones: Record<BoneName, Bone>, owner: Object3D, inp: ProceduralInput) {
    this.time += dt;
    const t = this.time;
    const smooth = (rate: number) => 1 - Math.exp(-rate * dt);

    // 呼吸
    addRot(bones.chest, Math.sin(t * 2.1) * 1.2, 0, 0);

    // 看向
    let yaw = 0;
    let pitch = 0;
    let wantW = 0;
    if (inp.lookTarget && inp.lookWeight > 0) {
      const head = bones.head.getWorldPosition(new Vector3());
      const target = inp.lookTarget.clone();
      owner.worldToLocal(head);
      owner.worldToLocal(target);
      const d = target.sub(head);
      yaw = Math.atan2(d.x, d.z);
      pitch = Math.atan2(-d.y, Math.hypot(d.x, d.z));
      const behind = Math.abs(yaw) > 1.9;
      yaw = Math.max(-0.9, Math.min(0.9, yaw));
      pitch = Math.max(-0.35, Math.min(0.45, pitch));
      wantW = behind ? 0 : inp.lookWeight;
    }
    this.lookW += (wantW - this.lookW) * smooth(3);
    this.lookYaw += (yaw - this.lookYaw) * smooth(5);
    this.lookPitch += (pitch - this.lookPitch) * smooth(5);
    const ly = (this.lookYaw / D2R) * this.lookW;
    const lp = (this.lookPitch / D2R) * this.lookW;
    addRot(bones.neck, lp * 0.35, ly * 0.35, 0);
    addRot(bones.head, lp * 0.65, ly * 0.65, 0);

    // 被摸：歪头
    const wantTilt = this.happyLeft > 0 ? 16 : 0;
    this.tilt += (wantTilt - this.tilt) * smooth(6);
    addRot(bones.head, 0, 0, this.tilt);

    // 尾巴：每节一个阻尼弹簧，尾尖更软、更滞后
    for (let i = 0; i < 6; i++) {
      const k = 60 - i * 7;
      const c = 2 * Math.sqrt(k) * 0.35;
      const sway = Math.sin(t * 1.4 - i * 0.55) * inp.tailSway * (0.4 + i * 0.15);
      const targetYaw = sway - inp.turnRate * 9 * (i + 1) * 0.5;
      const targetPitch = Math.sin(t * 0.9 - i * 0.4) * inp.tailSway * 0.3 + inp.speed * 18;
      for (const [s, target] of [
        [this.tailYaw[i], targetYaw],
        [this.tailPitch[i], targetPitch],
      ] as const) {
        s.v += (k * (target - s.x) - c * s.v) * dt;
        s.x += s.v * dt;
      }
      addRot(bones[`tail${i}` as BoneName], this.tailPitch[i].x / 6, this.tailYaw[i].x / 3, 0);
    }

    // 耳朵抖动
    if (t > this.nextTwitch) {
      const side = Math.random() < 0.5 ? 'L' : 'R';
      this.ear[side] = 1;
      this.nextTwitch = t + 1.5 + Math.random() * 4.5;
    }
    this.ear.L = Math.max(0, this.ear.L - dt * 4);
    this.ear.R = Math.max(0, this.ear.R - dt * 4);
    const tw = (x: number) => Math.sin(x * Math.PI * 3) * 28 * x;
    addRot(bones.earL, 0, 0, -tw(this.ear.L));
    addRot(bones.earR, 0, 0, tw(this.ear.R));

    // 眨眼
    if (t > this.nextBlink) {
      this.blinkUntil = t + 0.13;
      this.nextBlink = t + 2.2 + Math.random() * 3.5;
    }
  }
}
