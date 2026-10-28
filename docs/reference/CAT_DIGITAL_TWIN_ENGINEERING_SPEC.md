# 猫咪数字分身：母版、CatGenome、固定 UV 与共享骨骼技术工程文档

> 文档性质：可执行施工说明，不是概念提案。
>
> 适用范围：8 张猫照片生成统一身份资产，经 Blender 离线烘焙为 8 方向 HD-2D 精灵，在 Godot 4 中播放固定动作并互动。
>
> 关联方案：`docs/prd/猫咪数字分身hd-2d方案_114933f1.plan.md`。
>
> 默认技术栈：Blender 4.2 LTS、Python 3.11、Godot 4.x Mobile、Pydantic 2、NumPy、OpenCV、Pillow。模型权重与训练/评测数据集的许可证必须单独核查，不能用代码许可证代替。

---

## 0. 文档目标与最终产物

本文档只深入以下核心链路：

```text
规范 8 图
  → 照片质检、分割、关键点、视角和颜色分析
  → CatGenome + 五印记来源数据
  → 共享体形拟合、逐图姿态/相机拟合
  → 固定 UV 反照率与印记贴图
  → 猫母版实例化（Identity + Style）
  → 共享骨骼动作重定向与每猫接触修正
  → 8 方向颜色/法线/锚点烘焙
  → 固定像素网格、统一调色板、CatAsset
```

最终每只猫得到一套可版本化资产：

```text
canonical_identity.glb       真实身份比例，用于审核和后续重建
stylized_rigged.blend        风格化、已绑定、已修正动作的 Blender 实例
fur_albedo.png               固定 UV 中性反照率
coverage.png                 UV 观测来源覆盖图
genome.json                  CatGenome 主数据
markings.json                五印记 UV 与照片来源
anim.json                    帧、方向、锚点、接触和版本元数据
atlas_<action>_albedo.png    各动作颜色图集
atlas_<action>_normal.png    各动作法线图集
identity_review.png          用户身份确认板
```

### 0.1 四条不可破坏的原则

1. **不逐帧生成猫。** 身份、UV 和骨架只生成一次，动作共享。
2. **身份主数据必须独立于渲染图。** 五印记保存为 UV 几何/mask，不是某张正面 sprite。
3. **Identity、Style、Motion 分层。** 照片决定身份，统一美术规范决定风格，动作库与接触修正决定运动。
4. **共享骨骼不等于零成本复用动画。** 每只猫在风格变形后必须离线修正脚底、舌头和交互接触，再烘焙。

### 0.2 第一版边界

第一版只做：短毛猫、`idle / walk / sit_down / sit_idle / stand_up / groom / pet_react`、8 方向、固定相机、固定动作库、用户确认。

暂不做：任意文本动作、真实毛发仿真、自由旋转视角、逐帧 AI 精修、复杂双猫互动。

---

## 1. 总体架构与数据契约

### 1.1 三层模型

#### Identity 层：这只猫是谁

保存：

- 真实躯干、腿、头、耳、尾的比例；
- 毛色分区、五处身份印记；
- 眼睛、鼻子、肉垫颜色；
- 照片证据、拟合结果、覆盖率和置信度。

#### Style 层：在小镇里长什么样

保存：

- 统一的短腿、大头、大眼和圆润程度；
- 相机、光照、描边、色板、像素网格；
- 不改变身份的颜色映射与最小印记线宽。

#### Motion 层：怎样动起来

保存：

- 共享骨架语义和动作；
- 每猫实例的脚底、坐姿、舔毛、抚摸接触修正；
- 世界移动速度、方向、锚点和行为事件。

### 1.2 版本号必须分开

```json
{
  "schema_version": 1,
  "master_mesh_version": 1,
  "uv_version": 1,
  "rig_version": 1,
  "animation_version": 1,
  "render_spec_version": 1,
  "identity_version": 1,
  "asset_version": 1
}
```

版本变更规则：

| 变更 | 必须升级的版本 | 旧资产处理 |
|---|---|---|
| CatGenome 字段增删/含义变化 | `schema_version` | 写迁移脚本 |
| 网格拓扑或语义顶点变化 | `master_mesh_version` | 重新绑定/拟合 |
| 任意 UV 坐标、岛布局变化 | `uv_version` | 旧 mask 和贴图全部失效 |
| 骨骼名称、层级、静止姿态语义变化 | `rig_version` | 动作重定向/重做 |
| 动作内容或接触定义变化 | `animation_version` | 全部猫重烘相关动作 |
| 相机、调色板、像素规则变化 | `render_spec_version` | 重烘颜色/法线图集 |
| 用户修改身份 | `identity_version` | 重建该猫资产 |

**UV 一旦冻结，禁止为了修一个贴图问题而顺手移动 UV。修贴图，不修 UV。**

### 1.3 推荐目录

```text
art/master_cat/
  master_cat.blend
  master_spec.json
  rig_map.json
  uv_manifest.json
  uv_layout.png
  landmark_vertices.json
  actions/
  masks/
pipeline/
  common/       genome.py, versions.py, hashing.py, coords.py
  perception/   qc.py, detect.py, segment.py, keypoints.py, views.py, color.py, vlm.py
  fit/          fit_shape.py, fit_cameras.py, landmarks.py
  texture/      compose.py, project.py, markings.py, coverage.py
  rig/          instantiate.py, adapt_rest.py, retarget.py, contacts.py
  bake/         bake.py, normals.py, anchors.py, post.py, pack.py
  eval/         validate_master.py, validate_identity.py, validate_animation.py
cats/{cat_id}/
  capture_v1/
    raw/, normalized/, masks/, landmarks/
    capture.json, quality.json, views.json
  identity_v1/
    genome.json, markings.json, eyes.json
    identity_shape.json, style_shape.json
    fitted_cameras.json, fit_report.json
    fur_albedo.png, coverage.png, confidence.json
    canonical_identity.glb, stylized_rigged.blend
    approval.json, identity_review.png
  asset_v1/
    anim.json, palette.png, palette.json
    atlas_<action>_albedo.png
    atlas_<action>_normal.png
    manifest.json
```

---

## 2. 坐标、单位、颜色和方向约定

