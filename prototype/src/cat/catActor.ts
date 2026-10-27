import {
  AnimationMixer,
  Group,
  LoopOnce,
  LoopRepeat,
  MeshToonMaterial,
  Vector3,
  type AnimationAction,
  type AnimationClip,
  type Texture,
} from 'three';
import { applyShape, buildCatMesh, type CatMesh } from './buildCat';
import { bakeCoat, loadCoatImage, makeCoatTexture, snapToPalette } from './coatBaker';
import { FaceRig, type EyeState, type MouthState } from './face';
import type { PetDNA } from './dna';
import { ANIM_BONES } from './skeleton';
import { buildClip, faceAt } from '../anim/clipDsl';
import { CLIPS, clipDef } from '../anim/clips';
import { Procedural } from '../anim/procedural';
import { Brain, type WorldNav } from '../anim/brain';

/**
 * 一只猫 = 母版网格（全猫共用） + 动作库（全猫共用） + 一份 Pet DNA（每只猫一份）。
 * applyDNA 只改贴图、形态键、眼睛颜色和性格权重，从不碰动作。
 */
export class CatActor {
  readonly group = new Group();
  readonly cat: CatMesh;
  readonly face: FaceRig;
  readonly coatCanvas = document.createElement('canvas');
  readonly coatTexture: Texture;
  readonly material: MeshToonMaterial;
  readonly mixer: AnimationMixer;
  readonly clips: AnimationClip[];
  readonly brain: Brain;
  readonly procedural = new Procedural();
  private actions: Record<string, AnimationAction> = {};
  private animPose = new Float32Array(ANIM_BONES.length * 7);
  current = '';
  dna?: PetDNA;
  heading = 0;
  lookTarget: Vector3 | null = null;
  expression: { eyes: EyeState; mouth: MouthState } = { eyes: 'open', mouth: 'closed' };

  constructor(gradientMap: Texture, nav: WorldNav) {
    this.coatCanvas.width = this.coatCanvas.height = 256;
    this.coatTexture = makeCoatTexture(this.coatCanvas);
    this.material = new MeshToonMaterial({ map: this.coatTexture, gradientMap });
    this.cat = buildCatMesh(this.material);
    this.face = new FaceRig(this.cat.sk);
    this.group.add(this.cat.mesh);
    ANIM_BONES.forEach((name, i) => {
      this.animPose.set([0, 0, 0, 1], i * 7);
      this.cat.sk.restLocal[name].toArray(this.animPose, i * 7 + 4);
    });
    this.mixer = new AnimationMixer(this.cat.mesh);
    const restHips = this.cat.sk.restLocal.hips.toArray() as [number, number, number];
    this.clips = CLIPS.map((def) => buildClip(def, restHips));
    for (const clip of this.clips) {
      const def = clipDef(clip.name);
      const a = this.mixer.clipAction(clip);
      a.setLoop(def.loop ? LoopRepeat : LoopOnce, def.loop ? Infinity : 1);
      a.clampWhenFinished = true;
      this.actions[clip.name] = a;
    }
    const self = this;
    this.brain = new Brain(
      {
        position: this.group.position,
        get heading() {
          return self.heading;
        },
        set heading(v: number) {
          self.heading = v;
        },
        play: (name) => this.play(name),
      },
      nav,
    );
    this.play('idle');
  }

  async applyDNA(dna: PetDNA) {
    this.dna = dna;
    applyShape(this.cat.mesh, dna.shape);
    this.face.applyShape(dna.shape);
    this.face.applyColors(dna);
    if (dna.coat.texture) {
      await loadCoatImage(`${import.meta.env.BASE_URL}pets/${dna.coat.texture}`, this.coatCanvas);
      if (dna.coat.palette) snapToPalette(this.coatCanvas, dna.coat.palette);
    } else {
      bakeCoat(dna, this.coatCanvas);
    }
    this.coatTexture.needsUpdate = true;
    this.brain.setPersonality(dna.personality);
  }

  play(name: string, fade = 0.4) {
    if (name === this.current) return;
    const next = this.actions[name];
    const prev = this.actions[this.current];
    next.reset();
    next.setEffectiveTimeScale(1);
    next.setEffectiveWeight(1);
    next.play();
    if (prev) prev.crossFadeTo(next, fade, false);
    this.current = name;
  }

  update(dt: number) {
    this.brain.update(dt);
    this.group.rotation.y = this.heading;

    const walkDef = clipDef('walk');
    const walk = this.actions.walk;
    if (this.current === 'walk') walk.setEffectiveTimeScale(Math.max(0.3, this.brain.speed / walkDef.speed!));

    // 每帧：还原上一帧的动画姿态（去掉程序化叠加）-> 动画混合 -> 记下动画姿态 -> 程序化叠加。
    // 混合器只在数值变化时才写骨骼，所以不能复位到静止姿态，否则静止的姿态（坐着）会被抹掉。
    const { bones } = this.cat.sk;
    ANIM_BONES.forEach((name, i) => {
      bones[name].quaternion.fromArray(this.animPose, i * 7);
      bones[name].position.fromArray(this.animPose, i * 7 + 4);
    });
    this.mixer.update(dt);
    ANIM_BONES.forEach((name, i) => {
      bones[name].quaternion.toArray(this.animPose, i * 7);
      bones[name].position.toArray(this.animPose, i * 7 + 4);
    });

    const def = clipDef(this.current);
    this.procedural.apply(dt, bones, this.group, {
      lookTarget: this.lookTarget,
      lookWeight: def.lookWeight ?? 0.5,
      tailSway: def.tailSway ?? 6,
      turnRate: this.brain.turnRate,
      speed: this.brain.speed,
    });

    this.updateFace(def.name);
  }

  private updateFace(clipName: string) {
    const action = this.actions[clipName];
    const def = clipDef(clipName);
    const f = faceAt(def, action.time);
    let eyes: EyeState = f.eyes ?? 'open';
    let mouth: MouthState = f.mouth ?? 'closed';
    if (eyes === 'open' && this.procedural.blinking) eyes = 'closed';
    const happy = this.procedural.happyLeft;
    if (happy > 0) {
      eyes = 'happy';
      mouth = happy > 1.3 ? 'open' : 'closed';
    }
    if (eyes !== this.expression.eyes) this.face.setEyes(eyes);
    if (mouth !== this.expression.mouth) this.face.setMouth(mouth);
    this.expression = { eyes, mouth };
  }
}
