import type { Marking, PetDNA } from '../cat/dna';
import type { RestMap } from '../cat/coatBaker';
import type { FaceAnchorsMap } from '../cat/loadBaseGlb';
import type { ShapeParams } from '../cat/shape';

/**
 * 语义印记区域枚举（严守约定：left/right 恒指猫自身的左 `+X` / 右 `-X`！）
 * 正面照片中：画面左侧 = 猫自身右侧 (`right`, `-X`)，画面右侧 = 猫自身左侧 (`left`, `+X`)。
 */
export type SemanticRegion =
  | 'body.tabby_stripes'
  | 'back.dorsal_stripe'
  | 'back.saddle'
  | 'head.crown_stripes'
  | 'forehead.m_tabby'
  | 'nose_bridge.blaze_left'
  | 'nose_bridge.blaze_center'
  | 'muzzle.base_white'
  | 'muzzle.right'
  | 'muzzle.right_whisker_dots'
  | 'muzzle.left'
  | 'muzzle.left_lip'
  | 'chin'
  | 'chest.bib'
  | 'belly.base'
  | 'belly.center_spot'
  | 'flank.left'
  | 'flank.right'
  | 'paw.frontLeft'
  | 'paw.frontRight'
  | 'paw.frontRight.inner_wrist'
  | 'paw.hindLeft.thigh'
  | 'paw.hindLeft.sock'
  | 'paw.hindRight.thigh'
  | 'paw.hindRight.sock'
  | 'ear.left'
  | 'ear.right'
  | 'tail.rings'
  | 'tail.solid'
  | 'tail.tip';

export type MarkingExtent = 'small' | 'medium' | 'large' | 'full';

export interface SemanticMarking {
  id: string;
  label: string;
  region: SemanticRegion;
  color: string;
  secondaryColor?: string;
  extent?: MarkingExtent;
  connectsTo?: string[];
  enabled?: boolean;
}

/** 正脸照片上的 10 个关键点（归一化图像坐标 [u, v] ∈ [0, 1]²，左上角为 [0,0]） */
export interface FaceKeypoints2D {
  /** 猫右眼中心（正脸照画面左侧） */
  eyeR: [number, number];
  /** 猫左眼中心（正脸照画面右侧） */
  eyeL: [number, number];
  /** 鼻尖中心 */
  nose: [number, number];
  /** 通鼻火焰纹顶端（额心偏左或居中） */
  blazeTop: [number, number];
  /** 猫右嘴套外侧（正脸照画面左侧花生酱色块中心） */
  mouthR: [number, number];
  /** 猫左嘴套外侧（正脸照画面右侧白嘴套与窄唇边） */
  mouthL: [number, number];
  /** 下巴底端 */
  chin: [number, number];
  /** 额头 M 纹中心 */
  forehead: [number, number];
  /** 猫右耳根（画面左上） */
  earBaseR: [number, number];
  /** 猫左耳根（画面右上） */
  earBaseL: [number, number];
}

export interface PhotoExtractedDNA {
  id: string;
  name: string;
  coatPattern: 'tabby_and_white' | 'orange_tabby' | 'bicolor_tuxedo' | 'calico' | 'solid';
  baseColor: string;
  palette: string[];
  earInner: string;
  eyes: { iris: string; pupil: string };
  nose: string;
  shape: ShapeParams;
  semanticMarkings: SemanticMarking[];
  frontalPhotoUrl?: string;
  faceKeypoints?: FaceKeypoints2D;
  useFaceProjection?: boolean;
}

/**
 * 将视觉大模型提取的语义印记列表（`SemanticMarking[]`）翻译为底层 3D 印记（`Marking[]`）：
 * 所有区域中心、半径与边界均从母版 GLB 的 `_PART` 包围盒（`restMap.partBoxes`）和 `faceAnchors` 动态算出，不硬编码死坐标。
 */
