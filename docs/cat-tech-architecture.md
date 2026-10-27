# 喵汪小镇 · 猫猫还原技术架构（3D 骨骼母版 + 实时像素化）

> 目标：一套母版骨骼驱动所有猫的所有动作；每只猫只是一份数据（Pet DNA + 一张印记贴图）；画风由渲染管线统一输出为 HD-2D 像素风。
> 工作量从「动作数 x 宠物数 x 帧数」降为「动作数 + 宠物数」。

## 1. 三层解耦

| 层 | 产出 | 做几次 | 代码位置 |
| --- | --- | --- | --- |
| 外观层 | Pet DNA JSON + 印记贴图（或印记描述） | 每只宠物一次 | `prototype/public/pets/*.json` |
| 动作层 | 母版骨骼 + 动作片段 + 程序化层 | 每个动作一次，全猫通用 | `prototype/src/anim/` |
| 画风层 | 低分辨率渲染 + 卡通色阶 + 描边 + 像素对齐 | 全局一次 | `prototype/src/render/` |

硬性约束（违反任何一条就回到了旧路线）：

1. 动作片段文件里**不允许**出现任何宠物 id、宠物颜色或宠物专属贴图引用。
2. 宠物目录里**只允许**出现 JSON 和图片，不允许出现动作数据或代码。
3. 印记只存在于模型表面的贴图上，不存在于任何一帧画面里。

## 2. 母版猫（Base Rig #2）

### 2.1 来源

- 验证阶段：`prototype/src/cat/` 下的程序化构建器直接生成蒙皮网格（参数化部件 -> 网格 + 骨骼权重 + 形态键 + 非镜像 UV）。
  对外接口是 `CatAsset { mesh, skeleton, bones, partLayout }`，和 Blender 导出的 GLB 等价。
- 量产阶段：demo 内「导出 GLB」得到 `cat_base.glb`，导入 Blender 精修造型和动作后再导出 GLB 替换即可，运行时代码不需要改。

### 2.2 比例（Q 版）

单位：1 = 1 米级抽象单位，地面 y = 0，猫朝 +Z，猫自身的左侧为 +X。

| 部件 | 中心 | 尺寸 |
| --- | --- | --- |
| 身体 | (0, 0.52, 0) | 椭球半径 (0.29, 0.27, 0.48) |
| 头 | (0, 0.92, 0.55) | 椭球半径 (0.36, 0.32, 0.31)，头身比约 1:1.4 |
| 嘴套 | (0, 0.83, 0.80) | 椭球半径 (0.14, 0.085, 0.08) |
| 腿 | 肩/胯高 0.45 | 短腿，爪球半径 0.075 |
| 尾巴 | 根部 (0, 0.6, -0.5) | 6 节骨骼，向后上方弯曲 |

### 2.3 骨骼

```
root（位移/朝向，供闲逛移动）
└─ hips
   ├─ spine ─ chest ─ neck ─ head ─ earL / earR
   │          ├─ shoulderL ─ elbowL ─ fpawL
   │          └─ shoulderR ─ elbowR ─ fpawR
   ├─ hipL ─ kneeL ─ hpawL
   ├─ hipR ─ kneeR ─ hpawR
   └─ tail0 ─ tail1 ─ tail2 ─ tail3 ─ tail4 ─ tail5
```

所有骨骼静止姿态的局部轴与世界轴对齐，动作数据直接写欧拉角（度）：

- 绕 X 正方向：低头 / 腿向后摆。
- 绕 Y 正方向：向猫自身左侧转。
- 绕 Z 正方向：向猫自身右侧歪（歪头）。

### 2.4 UV 与贴图像素密度规范

- **UV 绝不左右镜像**：左右耳、左右脸、四条腿各有独立区域。非对称五印记依赖这一点。
- 印记贴图 `512x512`（`ATLAS_SIZE = 512`），最近邻采样，不开 mipmap。
- 嘴套区域拥有 `128x64` 纹素，确保左唇下沿窄浅杏棕边、右嘴套焦糖斑与胡须点、鼻梁偏左白火焰等细微非对称特征在默认与近景镜头下均清晰可读。
- 图集布局（像素）：

