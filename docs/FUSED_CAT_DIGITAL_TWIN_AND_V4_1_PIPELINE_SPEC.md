# 《喵汪小镇》猫咪数字分身融合技术架构规范（工业母版管线 × Route A v4.1 外观锚点）

> **版本**：v1.0（2026-10-28）  
> **定位**：将《猫咪数字分身：母版、CatGenome、固定 UV 与共享骨骼技术工程文档》（`docs/reference/CAT_DIGITAL_TWIN_ENGINEERING_SPEC.md`）的工业级底层管线，与已获用户验收通过的《零散真照片 → HD-2D 精致像素猫 实战经验手册》（`docs/PHOTO_TO_HD2D_PIXEL_CAT_PLAYBOOK.md`，`Route A v4.1` 标杆）深度融合的**唯一施工蓝图**。  
> **状态**：架构对齐阶段（待用户审阅确认后再启动代码与 Blender 母版实施）。

---

## 0. 为什么要做「双剑合璧」融合？（解决单一方案的死穴）

在前期探索与实证中，我们验证了两个互补的事实：

1. **纯 2D/单视角 AI 生成（如 `Route A v4.1` 静态单帧）的优势与局限**：
   - **优势**：在不要求用户拍出「8 张标准站姿教材照」的前提下，仅靠日常 3～8 张随手拍杂照 + AI 原生毛流生成 + 掩码外延区域均值采样（`114×104` 逻辑网格、`2×2` 整数像素块），就能做出**一眼认出咩咩、毛流细腻、眼神通透、零脚本涂鸦感**的黄金静态标杆。
   - **局限**：如果每个方向、每一帧动作都让 AI 独立生成，必然出现**五印记在转身/走路时漂移、闪烁、换侧**，无法支撑 8 方向与多动作（`idle / walk / sit / groom / pet_react`）的一致性。

2. **《猫咪数字分身工程文档》（工业母版 + 固定 UV + 共享骨骼离线烘焙）的优势与局限**：
   - **优势**：确立了 **「身份、UV、骨架只生成一次，动作共享且经离线接触修正后统一烘焙 8 方向 Albedo + Normal 图集」** 的工业级铁律——从根源消灭印记漂移、颜色闪烁、短腿滑步、舔毛穿模与双重阴影。
   - **局限**：原文档第 6、9 节假设用户能拍齐「8 个规范槽位（`000_front`..`315_front_left`）的四足对称站立照」并逐图拟合相机反投 UV；但真实养猫场景下（用户实测反馈），**猫咪极难配合拍出教材级 8 方向标准站姿照**。且若在 UV 上用程序脚本硬画几何色块（如我们早期 v1–v3 踩过的坑），烘出来的猫会像塑料涂鸦怪。

### 融合核心公式（一句话总纲）

> **输入端用「日常杂照提取 `CatGenome` + AI 锁 `v4.1` 外观锚点多视角受控重绘投影」替代苛刻的规范 8 图拍摄，一次性烘焙进「冻结哈希的 2048 固定非对称 UV（`fur_albedo.png`）」；驱动与输出端 100% 采用工程文档的「`id_*/sty_*` 分离母版 + `adapt_rest` 骨骼重配 + 脚底/舌头接触修正 + Blender 8 方向 `Albedo + Normal` 4× 超采样 Area 离线烘焙 + `2×2` 整数像素块合成」。**

---

## 1. 总体融合链路与端到端数据流