export function translateSemanticMarkings(
  list: SemanticMarking[],
  restMap?: RestMap,
  anchors?: FaceAnchorsMap,
): Marking[] {
  const boxes = restMap?.partBoxes;
  const headBox = boxes?.[0];
  const muzzleBox = boxes?.[1];
  const bodyBox = boxes?.[3];
  const fLegLBox = boxes?.[4];
  const fLegRBox = boxes?.[5];
  const hLegLBox = boxes?.[6];
  const tailBox = boxes?.[10];

  const mouthPos = anchors?.mouth.pos ?? [0, 0.828, 0.804];
  const eyeLPos = anchors?.eyeL.pos ?? [0.114, 0.88, 0.774];

  const bodyMinY = bodyBox ? bodyBox.min.y : 0.25;
  const bodyMaxY = bodyBox ? bodyBox.max.y : 0.75;
  const bodyMaxX = bodyBox ? bodyBox.max.x : 0.23;
  const muzzleMaxZ = muzzleBox ? muzzleBox.max.z : 0.81;
  const fLegTopY = fLegLBox ? fLegLBox.max.y : 0.42;
  const hLegTopY = hLegLBox ? hLegLBox.max.y : 0.41;

  const out: Marking[] = [];

  for (const sm of list) {
    if (sm.enabled === false) continue;
    const ext = sm.extent ?? 'medium';
    const scale = ext === 'small' ? 0.75 : ext === 'large' ? 1.22 : ext === 'full' ? 1.45 : 1.0;

    switch (sm.region) {
      case 'body.tabby_stripes':
        out.push({
          type: 'stripes',
          color: sm.color,
          axis: 'z',
          frequency: 6.4,
          width: 0.35,
          noise: 0.3,
          parts: ['body'],
          minY: bodyMinY + 0.06,
        });
        out.push({
          type: 'stripes',
          color: sm.color,
          axis: 'y',
          frequency: 9.0,
          width: 0.32,
          noise: 0.2,
          parts: ['fLegL', 'fLegR'],
          minY: fLegTopY * 0.74,
        });
        break;

      case 'back.dorsal_stripe':
        out.push({
          type: 'blob',
          color: sm.color,
          center: [0, bodyMaxY - 0.03, -0.02],
          radius: [0.075 * scale, 0.085, 0.45],
          noise: 0.25,
          parts: ['body'],
        });
        break;

      case 'back.saddle':
        out.push({
          type: 'blob',
          color: sm.color,
          center: [-0.04, bodyMaxY - 0.03, -0.08],
          radius: [0.28 * scale, 0.24 * scale, 0.32 * scale],
          noise: 0.32,
          parts: ['body'],
        });
        break;

      case 'head.crown_stripes':
      case 'forehead.m_tabby':
        out.push(
          {
            type: 'stripes',
            color: sm.color,
            axis: 'x',
            frequency: 10.5,
            width: 0.33,
            noise: 0.15,
            parts: ['head'],
            minY: (headBox?.center.y ?? 0.9) + 0.02,
            minZ: 0.45,
          },
          {
            type: 'stripes',
            color: sm.color,
            axis: 'z',
            frequency: 6.8,
            width: 0.32,
            noise: 0.22,
            parts: ['head'],
            minY: 0.8,
            maxZ: 0.62,
          },
          {
            type: 'stripes',
            color: sm.color,
            axis: 'y',
            frequency: 11.0,
            width: 0.3,
            noise: 0.15,
            parts: ['head'],
            minY: 0.78,
            maxY: 0.92,
            minZ: 0.52,
          },
        );
        break;

      case 'belly.base':
        out.push(
          {
            type: 'underside',
            color: sm.color,
            threshold: -0.52,
            noise: 0.14,
            parts: ['body'],
          },
          {
            type: 'blob',
            color: sm.color,
            center: [0, bodyMinY + 0.01, 0.0],
            radius: [0.18 * scale, 0.075, 0.43],
            maxY: bodyMinY + 0.07,
            noise: 0.1,
            parts: ['body'],
          },
        );
        break;

      case 'chest.bib':
        out.push(
          {
            type: 'blob',
            color: sm.color,
            center: [0, 0.56, 0.39],
            radius: [0.18 * scale, 0.21 * scale, 0.17 * scale],
            minZ: 0.22,
            noise: 0.14,
            parts: ['neck', 'body'],
          },
          {
            type: 'blob',
            color: sm.color,
            center: [0, 0.69, 0.66],
            radius: [0.21 * scale, 0.095, 0.18],
            maxY: 0.78,
            noise: 0.12,
            parts: ['head', 'neck'],
          },
        );
        break;

      case 'flank.left':
        out.push({
          type: 'blob',
          color: sm.color,
          center: [bodyMaxX * 0.78, bodyMinY + 0.11, -0.05],
          radius: [0.16 * scale, 0.11 * scale, 0.15 * scale],
          noise: 0.22,
          minX: 0.04,
          maxY: bodyMinY + 0.18,
          parts: ['body'],
        });
        break;

      case 'flank.right':
        out.push({
          type: 'blob',
          color: sm.color,
          center: [-bodyMaxX * 0.78, bodyMinY + 0.14, -0.05],
          radius: [0.16 * scale, 0.12 * scale, 0.16 * scale],
          noise: 0.22,
          maxX: -0.04,
          parts: ['body'],
        });
        break;

      case 'paw.frontLeft': {
        const sockTop = ext === 'large' || ext === 'full' ? 0.33 : ext === 'small' ? 0.14 : 0.24;
        out.push({
          type: 'part',
          color: sm.color,
          maxY: sockTop,
          noise: 0.08,
          parts: ['fLegL'],
        });
        break;
      }

      case 'paw.frontRight': {
        const sockTop = ext === 'large' || ext === 'full' ? 0.33 : ext === 'small' ? 0.14 : 0.24;
        out.push({
          type: 'part',
          color: sm.color,
          maxY: sockTop,
          noise: 0.08,
          parts: ['fLegR'],
        });
        break;
      }

      case 'paw.frontRight.inner_wrist': {
        const legX = fLegRBox ? fLegRBox.center.x : -0.145;
        const legZ = fLegRBox ? fLegRBox.center.z : 0.31;
        out.push({
          type: 'blob',
          color: sm.secondaryColor ?? '#dca675',
          center: [legX + 0.05, 0.22, legZ + 0.02],
          radius: [0.052 * scale, 0.048 * scale, 0.058 * scale],
          minX: legX,
          parts: ['fLegR'],
        });
        out.push({
          type: 'blob',
          color: sm.color,
          center: [legX + 0.05, 0.22, legZ + 0.02],
          radius: [0.038 * scale, 0.036 * scale, 0.045 * scale],
          minX: legX + 0.007,
          parts: ['fLegR'],
        });
        break;
      }

      case 'paw.hindLeft.thigh':
        out.push({
          type: 'stripes',
          color: sm.color,
          axis: 'y',
          frequency: 9.5,
          width: 0.33,
          noise: 0.2,
          parts: ['hLegL'],
          minY: hLegTopY * 0.48,
        });
        break;

      case 'paw.hindRight.thigh':
        out.push({
          type: 'stripes',
          color: sm.color,
          axis: 'y',
          frequency: 9.5,
          width: 0.33,
          noise: 0.2,
          parts: ['hLegR'],
          minY: hLegTopY * 0.48,
        });
        break;

      case 'paw.hindLeft.sock':
        out.push({
          type: 'part',
          color: sm.color,
          maxY: ext === 'small' ? 0.16 : 0.2,
          noise: 0.08,
          parts: ['hLegL'],
        });
        break;

      case 'paw.hindRight.sock':
        out.push({
          type: 'part',
          color: sm.color,
          maxY: ext === 'small' ? 0.16 : 0.2,
          noise: 0.08,
          parts: ['hLegR'],
        });
        break;

      case 'belly.center_spot':
        out.push(
          {
            type: 'blob',
            color: sm.secondaryColor ?? '#dca675',
            center: [0, bodyMinY + 0.01, -0.02],
            radius: [0.088 * scale, 0.08 * scale, 0.108 * scale],
            maxY: bodyMinY + 0.08,
            noise: 0.08,
            parts: ['body'],
          },
          {
            type: 'blob',
            color: sm.color,
            center: [0, bodyMinY + 0.01, -0.02],
            radius: [0.068 * scale, 0.07 * scale, 0.086 * scale],
            maxY: bodyMinY + 0.07,
            noise: 0.06,
            parts: ['body'],
          },
        );
        break;

      case 'muzzle.base_white':
        out.push(
          { type: 'part', color: sm.color, parts: ['muzzle'] },
          {
            type: 'blob',
            color: sm.color,
            center: [0.016, mouthPos[1] - 0.018, muzzleMaxZ - 0.04],
            radius: [0.125, 0.078, 0.11],
            maxY: eyeLPos[1],
            parts: ['head'],
          },
        );
        break;

      case 'nose_bridge.blaze_left':
        out.push(
          {
            type: 'blob',
            color: sm.color,
            center: [0.02, eyeLPos[1] + 0.02, muzzleMaxZ - 0.03],
            radius: [0.038 * scale, 0.068 * scale, 0.08],
            minX: -0.01,
            parts: ['head', 'muzzle'],
          },
          {
            type: 'blob',
            color: sm.color,
            center: [0.028, eyeLPos[1] + 0.08, muzzleMaxZ - 0.05],
            radius: [0.026 * scale, 0.048 * scale, 0.07],
            minX: 0.0,
            parts: ['head'],
          },
        );
        break;

      case 'nose_bridge.blaze_center':
        out.push({
          type: 'blob',
          color: sm.color,
          center: [0, eyeLPos[1] + 0.01, muzzleMaxZ - 0.03],
          radius: [0.045 * scale, 0.075 * scale, 0.08],
          parts: ['head', 'muzzle'],
        });
        break;

      case 'muzzle.right':
        out.push(
          {
            type: 'blob',
            color: sm.color,
            center: [-0.062, mouthPos[1] + 0.007, muzzleMaxZ - 0.02],
            radius: [0.076 * scale, 0.06 * scale, 0.085],
            maxX: -0.003,
            minY: mouthPos[1] - 0.05,
            noise: 0.06,
            parts: ['muzzle', 'head'],
          },
          {
            type: 'blob',
            color: sm.color,
            center: [-0.032, mouthPos[1] + 0.052, muzzleMaxZ - 0.02],
            radius: [0.04 * scale, 0.04 * scale, 0.07],
            maxX: 0.002,
            minY: mouthPos[1],
            parts: ['muzzle', 'head'],
          },
        );
        break;

      case 'muzzle.right_whisker_dots':
        out.push(
          {
            type: 'blob',
            color: sm.color,
            center: [-0.048, mouthPos[1], muzzleMaxZ],
            radius: [0.011, 0.009, 0.03],
            parts: ['muzzle'],
          },
          {
            type: 'blob',
            color: sm.color,
            center: [-0.074, mouthPos[1] - 0.01, muzzleMaxZ - 0.01],
            radius: [0.011, 0.009, 0.03],
            parts: ['muzzle'],
          },
        );
        break;

      case 'muzzle.left_lip':
      case 'muzzle.left':
        out.push({
          type: 'blob',
          color: sm.color,
          center: [0.048, mouthPos[1] - 0.036, muzzleMaxZ - 0.01],
          radius: [0.052 * scale, 0.018 * scale, 0.065],
          minX: 0.01,
          minY: mouthPos[1] - 0.052,
          maxY: mouthPos[1] - 0.018,
          parts: ['muzzle'],
        });
        break;

      case 'chin':
        out.push({
          type: 'blob',
          color: sm.color,
          center: [0, mouthPos[1] - 0.083, muzzleMaxZ - 0.04],
          radius: [0.12, 0.024, 0.08],
          maxY: mouthPos[1] - 0.063,
          parts: ['muzzle'],
        });
        break;

      case 'ear.left':
        out.push({ type: 'part', color: sm.color, parts: ['earL'] });
        break;

      case 'ear.right':
        out.push({ type: 'part', color: sm.color, parts: ['earR'] });
        break;

      case 'tail.rings':
        out.push({
          type: 'stripes',
          color: sm.color,
          axis: 'y',
          frequency: 8.5,
          width: 0.38,
          parts: ['tail'],
        });
        break;

      case 'tail.solid':
        out.push({ type: 'part', color: sm.color, parts: ['tail'] });
        break;

      case 'tail.tip': {
        const tipPos: [number, number, number] = tailBox
          ? [0, tailBox.max.y - 0.02, tailBox.min.z + 0.02]
          : [0, 0.89, -0.92];
        out.push({
          type: 'blob',
          color: sm.color,
          center: tipPos,
          radius: [0.09 * scale, 0.09 * scale, 0.09 * scale],
          parts: ['tail'],
        });
        break;
      }
    }
  }

  return out;
}

