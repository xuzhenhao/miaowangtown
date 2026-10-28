# 《喵汪小镇》猫咪数字分身开发计划（v1.3 终审定稿版 · 防走偏施工路线图）

> **版本**：v1.3（2026-10-28，已合入全部架构 Review 必改项、前后文口径统一、剪影边界距离测法与 M2.2 候选开源模型许可证清单）  
> **基准规范**：
> 1. `docs/FUSED_CAT_DIGITAL_TWIN_AND_V4_1_PIPELINE_SPEC.md`（融合技术架构规范；**注：该规范 3.3 节旧写法 `sty_head_enlarge = 0.42` 已作废，一律以本计划 v1.3「原生微 Q 静止建模 + `sty_*` 滑杆 `0..1` + 变形后实测头高占比 `40%～43%`」为准**）
> 2. `docs/PHOTO_TO_HD2D_PIXEL_CAT_PLAYBOOK.md`（`Route A v4.1` 实战避坑手册）
> 3. `docs/reference/CAT_DIGITAL_TWIN_ENGINEERING_SPEC.md`（母版/CatGenome/固定UV/共享骨骼规范）

---

## 零、 开工前锁死的 9 条核心修正（彻底扫清 M1 冻错、M2 卡死、M3 误判、M4 光照发脏与贴纸感）

1. **真照片绝不直接反投 UV，且 `d045` 锚点锁定「叠光前」的无光影纯净毛流底图**：
   - 咩咩 16 张生活照只提供 **Lab 实测色板** 与 **五印记语义证据**；真正进入 `bake_uv_from_views.py` 的，只能是从变形后母版导出的已知相机 `Depth/Normal` 控制图所对应的同姿态正交毛流视图。
   - **关键修正（消除二次叠光冲突）**：`docs/validation/route_a_v4_1_ultimate/route_a_v4_1_sprite.png` 已包含第 160 行之后的灯笼暖光与腹底 AO，不能直接当反照率锚点！我们已从 `build_route_a_v4_1.py` 第 160 行叠光之前导出并归档了 **纯净无光影高分毛流锚点 `docs/validation/route_a_v4_1_ultimate/route_a_v4_1_unlit_albedo_anchor_hi.png`**，M2 的 `d045` 反照率投影严格以这张无光影底图为准。
2. **第一只猫（咩咩）基因与五印记人工冻结**：
   - M2 第一步直接人工编写冻结 `markings.json`（按猫自身解剖学左右：焦糖花生斑在 `_R / X>0`，左肋白云在 `_L / X<0`），再用生活照在 Lab 空间（去高低光 5%）实测量色写入 `genome.json`。SAM2/关键点/VLM 留到 M5 第二只猫再接。
3. **脚本禁令精准化（禁硬边涂鸦，允 `v4.1` 保频高斯调制）**：
   - 严禁画硬边椭圆、圆点、多边形色块、死板八字胡；允许 `v4.1` 式大半径高斯场 × 原生毛流明度比调制，且每次调制必须输出 **「调制前 vs 调制后 4x 放大对比图」**。
4. **视觉门禁分级可判定化（全文档统一指向 M2.1 四条可计数硬指标）**：
   - **`d045` 基准方向**：执行 M2.1 的 **四条可计数硬指标**（① 头身主轮廓与 `v4.1` 标杆不透明掩码的边界距离最大偏离 `<= 2` 个逻辑像素；② 五印记位置准确且零换侧；③ 四只白爪零灰边；④ 独立眼睛的上眼睑线、双层翡翠绿虹膜、竖瞳、左上角纯白主高光 4 要素齐全清晰）；
   - **其余 7 个方向（含背面/正侧）**：考核五印记跨视角守恒、零换侧、四腿完整不断裂、白爪零灰边、逻辑网格内绿眼清晰可读；
   - **M3 动作帧**：考核四足步态节奏、脚底零滑步、舌尖真接触、同 UV 非透明像素零闪烁。
