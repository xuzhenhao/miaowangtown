# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30 13:27（Asia/Shanghai）· d225 受控重生 1 次 FAIL  
**结论**：仍 **CONDITIONAL HOLD**。**整条源重生停**（禁第二次）。d225 回滚 PASS `f3ec8950…`；fur 保持 baseline `46e56675…`；未 fuse；不冻、不开 M3、不交用户点2。

## 2026-10-30 d225 受控重生（恰好 1 次 · FAIL · 停）

| try | seed_offset | seed | sha | CLIP77 | 门禁 |
|---:|---:|---:|---|---|---|
| 1 | 70011 | 20331396 | `1db95dd9…` | 77 / truncate=False | **FAIL**（头切竖条/层状碎块/断爪/塑料椭圆） |

- 控图未重导出（`bf13e9a` 边距≥16）；control/ip/guidance 保持 PASS 档未升 depth
- 正词禁全局提亮；`omit_view_style_tail` 保 CLIP=77
- 近黑 frac&lt;40 表面↓（11%→0.3%）但几何门禁权威 FAIL → 不 fuse
- 归档：`pre_d225_regen_bf13e9a/` + `failed_d225_regen_try1_70011/`
- 状态文：`hold_diag/D225_REGEN_STATUS.md`
- **未**宣称可冻；**整条源重生停** 等 opus HOLD 选项

## 此前摘要（保留）

# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30 13:19（Asia/Shanghai）· d225 源图暗采样只读归因  
**结论**：仍 **CONDITIONAL HOLD**。ROI 软降权整条已停；fur 保持 baseline `46e56675…`。**主责= d225 源图岛内碎斑/近黑（贡献 abs&lt;40≈34%）**写入 d090 侧躯干相对暗带；非剪影外背景泄漏。未 soft / 未 fuse / 未重生 / 未冻；不交用户点2。

## 2026-10-30 d225 源图暗采样（只读 · 对标 12a1945）

| 向 | 暗带源均亮 | 岛内% | 近缘12px% | 源≤rel% | 贡献源 abs&lt;40 | 判定 |
|---|---:|---:|---:|---:|---:|---|
| **d225** | **80.47** | **96.1** | 3.9 | 49.79 | **34.4%** | 岛内碎斑压黑拉低 |
| d135 | 68.98 | 99.58 | 0.42 | 71.05 | 22.9% | 对照：碎斑型 |
| d180 | 69.54 | 99.25 | 0.75 | 73.97 | 1.0% | 对照：背纹中暗型 |
| d090 | 124.65 | 92.78 | 7.22 | 5.26 | 3.5% | 源偏亮，非主责 |

- 先验 x015「~60%」澄清：是暗带内 abs&lt;40 **样本权重**中 d225 占比（`dark_sample_weight_share`），不是源像素有 60% 近黑；本轮真正 `frac_lt40(d225)=34.4%`，权重侧 `src_lum_lt40=45.53%`。
- soft C 后全 8 向 pull-down d225 升至 22.27% 榜首（基线 15.72%）与本结论一致。
- **候选下一步（仅文字，未执行）**：`controlled_local_ROI_regen_candidate_if_blotchy`——可请示仅侧躯干 ROI 受控重生；**禁**整向假绿、禁程序化填红、**禁提前软降**。d135 两次 FAIL 先例在，须制作人拍板。
- 路径：`docs/validation/m2_2_8dir/hold_diag/source_dark_d225/`（`D225_SOURCE_DARK_ON_D090_TORSO.md` + json + overlays）

## 此前摘要（保留）

# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30 13:14（Asia/Shanghai）· fuse ROI 软降 d135+d180 A/B/C  
**结论**：门槛 **NO**。**整条 ROI 软降权停**；工作 fur 回退 baseline `46e56675…`（CANDIDATE_UNFROZEN）。仍 **CONDITIONAL HOLD**。不冻、不开 M3、不交用户点2。下一结构：**只读查 d225 源**（本轮不软降）。

## 2026-10-30 fuse ROI 软降 d135+d180（A/B/C）— 门槛 NO · 停软降 · 回 baseline

| 档 | d135 | d180 | n_dark d090 | vs基线 | 红 | d225↓ | 4x dark40 | 门槛 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 1.0 | 1.0 | 6283 | — | 29.69% | 15.72% | 3888 | — |
| A | 1.0 | ×0.35 | 6110 | −2.8% | 29.65% | 15.84% | 3824 | NO |
| B | 1.0 | ×0.15 | 6022 | −4.2% | 29.65% | 16.20% | 3824 | NO |
| C | ×0.15 | ×0.15 | 5180 | **−17.6%** | 29.65% | **22.27%** | 3824 | **NO**（UV 过、4x 不过） |

- C 虽 UV `n_dark_inner` ≤ −15%，但 Layer A 4x 屏上 dark40 仅 −1.6%（基线近黑 98.8% 仍近黑）→ 「且」肉眼改善失败。
- C 上 d225 成 pull-down 榜首 → 下一刀只读查 d225 源。
- 详情：`hold_diag/fuse_soft_d135_d180_roi/README.md` + `contrast_report.json`

