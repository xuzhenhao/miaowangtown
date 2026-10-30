# fuse ROI 软降 d135 对照（×0.35 / ×0.15）

**时间**：2026-10-30（Asia/Shanghai）  
**tip 起点**：`5d2e618` / 归因 `12a1945`  
**结论**：**仍 HOLD**。两档暗带未明显收缩 → **回退 baseline** fur `46e56675…`（CANDIDATE_UNFROZEN）。**停等 opus**（可请示是否同样 ROI 软降 d180）。

## 范围锁

| 项 | 状态 |
|---|---|
| ROI | `d090_torso_dark_uv_inner_mask.png` n=6283（对齐 12a1945） |
| d135 | 仅 ROI 内写入权重 ×0.35 / ×0.15 |
| d180 | **一字未改** |
| EDGE / graze / 全局 view-weight | **未拧**（全 1.0 / graze0.20 / EDGE10） |
| 源图 PASS | 未动；禁假绿 / 禁程序化填红 / 禁 LUT 提亮 |
| 冻 / M3 / 用户点2 | **否** |

## 指标表

| 档 | fur sha | GY 绿+黄 | 红 | n_dark_inner d090 | n_dark d045 | d135 pull-down | d180 pull-down | d135 权重占比 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | `46e56675…` | 70.31% | 29.69% | **6283** | 2738 | 30.05% | 30.79% | 25.52% |
| ×0.35 | `7c5292bf…` | 70.35% | 29.65% | 6228 (−55 / −0.9%) | 2861 | 23.70% (−6.4pp) | 29.40% | 22.25% |
| ×0.15 | `0bdade2a…` | 70.35% | 29.65% | 5969 (−314 / −5.0%) | 2678 | 22.23% (−7.8pp) | 29.15% | 21.73% |

## 判定

- coverage 几乎不变（未崩）——软降只动 ROI 内权重，符合预期。
- d135 pull-down **占比**下降，但 **n_dark_inner 未明显收缩**（最好一档 ×0.15 也仅 −5%）；d180 仍 ~29% 主导。
- 制作人 4x（Layer A 黑底）：见 `x035/compare_layer_a_d090_d045_4x_black.png`、`x015/…` —— 假透空视觉改善不足以宣称过关。
- **选留**：**baseline**（两档都不达「明显收缩」）。×0.15 相对更好但仍不足。
- **下一步请示**：是否对 d180 做同样 ROI 软降（本轮锁死未动）。禁第三次 d135 盲试 regen。

## 路径

- 实验根：`docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_roi/`
- 报告：`contrast_report.json`（本 md）
- 边距次路径：`../CONTROL_FRAME_MARGIN_NOTE.md`（d135/d180 顶底贴边=0；未来重渲需 ≥16px）
- 归档：`cats/miemie/identity_v1/archive/pre_fuse_soft_d135_*`
- fuse 开关：`--roi-mask` / `--roi-view-soft`（不改默认全局 view-weight 表）