5. **光照只加一次（M2 双层审核板：纯 Albedo 板 + 运行时同款灯光合成板）**：
   - `fur_albedo.png` 与 `atlas_<action>_albedo.png` 保持零方向光死阴影的纯净反照率（2048 真彩色）；M2 审核板同时输出 **Layer A（纯反照率像素板）** 与 **Layer B（加运行时同款右上暖灯笼光 + 腹底 AO 的合成板）**，拿 Layer B 对照检验上述四条可计数硬指标。
6. **修正 `coverage.png` 图例与 20% 门禁定义冲突**：
   - 凡是通过 4x 毛流质检的已知相机控制视角（无论来自 `d045` 主锚点还是通过质检的 `d000/d090/d180/d270` 互补受控视角），按法线夹角正面直投（$\mathbf{N}\cdot\mathbf{V}_i \ge 0.5$）记为 **绿色（`direct_controlled`）**，斜向过渡（$0.2 \le \mathbf{N}\cdot\mathbf{V}_i < 0.5$）记为 **黄色（`grazing_interpolated`）**；**红色（`unseen_inpainted`）仅代表没有任何控制视角能直接看到的死角纹素（如下腹底面、腋窝深处、脚掌底面）**。由此「高频身份区绿+黄覆盖率 `>= 92%`」与「红色盲区全 UV 占比 `<= 20%`」完全自洽。
7. **M2 拆为 M2.1 单向打穿与 M2.2 八向合拢（内置候选模型与许可证清单，严禁程序化退回充当默认）**：
   - **M2.1（`d045` 单方向两步对齐与四条可计数门禁验证）**：
     1. **第一步（相机与站姿轮廓对齐 + 边缘安全内缩反投）**：利用 M1 的剪影叠比，将 `d045` 相机的 `ortho_scale`、平移与母版站姿对齐到锚点轮廓；反投时对轮廓边缘对不齐的边界纹素做内缩剥离（不写入 UV，由内部顺毛流外延填充，防止把背景或边缘伪影投进 UV）；
     2. **第二步（四条可计数门禁验收）**：不要求与 2D 锚点逐像素重合，严格按以下 4 条可计数标准验收——**① 头身剪影误差 `<= 2` 个逻辑像素（测法：采用与 `build_route_a_v4_1.py` / `post_v4_1_pixel.py` 相同的硬阈值 `Alpha > 162` 提取两边掩码的头身边界像素（排除半透明边缘干扰），计算双向轮廓最近距离，最大偏离不超过 2 个逻辑像素）；② 五印记位置准确且不换侧；③ 四只白爪零灰边；④ 独立眼睛的深色上眼睑线、双层翡翠绿虹膜、竖瞳与左上角纯白主高光 4 要素齐全清晰（不以眼睛与锚点逐像素相同作为通过条件）**；同时完成色板实验并固化 `render_spec.json`。
   - **M2.2（锁定可商用 Hugging Face 仓库与模型卡许可证 + 互补视角 4x 门禁与 8 方向合拢）**：
     - **已锁定的可商用模型仓库与许可证（已移除含 `FLUX.1-dev` 非商用权重的方案 B）**：
       - 基础模型：`stabilityai/stable-diffusion-xl-base-1.0`（许可证以该仓库模型卡为准：`CreativeML OpenRAIL++-M`，可商用）；
       - 几何控制：`diffusers/controlnet-depth-sdxl-1.0`（模型卡许可证：`CreativeML OpenRAIL++-M`，可商用）与 `xinsir/controlnet-union-sdxl-1.0`（含 Depth/Normal 控制，模型卡许可证：`Apache-2.0`）；
       - 外观锚点控制：`h94/IP-Adapter` 中的 `ip-adapter-plus_sdxl_vit-h.bin`（腾讯官方仓库，模型卡许可证：`Apache-2.0`）；
     - **准入硬规则**：严禁把「切线场 + 采毛簇块 + 高斯场」这类程序化方法当成默认路径；无论哪条路径产出的互补视角图，进入 `bake_uv_from_views.py` 之前都必须先通过同一套 **4x 放大毛流自然度与五印记门禁**，仅几何对齐绝不算通过。
