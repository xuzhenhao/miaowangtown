# V2 腿内侧控图 + 理论 N·V 覆盖

**时间**：2026-10-30 17:42（Asia/Shanghai）
**状态**：控图已出 · **不开 SDXL / fuse**（本轮仅控图+理论）
**fur**：工作 `3be77787ab0f…` · **CANDIDATE_UNFROZEN**（未冻）
**coverage**：`1a8dbaf08c93…`（8+V1 合拢写入后）

> 硬门不降。禁假绿填红 / 软降 / 拧 EDGE·graze / regen / 冻 / 开 M3。
> 旧 8 向 + V1 控图**未**重渲。

## 相机

| name | yaw | pitch | fit_margin | visible_px | 路径 |
|---|---:|---:|---:|---:|---|
| `v2_leg_inner_L` | **-75.0°** | **15.0°** | 0.08 | 38610 | `cats/miemie/identity_v1/control_views/v2_leg_inner_L/` |
| `v2_leg_inner_R` | **75.0°** | **15.0°** | 0.08 | 27169 | `cats/miemie/identity_v1/control_views/v2_leg_inner_R/` |

说明：yaw 相对 ±90° **偏内 15°**（朝 yaw=0）；pitch=+15° 略俯。目标 C3/C4 后腿内侧 + 部分前腿腋下。

## 边距自检（hi 456×416）

| 图 | T | B | L | R | ≥16 |
|---|---:|---:|---:|---:|:---:|
| v2_leg_inner_L/depth | 34 | 33 | 47 | 57 | YES |
| v2_leg_inner_L/clay | 34 | 33 | 47 | 57 | YES |
| v2_leg_inner_R/depth | 33 | 33 | 78 | 65 | YES |
| v2_leg_inner_R/clay | 33 | 33 | 78 | 65 | YES |

## 理论覆盖（诚实 bary 岛 · graze=0.20 · **相对 8+V1 基线** · 无遮挡上限）

基线 GY/岛 = **0.9493** · 红/岛 = **0.0507**（写入后工作 coverage）

### L+R 合看

| 指标 | n | % |
|---|---:|---:|
| 诚实红被 V2 N·V≥graze | 10502 | 23.81 |
| 其中相对 8+V1 **新**可吃（prev&lt;graze） | 4512 | 10.23 |
| 背向红（prev&lt;0）可吃 | 0/3591 | 0.0 |
| legs 红可吃 | 2167/12205 | 17.76 |
| C3_leg_BL 红可吃 | 1014/5599 | 18.11 |
| C4_leg_BR 红可吃 | 1085/5751 | 18.87 |
| 前腿红可吃 | 68/855 | 7.95 |
| 阈值带红可吃 | 4512/30169 | 14.96 |
| face_detail 红可吃（**非本战役标准**） | 2895/13388 | 21.62 |

### 分向

| 向 | 新吃红 n | 新吃% | 估 GY | ΔGY pp | C3% | C4% |
|---|---:|---:|---:|---:|---:|---:|
| `v2_leg_inner_L` | 1204 | 2.73 | **0.9507** | +0.14 | 11.27 | 2.43 |
| `v2_leg_inner_R` | 3308 | 7.5 | **0.9531** | +0.38 | 6.84 | 16.43 |
| **L+R** | 4512 | 10.23 | **0.9545** | +0.52 | 18.11 | 18.87 |

### 估算合拢后（L+R）

| 口径 | GY/岛 | 红/岛 | ΔGY |
|---|---:|---:|---:|
| 现在（8+V1 工作） | 0.9493 | 0.0507 | — |
| +V2 L+R **乐观**（无遮挡） | **0.9545** | 0.0455 | **+0.52 pp** |
| 硬门 GY≥0.92 | 已过 → 仍过 | 红门均仍 PASS | — |

**一句话**：V2 L/R yaw=±75 pitch=15 边距≥16=YES；相对 8+V1 基线 GY=0.9493/红=0.0507；L+R 理论新吃红 4512 (10.23%) → GY 0.9493→0.9545(+0.52pp)；C3/C4 红可吃 18.11%/18.87%；未开 SDXL/fuse。

## 非目标

- face_detail / 鼻垫红：**不进本战役成功标准**。
- 旧 8 向 + V1 控图：**未**重渲。
- SDXL / fuse / 冻 / 开 M3：**未**做。

## 产出

- `v2_leg_inner_control_sheet.png`
- `control_preview/v2_leg_inner_L|R/`
- `theory_v2_eat_red_512.png`（青=V2可吃 · 黄=后腿新吃 · 橙=前腿新吃 · 红=仍盲）
- `theory_v2_ndotv_on_red_512.png`
- `theory_v2_leg_inner_coverage.json`

路径：`docs/validation/m2_2_8dir/hold_diag/v2_leg_inner_control/`