```text
【输入层：容忍真实养猫拍摄条件的杂照输入】
用户日常随手拍 3～8 张杂照（正脸、侧身、肚皮、俯拍随意，不强求四足标准站姿）
  │
  ├─► 1. 感知与特征提取（Perception & Genome Extraction）
  │     ├─ SAM2 分割 + 部位关键点 + CIE Lab 去高低光 5% 颜色聚类（不用 VLM 口述覆盖实测色）
  │     ├─ 识别五印记语义特征与观测来源（observed / interpolated / generated）
  │     └─ 产出：genome.json（CatGenome 主数据）+ markings.json
  │
  ├─► 2. 母版实例化与微 Q 风格变形（Identity + Style Instantiation）
  │     ├─ 复制冻结母版 art/master_cat/master_cat.blend（严禁改源母版）
  │     ├─ 先套 Identity 形态键（id_body_fat, id_face_round, id_muzzle_len, id_ear_size...）
  │     ├─ 再套 Style 统一微 Q 形态键（sty_head_enlarge, sty_leg_shorten, sty_eye_enlarge, sty_paw_round）
  │     └─ 运行 adapt_rest.py：按 landmark_vertices.json 将 40 根骨骼关节对齐到变形后网格，重放 hot_*/foot_*
  │
  ├─► 3. Route A v4.1 锚点驱动的固定 UV 贴图生成（v4.1-Guided UV Albedo Synthesis）★核心融合点★
  │     ├─ 从已变形的微 Q 母版导出固定正交/透视视角的 Depth + Normal 控制图
  │     ├─ 结合真照与 CatGenome，生成/精修达到 Route A v4.1 标杆品质的毛流参考锚点（零脚本几何椭圆涂鸦！）
  │     ├─ 按法线可见性权重 w_i = visible_i × max(dot(N, V_i), 0)^p × sharpness_i 反投融合至 2048×2048 固定非对称 UV
  │     ├─ 顺毛流无边界柔化校对五印记（阴阳嘴套、胸腹白围脖连左肋白云、腹缘暖橘过渡、前高后低白袜）
  │     └─ 产出：fur_albedo.png（纯 sRGB 反照率，无烘焙死阴影）+ coverage.png + identity_review.png（8 方向确认板）
  │
  ├─► 4. 共享骨骼动作重定向与每猫离线接触修正（Motion Retarget & Contact Fix）
  │     ├─ 导入共享动作库（idle, walk, sit_down, sit_idle, stand_up, groom, pet_react，源 30fps）
  │     ├─ 按骨长/体长缩放位移曲线，计算该猫专属 world_speed_mps（彻底消除短腿滑步）
  │     ├─ 对 walk 的 planted 相位施加脚底 IK 锁死地面；对 groom 将舌尖约束到前腿 hot_groom
  │     └─ 产出：stylized_rigged.blend（动作已 Bake 且无穿模的猫实例）
  │
  └─► 5. Blender 8 方向双通道离线烘焙与 v4.1 级像素化（Offline Bake & Crisp Pixel Pack）
        ├─ 固定正交相机（俯角 pitch 35°），旋转猫 root 遍历 8 方向（d000..d315，严禁左右镜像代替）
        ├─ 4× 超采样渲染双通道：
        │    ├─ Albedo Pass（Emission + Standard 色彩变换，曝光 0，Gamma 1，零直接光死阴影）
        │    └─ Normal Pass（Camera-Space OpenGL 法线，Non-Color，供小镇灯笼光实时受光）
        ├─ 同步投影每帧 root(pivot)、hot_head/back/belly/groom/pet、foot_FL/FR/BL/BR 像素坐标
        ├─ 执行 v4.1 级像素化后处理：
        │    ├─ 掩码外延预滤波 + Area/Box 区域积分降采样至逻辑网格（猫体净尺寸对齐 ~114×104 逻辑格，安全框 Cell 160/192）
        │    ├─ 锁定必保色（翠绿眼三层、粉鼻、五印记色、自然毛流过渡色阶，禁止 14 色粗暴迷彩量化，禁止帧间闪烁）
        │    ├─ 1px 邻近最深毛色外描边（#1b100a）+ 单像素跳采飞点剔除（保留眼高光与胡须）
        │    └─ 法线贴图独立做块内向量平均 + 重新 normalize
        └─ 产出：atlas_<action>_albedo.png + atlas_<action>_normal.png + anim.json（Web/Three.js 与 Godot 通用）
```

---

## 2. 三层架构与核心数据契约（采纳文档第 1、2、7 节并结合 v4.1 标杆）

### 2.1 三层严格解耦

