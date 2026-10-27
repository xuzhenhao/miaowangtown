import {
  Color,
  DataTexture,
  DepthTexture,
  HalfFloatType,
  LinearFilter,
  Mesh,
  NearestFilter,
  OrthographicCamera,
  PCFSoftShadowMap,
  PlaneGeometry,
  RedFormat,
  Scene,
  ShaderMaterial,
  Vector2,
  Vector3,
  WebGLRenderTarget,
  WebGLRenderer,
  type Material,
  type Object3D,
} from 'three';

/** 4 档色阶的卡通光照渐变图（供场景材质可选使用） */
export function makeToonGradient(): DataTexture {
  const data = new Uint8Array([76, 142, 206, 255]);
  const tex = new DataTexture(data, data.length, 1, RedFormat);
  tex.magFilter = LinearFilter;
  tex.minFilter = LinearFilter;
  tex.needsUpdate = true;
  return tex;
}

const POST_VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}`;

const POST_FRAG = /* glsl */ `
uniform sampler2D tEnvColor;
uniform sampler2D tEnvDepth;
uniform sampler2D tCatColor;
uniform sampler2D tCatDepth;
uniform vec2 envRes;
uniform vec2 rtRes;
uniform vec2 viewRes;
uniform vec2 offset;
uniform float outline;
uniform float posterize;
uniform float tiltShift;
uniform float bloom;
uniform float vignette;
uniform float depthRange;
varying vec2 vUv;

float luma(vec3 c) {
  return dot(c, vec3(0.299, 0.587, 0.114));
}

vec3 envColorAt(vec2 uv) {
  vec4 raw = texture2D(tEnvColor, clamp(uv, 0.001, 0.999));
  return linearToOutputTexel(raw).rgb;
}

float envDepthAt(vec2 uv) {
  return texture2D(tEnvDepth, clamp(uv, 0.001, 0.999)).x;
}

vec2 catUvFromPx(vec2 px) {
  return clamp((px + 0.5) / rtRes, 0.001, 0.999);
}

vec4 catRawAt(vec2 px) {
  return texture2D(tCatColor, catUvFromPx(px));
}

float catDepthAt(vec2 px) {
  return texture2D(tCatDepth, catUvFromPx(px)).x;
}