/**
 * 将 `PhotoExtractedDNA` 转换为完整的 `PetDNA`
 */
export function buildPetDnaFromExtracted(
  extracted: PhotoExtractedDNA,
  restMap?: RestMap,
  anchors?: FaceAnchorsMap,
): PetDNA {
  return {
    id: extracted.id,
    name: extracted.name,
    shape: { ...extracted.shape },
    coat: {
      texture: null,
      base: extracted.baseColor,
      palette: [...extracted.palette],
      markings: translateSemanticMarkings(extracted.semanticMarkings, restMap, anchors),
    },
    earInner: extracted.earInner,
    eyes: { ...extracted.eyes },
    nose: extracted.nose,
    personality: { idle: 0.2, walk: 0.25, sit: 0.15, loaf: 0.15, groom: 0.15, belly: 0.1 },
  };
}

/**
 * 内置咪咪 8 张真实照片的视觉大模型结构化提取结果（含正脸照片关键点与 5 大非对称语义印记）
 */
export const MIEMIE_PHOTO_LIST = [
  { file: 'reference_muzzle_closeup.jpg', tag: '正脸微距（阴阳嘴套+偏左火焰）' },
  { file: 'photo_07_closeup_asymmetry.jpg', tag: '正侧卧姿（右嘴套焦糖+左腹白云）' },
  { file: 'photo_04_front_loaf.jpg', tag: '正坐揣手（右前腕内侧暖金斑）' },
  { file: 'photo_02_belly_spot.jpg', tag: '仰躺翻肚皮（雪白腹中央暖橘斑）' },
  { file: 'photo_01_biting_toy.jpg', tag: '咬玩具（前长白袜+后短白袜）' },
  { file: 'photo_03_top_angle.jpg', tag: '俯视背脊（深棕虎斑背鞍）' },
  { file: 'photo_05_curled_ball.jpg', tag: '蜷睡球姿（S型环纹尾+黑尾尖）' },
  { file: 'photo_06_desk_companion.jpg', tag: '桌面伴读（翡翠绿眼+挺拔耳）' },
];