这些约定必须先写进 `master_spec.json`，否则后续会出现左右互换、法线反向、动画旋转错误。

### 2.1 Blender 母版空间

- 单位：米，1 Blender Unit = 1 m。
- 地面：Z=0。
- 上方向：+Z。
- 猫前方：+Y。
- 猫右方：+X；猫的解剖学左侧：X<0，后缀 `_L`。
- `root` 位于两脚之间地面投影，坐标 `(0,0,0)`。
- 母版按真实猫肩高约 0.25–0.35 m 建模，最后显示大小由统一的 `px_per_meter` 控制。

选择 +Y 向前的原因：Blender glTF 导出常用映射 `(x,y,z) → (x,z,-y)`，因此 Blender +Y 会变为 glTF/Godot -Z，符合 Godot 的前方约定。实际导出后必须用一个朝前箭头做自动/人工验证，不能只依赖经验。

### 2.2 Godot 空间

- 上方向：+Y。
- 猫前方：-Z。
- 猫右方：+X，左侧 `_L` 仍为 X<0。
- 游戏世界移动由 `CharacterBody3D` 负责，sprite 的 `walk` 原地播放。

### 2.3 相机方向编号

`d000` 表示猫正面视角，相机位于 Blender +Y，朝原点看。其余方向绕 Z 轴每 45° 递增：

```text
d000=front, d045=front_right, d090=right, d135=rear_right,
d180=rear, d225=rear_left, d270=left, d315=front_left
```

方向编号表示**相机看猫的方向**，不是猫正在移动的方向。`anim.json` 必须另存 `world_yaw_offset`，供 Godot 映射移动方向。

### 2.4 UV 与图片坐标

- JSON 中 UV 使用 Blender 约定：左下 `(0,0)`，右上 `(1,1)`。
- PNG 数组使用左上原点。
- 转换：`x = u * (W-1)`，`y = (1-v) * (H-1)`。
- 所有转换只放在 `pipeline/common/coords.py`，禁止各模块自行再写一套。

### 2.5 颜色空间

- `fur_albedo.png`、颜色图集：sRGB。
- mask、coverage、normal：`Non-Color`。
- Blender 烘焙颜色时使用 `Standard`，`Look=None`，曝光 0，Gamma 1。
- 不用 Filmic/AgX 烘焙像素 albedo。
- 眼睛和颜色取样保留 sRGB 十六进制与 CIE Lab 两种值；色差计算用 Lab。

### 2.6 法线约定

第一版固定为 `camera_opengl`：

- +X 朝相机右方；
- +Y 朝相机上方；
- +Z 朝相机/观察者可看见表面的外侧；
- 存储：`rgb = normal_xyz * 0.5 + 0.5`；
- 法线贴图是 Non-Color，不做调色板量化。

在 Godot 中用一只已知朝向的斜面验证光照。如果明暗相反，只允许在统一 normal 转换层修改，不逐张修图。

---

## 3. 猫母版施工规范

### 3.1 Blender 对象命名

```text
CAT_BODY             身体、四肢、头、耳、尾，可为一个连通或分部件网格
CAT_EYE_L            左眼球/虹膜/瞳孔，可子对象但共享材质语义
CAT_EYE_R
CAT_TONGUE
CAT_ARMATURE
CAT_CAMERA_BAKE      仅烘焙文件需要
hot_head             空物体，头顶交互锚点
hot_back             空物体，背部交互锚点
hot_belly            空物体，腹部交互锚点
hot_groom            空物体，舔毛目标点
hot_pet              空物体，抚摸接触点
foot_FL              四足地面参考点，可用空物体或语义顶点
foot_FR
foot_BL
foot_BR
```

源母版不保存某个用户的毛色。材质使用中性占位贴图，用户实例通过脚本替换。

### 3.2 网格要求

首版短毛母版建议 3000–6000 三角面，眼睛和舌头可另计。重点不是面数，而是变形拓扑。

必须满足：

- 肩/髋、肘/膝、腕/踝有足够环状拓扑；
- 颈部、下颌、耳根、尾根有独立变形区域；
- 嘴能张开，舌头能伸出并与前腿接触；
- 眼睑有独立几何或可实现眨眼的 shape key；
- 眼睛独立网格/材质，不与皮毛共用低分辨率 UV；
- 左右身体和四肢保留独立 UV，禁止镜像复用；
- 所有缩放 apply，法线方向统一，无零面积面、非流形边和重复顶点；
- 骨骼绑定前只保留必要修改器，最终网格拓扑固定。

### 3.3 语义顶点表

在母版制作时，把关键网格顶点编号写入 `landmark_vertices.json`：

```json
{
  "mesh_version": 1,
  "points": {
    "head_center": [1201],
    "chin": [1188],
    "shoulder_FL": [330, 334],
    "elbow_FL": [362],
    "wrist_FL": [391],
    "paw_FL": [405, 409],
    "hips_center": [80, 82],
    "tail_root": [92],
    "groom_foreleg": [370, 374, 378]
  }
}
```

这些点用于：

- 体形变化后重新放置骨骼；
- 计算脚底和交互接触点；
- 校验动作变形；
- 后续自动拟合。

拓扑改变后顶点编号可能变化，所以必须升级 `master_mesh_version`，不能沿用旧表。

---

## 4. 固定 UV 施工规范

### 4.1 工作分辨率与交付分辨率

- 母版工作贴图：2048×2048。
- 第一版游戏 UV 贴图：1024×1024。
- mask 源文件：2048×2048 灰度 PNG。
- 导出游戏贴图时用 Area/Lanczos 降采样，不用最近邻。

### 4.2 推荐 UV 岛布局

可用 4×4 逻辑网格管理岛位置；实际岛形不必是矩形，但不能越出自己的区域。2048 工作图每格约 512×512。