8. **`idle` 防闪烁门禁改为「同 UV 非透明像素对比」+ 色板结论固化至 `render_spec.json`**：
   - **防误伤呼吸移动**：Blender 同步导出每帧像素对应的 **UV 坐标缓冲（UV Pass）**，闪烁率只统计 **相邻两帧均非透明、处于躯干/头部核心毛斑区、且映射回同一 UV 邻域（$|\Delta uv| < 1/1024$）的像素颜色变化率 `< 0.5%`**，正常呼吸平移不算闪烁。
   - **色板结论唯一落点**：`fur_albedo.png` 永远保持 `2048×2048` 真彩色（True-Color sRGB）；M2.1 完成「不量化 vs 36 色 vs 48 色（`dither=none`）」4x 放大对比后，将最终定案的 `quantize_mode`（`none / lut36 / lut48`）及锁定色板哈希正式写入 `art/master_cat/render_spec.json`，M3 的 `post_v4_1_pixel.py` 只读该配置，严禁临时手改。
9. **明确 M4 小镇底板、相机空间与「同景深前景走廊」行走范围 + M5 Godot 路线留白**：
   - **M4 统一采用「`clean_town_bg.png` 高清古镇底板 + 仅限于与 `Route A v4.1` 标杆猫同一景深层的石阶前青石板前景走廊带（Iso-Depth Foreground Corridor）可行走导航多边形 + 锁死 `pitch=35°` 相机空间的 2D 法线受光 `CatSpriteActor`」方案**：不在固定 `114×104` 精灵尺寸下铺设上石桥或跨桥远景导航网格（防止固定大小的猫走到远景桥面变成巨人贴纸），远景纵深移动留待后续单独定义分档整数倍缩放后再开放。
   - **M5 Godot 集成路线不预设锁死**：M4 先在 Web 端验证 2D Camera-Space Normal 受光公式；到 M5 接入 Godot 时，再根据客户端实际场景形态在「2D `CanvasTexture + Light2D`」与「工程规范第 13 节 3D 场景正交相机 `Sprite3D Billboard + Spatial Normal Shader`」之间做专项技术选型。

---

## 一、 标准工程目录结构

```text
miaowangtown/
├── docs/                                  # 核心规范与标杆验证
│   ├── DEVELOPMENT_PLAN.md                # 本开发计划 (v1.3)
│   ├── FUSED_CAT_DIGITAL_TWIN_AND_V4_1_PIPELINE_SPEC.md
│   ├── PHOTO_TO_HD2D_PIXEL_CAT_PLAYBOOK.md
│   ├── reference/CAT_DIGITAL_TWIN_ENGINEERING_SPEC.md
│   └── validation/route_a_v4_1_ultimate/  # v4.1 静态标杆（含叠光前无光影底图 route_a_v4_1_unlit_albedo_anchor_hi.png）
├── reference/                             # 只读原始输入与参考图
│   ├── miemie_photos/                     # 咩咩 16 张真实生活照（仅提色板与印记证据）
│   ├── town_ref/                          # target_redbox_ref.png + clean_town_bg.png 无猫干净底板
│   └── open_cat_bases/                    # 拓扑参考网格
├── art/                                   # 【M1/M3 产出】冻结母版与手 K 共享动作源
│   ├── master_cat/                        # master_cat.blend, master_spec.json, render_spec.json, uv_manifest.json, landmark_vertices.json
│   └── animations/                        # 基于 40 骨母版手 K 的 7 套标准动作源
├── pipeline/                              # 【M1-M3 产出】离线构建与烘焙管线
│   ├── master/                            # build_master.py, validate_master.py
│   ├── rig/                               # adapt_rest.py, retarget_motion.py, contacts.py
│   ├── texture/                           # extract_genome.py, render_control_views.py, bake_uv_from_views.py
│   └── bake/                              # render_8dir_passes.py, post_v4_1_pixel.py, pack_atlas.py
├── cats/                                  # 【M2-M3 产出】单猫数字分身资产包
│   └── miemie/
│       ├── identity_v1/                   # genome.json, markings.json, fur_albedo.png, coverage.png, identity_review.png
│       └── asset_v1/                      # 8方向 Albedo/Normal 图集 + anim.json
└── prototype/                             # 【M4 产出】基于 clean_town_bg 同景深走廊与 2D 法线受光的离线精灵预览器
```