void main() {
  // =========================================================================
  // 第一层：全高清（Full HD）3D 古镇环境渲染 + 移轴景深 + 暖光灯笼辉光 + 电影感暗调分级
  // =========================================================================
  vec3 envCol = envColorAt(vUv);
  vec2 envStep = 1.0 / envRes;

  // 1. 电影级移轴景深 (Tilt-Shift DoF)：远近端高清柔焦散景，中央聚焦区保持原生全高清锐度
  if (tiltShift > 0.5) {
    float topBlur = smoothstep(0.68, 0.98, vUv.y);
    float botBlur = smoothstep(0.26, 0.01, vUv.y);
    float dof = clamp(max(topBlur, botBlur * 0.82), 0.0, 1.0);
    if (dof > 0.01) {
      float rad = dof * 5.5;
      vec3 acc = envCol * 1.5;
      float wSum = 1.5;
      vec2 taps[12];
      taps[0] = vec2(1.0, 0.0);
      taps[1] = vec2(-1.0, 0.0);
      taps[2] = vec2(0.0, 1.0);
      taps[3] = vec2(0.0, -1.0);
      taps[4] = vec2(0.707, 0.707);
      taps[5] = vec2(-0.707, 0.707);
      taps[6] = vec2(0.707, -0.707);
      taps[7] = vec2(-0.707, -0.707);
      taps[8] = vec2(1.85, 0.45);
      taps[9] = vec2(-1.85, -0.45);
      taps[10] = vec2(0.45, 1.85);
      taps[11] = vec2(-0.45, -1.85);
      for (int i = 0; i < 12; i++) {
        vec3 s = envColorAt(vUv + taps[i] * envStep * rad);
        float bokehW = 1.0 + smoothstep(0.62, 0.94, luma(s)) * 0.9;
        acc += s * bokehW;
        wSum += bokehW;
      }
      envCol = mix(envCol, acc / wSum, smoothstep(0.0, 1.0, dof));
    }
  }

  // 2. 暖黄灯笼柔光辉散与斜向暖阳氛围光 (Warm Lantern Bloom)
  if (bloom > 0.5) {
    vec3 glow = vec3(0.0);
    vec2 bOffsets[8];
    bOffsets[0] = vec2(3.0, 0.0);
    bOffsets[1] = vec2(-3.0, 0.0);
    bOffsets[2] = vec2(0.0, 3.0);
    bOffsets[3] = vec2(0.0, -3.0);
    bOffsets[4] = vec2(6.5, 4.5);
    bOffsets[5] = vec2(-6.5, 4.5);
    bOffsets[6] = vec2(6.5, -4.5);
    bOffsets[7] = vec2(-6.5, -4.5);
    for (int i = 0; i < 8; i++) {
      vec3 s = envColorAt(vUv + bOffsets[i] * envStep);
      float b = smoothstep(0.62, 0.95, luma(s));
      glow += s * b;
    }
    glow /= 8.0;
    envCol += glow * vec3(1.06, 0.82, 0.52) * 0.28;
  }

  // 3. 江南古镇沉稳暗调暖光色彩分级与柔和暗角 (Color Grading & Vignette)
  if (vignette > 0.5) {
    float lum = luma(envCol);
    vec3 highlightTint = vec3(1.03, 0.97, 0.89);
    envCol *= mix(vec3(0.95, 0.94, 0.96), highlightTint, smoothstep(0.28, 0.85, lum));
    envCol = clamp(envCol, 0.0, 1.0);
    envCol = mix(envCol, envCol * envCol * (3.0 - 2.0 * envCol), 0.14);

    vec2 centered = (vUv - 0.5) * vec2(1.1, 1.0);
    float dist = length(centered);
    float vig = smoothstep(0.42, 0.95, dist);
    envCol = mix(envCol, envCol * vec3(0.22, 0.17, 0.15), vig * 0.42);
  }

  vec3 finalCol = envCol;

  // =========================================================================
  // 第二层：猫咪独立低分辨率像素图层 (Nearest 采样 + 干净 1px 深暖黑褐像素描边 #1b100a)
  // =========================================================================
  vec2 catPx = floor(vUv * viewRes + (rtRes - viewRes) * 0.5 + offset);
  vec4 catRaw = catRawAt(catPx);
  float catD = catDepthAt(catPx);
  float envD = envDepthAt(vUv);
  vec3 outlineCol = vec3(0.106, 0.063, 0.039); // #1b100a 深暖黑褐像素描边

  bool catVisible = (catRaw.a > 0.5) && (catD <= envD + 0.0025);
  if (catVisible) {
    vec3 catCol = linearToOutputTexel(catRaw).rgb;
    if (posterize > 0.5) {
      catCol = floor(catCol * 10.0 + 0.5) / 10.0;
    }
    // 部件交界处内部 1px 像素分界线（如前腿迈步跨过后腿、下巴与胸脯交界）
    if (outline > 0.5) {
      vec2 nOffsets[4];
      nOffsets[0] = vec2(1.0, 0.0);
      nOffsets[1] = vec2(-1.0, 0.0);
      nOffsets[2] = vec2(0.0, 1.0);
      nOffsets[3] = vec2(0.0, -1.0);
      float maxJump = 0.0;
      for (int i = 0; i < 4; i++) {
        vec2 np = catPx + nOffsets[i];
        if (catRawAt(np).a > 0.5) {
          float nd = catDepthAt(np);
          maxJump = max(maxJump, (catD - nd) * depthRange);
        }
      }
      if (maxJump > 0.14) {
        catCol = mix(catCol, outlineCol, 0.82);
      }
    }
    finalCol = catCol;
  } else if (outline > 0.5) {
    // 猫咪外轮廓 1px 像素描边（检测 4 邻域与对角邻域的不透明猫体像素）
    vec2 n4[4];
    n4[0] = vec2(1.0, 0.0);
    n4[1] = vec2(-1.0, 0.0);
    n4[2] = vec2(0.0, 1.0);
    n4[3] = vec2(0.0, -1.0);
    bool hitEdge = false;
    for (int i = 0; i < 4; i++) {
      vec2 np = catPx + n4[i];
      if (catRawAt(np).a > 0.5 && catDepthAt(np) <= envD + 0.0025) {
        hitEdge = true;
      }
    }
    if (!hitEdge) {
      vec2 d4[4];
      d4[0] = vec2(1.0, 1.0);
      d4[1] = vec2(-1.0, 1.0);
      d4[2] = vec2(1.0, -1.0);
      d4[3] = vec2(-1.0, -1.0);
      int diagHits = 0;
      for (int i = 0; i < 4; i++) {
        vec2 np = catPx + d4[i];
        if (catRawAt(np).a > 0.5 && catDepthAt(np) <= envD + 0.0025) {
          diagHits++;
        }
      }
      if (diagHits >= 2) hitEdge = true;
    }
    if (hitEdge) {
      finalCol = outlineCol;
    }
  }

  gl_FragColor = vec4(clamp(finalCol, 0.0, 1.0), 1.0);
}`;

/**
 * 真 HD-2D 分层复合渲染管线（八方旅人式架构）：
 * - 环境通道（Full HD 原生高分辨率）：3D 古镇场景、柔和阴影（含猫咪投在地面上的真实 3D 阴影）、移轴景深与暖光辉光；
 * - 猫咪通道（Low-Res 独立像素画图层）：仅猫咪单独走低分辨率像素管线 + 1px 深暖黑褐像素外轮廓描边，再合成回高清场景。
 */
export class PixelPipeline {
  readonly renderer: WebGLRenderer;
  readonly camera: OrthographicCamera;
  readonly focus = new Vector3();
  pixelScale = 3;
  viewHeight = 4.2;
  pitchDeg = 28;
  yawDeg = -12;
  distance = 30;
  outline = true;
  posterize = false;
  tiltShift = true;
  bloom = true;
  vignette = true;

  private envRT!: WebGLRenderTarget;
  private catRT!: WebGLRenderTarget;
  private postScene = new Scene();
  private postCam = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private post: ShaderMaterial;
  private envRes = new Vector2();
  private rtRes = new Vector2();
  private viewRes = new Vector2();
  private offset = new Vector2();
  private savedClearColor = new Color();

  constructor(private canvas: HTMLCanvasElement) {
    this.renderer = new WebGLRenderer({ canvas, antialias: false });
    this.renderer.setPixelRatio(1);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFSoftShadowMap;
    this.camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, this.distance * 2);
    this.post = new ShaderMaterial({
      vertexShader: POST_VERT,
      fragmentShader: POST_FRAG,
      uniforms: {
        tEnvColor: { value: null },
        tEnvDepth: { value: null },
        tCatColor: { value: null },
        tCatDepth: { value: null },
        envRes: { value: this.envRes },
        rtRes: { value: this.rtRes },
        viewRes: { value: this.viewRes },
        offset: { value: this.offset },
        outline: { value: 1 },
        posterize: { value: 0 },
        tiltShift: { value: 1 },
        bloom: { value: 1 },
        vignette: { value: 1 },
        depthRange: { value: this.camera.far - this.camera.near },
      },
      depthTest: false,
      depthWrite: false,
    });
    this.postScene.add(new Mesh(new PlaneGeometry(2, 2), this.post));
    this.resize();
  }

  get pixelWorld() {
    return this.viewHeight / this.viewRes.y;
  }

  resize() {
    const w = Math.max(1, this.canvas.clientWidth);
    const h = Math.max(1, this.canvas.clientHeight);
    this.renderer.setSize(w, h, false);

    // 1. 环境全高清 RenderTarget（不降分辨率，保持建筑与石板砖缝锐利细腻）
    this.envRes.set(w, h);
    this.envRT?.dispose();
    this.envRT = new WebGLRenderTarget(w, h, {
      minFilter: LinearFilter,
      magFilter: LinearFilter,
      type: HalfFloatType,
      depthTexture: new DepthTexture(w, h),
    });

    // 2. 猫咪独立低分辨率像素 RenderTarget（Nearest 采样）
    this.viewRes.set(w / this.pixelScale, h / this.pixelScale);
    this.rtRes.set(Math.ceil(this.viewRes.x) + 2, Math.ceil(this.viewRes.y) + 2);
    this.catRT?.dispose();
    this.catRT = new WebGLRenderTarget(this.rtRes.x, this.rtRes.y, {
      minFilter: NearestFilter,
      magFilter: NearestFilter,
      type: HalfFloatType,
      depthTexture: new DepthTexture(this.rtRes.x, this.rtRes.y),
    });

    this.post.uniforms.tEnvColor.value = this.envRT.texture;
    this.post.uniforms.tEnvDepth.value = this.envRT.depthTexture;
    this.post.uniforms.tCatColor.value = this.catRT.texture;
    this.post.uniforms.tCatDepth.value = this.catRT.depthTexture;
  }

  private placeCamera() {
    const pw = this.pixelWorld;
    const cam = this.camera;
    const halfW = (this.rtRes.x * pw) / 2;
    const halfH = (this.rtRes.y * pw) / 2;
    cam.left = -halfW;
    cam.right = halfW;
    cam.top = halfH;
    cam.bottom = -halfH;
    cam.updateProjectionMatrix();

    const p = (this.pitchDeg * Math.PI) / 180;
    const y = (this.yawDeg * Math.PI) / 180;
    const back = new Vector3(Math.sin(y) * Math.cos(p), Math.sin(p), Math.cos(y) * Math.cos(p));
    cam.position.copy(back).multiplyScalar(this.distance);
    cam.lookAt(0, 0, 0);
    cam.updateMatrixWorld();
    const right = new Vector3().setFromMatrixColumn(cam.matrixWorld, 0);
    const up = new Vector3().setFromMatrixColumn(cam.matrixWorld, 1);

    const r = this.focus.dot(right);
    const u = this.focus.dot(up);
    const sr = Math.round(r / pw) * pw;
    const su = Math.round(u / pw) * pw;
    this.offset.set((r - sr) / pw, (u - su) / pw);
    cam.position
      .copy(this.focus)
      .addScaledVector(right, sr - r)
      .addScaledVector(up, su - u)
      .addScaledVector(back, this.distance);
    cam.updateMatrixWorld();
  }

  /** 屏幕坐标 -> 相机 NDC（考虑裁边和亚像素偏移），用于点击/绘制拾取 */
  screenToNdc(clientX: number, clientY: number, out = new Vector2()): Vector2 {
    const rect = this.canvas.getBoundingClientRect();
    const sx = ((clientX - rect.left) / rect.width) * this.viewRes.x;
    const sy = (1 - (clientY - rect.top) / rect.height) * this.viewRes.y;
    const rx = sx + (this.rtRes.x - this.viewRes.x) / 2 + this.offset.x;
    const ry = sy + (this.rtRes.y - this.viewRes.y) / 2 + this.offset.y;
    return out.set((rx / this.rtRes.x) * 2 - 1, (ry / this.rtRes.y) * 2 - 1);
  }

  private setCatColorDepthWrite(catGroup: Object3D | undefined, enabled: boolean) {
    if (!catGroup) return;
    catGroup.traverse((obj) => {
      const mesh = obj as Mesh;
      if (!mesh.isMesh || !mesh.material) return;
      const mats: Material[] = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const m of mats) {
        m.colorWrite = enabled;
        m.depthWrite = enabled;
      }
    });
  }

  render(scene: Scene) {
    this.placeCamera();
    this.post.uniforms.outline.value = this.outline ? 1 : 0;
    this.post.uniforms.posterize.value = this.posterize ? 1 : 0;
    this.post.uniforms.tiltShift.value = this.tiltShift ? 1 : 0;
    this.post.uniforms.bloom.value = this.bloom ? 1 : 0;
    this.post.uniforms.vignette.value = this.vignette ? 1 : 0;

    const catGroup = scene.getObjectByName('cat_actor_group');

    // 1. 全高清环境通道：猫咪参与投射真实 3D 地面阴影，但不写入高清环境颜色/深度缓冲
    this.setCatColorDepthWrite(catGroup, false);
    this.renderer.setRenderTarget(this.envRT);
    this.renderer.render(scene, this.camera);
    this.setCatColorDepthWrite(catGroup, true);

    // 2. 猫咪独立低分辨率像素通道（透明背景 alpha=0）
    const hiddenObjects: Object3D[] = [];
    for (const child of scene.children) {
      if (child !== catGroup && !(child as unknown as { isLight?: boolean }).isLight) {
        if (child.visible) {
          child.visible = false;
          hiddenObjects.push(child);
        }
      }
    }
    const prevBg = scene.background;
    const prevShadowAuto = this.renderer.shadowMap.autoUpdate;
    this.renderer.getClearColor(this.savedClearColor);
    const prevClearAlpha = this.renderer.getClearAlpha();

    scene.background = null;
    this.renderer.shadowMap.autoUpdate = false;
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.setRenderTarget(this.catRT);
    this.renderer.clear(true, true, false);
    this.renderer.render(scene, this.camera);

    scene.background = prevBg;
    this.renderer.shadowMap.autoUpdate = prevShadowAuto;
    this.renderer.setClearColor(this.savedClearColor, prevClearAlpha);
    for (const obj of hiddenObjects) obj.visible = true;

    // 3. 合成输出到屏幕
    this.renderer.setRenderTarget(null);
    this.renderer.render(this.postScene, this.postCam);
  }
}
