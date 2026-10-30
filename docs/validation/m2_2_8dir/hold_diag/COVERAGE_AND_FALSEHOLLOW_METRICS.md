# coverage 硬门 vs 假透空口径（gate 对照）

**时间**：2026-10-30 13:35（Asia/Shanghai）

本页把两类「红」拆开，避免混读。权威细节见 `METRIC_REFRAME_ABS_DARK.md`。

## 1) coverage 绿+黄 / 红（fuse 硬门 · **未改**）

| 指标 | 阈值 | baseline `46e56675…` |
|---|---|---|
| high_freq 绿+黄比 | ≥ 0.92 | **0.7032** FAIL |
| 红盲区 / 岛 | ≤ 0.20 | **0.2968** FAIL |

来源：`coverage.png` / `fuse_8dir_report.json`。选项 A **不**重 fuse、**不**程序化填红。

## 2) 4x 假透空／近黑「红区」标注（选项 A 重框）

| 口径 | 定义 | 用途 |
|---|---|---|
| **旧** | 相对暗 `lum ≤ max(p10, 85)`（`rel_thr` / `n_dark_inner`） | 易把**虎斑相对暗**算进假透空 |
| **新** | **abs `lum < 40` + 4-连通域**，保留 `area ≥ 12 px²`（文档允许 8–16；固定 12） | 只计**真近黑连通假洞候选** |

独立脚本：`pipeline/texture/metric_reframe_abs_dark.py`（开关式新口径；默认 fuse 行为不变）。

## 3) 本轮数字（body=clay_noeye）

| 向 | 旧 n_dark_rel | 新 n_abs_dark | 新 max_cc |
|---|---:|---:|---:|
| d090 | 895 | 67 | 15 |
| d045 | 1005 | 67 | 15 |

UV 旧相对暗 ROI 上 abs+CC=0 → 合拢贴图岛内无大块真近黑假洞。