| 区域 | UV 象限/格 | 内容 |
|---|---|---|
| A1 | 第 1 行第 1 列 | 头部正面、脸颊、额头 |
| A2 | 第 1 行第 2 列 | 后脑、头顶 |
| A3 | 第 1 行第 3 列 | 口鼻、下巴、喉部 |
| A4 | 第 1 行第 4 列 | 左右耳，耳内/耳外分区 |
| B1 | 第 2 行第 1 列 | 左躯干 |
| B2 | 第 2 行第 2 列 | 右躯干 |
| B3 | 第 2 行第 3 列 | 背部 |
| B4 | 第 2 行第 4 列 | 腹部 |
| C1–C4 | 第 3 行 | FL、FR、BL、BR 四条腿，各自完整内侧/外侧 |
| D1 | 第 4 行第 1 列 | 尾巴整段，按尾根到尾尖单向展开 |
| D2 | 第 4 行第 2 列 | 左右眼球、虹膜、瞳孔独立区域 |
| D3 | 第 4 行第 3 列 | 鼻、肉垫、舌头、口腔 |
| D4 | 第 4 行第 4 列 | 预留，不得提前用作镜像省略区 |

施工要求：

- 1024 输出时岛间至少 8 px padding；2048 工作时至少 16 px。
- 额头 M 纹等关键标记尽量不跨 UV 接缝。
- 五印记高频区域可分配更多面积，但不能在冻结后再调整。
- 左右不对称区域绝不共享 UV。
- 身体两侧的花纹不能用“另一侧面片复制”代替。

### 4.3 UV 冻结产物

完成 UV 后立刻生成：

```text
uv_layout.png       带岛编号、区域名和坐标的审核图
uv_manifest.json    岛、语义部位、分辨率、padding、哈希
```

`uv_manifest.json` 示例：

```json
{
  "uv_version": 1,
  "size_work": 2048,
  "size_game": 1024,
  "origin": "bottom_left",
  "padding_game_px": 8,
  "regions": {
    "head_front": {"grid": [0, 3], "semantic": "head"},
    "body_left": {"grid": [0, 2], "semantic": "torso_L"}
  },
  "uv_hash": "sha256:..."
}
```

### 4.4 UV 哈希算法

在 Blender Python 中按固定顺序收集每个 loop 的顶点索引和 UV，浮点统一四舍五入到 1e-6，再序列化计算 SHA-256：

```python
import hashlib, json, bpy

mesh = bpy.data.objects["CAT_BODY"].data
uv = mesh.uv_layers.active.data
rows = [
    [loop.vertex_index, round(uv[loop.index].uv.x, 6), round(uv[loop.index].uv.y, 6)]
    for loop in mesh.loops
]
payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode()
print("sha256:" + hashlib.sha256(payload).hexdigest())
```

CI 每次打开母版重算；哈希不一致直接失败，禁止静默覆盖。

---

## 5. 共享骨骼施工规范

### 5.1 骨骼清单与层级

首版约 40 根，名称和层级固定：

```text
root
└── hips
    ├── spine_01 → spine_02 → spine_03 → spine_04
    │   ├── neck_01 → neck_02 → head
    │   │   ├── jaw
    │   │   ├── eye_L, eye_R
    │   │   ├── ear_L_01 → ear_L_02
    │   │   └── ear_R_01 → ear_R_02
    │   ├── leg_FL_01 → leg_FL_02 → leg_FL_03 → leg_FL_04
    │   └── leg_FR_01 → leg_FR_02 → leg_FR_03 → leg_FR_04
    ├── leg_BL_01 → leg_BL_02 → leg_BL_03 → leg_BL_04
    ├── leg_BR_01 → leg_BR_02 → leg_BR_03 → leg_BR_04
    └── tail_01 → … → tail_08
```

规则：

- `root` 不承担身体蒙皮，负责整体变换。
- 前腿 `leg_F*_01` 挂 `spine_04`，后腿 `leg_B*_01` 挂 `hips`。
- 每条腿四节依次为上腿、下腿、脚掌、脚趾。
- 所有骨骼 `Y` 轴沿骨长方向，roll 统一；骨骼局部坐标必须在 `rig_map.json` 留图。
- `_L/_R` 以猫自身左右为准，不以相机画面左右为准。
- 眼骨只控制视线；眨眼由 shape key 完成。
- jaw 与 tongue 必须能独立动作。

### 5.2 静止姿态

统一使用自然站立 Rest Pose：

- 四足着地、脊柱自然、头朝 +Y、嘴闭合；
- 尾巴轻度弯曲但不过度贴身；
- 眼睛正视前方；
- 四肢不要完全伸直，保留可弯曲空间；
- 所有 shape key 为 Basis 时，骨骼和网格对应。

共享动作以这个 Rest Pose 为参考。修改 Rest Pose 属于 `rig_version` 破坏性变更。

### 5.3 蒙皮权重

- 每顶点最多 4 个骨骼影响，归一化总和为 1。
- 眼球/舌头等刚性部位可使用单骨 100% 权重。
- 关节处权重跨越 2–3 个环，避免“糖果纸扭转”。
- 左右骨不能串权重；脚本检查 `_L` 区域不得出现 `_R` 权重视为错误，除非明确位于中线。
- 极端姿态测试：抬前腿 90°、头低到下腿、坐姿、尾摆、下颌张开、抚摸压头。

### 5.4 形态键：Identity 与 Style 分开

建议命名：

| 类型 | Shape Key | 含义 | 输入范围 |
|---|---|---|---|
| Identity | `id_body_fat` | 躯干胖瘦 | 0–1 |
| Identity | `id_belly` | 腹部厚度 | 0–1 |
| Identity | `id_leg_len` | 真实腿长比例 | 0–1 |
| Identity | `id_neck_len` | 颈长 | 0–1 |
| Identity | `id_face_round` | 脸颊圆度 | 0–1 |
| Identity | `id_muzzle_len` | 吻长 | 0–1 |
| Identity | `id_ear_size` | 耳大小 | 0–1 |
| Identity | `id_ear_fold` | 折耳程度 | 0–1 |
| Style | `sty_head_enlarge` | 大头 | 0–1 |
| Style | `sty_leg_shorten` | 短腿 | 0–1 |
| Style | `sty_eye_enlarge` | 大眼 | 0–1 |
| Style | `sty_paw_round` | 爪部圆润 | 0–1 |
| Face | `blink_L`, `blink_R` | 左右眨眼 | 0–1 |
| Face | `squint_L`, `squint_R` | 半眯眼 | 0–1 |
| Face | `mouth_open` | 张嘴辅助 | 0–1 |