| 层级 | 职责定义 | 决定因素 | 严禁越界红线 |
| :--- | :--- | :--- | :--- |
| **Identity 层（它是谁）** | 真实躯干/头/腿比例、毛色分区、五处非对称印记、眼/鼻/肉垫颜色、照片来源与置信度 | 用户提供的猫咪杂照 + 用户在确认板上的微调 | 严禁把「小镇 Q 版大头短腿」写进 Identity；严禁每帧重跑感知 |
| **Style 层（小镇里长什么样）** | HD-2D 微 Q 比例（头占全身高 ~42%、大杏仁眼、圆润脸颊与短实四肢）、正交俯角、描边、像素网格（`2×2` 画布像素块）、小镇暖光/腹底 AO 规范 | 小镇全局统一美术规范（`render_spec.json`） | 严禁从照片去「识别」Style 参数；所有猫共享同一套 `sty_*` 与渲染规格 |
| **Motion 层（怎么动与互动）** | 40 根共享骨骼语义、7 套基础动作、每猫 `adapt_rest` 后的脚底 IK / 舌尖 `hot_groom` 接触修正、`world_speed_mps` | 共享动作库 + 每猫实例骨骼长度与接触点自适应 | 严禁靠事后逐张涂抹 sprite 修脚或修舌头；严禁用左右水平翻转冒充左/右方向（否则阴阳嘴套与左肋白云会换侧！） |

### 2.2 坐标系、方向与版本号契约（写入 `master_spec.json`）

1. **坐标与左右约定**：
   - Blender 母版空间：`+Z` 向上，地面 `Z=0`，**猫前方 `+Y`**，**猫右方 `+X`**，**猫自身解剖学左侧 `X < 0`（后缀 `_L`）**。
   - **铁律**：`_L / _R` 永远以**猫自身解剖学左右**为准，绝不以屏幕画面左右为准！（例如咩咩的焦糖花生斑在**猫右嘴套 `_R` / `X>0`**，正面看时位于**画面左侧**；左肋白云在**猫左躯干 `_L` / `X<0`**，正面/左前看时位于**画面右侧**）。
2. **8 方向定义（相机看猫的方向）**：
   - `d000`（正前）、`d045`（右前，即 `Route A v4.1` 标杆对应的左朝向 3/4 视角）、`d090`（正右）、`d135`（右后）、`d180`（正背）、`d225`（左后）、`d270`（正左）、`d315`（左前）。
   - 烘焙时**固定相机与弱 AO 环境，旋转猫 `root` 骨骼**，确保所有方向的相机俯角（`pitch_deg = 35°`）与透视关系恒定。
3. **八大独立版本号（破坏性变更自动拦截）**：
   - `schema_version`、`master_mesh_version`、`uv_version`（配合 `uv_hash` SHA-256 强制校验）、`rig_version`、`animation_version`、`render_spec_version`、`identity_version`、`asset_version`。
   - **UV 冻结铁律**：**母版 UV 一旦展开并生成 `uv_hash`，严禁为了修某张贴图而顺手移动 UV 顶点！修贴图，不修 UV。**

---

## 3. 猫母版（Master Cat）与固定 UV 施工规范（采纳文档第 3、4、5 节）

### 3.1 Blender 母版对象与独立部件（解决「大眼缩像素变糊」与「舔毛穿模」）

在 `art/master_cat/master_cat.blend` 中，严禁把眼睛、舌头和身体合成一个粗糙低模：

```text
CAT_BODY          连通流形短毛猫网格（3,500～6,000 三角面，肩/肘/腕/髋/膝/踝具备 2～3 环变形拓扑）
CAT_EYE_L         独立左眼球网格（含深色上眼睑缘、通透虹膜区、竖瞳、高光层，独立材质 MAT_EYE_L）
CAT_EYE_R         独立右眼球网格（独立材质 MAT_EYE_R，不与皮毛抢低分 UV）
CAT_TONGUE        独立舌头网格（平时收于下颌内，groom 动作时伸出并约束至 hot_groom）
CAT_ARMATURE      约 40 根标准四足骨骼（root → hips → spine_01..04 → neck_01..02 → head/jaw/eye/ear，四肢各 4 节，tail_01..08）
hot_head / hot_back / hot_belly / hot_groom / hot_pet   交互与接触空物体锚点
foot_FL / foot_FR / foot_BL / foot_BR                   四足地面接触参考点
```

### 3.2 固定 `4×4` 象限非对称 UV 布局（工作 `2048×2048` / 交付 `1024×1024`）

- **100% 非镜像独立展开**：左脸与右脸、左躯干（`B1`）与右躯干（`B2`）、四条腿（`C1..C4`）各自拥有独立 UV 岛，岛间至少 `16 px`（2048 图）/ `8 px`（1024 图）padding。
- **高频身份区加密分配**：头部正面/口鼻（`A1/A3`，承载阴阳嘴套与额头 M 纹）、左右躯干与腹部（`B1/B2/B4`，承载胸前白围脖、左肋白云与腹缘暖橘斑）分配充足纹素面积，且额头 M 纹与鼻梁嘴套**不跨 UV 接缝**。
- 生成 `uv_layout.png` 与 `uv_manifest.json`（含 `uv_hash`），每次 CI 与烘焙脚本启动时自动校验哈希。

