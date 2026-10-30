# 加视角最小计划（半页）

**时间**：2026-10-30 17:38:43 Asia/Shanghai  
**状态**：**V1 候选已写入工作 fur（CANDIDATE_UNFROZEN）· 未冻 · 未开 M3**  
**禁**：假绿填红、软降、拧 EDGE/graze、盲 regen、降硬门、冻、开 M3。

---

## V1 进度

| 项 | 状态 |
|---|---|
| 控图 yaw0 pitch−30 | ✅ |
| SDXL ≤2 seed | ✅ seed1 FAIL / **seed2 PASS**（81011→20342080） |
| 对照 fuse（bary） | ✅ 诚实岛 GY **0.9493** / 红 **0.0507** |
| 硬门 0.92 / 红 0.20 | ✅ 过 |
| 写入工作 fur + coverage | ✅ `3be77787ab0f…` / `1a8dbaf08c93…` |
| 旧 baseline 归档 | ✅ `v1_belly_sdxl/archive_baseline_46e56675/`（`46e56675…`） |
| 状态标 | **CANDIDATE_UNFROZEN**（`cats/miemie/identity_v1/CANDIDATE_UNFROZEN.md`） |
| 冻 fur / 开 M3 | **未做** |

## V2（下一步 · 仅控图+理论）

| # | 建议姿态 | 目标吃红 | 本轮 |
|---|---|---|---|
| **V2** | yaw ≈ ±90° **偏内** 10–20°，pitch ≈ 10–20° | `C3/C4` 后腿内侧 + 部分前腿腋下 | **控图导出 + 理论 N·V**（**不开 SDXL**） |

建议命名：`v2_leg_inner_L` / `v2_leg_inner_R`；边距≥16；基线=写入后 8+V1 合拢 coverage 诚实岛。

## 非目标

- face_detail 不进本仗成功标准。
- 不请用户冻结；不开 M3。

详报：`hold_diag/v1_belly_sdxl/V1_BELLY_SDXL_REPORT.md` · 状态：`CANDIDATE_UNFROZEN.md`