## 此前摘要（保留）

# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30 13:01（Asia/Shanghai）· d135 受控重生两次 FAIL  
**结论**：仍 **CONDITIONAL HOLD**。**已停等 opus**（不做第三次）。d135 回滚 PASS `acabf10c…`；d180 未动；fur 保持 `46e56675…`；未 fuse；不冻、不开 M3、不交用户点2。


## 2026-10-30 fuse ROI 软降 d135（×0.35 / ×0.15）— 回退 baseline · 仍 HOLD

- 停 d135 源重生后，主路径改 fuse：**仅 ROI 内**软降 d135 写入（d180 锁死；EDGE/graze/全局权重未拧）。
- n_dark_inner：6283 → 6228（×0.35）/ 5969（×0.15，−5%）；d135 pull-down 占比 30→23.7/22.2，但 **d180 仍 ~29% 主导**，假透空未明显减轻。
- **工作树回退** fur `46e56675…`（CANDIDATE_UNFROZEN）。停等 opus；可请示同样软降 d180。
- 次路径：`hold_diag/CONTROL_FRAME_MARGIN_NOTE.md`（d135/d180 顶底贴边=0；未来重渲需 ≥16px）。
- 详情：`hold_diag/fuse_soft_d135_roi/README.md` + `contrast_report.json`

## d135 重生（本轮）

| try | seed_offset | seed | sha | CLIP77 | 门禁 |
|---:|---:|---:|---|---|---|
| 1 | 50011 | 20311360 | `4830e4d7…` | 77 / truncate=False | **FAIL**（浮空碎块/头切/断爪） |
| 2 | 60011 | 20321052 | `f0830671…` | 77 / truncate=False | **FAIL**（浮空白圆/头切/压黑仍重） |

- VIEW_TUNING 已写入（抬近黑→中灰棕 + omit_view_style_tail 保 CLIP≤77）
- 归档：`pre_d135_regen_12a1945/` + `failed_d135_regen_try{1,2}_*`
- 状态文：`hold_diag/D135_REGEN_STATUS.md`
- **未**宣称可冻；**未**开 d180

## 此前摘要（保留）

# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30（Asia/Shanghai）· d135/d180 源图暗采样归因（只读）  
**结论**：仍 **CONDITIONAL HOLD**。graze0.35 已回退。**主责= d135/d180 源图岛内躯干相对过暗**写入 d090 侧躯干相对暗带；非剪影外背景泄漏、近缘带非主导（与 graze 拧不动一致）。未 fuse / 未重生 / 未冻；fur 保持 `46e56675…`；d270 维持回滚 PASS。

## 源图归因（本轮）

| 向 | 暗带源均亮 | 岛内权重% | 近缘12px% | 源≤rel% | 判定 |
|---|---:|---:|---:|---:|---|
| d135 | 68.98 | 99.58 | 0.42 | 71.05 | 岛内过暗拉低 |
| d180 | 69.54 | 99.25 | 0.75 | 73.97 | 岛内过暗拉低 |
| d090 | 124.65 | 92.78 | 7.22 | 5.26 | 源偏亮，非主责 |
| d045 | 61.13 | 83.32 | 16.68 | 80.54 | 对照偏暗但权重较低 |

**制作人候选（未执行）**：可对 d135/d180 提「仅侧躯干 ROI / 调提示提亮 / 换 seed」受控重生方案；**禁止**整向假绿、禁程序化填红。结构结论：停拧 graze/view-weight。  
**路径**：`docs/validation/m2_2_8dir/hold_diag/source_dark_d135_d180/`（`D135_D180_SOURCE_DARK_ON_D090_TORSO.md` + json + overlays）

## 此前摘要（保留）

# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30（Asia/Shanghai）· EDGE/graze 小对照（仅 NDOTV_GRAZE）  
**结论**：仍 **CONDITIONAL HOLD**。对照档 **已回退**。

## graze0.35 对照（本轮）

| 项 | 旧 (工作树已恢复) | 新 (归档对照，已回退) |
|---|---|---|
| `NDOTV_GRAZE` | **0.20** | **0.35** |
| `EDGE_ERODE` | **10**（未动） | **10** |
| view-weight | 全 1.0 | 全 1.0 |
| fur sha | `46e56675…` | `1dc3b5b5…`（候选已存 `hold_diag/edge_graze_035/after/`） |
| coverage 绿+黄 | **70.31%** | **65.47%**（更差） |
| coverage 红 | **29.69%** | **34.53%**（更差） |
| d135 pull-down% | 30.05 | 28.45（Δ−1.60） |
| d180 pull-down% | 30.79 | 30.80（Δ+0.01） |
| d135+d180 | 60.84 | 59.25 |
| n_dark_inner d090 | 6283 | 5534 |
| n_dark_inner d045 | 2738 | 1875 |

