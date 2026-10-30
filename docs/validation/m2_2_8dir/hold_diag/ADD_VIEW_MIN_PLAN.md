# 加视角最小计划（半页）

**时间**：2026-10-30 17:42:27 Asia/Shanghai  
**状态**：**V1 已写入工作 fur（CANDIDATE_UNFROZEN）· V2 控图+理论已出 · 未开 SDXL · 未冻 · 未开 M3**  
**禁**：假绿填红、软降、拧 EDGE/graze、盲 regen、降硬门、冻、开 M3。

---

## V1 进度

| 项 | 状态 |
|---|---|
| 控图 yaw0 pitch−30 | ✅ |
| SDXL ≤2 seed | ✅ seed1 FAIL / **seed2 PASS** |
| 对照 fuse（bary） | ✅ 诚实岛 GY **0.9493** / 红 **0.0507** |
| 写入工作 fur + coverage | ✅ `3be77787ab0f…` / `1a8dbaf08c93…` |
| 旧 baseline 归档 | ✅ `v1_belly_sdxl/archive_baseline_46e56675/`（`46e56675…`） |
| 状态标 | **CANDIDATE_UNFROZEN** |
| 冻 fur / 开 M3 | **未做** |

## V2 进度

| 项 | 状态 |
|---|---|
| 控图 `v2_leg_inner_L` yaw=**−75** pitch=**15** | ✅ 边距 depth T/B/L/R 见报告 ≥16 |
| 控图 `v2_leg_inner_R` yaw=**+75** pitch=**15** | ✅ 边距 ≥16 |
| 理论 N·V（相对 8+V1 工作 coverage） | ✅ L+R 新吃红 **4512**（10.23%）→ GY 0.9493→**0.9545**（+0.52pp） |
| C3/C4 红可吃 | 18.11% / 18.87% |
| SDXL | **未开**（等点头） |
| fuse / 冻 / 开 M3 | **未做** |

详报：`hold_diag/v2_leg_inner_control/V2_LEG_INNER_CONTROL.md`

## 非目标

- face_detail 不进本仗成功标准。
- 不请用户冻结；不开 M3。

