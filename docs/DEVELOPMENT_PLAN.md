# 《喵汪小镇》猫咪数字分身开发计划（防走偏施工路线图）

> **版本**：v1.0（2026-10-28）  
> **基准规范**：
> 1. `docs/FUSED_CAT_DIGITAL_TWIN_AND_V4_1_PIPELINE_SPEC.md`（融合技术架构规范）
> 2. `docs/PHOTO_TO_HD2D_PIXEL_CAT_PLAYBOOK.md`（`Route A v4.1` 实战避坑手册）
> 3. `docs/reference/CAT_DIGITAL_TWIN_ENGINEERING_SPEC.md`（母版/CatGenome/固定UV/共享骨骼规范）

---

## 一、 六条防走偏铁律（任何阶段违反直接内部打回）

1. **视觉锚点铁律**：任何多视角或动作帧的单帧画质，**严禁低于 `Route A v4.1` 静态标杆**（头高占全身 ~42% 微 Q 比例、通透翡翠绿大眼配高光、自然毛流明度比、无灰边白爪、`114×104` 逻辑格级清晰度、`2×2` 整数画布像素块）。
2. **严禁脚本画几何色块铁律**：**绝对禁止**再用 Python/Canvas 画椭圆、圆点、硬边多边形去凑五印记或八字胡；所有毛色与印记必须源自「AI 原生毛流多视角受控投影 + 大半径高斯场顺毛流无边界调制」。
3. **严禁 14 色粗暴迷彩量化铁律**：禁止用低色数 K-Means 把柔和毛流砍成迷彩斑块；采用全动作统一的 36～48 色高保真色板（锁定眼/鼻/五印记必保色，`dither=none`），兼顾柔顺过渡与帧间零闪烁。
4. **UV 冻结与非对称铁律**：母版 `2048×2048` 固定 `4×4` 象限 UV 一旦生成 `uv_hash`，**永远只修贴图、不改 UV**；8 方向（`d000..d315`）全部真三维旋转烘焙，**严禁左右水平翻转代替左/右方向**（防止阴阳嘴套和左肋白云换侧）。
5. **变形必重配骨骼铁律**：每次应用完 `id_*`（真实身份）+ `sty_*`（微 Q 风格）形态键后，**必须运行 `adapt_rest.py` 重算 40 根骨骼关节并重置 Rest Pose + 跑脚底 IK / 舌尖接触修正**，从根源消灭短腿滑步、碎腿与舔空气。
6. **先自审后汇报铁律**：每个阶段完成后，制作人必须先跑自动化校验脚本 + **4x/8x 放大特写自审**并给出明确审核结论；不达标内部重做，达标后才交用户拍板，拍板通过后再进下一阶段。

---

## 二、 标准工程目录结构（杜绝临时脚本乱放）

```text
miaowangtown/
├── docs/                                  # 仅存核心规范与当前标杆验证
│   ├── DEVELOPMENT_PLAN.md                # 本开发计划
│   ├── FUSED_CAT_DIGITAL_TWIN_AND_V4_1_PIPELINE_SPEC.md
│   ├── PHOTO_TO_HD2D_PIXEL_CAT_PLAYBOOK.md
│   ├── reference/CAT_DIGITAL_TWIN_ENGINEERING_SPEC.md
│   └── validation/route_a_v4_1_ultimate/  # v4.1 静态黄金标杆
├── reference/                             # 只读原始输入与参考图
│   ├── miemie_photos/                     # 咩咩 16 张真实生活照
│   ├── town_ref/                          # 小镇参考原图 + 无猫干净底板
│   └── open_cat_bases/                    # CC0 四足站立参考网格
├── art/                                   # 【M1 产出】冻结母版与共享动作源
│   ├── master_cat/                        # master_cat.blend, uv_manifest.json, landmark_vertices.json
│   └── animations/                        # 共享动作源与动作元数据
├── pipeline/                              # 【M1-M3 产出】离线构建与烘焙管线
│   ├── master/                            # build_master.py, validate_master.py
│   ├── rig/                               # adapt_rest.py, contacts.py
│   ├── texture/                           # extract_genome.py, bake_uv_from_views.py
│   └── bake/                              # render_8dir_passes.py, post_v4_1_pixel.py, pack_atlas.py
├── cats/                                  # 【M2-M3 产出】单猫数字分身资产包
│   └── miemie/
│       ├── identity_v1/                   # genome.json, markings.json, fur_albedo.png, identity_review.png
│       └── asset_v1/                      # 8方向 Albedo/Normal 图集 + anim.json
└── prototype/                             # 【M4 产出】HD-2D 小镇实景运行时预览器
```

---

## 三、 四阶段里程碑与逐级验收门禁（Stage Gates）

### 阶段 M1：微 Q 工业母版、固定非对称 UV 与 40 骨自适应底座
- **核心目标**：把「骨骼、网格、UV、形态键」一次性做扎实并锁死哈希，彻底告别临时改模型。
- **具体任务**：
  1. 基于对称四足站立拓扑构建 `art/master_cat/master_cat.blend`，包含独立對象：`CAT_BODY`（流形网格）、`CAT_EYE_L`、`CAT_EYE_R`、`CAT_TONGUE`、`CAT_ARMATURE`（40 骨）及 `hot_*/foot_*` 锚点。
  2. 制作分离的两组 Shape Keys：`id_*`（胖瘦、脸圆、嘴套、耳大小等）与 `sty_*`（锁定对齐 `Route A v4.1` 的微 Q 大头大眼短腿比例）。
  3. 展开 `4×4` 象限 100% 非镜像 UV，导出 `uv_layout.png` 与 `uv_manifest.json`（锁死 `uv_hash`）。
  4. 编写 `landmark_vertices.json` 与 `pipeline/rig/adapt_rest.py`（变形后自动对齐 40 骨关节与四足地面 `Z=0`）。