`tail_len` 和 `tail_bob` 可用尾骨缩放/弯曲实现，但同样区分身份与风格。

制作要求：

- 所有形态键相对同一 Basis，滑杆范围明确；
- `id_*` 只由照片/用户确认决定；
- `sty_*` 只由统一美术规范决定，不能从照片“识别”；
- 形态键叠加后检查眼、嘴、腿和地面关系；
- 形态键改变网格后，骨骼不能原地不动，必须执行第 8 节的 Rest Rig 适配。

### 5.5 必备表情与接触点

首版至少：

```text
blink_L / blink_R
squint_L / squint_R
mouth_open
hot_head / hot_back / hot_belly
hot_groom / hot_pet
foot_FL / foot_FR / foot_BL / foot_BR
```

---

## 6. 8 张照片与感知输入

### 6.1 规范拍摄槽位

```text
000_front
045_front_right
090_right
135_rear_right
180_rear
225_rear_left
270_left
315_front_left
```

要求：自然站立、四足着地、全身和耳尾完整、眼睛睁开、嘴闭合、同一设备和相近距离、柔和光、无滤镜、无景深虚化。正脸与两个前 45° 必须看清眼睛和面部花纹。

腹部、下颌底面、腿内侧等未覆盖区域进入 coverage；关键印记不可见时定向补拍，不假装精确恢复。

### 6.2 每张图的处理产物

```text
normalized/<slot>.png
masks/<slot>_cat.png
masks/<slot>_parts.json
landmarks/<slot>.json
views/<slot>.json
colors/<slot>.json
```

### 6.3 感知顺序

1. EXIF 转正、原图哈希、隐私信息清理；工作图不覆盖原图。
2. 单猫检测、人脸提醒、完整度和遮挡检查。
3. 模糊/过曝/偏色/分辨率质量检查。
4. SAM 2 整猫分割，低置信度人工修边。
5. 动物关键点与面部关键点，生成头/躯干/四肢/尾粗部位 mask。
6. 粗视角分类和重复视角检测。
7. DINOv2 相似度只作“可能非同猫”提示，不作为身份铁证。
8. 颜色提取、VLM 花色分类、五印记候选检测。
9. 用户确认低置信字段和关键印记。

初始阈值只作为工程起点：主体长边 ≥1200 px、正面双眼间距 ≥80 px、低置信字段 <0.7 进入确认。必须在自有评测集上重新校准。

### 6.4 颜色提取的可执行规则

在每个语义部位 mask 内：

1. sRGB 转 CIE Lab。
2. 排除 L 最低/最高各 5% 像素，减少阴影和高光。
3. 若同组照片可估计白平衡，先统一色温；否则保存颜色置信度，不盲目纠正。
4. k-means 聚 3–5 类，按面积排序为主色/次色。
5. 眼睛使用虹膜环形区域，排除瞳孔和高光，取中位色。
6. 不用 VLM 的口述颜色覆盖像素测量，只用其做异常提示。

### 6.5 体型字段的边界

VLM 可输出 `small/medium/large`、`short/medium/long` 等等级和置信度，但不能直接输出可信的 `body_fat=0.417`。

MVP 初始做法：

- 侧面关键点估计腿长/体长、头宽/肩宽等粗比例；
- 映射到 `id_*` 的 3–5 档；
- 用户在 8 方向预览中微调；
- 第二阶段再以共享形状的可微拟合替代连续数值猜测。

---

## 7. CatGenome：完整主数据设计

### 7.1 设计原则

- CatGenome 是身份与实例化契约，不直接等于一张贴图。
- 分类属性、连续形态、UV 印记、观测来源分开。
- 每个自动字段都能追溯到来源和置信度。
- 用户确认后冻结 identity 版本，动画不再重跑感知。

### 7.2 推荐 JSON 示例

```json
{
  "schema_version": 1,
  "cat_id": "cat_01J...",
  "identity_version": 1,
  "master": {
    "mesh": "cat_short",
    "mesh_version": 1,
    "uv_version": 1,
    "rig_version": 1
  },
  "identity_shape": {
    "id_body_fat": 0.45,
    "id_belly": 0.40,
    "id_leg_len": 0.42,
    "id_neck_len": 0.50,
    "id_face_round": 0.66,
    "id_muzzle_len": 0.48,
    "id_ear_size": 0.50,
    "id_ear_fold": 0.0,
    "tail_len": 0.92,
    "tail_bob": 0.0
  },
  "style_shape": {
    "sty_head_enlarge": 0.35,
    "sty_leg_shorten": 0.30,
    "sty_eye_enlarge": 0.45,
    "sty_paw_round": 0.25
  },
  "coat": {
    "pattern": "tabby_mackerel",
    "fur_length": "short",
    "colors": {
      "base": "#D8C8AA",
      "secondary": "#6B5138",
      "tertiary": null,
      "white": "#F0E9DC"
    },
    "white_regions": {
      "chin": 1.0,
      "chest": 0.75,
      "paw_FL": 1.0,
      "paw_FR": 1.0,
      "paw_BL": 0.4,
      "paw_BR": 0.4
    },
    "pattern_params": {"density": 0.5, "contrast": 0.65, "seed": 1234}
  },
  "eyes": {
    "left":  {"srgb": "#65A94C", "lab": [61.0, -35.0, 31.0]},
    "right": {"srgb": "#65A94C", "lab": [61.0, -35.0, 31.0]}
  },
  "nose": "#B98282",
  "pads": "#6B5555",
  "markers_ref": "markings.json",
  "texture": {
    "uv_version": 1,
    "size": 2048,
    "albedo": "fur_albedo.png",
    "coverage": "coverage.png"
  },
  "personality": {
    "clingy": 0.8,
    "brave": 0.3,
    "greedy": 0.7,
    "active": 0.5
  },
  "approval": {
    "status": "approved",
    "approved_by": "user",
    "approved_at": "ISO-8601"
  },
  "provenance": {
    "capture_version": 1,
    "perception_version": "git-sha",
    "automatic_fields": ["coat.pattern", "eyes.left", "eyes.right"],
    "user_edited_fields": ["identity_shape.id_face_round"]
  }
}
```

### 7.3 五印记 `markings.json`

