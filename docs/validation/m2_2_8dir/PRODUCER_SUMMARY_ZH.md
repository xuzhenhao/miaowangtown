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