### 3.3 Identity 与 Style 形态键分离 + `adapt_rest.py` 骨骼自适应

1. **Identity 形态键（`id_*`，由猫自身特征决定）**：
   - `id_body_fat`、`id_belly`、`id_leg_len`、`id_neck_len`、`id_face_round`、`id_muzzle_len`、`id_ear_size`、`id_ear_fold`。
2. **Style 形态键（`sty_*`，锁定为 `Route A v4.1` 验证通过的微 Q 黄金比例）**：
   - `sty_head_enlarge = 0.42`（放大头身比至头高占全身 ~42%，保住像素化后的五官可读性）
   - `sty_eye_enlarge = 0.45`（大杏仁眼窝，容纳高光与通透翡翠绿虹膜）
   - `sty_face_chibi_cheek = 0.35`（饱满圆润脸颊）
   - `sty_leg_shorten = 0.25`、`sty_paw_round = 0.30`（圆润白袜猫爪）
3. **`adapt_rest.py`（形态键求值后重配骨骼 Rest Pose）**：
   - 读取 `landmark_vertices.json` 中肩、肘、腕、爪、髋、膝、踝、头、下巴、尾根的变形后 3D 坐标，在 Edit Mode 下自动对齐 40 根骨骼的 `head/tail` 并重置 Rest Pose，确保四足严丝合缝落在 `Z=0` 地面，从根源杜绝「改完微 Q 比例后走路碎腿、坐姿悬空」。

---

## 4. 核心融合模块：从日常杂照到固定 UV（`v4.1` 外观锚点 × 多视角法线加权烘焙）

这是将文档第 9 节改造为适应「真实养猫无法拍规范 8 图」的关键模块（位于 `pipeline/texture/`）：

### 4.1 第一步：从杂照提取 `CatGenome` 与五印记定义（`genome.json` + `markings.json`）
- 对用户上传的日常杂照（如 `reference/miemie_photos/` 中的 8 张生活照），运行分割与 Lab 色彩提取（剔除最亮/最暗 5% 像素），提取真实毛色色板：
  - 暖金棕底毛、深黑褐鲭鱼虎斑、奶油白胸腹毛、右嘴套暖焦糖斑、腹缘微暖橘过渡毛、翠绿虹膜（Lab 与 sRGB 双存）、砖红粉鼻。
- 将咩咩的 **5 处核心非对称印记** 结构化写入 `markings.json`（绑定到固定 UV 语义区）：
  1. `mark_01_muzzle_peanut`（`head_muzzle`：猫右侧 `_R` 暖焦糖饱满花生斑 vs 猫左侧 `_L` 奶油白脸颊，`source_type: observed`）
  2. `mark_02_chest_bib_and_left_cloud`（`torso_front` + `torso_L`：雪白胸围脖向下连腹，并在左肋腹 `_L` 向上柔和漫延出白云斑托起虎斑，`source_type: observed`）
  3. `mark_03_belly_orange_transition`（`torso_L_belly_edge`：左肋白云斑与深棕虎斑交界处的暖杏橘毛根过渡，`source_type: observed`）
  4. `mark_04_asymmetric_white_socks`（`leg_FL/FR/BL/BR`：前腿过腕高白袜 + 右前腕内侧小焦糖斑，后腿脚踝短白袜配大腿深棕虎斑花裤衩，`source_type: observed`）
  5. `mark_05_tabby_stripes_and_ringed_tail`（`torso_back` + `tail`：额头 M 纹、背部鲭鱼竖纹、尾巴深浅棕交替环纹与黑尾尖，`source_type: observed`）

### 4.2 第二步：基于微 Q 母版多视角控制图 + `Route A v4.1` 锚点反投烘焙 `fur_albedo.png`
为了既拥有 **`Route A v4.1` 的 AI 原生细腻绒毛笔触（彻底摒弃早期脚本画椭圆色块的塑料感）**，又拥有 **360° 固定 UV 的全视角一致性**：