| 区域 | 矩形 (x, y, w, h) | 映射 |
| --- | --- | --- |
| 头 | 0, 0, 256, 128 | 横向绕 Y 一圈（中线 = 正脸），纵向从头顶到下巴 |
| 嘴套 | 256, 0, 128, 64 | 同上 |
| 脖子 | 384, 0, 128, 64 | 横向绕脖一圈，纵向从胸到头 |
| 身体 | 0, 128, 256, 192 | 横向绕身体一圈（中线 = 背），纵向从尾到胸 |
| 四条腿 | 256, 64 起，每条 64x96 | 横向绕腿一圈，纵向从肩到爪 |
| 左右耳 | 256, 160 / 320, 160，各 64x64 | 横向绕耳一圈，纵向从耳根到耳尖 |
| 尾巴 | 0, 320, 256, 64 | 横向从尾根到尾尖，纵向绕尾一圈 |

### 2.5 形态键（体型）

形态键只改外形、不移动骨骼，所以不会破坏任何动作。

| 键 | 0 | 1 |
| --- | --- | --- |
| `headRound` | 标准头 | 更宽更圆的大饼脸 |
| `weight` | 标准身材 | 圆滚滚、肚子下垂 |
| `earSize` | 标准耳 | 大耳朵 |
| `tailFluff` | 细尾 | 蓬松大尾巴 |
| `cheekFluff` | 无腮毛 | 腮毛外扩 |
| `muzzleSize` | 小嘴套 | 饱满嘴套 |

腿长会移动关节位置，验证阶段不做形态键（Q 版统一短腿）；量产需要时改为调整骨骼长度。

## 3. Pet DNA 规范與咪咪（咩咩）真照片校准

```json
{
  "id": "mimi",
  "name": "咪咪",
  "shape": { "headRound": 0.65, "weight": 0.38, "earSize": 0.42, "tailFluff": 0.42, "cheekFluff": 0.55, "muzzleSize": 0.72 },
  "coat": {
    "texture": null,
    "base": "#a87d56",
    "palette": ["#a87d56", "#4a3325", "#2f2017", "#f6f3ec", "#c68b59", "#dca675", "#dfa09a"],
    "markings": [ ... ]
  },
  "earInner": "#dfa09a",
  "eyes": { "iris": "#8fb369", "pupil": "#1b2416" },
  "nose": "#c85a48",
  "personality": { "idle": 0.2, "walk": 0.25, "sit": 0.15, "loaf": 0.15, "groom": 0.15, "belly": 0.1 }
}
```

对照咩咩 7 张真实照片校准的 5 大核心细节：

1. **四肢长短白袜**：双前腿（`fLegL` / `fLegR`）为过膝长白袜（`maxY: 0.40` 纯白 `#f6f3ec`），且右前腿（`fLegR`）内侧腕部带一小块暖金/焦糖斑（`#c68b59` / `#dca675`）；双后腿（`hLegL` / `hLegR`）上半截为焦糖底配深棕虎纹花裤衩（`minY: 0.22`），下半截脚踝与爪子为踩雪短白袜（`maxY: 0.22`）。
2. **翡翠黄绿眼与砖红粉鼻头**：虹膜采用翡翠黄绿 `#8fb369`（配深绿外环与双高光点），鼻头采用砖红粉 `#c85a48`。
3. **额头 M 纹与偏左通鼻白火焰**：鼻梁至额头中线略偏猫自身左侧（`+X` 侧，正面画面右侧）有一道向上收尖的雪白通鼻火焰斑（`#f6f3ec`），与左鼻孔下方纯白连通；额头上方保留深棕虎斑 M 纹。
4. **阴阳嘴套、纯白下巴与左腹通背白云斑**：猫右嘴套（`-X` 侧，正面画面左侧）为一整块饱满连到右鼻孔下的焦糖花生酱色块（`#c68b59`）并点缀深棕胡须点；猫左嘴套（`+X` 侧，正面画面右侧）左鼻孔下纯白，仅沿左唇下沿有一弯窄浅杏棕弧边（`#dca675`），下巴与胸前围脖纯白；左肋腹（`+X`）一道宽大通背白云斑从白肚皮漫延至背脊，右肋腹（`-X`）为连续焦糖底配深棕鱼骨刺虎斑。
5. **雪白肚皮正中央的独立小暖橘圆斑**：肚皮底面整体雪白（`#f6f3ec`），正中央（`[0, 0.25, -0.02]`）有一颗独立的圆润暖橘圆斑（外圈浅杏 `#dca675` + 核心焦糖橘 `#c68b59`）。