```json
{
  "uv_version": 1,
  "identity_version": 1,
  "markers": [
    {
      "id": "mark_01",
      "name": "额头主纹",
      "semantic_part": "head_front",
      "space": "uv",
      "polygon": [[0.21, 0.81], [0.24, 0.86], [0.27, 0.82]],
      "color": "#6B5138",
      "edge_color": "#58402D",
      "source_type": "observed",
      "confidence": 0.94,
      "crosses_uv_seam": false,
      "source_photos": [
        {
          "slot": "000_front",
          "polygon_norm": [[0.42, 0.20], [0.48, 0.16], [0.53, 0.21]],
          "fit_camera_id": "cam_000_front"
        }
      ],
      "user_confirmed": true
    }
  ]
}
```

`source_type` 枚举：

```text
observed             照片直接观察
mirrored_assumed     用户确认的对称推定
interpolated         规则延伸
generated            生成式补全
unknown              无可靠依据
```

关键身份印记若为 `generated/unknown`，确认页必须显著提示。

### 7.4 Pydantic 落地要求

`pipeline/common/genome.py` 至少定义：

- `HexColor`：校验 `#RRGGBB`；
- `ShapeParams`：所有值 `Field(ge=0, le=1)`；
- `Marker`：UV 顶点也在 0–1，至少 3 点；
- `MasterRef`：四个版本号必填；
- `CatGenome`：引用相同 `uv_version`，`identity_version>=1`；
- `Personality`：只来自问卷，不从照片推断；
- `model_config = ConfigDict(extra="forbid")`，防止字段悄悄写错。

构建时先验证，再允许 Blender 读取：

```python
genome = CatGenome.model_validate_json(Path("genome.json").read_text())
assert genome.master.uv_version == markings["uv_version"]
assert genome.approval.status == "approved"
```

JSON Schema 由同一份 Pydantic 模型导出，Godot 不手写另一套字段定义。

---

## 8. 母版实例化：从 CatGenome 到可绑定猫

### 8.1 执行顺序

严格按以下顺序：

```text
读取并验证 genome
→ 复制母版，禁止改源文件
→ 应用 id_* 形态键
→ 应用 sty_* 形态键
→ 重新计算语义顶点位置
→ 适配 Rest Rig 骨骼位置
→ 绑定/更新材质与 UV 贴图
→ 重定向共享动作
→ 接触修正
→ 保存 stylized_rigged.blend
```

### 8.2 设置形态键

```python
def apply_shape_values(obj, values: dict):
    for name, value in values.items():
        key = obj.data.shape_keys.key_blocks.get(name)
        if key is None:
            raise KeyError(f"Missing shape key: {name}")
        key.value = float(value)
```

`tail_len/tail_bob` 由专门函数处理，不当作 shape key。

### 8.3 为什么必须适配 Rest Rig

Shape Key 只改变网格，不会自动把肘、膝、脚底移到正确位置。如果腿缩短 30% 而骨骼不动，共享动作必然出现脚底滑动和穿插。

实现 `adapt_rest.py`：

1. 对当前形态键求值，取得变形后的网格顶点坐标。
2. 从 `landmark_vertices.json` 读取肩、肘、腕、髋、膝、踝、头、尾根等语义位置。
3. 进入 Edit Mode，将相应骨骼 head/tail 对齐到这些位置。
4. 保持骨骼父子关系和局部轴约定；不能重命名。
5. 重新放置 `hot_*` 和 `foot_*`。
6. 回到 Object Mode，检查 Rest Pose 四足落地。
7. 保存 `rig_adapt_report.json`，记录每根骨移动量。

动作以局部旋转为主，因此骨骼长度变化后仍可重定向；位移型 F-Curve 不能盲目复制，要按对应骨长或体长缩放。

### 8.4 材质实例化

- `MAT_FUR`：Base Color 接 `fur_albedo.png`，sRGB。
- `MAT_EYE_L/R`：虹膜色使用 genome 眼睛色；瞳孔和高光独立材质/图层。
- `MAT_NOSE`、`MAT_PADS`、`MAT_TONGUE`：固定 UV 区域或独立材质。
- 烘焙 albedo 时用统一 Emission 覆盖，避免灯光烘入；正常材质仅用于审核。
- 不把五印记画到独立方向图片上。

---

## 9. 从照片到固定 UV：拟合与贴图实现

### 9.1 共享形状、逐图姿态和相机

8 张照片不能共享同一猫姿态，因为猫会动。优化变量应是：

```text
全局共享：identity_shape
每图独立：camera_extrinsics、camera_scale、cat_pose、头/耳/尾姿态
```

第一阶段可用人工辅助完成：

1. 用侧面和斜侧面初始化身体比例。
2. 在 Blender 中为每张图设置相机与猫姿态，对齐 mask 和关键点。
3. 保存每图相机和姿态，不允许每图各改一份身份形状。
4. 用 8 方向审核板让用户修正明显错误。

第二阶段自动优化：

```text
L = λmask · (1 - SoftIoU(render_mask, photo_mask))
  + λkp   · Σ confidence_i · ||project(KP3d_i) - KP2d_i||²
  + λshape· ||identity_shape - prior||²
  + λpose · pose_prior
  + λsym  · symmetry_regularization
```

约束：身份形状全局共享，遮挡关键点不参与损失，体形参数有限范围，拟合失败回退到用户编辑而不是输出高置信结果。

### 9.2 照片印记转 UV 的精确步骤

对每一处在照片上圈出的印记：

1. 记录 `slot + polygon_norm`。
2. 使用该照片已拟合的相机和猫姿态。
3. 对多边形内采样点发射相机射线。
4. 与当前身份网格求交，取得 triangle id 和 barycentric weights。
5. 用三角形三个 loop UV 做重心插值：

```text
uv = w0·uv0 + w1·uv1 + w2·uv2
```

6. 将 UV 点集栅格化为 `mark_XX_uv.png`。
7. 保存射线失败、遮挡、低掠射角区域为低置信，不强行填色。
8. 多张照片的同一印记在 UV 中做置信度融合，由用户确认最终边界。

如果印记跨 UV 接缝，必须使用 3D 表面/多岛编辑器处理，不能把接缝两侧的像素硬拉到一起。

### 9.3 多视角 UV 投影融合