---

## 二、 五阶段里程碑与逐级验收门禁（M1 → M5）

### 阶段 M1：原生微 Q 工业母版、固定非对称 UV（含静态弯腿压力测试）与 40 骨底座
- **具体任务**：
  1. **原生微 Q 静止建模**：直接在 Blender 中按微 Q 黄金静止姿态建立 `art/master_cat/master_cat.blend`（Basis 默认状态下实测头高即占全身高 `40%～43%`），包含独立对象：`CAT_BODY`（3,500～6,000 面流形网格，关节处 2～3 环拓扑）、`CAT_EYE_L`、`CAT_EYE_R`、`CAT_TONGUE`、`CAT_ARMATURE`（40 骨）及 `hot_head/back/belly/groom/pet`、`foot_FL/FR/BL/BR` 空物体锚点。
  2. **分离形态键（滑杆 `0.0..1.0` 代表微调开度）**：
     - `id_*`：`id_body_fat`、`id_belly`、`id_leg_len`、`id_neck_len`、`id_face_round`、`id_muzzle_len`、`id_ear_size`、`id_ear_fold`；
     - `sty_*`：`sty_head_enlarge`、`sty_leg_shorten`、`sty_eye_enlarge`、`sty_face_chibi_cheek`、`sty_paw_round`。
  3. **眼部独立材质隔离**：`CAT_EYE_L/R` 拥有独立 `MAT_EYE_L/R` 与专用 UV，**绝不参与 `CAT_BODY` 毛流反投**，眼色 100% 来自 `CatGenome`。
  4. **固定 `4×4` 象限非对称 UV + 静态弯腿压力摆姿检视（不依赖 M3 动作库）**：
     - 100% 非镜像展开 `CAT_BODY`；在 M1 编写测试摆姿脚本，对 40 骨直接旋转摆出 **「静态蹲坐测试姿（Static Sit Pose）」与「静态大跨步测试姿（Static Wide-Stride Pose）」**（仅用于 M1 压测 UV 接缝与蒙皮权重，不依赖 M3 的手 K 动画序列），检查大腿内侧、腋下、腹底 UV 接缝是否隐藏良好、有无拉伸畸变。
  5. **`landmark_vertices.json` 与 `adapt_rest.py`**：形态键求值后自动对齐 40 根骨骼 `head/tail` 并重置 Rest Pose。