## 4. 动作层

### 4.1 动作片段

- 每个动作一个文件：`prototype/src/anim/clips/<name>.ts`，用关键帧 DSL 描述骨骼欧拉角、`hips` 位移、以及表情轨（眼睛/嘴的贴图状态）。
- 注册在 `prototype/src/anim/clips/index.ts`。**新增动作 = 新增一个文件 + 注册一行**，不碰任何宠物资源。
- 未写到的骨骼自动补静止姿态，保证动作间交叉淡入淡出干净。

当前动作库（7 个动作）：

| 动作 | 名称 | 循环 | 说明 |
| --- | --- | --- | --- |
| `idle` | 待机呼吸 | 是 | 胸腔起伏、微点头 |
| `walk` | 走 | 是 | 对角步态，移动速度与步频匹配 |
| `sit` | 坐下 | 是 | 后腿折叠、前腿撑地 |
| `loaf` | 揣手手 | 是 | 四肢收进身体下方、眯眼 |
| `groom` | 舔毛 | 是 | 坐姿抬右前爪，舔爪 + 吐舌表情 |
| `stretch` | 伸懒腰 | 否 | 第 6 个动作，用于验证门槛 2 |
| `belly` | 翻肚皮 | 是 | 第 7 个动作，仰躺侧翻露出雪白肚皮与中央暖橘圆斑，四肢舒展不遮挡腹部 |

### 4.2 程序化层（运行时叠加，零美术成本）

每帧顺序：还原上一帧的动画姿态（去掉上一帧的程序化叠加）-> 动画混合器写入动作 -> 记下动画姿态 -> 程序化层叠加。
注意：three.js 的动画混合器只在数值变化时才写骨骼，所以不能每帧复位到静止姿态，否则「坐着不动」这类恒定姿态会被抹掉。

- 看向：头和脖子按权重转向鼠标/玩家，限制角度。
- 尾巴弹簧：每节尾骨是一个阻尼弹簧，受身体转向、移动速度和慢速噪声驱动，尾尖滞后于尾根。
- 呼吸：胸腔微幅起伏叠加在任何动作上。
- 耳朵抖动：随机间隔的单耳快速抖动。
- 眨眼：随机间隔切换眼睛贴图；动作的表情轨优先。
- 脚部 IK：小镇地面目前是平地，暂不启用；有坡地后再加。

### 4.3 闲逛状态机（性格 = 权重）

`idle -> 按 personality 权重挑下一个状态 -> walk 到随机点 / sit / loaf / groom / belly -> ...`
同一套动作库，不同权重就是不同性格：懒猫 `loaf` 权重高，好动的猫 `walk` 权重高。

## 5. 画风层（像素化渲染管线）

1. 场景渲染到低分辨率目标（默认屏幕尺寸 / 像素倍率，倍率 3），最近邻采样。
2. 卡通材质：3 档色阶渐变贴图，主光 + 环境光 + 阴影。
3. 描边：后处理读深度，物体边缘一像素描边，颜色取自身颜色压暗（不是纯黑），更柔和。
4. 可选调色板量化：每通道限定色阶，强化像素画质感。
5. 像素对齐相机：正交相机，跟随目标时把相机位置吸附到像素网格，避免移动时画面闪烁。
6. 脸部：眼睛和嘴是手绘像素贴图集（睁眼/眨眼/开心眯眼/困/惊讶；闭嘴/张嘴/吐舌），贴在头骨上的小面片，切换状态而不是网格形变。

