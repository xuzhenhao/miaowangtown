# 加视角最小计划（半页）

**时间**：2026-10-30 17:50:18 Asia/Shanghai  
**状态**：**V1 已写入工作 fur（CANDIDATE_UNFROZEN）· 旧 V2 cam1 deprecated/不开战 · V2b 控图+理论已出 · 未开 SDXL · 未冻 · 未开 M3**  
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

## V2 cam1（旧 · DEPRECATED）

| 项 | 状态 |
|---|---|
| 控图 `v2_leg_inner_L/R` yaw=**±75** pitch=**15** | ✅ 边距≥16 · **文件保留** |
| 理论 | L+R 新吃红 10.23% · ΔGY **+0.52pp** · 背向红可吃 **0%** |
| 决策 | **不开 SDXL · 不作开战**（理论过薄） |

详报：`hold_diag/v2_leg_inner_control/V2_LEG_INNER_CONTROL.md`（已标 deprecated）

## V2b cam2（后内相机重设计 · 本轮）

| 项 | 状态 |
|---|---|
| 控图 `v2b_leg_hind_inner_L` yaw=**−115** pitch=**−10** | ✅ 边距≥16 |
| 控图 `v2b_leg_hind_inner_R` yaw=**+115** pitch=**−10** | ✅ 边距≥16 |
| 探针备选 B ±120/−15 | 理论并列 · 取授权带中位 A 写入正式控图 |
| 理论 N·V（相对 8+V1） | L+R 新吃红 **33760（76.55%）** → GY 0.9493→**0.9881（+3.88pp）** |
| 背向红（prev&lt;0）可吃 | **3591/3591（100%）** |
| C3/C4 红可吃 | **98.68% / 99.37%** |
| **建议开 SDXL** | **YES（理论明显过线）** · **本轮仍未开** |
| **整条 V2 停** | **NO**（新吃≥5% 且 背向>0） |
| fuse / 冻 / 开 M3 | **未做** |

详报：`hold_diag/v2b_leg_hind_inner_control/V2B_LEG_HIND_INNER_CONTROL.md`

## 非目标

- face_detail 不进本仗成功标准（理论可吃数含其红，战役成功另案）。
- 不请用户冻结；不开 M3。
- 本轮不开 SDXL（等点头）。