- **M1 验收门禁（12 项完整 `validate_master.py` + `114×104` 像素剪影叠比视觉门）**：
  - **`validate_master.py` 完整覆盖工程规范 14.1 节全部 M1 相关项 + 拓扑贴地项（共 12 项，将「动作可播放」留至 M3 校验）**：
    1. `CAT_BODY / CAT_EYE_L / CAT_EYE_R / CAT_TONGUE` 流形无破洞、0 非流形边；
    2. 法线方向一致朝外（无翻转面）；
    3. 顶点权重全部归一化，且 **单顶点受影响骨骼数 `<= 4`**；
    4. 所有 `id_*` 与 `sty_*` Shape Keys 顶点索引稳定、无 NaN 或自交；
    5. `CAT_BODY` 的 UV 全部在 `[0, 1]` 内，无非预期重叠，**左右部位 UV 岛 100% 独立不共用**；
    6. 实测 `uv_hash` 与 `uv_manifest.json` 完全一致；
    7. 40 根骨骼命名、父子层级与 `master_spec.json` 一致；
    8. **左右骨骼（`_L / _R`）严格按猫解剖学左右（`_L` 在 `X<0`，`_R` 在 `X>0`）分布，未互换**；
    9. **`landmark_vertices.json` 中所有顶点索引在网格范围内有效且变形后坐标对称**；
    10. **`hot_head / hot_back / hot_belly / hot_groom / hot_pet` 与 `foot_FL / foot_FR / foot_BL / foot_BR` 空物体锚点全部存在且绑定关系正确**；
    11. 形态键 + `adapt_rest.py` 后，四足参考点 `foot_FL/FR/BL/BR` 在 `Z=0` 地面误差 `< 0.5mm`；
    12. **源母版文件不含任何具体猫咪的身份贴图或脏数据**。
  - **像素尺寸级视觉门**：
    - 导出 **8 方向白模 + UV 棋盘格 + 两个静态弯腿压力摆姿检视板**；
    - **用临时测试贴图跑 `post_v4_1_pixel.py` 降采样至 `114×104` 逻辑网格，直接叠到 `Route A v4.1` 的 `114×104` 剪影上对比**：验证头身剪影边界距离最大偏离 `<= 2` 个逻辑像素，且大杏仁眼在 `114×104` 逻辑格内的像素颗粒清晰可读。
  - **【用户拍板点 1】**：审阅 M1 检视板（含 `114×104` 像素剪影叠比与静态弯腿 UV 压测）通过后，冻结 `master_cat` 与 `uv_hash`，进入 M2。

---

### 阶段 M2：咩咩人工冻结基因、分步毛流反投（M2.1 单向打穿 → M2.2 八向合拢）与双层审核板
- **具体任务**：
  1. **人工冻结 `markings.json` + Lab 实测量色 `genome.json`**（解剖学 `_R` 右嘴套焦糖花生斑、`_L` 左脸白、白围脖连 `_L` 左肋白云、左腹缘暖橘、前高后低四白袜、背部虎斑与环纹黑尾尖）。
  2. **M2.1：`d045` 单方向两步对齐反投 + 四条可计数门禁 + 色板实验（固化 `render_spec.json`）**：
     - **Step 1（对齐与去边反投）**：基于 M1 剪影叠比校准 `d045` 相机的 `ortho_scale` 与站姿，将 `route_a_v4_1_unlit_albedo_anchor_hi.png` 反投至 `2048` UV，对轮廓边缘未对齐的纹素直接豁免不写入 UV（由内侧毛流平滑外延）；
     - **Step 2（四条可计数门禁校验）**：走通 Blender `Albedo + Normal` 与 `post_v4_1_pixel.py`，输出 `d045` 的 **Layer A（纯 Albedo）** 与 **Layer B（加运行时同款灯笼光 + 腹底 AO 合成图）**；严格按以下 **四条可计数标准** 验收：
       1. **头身剪影误差 `<= 2` 个逻辑像素**：采用与 `build_route_a_v4_1.py` / `post_v4_1_pixel.py` 相同的硬阈值（`Alpha > 162`）提取两边掩码的头身边界像素，计算双向边界最近距离，最大偏离不超过 `2` 个逻辑像素；
       2. **五印记位置准确且零换侧**；
       3. **四只白爪零灰边**；
       4. **独立眼睛 4 要素齐全**：深色上眼睑线、双层翡翠绿虹膜、竖瞳、左上角纯白主高光清晰可读（不以眼睛或边缘与 2D 锚点逐像素完全重合作为条件）；
     - **Step 3（色板实验落点）**：对同一张 `d045` 输出 **「不量化原色版 vs 36 色 `dither=none` vs 48 色 `dither=none`」** 4x 放大对比图，实测选定不产生迷彩断层的模式并固化写入 `art/master_cat/render_spec.json`。
  3. **M2.2：基于已锁定开源模型清单生成互补视角 + 8 方向 `fur_albedo.png` 合拢**：
     - **已锁定的可商用 Hugging Face 仓库与模型卡许可证（已移除含 `FLUX.1-dev` 非商用权重的方案 B）**：
       - `stabilityai/stable-diffusion-xl-base-1.0`（模型卡许可证：`CreativeML OpenRAIL++-M`）；
       - `diffusers/controlnet-depth-sdxl-1.0`（模型卡许可证：`CreativeML OpenRAIL++-M`）+ `xinsir/controlnet-union-sdxl-1.0`（Depth/Normal 控制，模型卡许可证：`Apache-2.0`）；
       - `h94/IP-Adapter`（`ip-adapter-plus_sdxl_vit-h.bin`，腾讯官方仓库，模型卡许可证：`Apache-2.0`，以 `d045` 无光影锚点锁死毛流质感）；
     - 从变形后微 Q 母版导出其余正交方向（`d000 / d090 / d180 / d270 / d135 / d225 / d315`，固定 `pitch=35°`）的精确 `Depth + Normal + 部位语义 Mask` 控制图并固定随机种子；
     - **每一张互补视角图在进入 UV 反投前，必须先单独通过 4x 放大毛流质感与印记位置质检（严禁拿低质程序化色块或未过检的退回图充数）**；
     - 按法线夹角权重融合进 `2048×2048` 固定 UV，做顺毛流保频高斯微调（附调制前后 4x 对比图），输出完整 `fur_albedo.png`、`coverage.png` 与 **双层 8 方向静态审核板 `identity_review.png`**。