export const MIEMIE_PHOTO_EXTRACTED_DNA: PhotoExtractedDNA = {
  id: 'mimi',
  name: '咪咪（8张真照片提取）',
  coatPattern: 'tabby_and_white',
  baseColor: '#a87d56',
  palette: ['#a87d56', '#4a3325', '#2f2017', '#f6f3ec', '#c68b59', '#dca675', '#dfa09a'],
  earInner: '#dfa09a',
  eyes: { iris: '#68b85b', pupil: '#162112' },
  nose: '#c85a48',
  shape: {
    headRound: 0.48,
    weight: 0.28,
    earSize: 0.58,
    tailFluff: 0.35,
    cheekFluff: 0.48,
    muzzleSize: 0.55,
  },
  frontalPhotoUrl: 'photos/miemie/reference_muzzle_closeup.jpg',
  useFaceProjection: true,
  faceKeypoints: {
    eyeR: [0.30, 0.55],
    eyeL: [0.56, 0.56],
    nose: [0.42, 0.70],
    blazeTop: [0.47, 0.52],
    mouthR: [0.34, 0.72],
    mouthL: [0.52, 0.73],
    chin: [0.44, 0.80],
    forehead: [0.42, 0.36],
    earBaseR: [0.20, 0.35],
    earBaseL: [0.68, 0.36],
  },
  semanticMarkings: [
    { id: 'body_tabby', label: '背部与肋骨深棕虎斑条纹', region: 'body.tabby_stripes', color: '#4a3325', extent: 'medium', enabled: true },
    { id: 'dorsal_line', label: '背脊中线黑褐主脊纹', region: 'back.dorsal_stripe', color: '#2f2017', extent: 'medium', enabled: true },
    { id: 'hindL_thigh', label: '左后腿虎纹花裤衩', region: 'paw.hindLeft.thigh', color: '#4a3325', extent: 'medium', enabled: true },
    { id: 'hindR_thigh', label: '右后腿虎纹花裤衩', region: 'paw.hindRight.thigh', color: '#4a3325', extent: 'medium', enabled: true },
    { id: 'tail_rings', label: '尾巴深棕虎斑环纹', region: 'tail.rings', color: '#4a3325', extent: 'medium', enabled: true },
    { id: 'tail_tip', label: '黑褐尾尖', region: 'tail.tip', color: '#2f2017', extent: 'medium', enabled: true },
    { id: 'forehead_m', label: '额头深棕 M 字虎斑纹', region: 'forehead.m_tabby', color: '#4a3325', extent: 'medium', enabled: true },
    { id: 'belly_white', label: '纯白肚皮底色', region: 'belly.base', color: '#f6f3ec', extent: 'medium', enabled: true },
    { id: 'chest_bib', label: '胸前雪白大围脖', region: 'chest.bib', color: '#f6f3ec', extent: 'medium', enabled: true },
    { id: 'flank_left_cloud', label: '左肋腹通背白云斑 (+X)', region: 'flank.left', color: '#f6f3ec', extent: 'medium', enabled: true },
    { id: 'frontL_sock', label: '左前腿过膝长白袜', region: 'paw.frontLeft', color: '#f6f3ec', extent: 'large', enabled: true },
    { id: 'frontR_sock', label: '右前腿过膝长白袜', region: 'paw.frontRight', color: '#f6f3ec', extent: 'large', enabled: true },
    { id: 'frontR_wrist_spot', label: '右前腕内侧暖金焦糖斑 (-X)', region: 'paw.frontRight.inner_wrist', color: '#c68b59', secondaryColor: '#dca675', extent: 'medium', enabled: true },
    { id: 'hindL_sock', label: '左后脚踝踩雪短白袜', region: 'paw.hindLeft.sock', color: '#f6f3ec', extent: 'medium', enabled: true },
    { id: 'hindR_sock', label: '右后脚踝踩雪短白袜', region: 'paw.hindRight.sock', color: '#f6f3ec', extent: 'medium', enabled: true },
    { id: 'belly_spot', label: '雪白肚皮正中央独立暖橘圆斑', region: 'belly.center_spot', color: '#c68b59', secondaryColor: '#dca675', extent: 'medium', enabled: true },
    { id: 'muzzle_white', label: '嘴套雪白基底', region: 'muzzle.base_white', color: '#f6f3ec', extent: 'medium', enabled: true },
    { id: 'blaze_left', label: '鼻梁偏左眼通鼻白火焰 (+X)', region: 'nose_bridge.blaze_left', color: '#f6f3ec', extent: 'medium', connectsTo: ['muzzle.base_white'], enabled: true },
    { id: 'muzzle_right_caramel', label: '猫右嘴套连鼻焦糖色块 (-X)', region: 'muzzle.right', color: '#c68b59', extent: 'large', connectsTo: ['nose_bridge'], enabled: true },
    { id: 'muzzle_right_dots', label: '右嘴套深棕胡须点', region: 'muzzle.right_whisker_dots', color: '#4a3325', extent: 'small', enabled: true },
    { id: 'muzzle_left_lip', label: '猫左嘴套唇下窄浅杏边 (+X)', region: 'muzzle.left_lip', color: '#dca675', extent: 'small', enabled: true },
    { id: 'chin_white', label: '纯白下颌', region: 'chin', color: '#f6f3ec', extent: 'medium', enabled: true },
  ],
};
