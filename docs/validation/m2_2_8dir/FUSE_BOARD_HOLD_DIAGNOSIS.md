# M2.2 合拢板 HOLD 诊断（先证据、未改 fur_albedo、未重 fuse）

**时间**：2026-10-30（Asia/Shanghai）  
**范围**：制作人合拢板 CONDITIONAL HOLD（d090/d270 躯干透空、眼珠游离、颈拉长；coverage 70.35%/红 29.65% FAIL）  
**约束**：只诊断；**未**改 `fur_albedo`；**未**完整重跑 fuse；**未**冻结。  
**d090 语义更正**：互补 2D 门禁为 **PASS_WITH_HOLD / 合拢否决向**（2D 毛流 PASS ≠ 合拢重投影可冻）。

证据目录：`docs/validation/m2_2_8dir/hold_diag/`  
机器报告：`hold_diag/hold_diag_report.json`

---

## 根因一句话

**侧向「透空」主因是合拢 albedo 在黑底上的不透明近黑/碎斑 texel 造成的假透空（clay 同机位实心、alpha 岛内几乎全不透明），叠加 d090 独立眼网格外凸；不是破洞网格、不是非 Basis 动画、也不是 fur alpha 透明洞。coverage 红盲区是并行硬门，补盲排在侧向假透空处理之后。**

---

## 诊断顺序与分类

### a) 同机位 clay vs 合拢重投影（d090）

| 项 | 结果 |
|---|---|
| 投影 | 与 `run_m2_2_review.render_hi` 相同：自定义正交尺度 `S_LOG=0.0040`、`ORIG_LOG=(52.7,94.0)`、俯角 35°、SS=4 再 downsample；**无传统 FOV/近裁**；**开背面剔除**（`N·W < 0` skip）；**无 MSAA** |
| d045 vs d090 相机 | **仅 yaw 不同**（-45° vs -90°），其余参数一致 |
| Alpha | 光栅对 body 用三角形覆盖写二值 alpha；**未**用贴图 alpha 决定遮挡 |
| 封闭剪影洞（flood-fill） | clay **0** / albedo **0** |
| clay↔albedo alpha XOR | **0**（遮罩完全一致） |
| clay 躯干 | **实心米色填充**，无蛀洞式透空 |
| albedo 躯干 | 黑底上可见碎斑/近黑不透明像素 → **观感透空**（d090 `dark_opaque lum<40` = 18；d045 = 0） |

**分类**：**否 → 贴图/采样观感（非网格破洞、非非 Basis）**。  
更细：不是 `fur_albedo` **alpha 洞**，而是 **RGB 近黑/碎噪 + 黑画布** 被读成透空。

对照图：

- `hold_diag/d090_clay_vs_albedo_4x.png`
- `hold_diag/d090_clay_4x.png` / `d090_albedo_4x.png` / `d090_clay_noeye_4x.png`
- `hold_diag/d090_classify_clay_alb_darkcyan_4x.png`（右栏青=近黑不透明）
- `hold_diag/d045_clay_vs_albedo_4x.png`（对照：三向更干净）

### b) `fur_albedo` alpha × coverage 红区

| 项 | 结果 |
|---|---|
| `fur_albedo` 尺寸 | 2048² RGBA |
| alpha 取值 | 仅 `{0,255}`；岛内 `alpha==0` **1** texel（可忽略） |
| coverage | 绿 612562 / 黄 93944 / 红 297565 → 绿+黄 **70.36%**、红 **29.64%**（门 ≥92% / ≤20% → FAIL） |
| 红区内 alpha | **全不透明**；均值 RGB ≈ `(121,104,82)` → **灰棕 midtone seed**，不是透明洞、不是纯黑洞 |
| 红∩alpha 洞重叠率 | **≈0** |
| d090 正面三角重心采样红占比 | **3.3%**（侧向假透空不是「整侧都在红盲区」） |

**分类**：**红区 = 未看见的不透明 seed 底**；与侧向假透空机制分离。  
图：`hold_diag/coverage_512.png`、`hold_diag/coverage_red_overlay_512.png`