对每个 UV texel 找到其三维表面点，对每张照片计算：

```text
w_i = visible_i
    × max(dot(normal, view_dir), 0)^p
    × sharpness_i
    × exposure_quality_i
    × fit_confidence_i
```

- 背面、mask 外、遮挡：`visible=0`。
- 掠射角权重降低，可先从 `p=2` 验证。
- 模糊、过曝、拟合残差大时降低权重。
- 最终颜色：`C = Σ(w_i·C_i) / Σw_i`。

输出来源数量、总权重和最大单图权重，便于发现某区域其实只被一张低质量照片覆盖。

### 9.4 去光照的现实做法

8 张 RGB 不能可靠求解物理反照率。第一版目标是“去掉明显拍摄光照”：

1. 同组照片做曝光/白平衡归一。
2. 剔除高光、硬阴影样本。
3. 在 Lab 的 L 通道估计低频照明，只做有限强度校正，避免把真实花纹当阴影抹掉。
4. 审核是否出现双重阴影；无法可靠处理时保留中性化结果并降低置信度。

### 9.5 缺区处理顺序

```text
其他真实照片
→ 用户确认的左右对称推定
→ 相邻毛色规则延伸
→ 限定 mask 的生成式补全
```

生成式补全只处理局部非关键缺区，保存模型、权重、prompt、mask、seed 和输出哈希。五印记缺失时优先补拍，不靠模型“猜得像”。

### 9.6 贴图图层顺序

```text
1. 中性底色
2. 通用花色/斑纹层
3. 白斑区域层
4. 多视角照片投影层
5. 用户确认的五印记 UV 层
6. 眼睛、鼻、肉垫、舌头固定区域
7. 缺区来源覆盖与审核标记（单独 coverage，不画进 albedo）
```

复杂三花/玳瑁不允许只换随机 seed 就标记为“已复刻”；随机纹理只能作底稿，关键色块必须来自照片或用户编辑。

---

## 10. 共享动作库与每猫接触修正

### 10.1 动作存储规范

- Blender 源动作 30 fps 制作。
- Action 命名：`cat_idle`、`cat_walk`、`cat_groom` 等。
- 位移型世界运动不写入 sprite；`walk` 原地循环。
- 源动作保存局部骨骼旋转、必要的局部位置曲线、眨眼轨道和接触事件。
- 输出帧率与源帧率分离，例如 walk 源 30 fps，导出 10 fps。

### 10.2 最小动作内容

| 动作 | 循环 | 说明 |
|---|---|---|
| idle | 是 | 呼吸、轻微头尾运动，包含自然 blink |
| walk | 是 | 原地四足步态，脚底接触事件明确 |
| sit_down | 否 | 站立到坐姿 |
| sit_idle | 是 | 坐姿呼吸 |
| stand_up | 否 | 回站立 |
| groom | 可循环 | 坐姿舔前腿/舔爪，舌头接触明确 |
| pet_react | 否/短循环 | 头顶接触、轻压头、眯眼或耳反应 |

### 10.3 接触元数据

`actions/shared/contacts.json` 示例：

```json
{
  "animation_version": 1,
  "walk": {
    "source_fps": 30,
    "export_fps": 10,
    "contacts": [
      {"foot": "foot_FL", "start_frame": 1, "end_frame": 12, "type": "planted"},
      {"foot": "foot_BR", "start_frame": 1, "end_frame": 12, "type": "planted"}
    ]
  },
  "groom": {
    "target": "hot_groom",
    "effector": "tongue_tip",
    "contact_frames": [8, 9, 10, 18, 19, 20]
  },
  "pet_react": {
    "target": "hot_head",
    "external_effector": "user_hand"
  }
}
```

### 10.4 每猫离线修正流程

1. 实例化身份和风格形态。
2. 适配 Rest Rig。
3. 将共享 Action 复制到该猫实例。
4. 按骨长/体长缩放局部位移曲线。
5. 对 planted 脚相位使用 IK/位置约束固定脚底世界位置。
6. 若腿因短腿无法到达，先调整 root/hips 高度，再修腿部姿态。
7. groom 中将舌尖目标约束到 `hot_groom`，修正头、下颌和舌骨，避免穿过腿。
8. pet_react 中按 `hot_head` 修正压头幅度与外部手锚点。
9. 检查坐姿地面接触、身体自穿插和尾巴穿模。
10. 将修正后的姿态重新 Bake Action，保存到该猫实例。

修正发生在骨骼层，然后统一渲染；禁止事后逐张 sprite 涂抹修脚或舌头。

### 10.5 世界移动与滑步

`walk` 导出时计算一个参考步态速度：

```text
world_speed = 单个步态周期内理论前进距离 / 周期秒数
```

游戏控制器使用这个速度移动； planted 脚在世界空间应基本不动。换体型后重新计算，不能所有猫共用一个移动速度。

---

## 11. Blender 烘焙实施

### 11.1 命令入口

```bash
blender -b art/master_cat/master_cat.blend \
  -P pipeline/bake/bake.py -- \
  --genome cats/cat_demo/identity_v1/genome.json \
  --markings cats/cat_demo/identity_v1/markings.json \
  --texture cats/cat_demo/identity_v1/fur_albedo.png \
  --actions idle,walk,groom,pet_react \
  --out cats/cat_demo/asset_v1/raw
```

`bake.py` 必须先验证 master/uv/rig/animation 版本，再复制母版；禁止保存覆盖源母版。

### 11.2 固定渲染参数

首轮建议，后续写入 `render_spec.json` 并冻结：

```json
{
  "render_spec_version": 1,
  "cell": 192,
  "supersample": 4,
  "directions": 8,
  "camera": {"type": "orthographic", "pitch_deg": 35, "ortho_scale": 0.85},
  "view_transform": "Standard",
  "transparent": true,
  "normal_space": "camera_opengl",
  "downsample": "area",
  "palette_size": 32,
  "dither": "none",
  "outline_px": 1
}
```

192 是画布，不是猫必须高 192 px。猫身大小、尾巴和耳朵要留在统一安全框中。所有猫共用 ortho scale，保留胖瘦和大小差异。

### 11.3 每帧执行顺序