- **M2 验收门禁**：
  - **`coverage.png` 门禁（修正后自洽定义）**：通过质检的控制视角直投区（绿，`direct_controlled`）+ 斜向过渡区（黄，`grazing_interpolated`）在高频身份区占比 `>= 92%`；任何控制视角均不可见的死角补全区（红，`unseen_inpainted`，仅限腹底与脚掌底）全 UV 占比 `<= 20%`。
  - **8 方向双层审核板（Layer A 纯反照率 + Layer B 带光合成）**：
    - `d045` Layer B 严格满足 **M2.1 四条可计数门禁**（两边 `Alpha > 162` 硬阈值掩码边界距离最大偏离 `<= 2` 逻辑像素、五印记零换侧、白爪零灰边、独立眼睛 4 要素齐全）；
    - 其余 7 方向（含 `d135/d180/d225` 背面虎斑、后腿虎斑裤衩配短白袜、环纹黑尾尖专项 4x 放大）五印记严格守恒、零换侧、四腿完整、白爪零灰边、绿眼四要素可读。
  - **【用户拍板点 2】**：审阅 M2.1（`d045` + 色板实验）与 M2.2（双层 8 方向审核板 + 调制前后 4x 对比）通过后，冻结 `fur_albedo.png` 与 `render_spec.json` 进 M3。

---

### 阶段 M3：40 骨母版手 K 动作、变形重定向、离线接触修正与双通道图集烘焙
- **具体任务**：
  1. **手 K 源动作 → `adapt_rest.py` → `retarget_motion.py` → `contacts.py`**：
     - 在 `master_cat.blend` 40 骨上直接手 K 7 套标准动作（源 `30 fps`），并把工程规范 14.1 节的「全部动作在母版与变形实例上可正常播放无翻转」纳入 M3 自动化校验；
     - 变形并 `adapt_rest.py` 后，运行 `retarget_motion.py` 按新旧骨长缩放位移曲线、计算 `world_speed_mps`；
     - 运行 `contacts.py`：对 `walk` 的 planted 相位施加脚底 IK 锁死 `Z=0`；对 `groom` 将 `tongue_tip` 约束到前腕 `hot_groom`。
  2. **锁定烘焙规格（只读 `render_spec.json`）**：
     - 固定正交俯角 `pitch_deg = 35.0°`，安全单元格 `cell_w = 192, cell_h = 192`（4× 超采样渲染 `768×768` 后 `Area/Box` 降采样回 `192×192`，使猫体净尺寸对齐 `v4.1` 的 `~114×104` 逻辑网格），唯一对齐锚点 `pivot` 固定为 `root` 地面投影，**严禁逐帧自动裁剪居中**；
     - `post_v4_1_pixel.py` 只读 `render_spec.json` 中在 M2 锁定的色板/采样参数，同步导出 Albedo Pass、Camera-Space Normal Pass、UV Pass（供防闪烁校验）及 `anim.json`。
  3. **分两批交付**：
     - **M3.1**：`idle (8fps, 12帧)`、`walk (12fps, 12帧)`、`sit_down (10fps, 8帧)`、`sit_idle (8fps, 10帧)`、`stand_up (10fps, 8帧)`；
     - **M3.2**：`groom (10fps, 14帧)`、`pet_react (10fps, 10帧)`。