### c) 眼网格 / 游离

| 项 | 结果 |
|---|---|
| 对象 | 独立网格 `CAT_EYE_L` / `CAT_EYE_R`（各 110 v），Armature 修改器，`parent_bone` 空 |
| 材质 | `MAT_EYE_*`，`blend=HASHED`，**无 Emission 节点** |
| 评审绘制 | `run_m2_2_review.py` 在 body 之后对眼做 **参数化 UV 上色**（绿虹膜/瞳孔/高光），不是发光球材质叠层 |
| 姿态 | 骨架 **0** 非 rest 骨；无 action；frame 1；shape key 全 0（含 `id_neck_len`） |
| d045 眼像素落在 body 外 | **0** |
| d090 眼像素落在 body 外 | **99**；到 body 最短距 mean **3.11** px / max **5.83** px |

**分类**：**侧向独立眼球外凸 + 参数化高对比上色 → 游离观感**；**不是**未绑骨动画跑飞，也**不是** Emission 错材。

图：`hold_diag/d090_clay_4x.png`（双眼悬于头前）vs `d090_clay_noeye_4x.png`。

### d) 颈拉长

| 项 | 结果 |
|---|---|
| clay 是否同样拉长 | **是**（同机位） |
| 是否弯腿/动画帧 | **否**（pure Basis rest，见上） |
| 相机 | 侧向 + 35° 俯角正交尺度，微 Q 剪影在 profile 易被读成「颈长」 |

**分类**：**投影读感 / 静模侧视比例**，不是错误动作帧。不优先当 fuse bug 修。

---

## 渲染脚本要点（清单 1）

来源：`pipeline/bake/run_m2_2_review.py`

1. **Alpha**：有（三角形覆盖二值）；贴图 alpha 不参与 body 遮挡。  
2. **背面剔除**：有。  
3. **MSA**：无；SS=4 最近点 downsample。  
4. **眼**：独立网格 + 参数色，非 Emission。  
5. **d045 vs d090**：同 FOV/近裁（本管线无此二者）；仅 yaw。

---

## 建议修复顺序（仍不冻；coverage 补盲靠后）

1. **先消侧向假透空（合拢否决向）**  
   - 查 `fuse_8dir_albedo.py` 对 d090/d270 的 `N·V` / `EDGE_ERODE` 是否把碎斑/过暗 texel 打进侧视可见绿黄区。  
   - **仅作对照**时可降 d090（及对称 d270）权重再 fuse；**保留**已归档候选 `archive/pre_fuse_m21_d045_*` 与当前 candidate sha，**不删**。  
   - 评审板可用非纯黑底或标记近黑不透明，避免假阳性「透空」。

2. **眼游离**  
   - 评审光栅：侧向隐藏对侧眼，或更严的头遮挡/内嵌 socket。  
   - 静模：确认 rest 下眼球不穿出头轮廓（属小几何/绑定检查，非重 fuse）。

3. **颈**  
   - 不改姿态；侧向假透空与眼修好后再肉眼看是否仍不可接受。

4. **最后才 coverage 补盲**  
   - 红 29.65% midtone seed → 向绿+黄 ≥92%、红 ≤20% 补；**排在侧向不「透空」之后**。  
   - 未过硬门前不交冻结拍板；**不开 M3**。

---

## 明确未做

- 未修改 `cats/miemie/identity_v1/fur_albedo.png`  
- 未完整重跑 fuse  
- 未冻结、未开 M3

## 诚实注记（opus 纠偏）
- `hold_diag_report.json` 中若 `silhouette_holes_*=-1`：表示当时环境 **无 scipy**，未跑 scipy 连通域；封闭洞计数改用 **纯 numpy/PIL flood-fill fallback**（或跳过），**不得**解读为 scipy 已验证 holes=0。
- 主结论「clay 实心 / albedo 假透空」仍以 clay-vs-albedo 目视对照图与 alpha 直方图为准。
