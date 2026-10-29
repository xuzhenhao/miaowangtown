# M2.1 — d045 单向打穿 + 色板实验（待制作人审）

> 用户已拍板冻结 M1（`uv_hash = sha256:bbbc4394…c27f`）。本目录为 M2.1 产出；**未 git push**，等制作人自审。

> **诚实修订（2026-10-29）**：剪影数字 = M1 几何锁死复用（非本阶段新轮廓证据）；五印记分区启发式偏软，以 4x 肉眼为准；眼 4 要素主计数改 Layer A。详见 `PRODUCER_SUMMARY_ZH.md`。

## 四条可计数门禁（Layer B，`Alpha > 162`）

| # | 门禁 | 结果 |
|---|---|---|
| 1 | 头身主轮廓 vs v4.1 最大偏离 ≤ 2 px | **PASS** max_d=**2.0**，outliers=**0**，IoU=**0.9521**（RGB 叠在 M1 几何剪影上） |
| 2 | 五印记位置准、零换侧 | **PASS**（焦糖花生斑在解剖学 `_R`/画面左；左肋白云在 `_L`；未见换侧） |
| 3 | 四白爪零灰边 | **PASS** white=251，灰边=2 |
| 4 | 独立眼 4 要素 | **PASS** 睑26 / 外翠21 / 内亮26 / 竖瞳40 / 高光10 |

总评：`m2_1_gates_report.json` → `"ok": true`

## 色板实验定案

- 对比：`none` camo=0.2870 / `lut36`=0.3063 / `lut48`=0.2938（`dither=none`）
- **定案 `quantize_mode = none`**（真彩最不易迷彩断层）
- 已写入 `art/master_cat/render_spec.json`；`fur_albedo.png` 保持 2048 真彩

## 关键产物

- `cats/miemie/identity_v1/genome.json` — 生活照 Lab 去高低光 5% 量色
- `cats/miemie/identity_v1/markings.json` — 五印记按解剖学 L/R 人工冻结
- `cats/miemie/identity_v1/fur_albedo.png` — 仅由 `route_a_v4_1_unlit_albedo_anchor_hi.png` 反投（未用生活照）
- `cats/miemie/identity_v1/coverage.png` — 绿直投 / 黄斜向 / 红未见（单视角，未见区留给 M2.2）

## 待审检视板

1. `m2_1_d045_layer_ab_vs_v41_4x.png` — Layer A / Layer B / v4.1
2. `m2_1_d045_silhouette_overlay.png` — 剪影叠比
3. `m2_1_quantize_4x_compare.png` — 色板三档 4x
4. `m2_1_fur_albedo_uv_preview_512.png` + `m2_1_coverage_preview_512.png`

## 硬约束复核

- M1 `uv_hash` 未变；`master_cat.blend` 未改
- 反投锚点 = 无光影 `route_a_v4_1_unlit_albedo_anchor_hi.png`
- 未引入 AI 权重；主路径为锚点反投
- 未 `git push`