1. **多视角控制图导出**：从已应用 `id_* + sty_*` 的微 Q 猫母版导出 4～8 个正交主视角（正前 `d000`、右前 `d045`、左前 `d315`、正左 `d270`、正右 `d090`、正背 `d180`）的精确深度图（Depth）与法线图（Normal）。
2. **外观锚点受控生成与投影**：
   - 以已验收通过的 `Route A v4.1` 高清毛流底图作为主锚点（对应 `d045`），结合 `CatGenome` 色板与真照五印记约束，生成其余互补视角的同画风无光影毛流图（去除了强方向光，仅保留原生毛簇高频纹理与色彩过渡）。
   - 采用文档 9.3 节的 **法线夹角与清晰度加权融合公式**，将多视角毛流反投烘焙到 `2048×2048` 固定 UV 上：
     $$w_i(u,v) = \text{visible}_i(u,v) \times \max(\mathbf{N}(u,v) \cdot \mathbf{V}_i, 0)^2 \times \text{sharpness}_i \times \text{confidence}_i$$
     $$C_{\text{uv}}(u,v) = \frac{\sum_i w_i(u,v) C_i(u,v)}{\sum_i w_i(u,v)}$$
3. **UV 空间顺毛流五印记精校（继承 `v4.1` 铁律）**：
   - 在 `2048×2048` UV 空间对照 `markings.json` 校验五印记落位；任何微调均采用 `v4.1` 验证成功的 **大半径无边界高斯场 × 原生毛流明度比（Frequency-Preserving Fur Modulation）**，**严禁在 UV 上画任何硬边几何圆点或色块**。
   - 同步生成 `coverage.png`（标明照片直测区 vs 延伸补全区）与 **8 方向静态身份确认板 `identity_review.png`**。

---

## 5. Blender 离线双通道烘焙与 `v4.1` 级像素化管线（采纳文档第 10、11、12 节 + `v4.1` 采样铁律）

### 5.1 动作库与每猫接触修正（`pipeline/rig/contacts.py`）
第一版支持 7 个标准动作：`idle`、`walk`、`sit_down`、`sit_idle`、`stand_up`、`groom`、`pet_react`。
- **防滑步**：`walk` 为原地循环，烘焙时自动测量 planted 脚在支撑相位的后移距离，写出该猫专属 `world_speed_mps`，小镇控制器严格按此速度推进坐标。
- **防悬空与穿模**：planted 相位启用脚底 IK 锁在 `Z=0`；`groom` 动作在接触帧将 `tongue_tip` 约束到前腿 `hot_groom` 空物体，确保真能舔到毛而非舔空气。

### 5.2 离线双通道渲染（Albedo Pass + Camera-Space Normal Pass）
- **Albedo Pass**：将 `MAT_FUR`、`MAT_EYE_L/R`、`MAT_NOSE` 切换为 `Emission`，Blender 色彩管理设为 `Standard / Look=None / Exposure=0 / Gamma=1`，以 `4×` 超采样渲染纯净本色（零烘焙死阴影，仅可叠加极弱的固定腹底/腿内侧 Soft AO 乘子）。
- **Normal Pass**：使用同一正交相机渲染 `camera_opengl` 空间法线（`+X` 右、`+Y` 上、`+Z` 朝镜头，`rgb = normal * 0.5 + 0.5`，`Non-Color`）。
- **锚点投影**：每帧用 `world_to_camera_view` 导出 `root (pivot)`、`hot_head/back/belly/groom/pet`、`foot_FL/FR/BL/BR` 在单元格内的精确像素坐标，写入 `anim.json`。

### 5.3 `Route A v4.1` 级像素化后处理（`pipeline/bake/post.py`）
将文档 12.1 节与我们在 `v4 → v4.1` 实测跑通的去糊去杂点管线合二为一：

1. **掩码外延预滤波 + `Area/Box` 降采样**：
   - 在 `4×` 高分渲染图上，先将猫体内部 RGB 向 Alpha 边界外延展填充 12～16px（彻底防止降采样时把透明背景的黑/灰底色吸进白爪边缘，根治白爪灰刺！）。
   - 用 `Area / Box` 区域积分均值降采样到固定逻辑网格（使猫在小镇标准视野下的净体高对齐 `v4.1` 的 **`~114×104` 逻辑网格**，统一放在固定安全单元格 `Cell` 中，且 **固定 `root` 地面投影为唯一 `pivot`，严禁逐帧自动裁剪居中**）。