- **交付物与门禁**：
  - 工程门：`validate_master.py` 10 项全绿（流形、0 非流形边、权重归一化、UV 无越界/无左右重叠、`uv_hash` 锁定、`adapt_rest` 后四足贴地误差 `< 0.5mm`）。
  - 视觉门：导出 **8 方向白模 + UV 棋盘格 + 骨骼锚点叠加检视板**，验证微 Q 轮廓与 `Route A v4.1` 一致、头部与躯干纹素充足无拉伸。
  - **【用户拍板点 1】**：确认母版体态比例与 UV 检视板通过后，冻结 `master_cat`，进入 M2。

---

### 阶段 M2：咩咩 `CatGenome` 提取、固定 UV 毛流烘焙与 8 方向静态审核板
- **核心目标**：不靠画椭圆色块，把 `Route A v4.1` 的细腻毛流与咩咩五印记烘焙进固定 `2048` UV，让 **8 个方向转一圈全都像咩咩**。
- **具体任务**：
  1. 从 `reference/miemie_photos/` 生成 `cats/miemie/identity_v1/genome.json`（Lab 实测色板）与 `markings.json`（五处非对称印记定义与观测来源）。
  2. 从变形后的咩咩微 Q 网格导出 8 方向 Depth/Normal 控制图；以 `Route A v4.1` 为主锚点（`d045`），生成互补视角同画风无阴影毛流图。
  3. 按法线夹角权重 $w_i = \text{visible}_i \times \max(\mathbf{N}\cdot\mathbf{V}_i, 0)^2$ 反投融合进 `2048×2048` 固定 UV，并用顺毛流高斯场精校五印记，输出 `fur_albedo.png` 与 `coverage.png`。
  4. 走 Blender `Albedo + Normal` 通道 + `v4.1` 像素化后处理，输出 **咩咩 8 方向静态像素审核板 `identity_review.png`**（含 `d045` 与 `Route A v4.1` 标杆同框对比、小镇实景合成）。
- **交付物与门禁**：
  - 制作人 4x/8x 放大自审：
    - `d045` 视角与 `Route A v4.1` 标杆同框对比无退步；
    - 8 个方向（正前/右前/正右/右后/正背/左后/正左/左前）五印记严格守恒：**右嘴套焦糖花生斑、左脸奶油白、左肋白云连白围脖与腹缘暖橘过渡、前高后低四白袜、背部虎斑与环纹黑尾尖** 位置准确、绝无换侧或断裂。
  - **【用户拍板点 2】**：用户肉眼验收 8 方向静态咩咩审核板通过后，冻结 `fur_albedo.png`，进入 M3。

---

### 阶段 M3：核心动作库、离线接触修正与 8 方向双通道图集烘焙
- **核心目标**：让锁定外观的咩咩动起来，且动作符合真猫步态、脚不滑步、舔毛不舔空气、像素帧间不闪烁。
- **具体任务**：
  1. 分两批落地共享动作并跑 `contacts.py`（planted 脚底 IK 锁地 + `groom` 舌尖约束至 `hot_groom` + 计算 `world_speed_mps`）：
     - **M3.1（移动与待机核心闭环）**：`idle`（呼吸微动+耳尾轻摆）、`walk`（标准四足猫斜对角步态）、`sit_down` / `sit_idle` / `stand_up`。
     - **M3.2（招牌灵动交互动作）**：`groom`（坐姿抬前爪舔毛，真舌头接触前腕）、`pet_react`（被摸头眯眼蹭手呼噜）。
  2. 运行 `render_8dir_passes.py` + `post_v4_1_pixel.py`，烘焙 8 方向 `atlas_<action>_albedo.png` + `atlas_<action>_normal.png` + `anim.json`。
- **交付物与门禁**：
  - 工程与视觉门：
    - `idle` 站立相邻帧非动作区像素跳变率 `< 0.5%`（毛发斑纹不闪烁）；
    - `walk` 四足落点符合 `foot_*` 接地相位，无第 5 残爪、无劈叉碎腿；
    - 产出动作序列帧全展开检视板 + 4x 放大动图/抽帧对比。
  - **【用户拍板点 3】**：先交 M3.1（`idle + walk + sit`）给用户验收步态与帧间稳定性，通过后再合入 M3.2（`groom + pet_react`）。

---

### 阶段 M4：HD-2D 小镇实景运行时集成（图集播放器 + 2D 法线受光 + 交互）
- **核心目标**：把烘焙好的咩咩资产包放进 `prototype/` 古镇石桥与客栈门前，实现可走、可看、可摸的完整体验。
- **具体任务**：
  1. 在 `prototype/src/` 实现轻量化 `CatSpriteActor`：加载 `anim.json` + `Albedo/Normal` 图集，按 `2×2` 整数像素块对齐渲染。
  2. 接入 2D Camera-Space Normal 实时受光 Shader（响应古镇右上暖黄灯笼光与暮色环境光）+ 脚下椭圆接地软阴影（由 `foot_*` 与 `root` 驱动，消除双重阴影）。
  3. 按 `world_speed_mps` 驱动 8 方向无滑步巡游，支持点击地面引路、点击 `hot_head / hot_back` 触发摸头反馈与蹲坐舔毛。
- **交付物与门禁**：
  - 实景多机位截图（参考图同款石阶机位、石桥中景、4x 特写）+ 可交互 Web 页面推送 GitHub Pages。
  - **【用户拍板点 4】**：用户在浏览器实机体验并验收全闭环。