**制作人 4x（黑底诚实板）**：d090/d045/d270 假透空**未明显减轻**；颈/躯干近黑碎斑观感仍 HOLD。  
**判定（按纠偏）**：coverage 崩 + pull-down/假透空无实质改善 → **回退该档**；工作树 fur 恢复 `46e56675…`。不升 0.40、本轮不动 EDGE。  
**下一步**：查源图暗采样（尤其 d135/d180），**禁止**自动整向假绿重生；不冻、不开 M3、禁程序化填红、不交用户点2。  
**路径**：`docs/validation/m2_2_8dir/hold_diag/edge_graze_035/`（`contrast_report.json`、`compare_layer_a_d090_d045_d270_4x_black.png`）  
**归档**：`cats/miemie/identity_v1/archive/pre_edge_graze_20261030_124423/`

## 此前摘要（保留）

# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30 · d270 重生回滚 + UV 归因  
**结论**：仍 **CONDITIONAL HOLD**。d270 重生（seed 20302032）制作人 4x **FAIL**，已回滚旧 PASS `98a81074…`。d090 假透空 UV 归因：**邻向 d135/d180 pull-down 主责**（禁盲降 d090）。下一步改 EDGE/graze 小对照。不冻、不开 M3。


## 此前摘要（保留）

# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30（Asia/Shanghai）· 降 d090/d270 权重对照后  
**结论**：**仍 CONDITIONAL HOLD · 禁止交用户冻结拍板**。d090 = **PASS_WITH_HOLD / 合拢否决向**（2D PASS ≠ 合拢过门）。coverage 硬门仍 FAIL。**未冻 fur_albedo、未开 M3、未程序化填红**。

## 状态总表

| 项 | 状态 |
|---|---|
| 互补 2D 门禁 | d000/d135/d180/d225/d270/d315 **PASS**；**d090 = PASS_WITH_HOLD** |
| 旧候选（归档） | `archive/pre_low_d090_weight_20261030_123200/` fur sha `4cfd0663…` |
| 对照新候选 | fur sha `46e56675…`，`CANDIDATE_UNFROZEN_CONTRAST` |
| coverage 绿+黄 | **旧 70.36% → 新 70.32%**（≥92% FAIL） |
| coverage 红盲区 | **旧 29.64% → 新 29.68%**（≤20% FAIL） |
| 假透空（body-only 114×104，lum&lt;40） | d090 **455→457**；d270 **455→455**（几乎无减轻） |
| 合拢板 | **仍 HOLD**（灰底仅减假阳性，不单独清 HOLD） |
| 冻结 / M3 | **否** |

## 对照实验 knobs（非冻结路径）

| knobs | 值 |
|---|---|
| `view_weight` | d090=**0.4**，d270=**0.4**，其余 1.0 |
| `dark_reject_lum`（仅降权向） | **40** |
| 评审 `hide_contralateral_eye` | d090 藏 `CAT_EYE_L`；d270 藏 `CAT_EYE_R` |
| 文档 | `hold_diag/low_d090_weight/contrast_report.json` |

## 源图预检（降权前）

| 向 | 结论 |
|---|---|
| **d090** `complementary_albedos/d090_unlit_albedo.png` | depth-mask 近黑轻微（body lum&lt;25 ≈0.07%，torso dark&lt;40 ≈1.3%，p05≈105）→ **不足以单独解释**合拢假透空；**降权不够根治**，若续 HOLD 需查 fuse 采样/边缘或重生，不宣称对照已治。 |
| **d270** | 躯干更脏（torso dark&lt;40 ≈6.2%，p05≈37）→ **对称降权不够，需重生 d270**。 |

## 对照图路径

- `docs/validation/m2_2_8dir/hold_diag/low_d090_weight/compare_layer_a_d090_d045_d270_black.png`（诚实黑底）
- `docs/validation/m2_2_8dir/hold_diag/low_d090_weight/compare_layer_a_d090_d045_d270_gray.png`（灰底减假阳性）
- `docs/validation/m2_2_8dir/hold_diag/low_d090_weight/compare_d090_d270_4x_black.png`
- `docs/validation/m2_2_8dir/hold_diag/low_d090_weight/before|after/m2_2_d090_layer_a_4x_crop.png`
- body-only 公平计数：`bodyonly_{before,after}_d090_4x.png` + `dark_opaque_bodyonly_report.json`

## scipy / silhouette_holes 诚实句

`hold_diag_report.json` 中 `silhouette_holes_*=-1`：**当时 Blender/诊断 Python 无可用 scipy**（notes 有失败信息）；封闭洞计数用 **numpy/PIL flood-fill fallback**。**不要**事后装 scipy 把 -1 读成「已验证 holes=0」。主结论「clay 实心 / albedo 假透空」以对照图与 alpha 为准。

## 诊断（仍成立）

侧向「透空」= 合拢近黑碎斑在黑底上的假透空 + 眼外凸；clay 实心。coverage 红= midtone seed，补盲靠后。

## 诚实原则（继承）

- 剪影若锁 M1 Alpha：**非新轮廓证据**。
- 眼 4 要素主计 **Layer A**；侧向可藏对侧眼（评审-only）。
- 分区启发式偏软，权威 = **4x 肉眼**。
- M1 `uv_hash` 未变。
- 未见 UV：**仅 genome 底色 seed**，禁止程序化毛流充数冲 92%。