## 6. 验证门槛

| 门槛 | 判定方式 |
| --- | --- |
| 1. 主人 3 秒认出自家猫 | 人工：主人看 demo 截图/实机（`docs/validation/mimi_front_sit.png`、`mimi_left_side.png`、`mimi_right_side.png`、`mimi_belly.png` 等） |
| 2. 新增动作不碰宠物专属资源 | 自动：`npm run check` 检查动作文件不引用宠物；`stretch` 与 `belly` 均为后加动作，所有宠物直接可用 |
| 3. 换猫只需贴图 + DNA | 自动：`npm run check` 检查宠物目录只有 JSON/图片；demo 内切换三只猫，7 个动作完全共用 |

## 7. 工具链

- 建模/绑定/动作精修：Blender + Rigify（免费）。
- 运行时：three.js + TypeScript + Vite。
- 像素贴图：LibreSprite（免费）或 Aseprite；也可直接用 demo 的「绘制印记」模式。
- 资源格式：glTF/GLB。

## 8. 运行

需要 Node 18+（本机用 `~/.nvm/versions/node/v20.20.2`）。

```bash
cd 喵汪小镇/prototype
npm install
npm run dev      # 打开 http://localhost:5173
npm run check    # 门槛 2、3 自动检查
npm run build    # 类型检查 + 生产构建
```

URL 参数（方便截图对比）：`pet=mimi|juzi|nainiu`、`action=idle|walk|sit|loaf|groom|stretch|belly`（定住该动作）、
`scale=1..6`（像素倍率）、`zoom`（视野高度，越小越近）、`heading`（猫朝向，弧度）、`pitch`（镜头俯角）、`ui=0`（隐藏面板）。

交互：鼠标移动猫会看你；点猫会歪头、眯眼开心；「在猫身上绘制」模式下直接在 3D 猫身上画印记，画完「导出印记 PNG」，
放进 `public/pets/` 并在 DNA 里填 `coat.texture` 即可。

## 9. 验证结果（2026-10-27）

| 门槛 | 结果 |
| --- | --- |
| 1. 主人 3 秒认出 | **已对照 7 张真照片完成全部 5 处细节精校**。截图见 `docs/validation/`：正脸（`mimi_front_sit.png`）、左侧（`mimi_left_side.png`）、右侧（`mimi_right_side.png`）、翻肚皮（`mimi_belly.png`）、揣手手（`mimi_loaf.png`）、舔毛（`mimi_groom.png`）、伸懒腰（`mimi_stretch.png`）、全景（`town_overview.png`） |
| 2. 新增动作不碰专属资源 | **通过**。`stretch`（伸懒腰）与 `belly`（翻肚皮）只新增 `clips/*.ts` + 注册一行，三只猫直接可用；`npm run check` 通过 |
| 3. 换猫只需贴图 + DNA | **通过**。咪咪 / 橘座 / 奶牛 三只猫只有三份 JSON 的差异（体型、印记、眼睛、性格），共用同一网格、骨骼、7 个动作（21 种组合） |

---

## 10. 母版升级（Blender 无界面一体流形 GLB）与 8 张照片转 DNA 流水线

### 10.1 一次性 Blender 母版流水线（`prototype/tools/blender/build_base.py`）

通过 `npm run build:base`（底层执行 `blender -b -P tools/blender/build_base.py`）自动完成 9 步标准化流水线：

1. **造型来源（双模式支持）**：
   - 默认模式：由闭合解剖子体经 Blender `EXACT Boolean Union` 融合；
   - 外部导入模式：`blender -b -P tools/blender/build_base.py -- --input raw_cat.glb` 导入 AI 图生 3D 模型并自动归一化至 `y=0` 接地、朝 `+Z`、身长约 `1.0`。