```text
选择 Action 和源帧
→ 应用该帧已修正的骨骼姿态
→ 设置方向 root yaw 或相机 yaw（只能选一种并固定）
→ 设置固定正交相机
→ 渲染 albedo 到 4× 画布
→ 切换 normal override，渲染法线到 4× 画布
→ 投影 hot_*/foot_*/root 到最终像素坐标
→ 写 frame manifest
```

渲染方向建议固定相机、旋转猫 root；这样光照与相机关系稳定。法线 pass 使用同一相机。

### 11.4 Albedo pass

- 所有皮毛/眼睛材质临时替换为 Emission。
- 不烘直接光、投影或自动曝光。
- 默认使用中性反照率 + 法线由 Godot 受光。
- 如需极轻 AO 增加体积感，AO 只作为固定、弱强度乘子，单独版本化，不能再叠一套强主光。

### 11.5 Normal pass

节点逻辑：

```text
Geometry.Normal
→ Vector Transform(WORLD → CAMERA)
→ Vector Multiply(0.5)
→ Vector Add(0.5)
→ Emission
→ Image
```

透明区域 alpha 与 albedo 一致。法线贴图不做 sRGB 转换，不做颜色量化。

### 11.6 锚点投影

使用 `bpy_extras.object_utils.world_to_camera_view`：

```python
from bpy_extras.object_utils import world_to_camera_view

p = world_to_camera_view(scene, camera, obj.matrix_world.translation)
x = p.x * cell_w
y = (1.0 - p.y) * cell_h
```

每帧保存：

- `root/pivot`；
- `hot_head/hot_back/hot_belly`；
- `hot_groom/hot_pet`；
- 四足 `foot_*`；
- 当前世界 yaw 与 `dXXX` 的映射。

---

## 12. 像素化、色板与图集

### 12.1 正确后处理顺序

```text
4× RGBA 渲染
→ Area/Box 降采样到固定单元格
→ 固定 alpha 规则
→ 全动画统一调色板量化 albedo
→ 1 px 描边与受控杂点清理
→ 法线单独平均降采样并重新归一化
→ 打图集
```

最近邻只用于 Godot 最终显示/整数倍放大，不用于高分辨率降采样。

### 12.2 调色板

第一版从 32 色开始，与 24/48 做视觉对照，不预设越少越好。

生成规则：

1. 收集该猫所有动作、所有方向的 albedo 样本。
2. 加入 genome 必须保留的眼睛、五印记和鼻色，防止被 k-means 合并。
3. 在 Lab 空间聚类/映射到统一 palette。
4. 所有帧使用同一 palette 和同一 hash。
5. 默认不抖动；新增动作沿用旧 palette，若改 palette 必须重处理全部旧动作。

动态光照后的最终屏幕颜色不必仍只有 32 色；32 色约束的是 albedo 资产。

### 12.3 Alpha、描边与眼睛

- alpha 阈值先固定 0.5，再检查耳尖和尾巴。
- 描边在最终像素网格上扩 1 px，颜色取邻近最深毛色，不默认纯黑。
- 不用“删除所有单像素”这种粗暴规则，眼睛高光和细尾尖可能是合法单像素；只清理明确噪声。
- 眼睛保留虹膜、瞳孔、高光三个层级，必要像素面积由美术规范锁定。
- 禁止逐帧自动裁剪和自动居中，pivot 固定为 root 地面投影。

### 12.4 法线后处理

对每个低分辨率像素：

1. 读取对应高分辨率块内的有效法线；
2. 解码到 `[-1,1]`；
3. 做向量平均；
4. 重新 `normalize`；
5. 编回 `[0,1]`；
6. 透明区域统一填 `(0.5,0.5,1.0)` 或约定值。

不做 Lab 量化、不做调色板、不做颜色描边。

### 12.5 图集策略

按动作分图集，避免 192 单元格下一张图集过大：

```text
atlas_walk_albedo.png
atlas_walk_normal.png
atlas_groom_albedo.png
atlas_groom_normal.png
...
```

每张最大 4096×4096，超出则分卷。`anim.json` 用图集索引和 cell index 引用，不依赖文件名顺序。

### 12.6 `anim.json` 必要结构

```json
{
  "asset_version": 1,
  "render_spec_version": 1,
  "animation_version": 1,
  "cell": [192, 192],
  "normal_space": "camera_opengl",
  "palette_hash": "sha256:...",
  "world_yaw_offset_deg": 0,
  "anims": {
    "walk": {
      "fps": 10,
      "loop": true,
      "world_speed_mps": 0.32,
      "directions": {
        "d000": {
          "atlas": 0,
          "cells": [0, 1, 2, 3, 4, 5, 6, 7],
          "pivots": [[96, 176]],
          "contacts": [{"cell": 0, "foot": "foot_FL", "type": "planted"}]
        }
      }
    }
  }
}
```

示例中的 `pivots` 如果每帧不同必须每帧记录；不能因为大多数相同就省略规则说明。

---

## 13. Godot 接入的最小技术要求

本文件不展开客户端完整实现，但母版/烘焙必须满足以下接口：

- albedo 使用 `source_color, filter_nearest`；normal 不使用 `source_color`。
- 透明像素 alpha clip；图集边缘留 padding，防止采样串帧。
- Billboard 节点朝向由 GDScript 控制，阴影面片单独处理。
- 方向根据猫的世界朝向与相机 yaw 选择，不用左右镜像代替真实方向。
- 游戏相机俯角必须与烘焙 render spec 一致。
- 法线光照使用中性 albedo，避免与强烘焙光影叠加。
- `walk` 移动速度读取 `world_speed_mps`，交互读取投影后的 `hot_*`。
- 运行时资源按 `asset_version + palette_hash + animation_version` 缓存。

---

## 14. 自动校验与测试

### 14.1 母版校验 `validate_master.py`

每次提交必须检查：

```text
[ ] 必需对象、40 根左右语义骨、骨骼父子关系存在
[ ] `_L/_R` 未互换，root 在地面原点
[ ] 必需 shape key 全部存在且范围合法
[ ] UV layer 存在、uv_hash 与 manifest 一致
[ ] UV 岛无非法重叠，padding 达标，左右身份区不镜像复用
[ ] 顶点权重归一化、单顶点影响数 ≤4、无未绑定顶点
[ ] landmark_vertices 索引有效
[ ] hot_* 和 foot_* 存在
[ ] walk/sit/groom/pet_react 能运行且无严重穿插
[ ] 源母版不含某用户贴图或身份数据
```

