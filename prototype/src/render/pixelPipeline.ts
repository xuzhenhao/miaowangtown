import {
  DataTexture,
  DepthTexture,
  HalfFloatType,
  Mesh,
  NearestFilter,
  OrthographicCamera,
  PlaneGeometry,
  RedFormat,
  Scene,
  ShaderMaterial,
  Vector2,
  Vector3,
  WebGLRenderTarget,
  WebGLRenderer,
} from 'three';

/** 4 档色阶的 HD-2D 卡通光照渐变图（深影 / 过渡暗部 / 受光面 / 暖阳高光） */
export function makeToonGradient(): DataTexture {
  const data = new Uint8Array([58, 132, 202, 255]);
  const tex = new DataTexture(data, data.length, 1, RedFormat);
  tex.magFilter = NearestFilter;
  tex.minFilter = NearestFilter;
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
uniform sampler2D tColor;
uniform sampler2D tDepth;
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

float depthAt(vec2 px) {
  return texture2D(tDepth, clamp((px + 0.5) / rtRes, 0.001, 0.999)).x;
}

vec3 colorAt(vec2 px) {
  vec4 raw = texture2D(tColor, clamp((px + 0.5) / rtRes, 0.001, 0.999));
  return linearToOutputTexel(raw).rgb;
}

float luma(vec3 c) {
  return dot(c, vec3(0.299, 0.587, 0.114));
}

// 像素采样 + 柔和深暖褐深度描边（#2a1b12）
vec3 samplePixelWithOutline(vec2 px) {
  vec3 c = colorAt(px);
  if (outline > 0.5) {
    float d = depthAt(px);
    if (d < 0.999) {
      float dz = 0.0;
      dz = max(dz, depthAt(px + vec2(1.0, 0.0)) - d);
      dz = max(dz, depthAt(px - vec2(1.0, 0.0)) - d);
      dz = max(dz, depthAt(px + vec2(0.0, 1.0)) - d);
      dz = max(dz, depthAt(px - vec2(0.0, 1.0)) - d);
      float edge = smoothstep(0.07, 0.22, dz * depthRange);
      vec3 warmDarkOutline = vec3(0.165, 0.106, 0.071);
      c = mix(c, warmDarkOutline, edge * 0.72);
    }
  }
  return c;
}

void main() {
  vec2 basePx = floor(vUv * viewRes + (rtRes - viewRes) * 0.5 + offset);
  vec3 col = samplePixelWithOutline(basePx);

  // 1. 移轴景深 (Tilt-Shift DoF)：上下远近端柔焦微缩景深，中央聚焦带保持刀锋锐利像素
  if (tiltShift > 0.5) {
    float topBlur = smoothstep(0.64, 0.96, vUv.y);
    float botBlur = smoothstep(0.30, 0.02, vUv.y);
    float dof = clamp(max(topBlur, botBlur * 0.85), 0.0, 1.0);
    if (dof > 0.01) {
      float rad = dof * 3.4;
      vec3 acc = col * 1.4;
      float wSum = 1.4;
      // 12-tap 环形散景核（高亮散景权重略高，呈现微缩模型光斑感）
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
        vec3 s = colorAt(floor(basePx + taps[i] * rad + 0.5));
        float bokehW = 1.0 + smoothstep(0.65, 0.95, luma(s)) * 0.9;
        acc += s * bokehW;
        wSum += bokehW;
      }
      col = mix(col, acc / wSum, smoothstep(0.0, 1.0, dof));
    }
  }

  // 2. 暖阳柔光溢散与丁达尔体积光束 (Warm Sunlight Bloom + Sunbeams)
  if (bloom > 0.5) {
    vec3 glow = vec3(0.0);
    vec2 bOffsets[8];
    bOffsets[0] = vec2(1.5, 0.0);
    bOffsets[1] = vec2(-1.5, 0.0);
    bOffsets[2] = vec2(0.0, 1.5);
    bOffsets[3] = vec2(0.0, -1.5);
    bOffsets[4] = vec2(3.2, 2.2);
    bOffsets[5] = vec2(-3.2, 2.2);
    bOffsets[6] = vec2(3.2, -2.2);
    bOffsets[7] = vec2(-3.2, -2.2);
    for (int i = 0; i < 8; i++) {
      vec3 s = colorAt(basePx + bOffsets[i]);
      float b = smoothstep(0.58, 0.94, luma(s));
      glow += s * b;
    }
    glow /= 8.0;
    col += glow * vec3(1.06, 0.88, 0.64) * 0.34;

    // 右上方斜射丁达尔暖阳体积光束 (God-rays)
    float rayCoord = vUv.x * 0.78 - vUv.y * 0.62;
    float shaft1 = smoothstep(0.18, 0.0, abs(rayCoord - 0.12));
    float shaft2 = smoothstep(0.24, 0.0, abs(rayCoord + 0.08));
    float shaft3 = smoothstep(0.15, 0.0, abs(rayCoord - 0.28));
    float sunCorner = smoothstep(0.15, 0.95, vUv.x * 0.55 + vUv.y * 0.65);
    float rays = (shaft1 * 0.55 + shaft2 * 0.45 + shaft3 * 0.4) * sunCorner;
    col += vec3(1.0, 0.84, 0.54) * rays * 0.095;
  }

  // 3. HD-2D 戏剧性色彩分级与电影感暗角 (Color Grading & Vignette)
  if (vignette > 0.5) {
    // 暗部微染深邃暖紫褐，高光通透暖金
    float lum = luma(col);
    vec3 shadowTint = vec3(0.13, 0.10, 0.15);
    vec3 highlightTint = vec3(1.04, 0.98, 0.90);
    col = mix(col, max(col, shadowTint * 0.45), (1.0 - lum) * 0.22);
    col *= mix(vec3(0.96, 0.94, 0.98), highlightTint, smoothstep(0.3, 0.85, lum));
    // 柔和 S 曲线提升光影层次感
    col = clamp(col, 0.0, 1.0);
    col = mix(col, col * col * (3.0 - 2.0 * col), 0.18);

    // 四角电影感暗角聚拢视线
    vec2 centered = (vUv - 0.5) * vec2(1.12, 1.0);
    float dist = length(centered);
    float vig = smoothstep(0.38, 0.92, dist);
    col = mix(col, col * vec3(0.20, 0.15, 0.14), vig * 0.48);
  }

  if (posterize > 0.5) {
    col = floor(col * 10.0 + 0.5) / 10.0;
  }

  gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}`;

/**
 * HD-2D 复合渲染管线：
 * 低分辨率像素化采样 + 深暖褐自适应深度描边 + 移轴景深 (Tilt-Shift DoF) +
 * 暖阳辉光与丁达尔体积光束 (Bloom & God-rays) + 戏剧暗角调色 (Vignette & Color Grading)。
 */
export class PixelPipeline {
  readonly renderer: WebGLRenderer;
  readonly camera: OrthographicCamera;
  readonly focus = new Vector3();
  pixelScale = 2;
  viewHeight = 4.2;
  pitchDeg = 28;
  yawDeg = -12;
  distance = 30;
  outline = true;
  posterize = false;
  tiltShift = true;
  bloom = true;
  vignette = true;

  private rt!: WebGLRenderTarget;
  private postScene = new Scene();
  private postCam = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private post: ShaderMaterial;
  private rtRes = new Vector2();
  private viewRes = new Vector2();
  private offset = new Vector2();

  constructor(private canvas: HTMLCanvasElement) {
    this.renderer = new WebGLRenderer({ canvas, antialias: false });
    this.renderer.setPixelRatio(1);
    this.renderer.shadowMap.enabled = true;
    this.camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, this.distance * 2);
    this.post = new ShaderMaterial({
      vertexShader: POST_VERT,
      fragmentShader: POST_FRAG,
      uniforms: {
        tColor: { value: null },
        tDepth: { value: null },
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
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    this.renderer.setSize(w, h, false);
    this.viewRes.set(w / this.pixelScale, h / this.pixelScale);
    this.rtRes.set(Math.ceil(this.viewRes.x) + 2, Math.ceil(this.viewRes.y) + 2);
    this.rt?.dispose();
    this.rt = new WebGLRenderTarget(this.rtRes.x, this.rtRes.y, {
      minFilter: NearestFilter,
      magFilter: NearestFilter,
      type: HalfFloatType,
      depthTexture: new DepthTexture(this.rtRes.x, this.rtRes.y),
    });
    this.post.uniforms.tColor.value = this.rt.texture;
    this.post.uniforms.tDepth.value = this.rt.depthTexture;
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

  render(scene: Scene) {
    this.placeCamera();
    this.post.uniforms.outline.value = this.outline ? 1 : 0;
    this.post.uniforms.posterize.value = this.posterize ? 1 : 0;
    this.post.uniforms.tiltShift.value = this.tiltShift ? 1 : 0;
    this.post.uniforms.bloom.value = this.bloom ? 1 : 0;
    this.post.uniforms.vignette.value = this.vignette ? 1 : 0;
    this.renderer.setRenderTarget(this.rt);
    this.renderer.render(scene, this.camera);
    this.renderer.setRenderTarget(null);
    this.renderer.render(this.postScene, this.postCam);
  }
}