2. **眼部高光保锐与单像素跳采飞点剔除**：
   - `CAT_EYE_L/R` 的深棕上眼睑线、深翠/亮翠双层虹膜、竖瞳与左上角纯白主高光在逻辑网格上强制保锐（不被均值模糊吃掉）。
   - 仅滤除猫体内部与 4 邻域明度差 `>20` 的孤立单像素跳采噪点，保留合法单像素（眼高光、细胡须）。
3. **全动画统一色板锁死（防闪烁）与禁用 14 色迷彩**：
   - 收集该猫全部动作、全部 8 方向的 Albedo 样本 + 强制锁死 `CatGenome` 必保色（眼、鼻、五印记色），在 CIE Lab 空间构建高保真统一色板（如 32～48 色，保留 `v4.1` 的柔顺毛流层次，绝不压成 14 色生硬迷彩，且全动画共用同一个 `palette_hash`、零抖动 `dither=none`，确保 `idle` 站立时毛发颗粒纹丝不动、零闪烁）。
4. **1px 邻近深色描边与 `2×2` 整数像素块显示**：
   - 在逻辑网格外扩 `1px` 实心外描边（取 `#1b100a` 深黑褐或邻近最深毛色）。
   - 引擎显示时严格使用 `filter_nearest` 按 **`2×2` 整数画布像素块** 放大，并结合 `atlas_<action>_normal.png` 接入小镇右上暖灯笼光源与脚下四足接地椭圆阴影。

---

## 6. 分阶段落地执行计划（对标文档第 15 节，循序渐进、每步可验收）

为了杜绝「一口气写完大管线却发现画面回退」，我们严格按以下 **4 个里程碑（Milestone）** 推进，每个阶段都由制作人先做 4x 放大特写与 checklist 自审：

### Milestone 1：冻结微 Q 工业母版与固定 UV（`art/master_cat/`）
- 在 Blender 中建立符合第 3、4、5 节规范的 `master_cat.blend`：
  - `CAT_BODY` + 独立 `CAT_EYE_L/R` + `CAT_TONGUE`；
  - 40 根语义骨骼 + `landmark_vertices.json` + `hot_* / foot_*`；
  - `id_*`（身份）与 `sty_*`（锁死 `v4.1` 微 Q 头身比）两套 Shape Keys + `adapt_rest.py`；
  - 展开 `4×4` 象限非对称 `2048` UV，导出 `uv_layout.png` 与 `uv_manifest.json`（冻结 `uv_hash`）；
  - 编写并跑通 `validate_master.py` 十项自动化检查。

### Milestone 2：咩咩身份切片与 8 方向静态审核板（`cats/miemie/identity_v1/`）
- 从 `reference/miemie_photos/` 生成 `genome.json` 与 `markings.json`；
- 以 `Route A v4.1` 为外观锚点，将多视角受控毛流与五印记反投融合进 `2048` 固定 UV，产出 `fur_albedo.png` 与 `coverage.png`；
- 用 Blender 离线烘焙出咩咩的 **8 方向 `v4.1` 级像素静态审核板 `identity_review.png`**（含 `d045` 与 `Route A v4.1` 标杆同屏直比，以及正前、正侧、正背等 8 个方向全貌），交用户肉眼确认「每个方向都像咩咩、五印记无换侧、画质不输 v4.1」。

### Milestone 3：动作接触修正与双通道图集烘焙（`cats/miemie/asset_v1/`）
- 制作并重定向共享动作（优先跑通核心闭环：`idle`、`walk`、`sit_down / sit_idle`、`groom`、`pet_react`）；
- 执行 `contacts.py` 修正 planted 脚底 IK 与 `groom` 舌尖接触，计算 `world_speed_mps`；
- 离线烘焙 8 方向 `atlas_<action>_albedo.png` + `atlas_<action>_normal.png` + `anim.json`，通过像素稳定性校验（帧间不闪、描边不跳、五印记不漂移）。

### Milestone 4：接入小镇实景运行时（8 方向行走 + 法线受光 + 互动）
- 将烘焙好的咩咩资产包接入小镇场景，用 `normal` 图集实时响应小镇暖灯笼光与地面阴影，按 `world_speed_mps` 驱动无滑步巡游与玩家靠近互动（蹲坐、舔毛、摸头反应）。