### 14.2 身份校验

- 8 方向与照片对照，五印记全部有来源和用户确认。
- UV 覆盖图标明未观测/推定/生成区域。
- 左右不对称印记没有换侧。
- 眼睛与确认色样一致。
- 拟合失败视角明确列出，不能静默忽略。

### 14.3 动画校验

- 同一印记的 UV 坐标在所有帧不变；只检查其投影结果是否合理。
- planted 脚无明显世界滑移。
- groom 舌尖接触目标，不穿腿/头。
- pet 锚点与外部手位置一致。
- 所有状态切换无透明双影、缺帧和卡死。
- 不用左右镜像帧替代真实烘焙。

### 14.4 像素稳定性校验

- 全部帧 cell、pivot 规则、palette hash 相同。
- 固定输入重复烘焙，文件像素哈希一致。
- 无逐帧自动曝光、自动调色板、随机抖动。
- idle 非动画区域不闪；描边宽度不跳。
- 最终在 Godot 实际显示尺寸检查，不只看放大 PNG。

---

## 15. 可直接照做的实施顺序

### 第一步：先做母版，不接 AI

1. 按第 2 节建立坐标与命名。
2. 完成 3000–6000 三角面短毛猫、独立眼睛/舌头。
3. 按第 4 节展开 UV，生成 `uv_layout.png` 和哈希并冻结。
4. 按第 5 节建骨、蒙皮、Identity/Style/Face shape keys。
5. 建 `hot_*`、`foot_*` 和语义顶点表。
6. 做 `idle/walk/sit_down/sit_idle/stand_up/groom/pet_react`。
7. 跑 `validate_master.py`，不通过则停止后续工作。

### 第二步：跑通无身份渲染

1. 使用中性临时贴图。
2. 按 render spec 输出 8 方向 albedo/normal。
3. 统一 192 cell、4× 渲染、Area 降采样、32 色、无抖动。
4. Godot 中验证方向、光照、pivot、walk 速度和交互热区。
5. 确认重复渲染确定、无闪烁后再接照片。

### 第三步：做一只猫的人工辅助身份切片

1. 拍齐规范 8 图。
2. 自动分割/关键点初始化，人工修正。
3. 生成粗 CatGenome；VLM 不直接给连续体型精确值。
4. 共享体形、逐图姿态/相机拟合。
5. 将五印记从照片射线投影到 UV，用户确认。
6. 生成 albedo、coverage 和 8 方向身份审核板。
7. 用户确认后冻结 identity 版本。

### 第四步：风格化与动作修正

1. 应用统一 `sty_*` 参数。
2. 运行 Rest Rig 适配。
3. 重定向共享动作并修正脚底、groom 和 pet 接触。
4. 烘焙三个代表动作：`walk + groom + pet_react`。
5. 在最终游戏尺寸验收身份、五印记、眼睛、滑步和像素稳定性。

### 第五步：再自动化

只有单猫垂直切片通过后，才增加：

- 更自动的体形/相机优化；
- 随意旧照片质量门控和补拍推荐；
- 生成式局部 UV 补全；
- 多猫批处理、FastAPI/Celery/MinIO；
- 更多动作和长毛母版。

---

## 16. 常见故障与排查顺序

| 故障 | 优先检查 | 不要先做什么 |
|---|---|---|
| 正面像、侧面不像 | 视角覆盖、共享形状是否被每图偷偷修改、相机拟合 | 增加随机斑纹 |
| 五印记转身后换侧 | 是否镜像 UV/镜像 sprite、左右映射 | 逐方向补画 |
| 舔毛时印记漂移 | 是否写入固定 UV、蒙皮拉伸、UV 分辨率 | 每帧 AI 修复 |
| 短腿后走路滑步 | Rest Rig 是否适配、planted 接触、world_speed | 只调动画播放速度 |
| 大眼像素化后糊 | cell/眼睛面积、降采样、palette、描边 | 直接叠清晰矢量眼 |
| 动画颜色闪烁 | 每帧 palette 是否不同、随机抖动、自动曝光 | 增加更多颜色 |
| 法线光照方向反 | normal space、相机空间、Non-Color、Godot 转换 | 逐张翻转法线图 |
| 贴图有双重阴影 | 照片光照是否烘入、albedo 是否又含主光 | 再加强游戏灯光 |
| 三花不像 | 是否只用了随机 seed、关键色块是否来自照片 | 扩大通用噪声库 |
| UV 修改后旧 mask 全错 | uv_version/uv_hash 是否被破坏 | 手工移动几张 mask 应付 |

---

## 17. 许可、性能与诚实边界

- 生产母版必须自制、委托或具有明确商业授权；保存来源、许可证和哈希。
- 研究许可模型只允许作方法对照，不把其网格、权重、贴图或骨架混入生产资产。
- 每个 AI 组件分别核查代码、权重、训练数据和输出条款。
- “分钟级”“24GB 同时常驻”“30 秒预览”都须实测后才能写成 SLO。
- 8 图只能恢复可见证据支持的数字分身，不能承诺毫米级三维或未观察区域精确复刻。
- 对随意旧照片，缺少关键视角时正确行为是要求补拍，不是用生成模型掩盖证据不足。

---

## 18. 核心验收门槛

只有以下全部成立，才认为“母版 + CatGenome + 固定 UV + 共享骨骼”链路真正跑通：

1. 同一只猫的 8 方向均能辨认，五印记和眼睛来源清晰。
2. UV 冻结且哈希可校验，左右不对称身份不会镜像错误。
3. 所有动作使用同一身份资产，没有逐帧重新生成。
4. 风格变形后 Rest Rig 和接触点已适配，walk/groom/pet 不穿帮。
5. 颜色、法线、像素网格、palette 和 pivot 在全动画中稳定。
6. 身份、母版、UV、骨骼、动作和资产都有独立版本及重建规则。
7. 最终由用户在 Godot 实际显示尺寸确认“这是同一只猫”，而不是只通过高分辨率 Blender 审核。