- **M3 验收门禁**：
  - **同 UV 非透明像素防闪烁门禁（不误伤呼吸）**：在 `idle` 与 `sit_idle` 中，仅统计 **相邻两帧均非透明、位于躯干/头部核心毛斑区、且 UV Pass 映射回同一 UV 邻域（$|\Delta uv| < 1/1024$）的像素**，其颜色跳变率必须 `< 0.5%`；
  - **步态与接触门禁**：`walk` 支撑脚地面滑移 `< 1.5 px`、无第 5 残爪、无碎腿；`groom` 接触帧舌尖距前腕 `< 2 px`。
  - **【用户拍板点 3】**：先验收 M3.1（待机/走路/蹲坐），通过后再合入 M3.2（舔毛/摸头）。

---

### 阶段 M4：Web 端古镇底板（同景深前景走廊）+ 2D 相机空间法线受光精灵预览器（`prototype/`）
- **具体任务**：
  1. **统一古镇底板、`pitch=35°` 相机空间与同景深前景走廊导航（全文档统一口径，消除贴纸感）**：
     - 废弃旧的实时 3D 猫像素化管线；M4 预览器直接以已验收的无猫高清古镇底板 `reference/town_ref/clean_town_bg.png` 为场景舞台，舞台光照与相机空间 **严格锁死对应烘焙时的 `pitch_deg = 35.0°`**，运行时绝不旋转相机俯角或偏航角；
     - **可行走范围统一限制在「与 `Route A v4.1` 标杆猫所处石阶前青石板地面同一景深层的前景走廊带（Iso-Depth Foreground Corridor）」**，绝不在固定精灵尺寸下把导航网格铺到远景石桥桥面或台阶高处。
  2. **2D 法线实时受光 + 单一接地软阴影（光照只加一次）**：
     - `CatSpriteActor` 加载 `atlas_<action>_albedo.png` 与 `atlas_<action>_normal.png`，按 **`2×2` 整数画布像素块** 渲染，并用与 M2 Layer B 完全同一套 2D Normal Shader 接入古镇右上暖黄灯笼光与腹底 AO；
     - 脚下仅绘制由 `anim.json` 中 `foot_FL/FR/BL/BR` 与 `root` 驱动的接地椭圆软阴影。
  3. **M4 核心交互闭环**：
     - 在上述同景深前景走廊带内，实现点击地面按 `world_speed_mps` 8 方向无滑步走动、停下转蹲坐/舔毛、点击 `hot_head / hot_back` 触发 `pet_react` 摸头反馈；远景跨桥纵深移动留待后续单独定义分档整数缩放层级后再开放。
- **【用户拍板点 4】**：输出同机位全局/中景/4x 整数放大实景图并推送 GitHub Pages，用户在浏览器实机交互验收。

---

### 阶段 M5（后续独立里程碑）：Godot 客户端技术选型与接入、多猫感知、效用 AI
- 在 M1～M4 完成咩咩数字分身资产包终验后开启：
  1. **M5.1 Godot 客户端渲染接入与选型**：基于 M3 产出的标准图集与 `anim.json`，根据 Godot 客户端实际架构，在「纯 2D `CanvasTexture + Light2D`」与「工程规范第 13 节 3D 场景正交相机 `Sprite3D Billboard + Spatial Normal Shader`」中选定一套落地；
  2. **M5.2 第二只猫与 SAM2/关键点辅助感知**；
  3. **M5.3 效用 AI（Utility AI）自主行为树**。
