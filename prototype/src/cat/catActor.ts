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
import { ATLAS_SIZE } from './parts';
import { FaceRig, type EyeState, type MouthState } from './face';
import type { PetDNA } from './dna';
import { ANIM_BONES } from './skeleton';
import { buildClip, faceAt } from '../anim/clipDsl';
import { CLIPS, clipDef } from '../anim/clips';
import { Procedural } from '../anim/procedural';
import { Brain, type WorldNav } from '../anim/brain';

/**
 * 像素画式猫咪着色材质（Flat Albedo + 单档底部/背光硬阴影）：
 * - 复用 Three.js 原生蒙皮与形态键法线管线，覆写光照输出；
 * - 头部、脸颊与受光躯干保持 100% 纯净贴图平涂本色，彻底消灭 3D 球面多阶色带（充气玩具感）；
 * - 仅在腹底/下颌底/内侧背光处保留一档干净的像素硬阴影（亮度 0.78），翻肚皮时朝上的肚皮保持全亮。
 */
function makePixelCatMaterial(coatTexture: Texture, gradientMap: Texture): MeshToonMaterial {
  const mat = new MeshToonMaterial({ map: coatTexture, gradientMap });
  mat.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace(
        '#include <common>',
        /* glsl */ `
        #include <common>
        varying vec3 vCatWorldNormal;
        varying float vCatHeight;
        `,
      )
      .replace(
        '#include <project_vertex>',
        /* glsl */ `
        #include <project_vertex>
        vCatWorldNormal = normalize(mat3(modelMatrix) * objectNormal);
        vec4 catWorldPos = modelMatrix * vec4(transformed, 1.0);
        vec4 catRootWorld = modelMatrix * vec4(0.0, 0.0, 0.0, 1.0);
        vCatHeight = catWorldPos.y - catRootWorld.y;
        `,
      );

    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        /* glsl */ `
        #include <common>
        varying vec3 vCatWorldNormal;
        varying float vCatHeight;
        `,
      )
      .replace(
        '#include <opaque_fragment>',
        /* glsl */ `
        vec3 nCat = normalize(vCatWorldNormal);
        vec3 sunDirCat = normalize(vec3(0.48, 0.76, 0.44));
        float shadeMetric = nCat.y * 0.72 + dot(nCat, sunDirCat) * 0.28;
        bool inShadow = (vCatHeight < 0.55) && (shadeMetric < -0.16);
        vec3 pixelLit = diffuseColor.rgb * (inShadow ? vec3(0.76, 0.73, 0.77) : vec3(1.0));
        outgoingLight = pixelLit;
        #include <opaque_fragment>
        `,
      );
  };
  return mat;
}

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
    this.group.name = 'cat_actor_group';
    this.coatCanvas.width = this.coatCanvas.height = ATLAS_SIZE;
    this.coatTexture = makeCoatTexture(this.coatCanvas);
    this.material = makePixelCatMaterial(this.coatTexture, gradientMap);
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