2. **体素重建与减面平滑（`Voxel Remesh + Smooth + Decimate`）**：消除内部穿插面，融合成 **单一连通水密流形表面（Single Continuous Manifold Mesh，约 6560 三角面）**，脖子、脸颊、嘴套、四肢与躯干 100% 零接缝。
3. **解剖部件顶点标签 `_PART`（`0..10`）**：写入 glTF 自定义属性 `_PART`（对应 `head, muzzle, neck, body, fLegL, fLegR, hLegL, hLegR, earL, earR, tail`）。
4. **非镜像高密度 UV 展开**：绝不左右镜像，头部（`256×128`）与嘴套（`128×64`）分配 1.6x 以上纹素密度，保持焊接连续法线。
5. **同名同层级 26 根骨骼与 `bones.json`**：导出 `prototype/public/base/bones.json` 供复核。
6. **平滑蒙皮权重**：头颈、肩胸、臀腿、尾骨链采用 Hermite 平滑过渡，7 个动作零撕裂。
7. **6 个标准形态键（ShapeKeys）**：`headRound, weight, earSize, tailFluff, cheekFluff, muzzleSize` 随 GLB 导出。
8. **表面五官锚点（`faceAnchors`）**：动态采样网格前表面生成 `eyeL, eyeR, mouth, whiskerL, whiskerR` 空物体与 glTF `extras`。
9. **导出母版 GLB**：输出 `prototype/public/base/cat_base.glb` 与 `assets/cat_base.glb`。

### 10.2 运行时加载 GLB 与 UV 静止姿态位置图（Rest-Map）

- `prototype/src/cat/loadBaseGlb.ts`：解析 `base/cat_base.glb`（支持稀疏 MorphTarget Accessor），按骨骼名将 `JOINTS_0` 映射到 `createSkeleton(positions)`，**只取 GLB 的关节静止位置、忽略关节初始朝向（保持单位四元数 Identity）**，使全部 7 个动作零修改直接驱动 Blender 新网格（同时保留 `?base=procedural` 作为后备）。
- `prototype/src/cat/coatBaker.ts`（`buildRestMap`）：在 `512×512` UV 空间光栅化母版网格的所有三角形，生成每个纹素的静止 3D 坐标 `pos`、法线 `norm` 与部件编号 `partId`，并统计各部件 3D 包围盒 `partBoxes`。

### 10.3 每只猫全自动：8 张照片转结构化 DNA + 正脸关键点分片仿射投影

- `prototype/server/vlm-proxy.mjs`：本地 Node 代理（`npm run vlm-proxy`），转发最多 8 张猫咪照片至 OpenAI 兼容视觉大模型，强制「左右 = 猫自身的左右」并输出 JSON Schema 结构化 DNA。
- `prototype/src/photo/semanticMarkings.ts`：根据 `RestMap.partBoxes` 与 `faceAnchors` 自动解算 22 项语义区域（如 `muzzle.right`, `nose_bridge.blaze_left`, `muzzle.left_lip`, `paw.frontRight.inner_wrist`, `belly.center_spot`, `flank.left`）的 3D 中心与半径。
- `prototype/src/photo/faceProjection.ts`：用正脸照片 10 个关键点与 3D 脸部锚点构建 16 个分片仿射三角形（Piecewise Affine Warp），将正脸真照片直接投影到 `head` 与 `muzzle` 的正脸 UV 区域，自动白平衡校正、调色板量化吸附并经 3×3 众数滤波清理为干净像素画。

---

## 11. 全链路闭环总纲文档（前半段 + 后半段完整拼合）

完整的「**前半段（Blender/AI 一体流形母版 + 512×512 UV Rest-Map 光栅化烘焙 + 8 张真照片转 22 语义区域 DNA + 正脸 10 关键点 16 三角片分片仿射投影）**」与「**后半段（Full HD 古镇场景 + 真实 3D 地面软阴影 + 猫咪独立低分像素层 + 单档 0.76 硬阴影平涂 + 1px 深暖黑褐描边 + 灵动像素眼与贴面像素胡须）**」全链路回顾总结与工程规范，详见：

- [`docs/HD2D_CAT_FULL_LOOP_TECHNICAL_SPEC.md`](./HD2D_CAT_FULL_LOOP_TECHNICAL_SPEC.md)
