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

/** 3 档色阶的卡通光照渐变图 */
export function makeToonGradient(): DataTexture {
  const data = new Uint8Array([70, 160, 255]);
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
uniform float depthRange;
varying vec2 vUv;

float depthAt(vec2 px) { return texture2D(tDepth, (px + 0.5) / rtRes).x; }

void main() {
  vec2 px = floor(vUv * viewRes + (rtRes - viewRes) * 0.5 + offset);
  vec4 c = texture2D(tColor, (px + 0.5) / rtRes);
  if (outline > 0.5) {
    float d = depthAt(px);
    if (d < 1.0) {
      float dz = 0.0;
      dz = max(dz, depthAt(px + vec2(1.0, 0.0)) - d);
      dz = max(dz, depthAt(px - vec2(1.0, 0.0)) - d);
      dz = max(dz, depthAt(px + vec2(0.0, 1.0)) - d);
      dz = max(dz, depthAt(px - vec2(0.0, 1.0)) - d);
      if (dz * depthRange > 0.12) c.rgb *= 0.3;
    }
  }
  vec4 o = linearToOutputTexel(c);
  if (posterize > 0.5) o.rgb = floor(o.rgb * 10.0 + 0.5) / 10.0;
  gl_FragColor = o;
}`;

/**
 * 画风层：低分辨率渲染 + 深度描边 + 可选色阶量化 + 像素对齐相机。
 * 相机吸附到像素网格后，把剩余的亚像素偏移挪到最终放大采样里，镜头移动顺滑又不闪烁。
 */
export class PixelPipeline {
  readonly renderer: WebGLRenderer;
  readonly camera: OrthographicCamera;
  readonly focus = new Vector3();
  pixelScale = 3;
  viewHeight = 5.2;
  pitchDeg = 32;
  yawDeg = 0;
  distance = 30;
  outline = true;
  posterize = false;

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
    this.renderer.setRenderTarget(this.rt);
    this.renderer.render(scene, this.camera);
    this.renderer.setRenderTarget(null);
    this.renderer.render(this.postScene, this.postCam);
  }
}
