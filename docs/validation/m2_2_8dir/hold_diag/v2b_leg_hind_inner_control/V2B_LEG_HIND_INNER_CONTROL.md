# V2b 后腿内侧相机重设计 · 控图 + 理论 N·V

**时间**：2026-10-30 17:48（Asia/Shanghai）
**状态**：控图已出 · **本轮不开 SDXL / fuse**（仅控图+理论）· 旧 V2 cam1 deprecated
**fur**：工作 `3be77787ab0f…` · **CANDIDATE_UNFROZEN**（未冻）
**coverage**：`1a8dbaf08c93…`（8+V1 合拢写入后）

> 硬门不降。禁假绿填红 / 软降 / 拧 EDGE·graze / regen / 冻 / 开 M3。
> 旧 8 向 + V1 控图**未**重渲。

## 相机

| name | yaw | pitch | fit_margin | visible_px | 路径 |
|---|---:|---:|---:|---:|---|
| `v2b_leg_hind_inner_L` | **-115.0°** | **-10.0°** | 0.08 | 27937 | `cats/miemie/identity_v1/control_views/v2b_leg_hind_inner_L/` |
| `v2b_leg_hind_inner_R` | **115.0°** | **-10.0°** | 0.08 | 40829 | `cats/miemie/identity_v1/control_views/v2b_leg_hind_inner_R/` |

说明：相对旧 V2 cam1（±75/+15）**更偏后内**：yaw=±115°（相对 ±90° 偏后 25°），pitch=−10° 略仰/偏低。目标吃背向红 + C3/C4 后腿内侧。探针 B(±120/−15) 理论并列，取授权带中位 A。

## 边距自检（hi 456×416）

| 图 | T | B | L | R | ≥16 |
|---|---:|---:|---:|---:|:---:|
| v2b_leg_hind_inner_L/depth | 33 | 33 | 74 | 86 | YES |
| v2b_leg_hind_inner_L/clay | 33 | 33 | 74 | 86 | YES |
| v2b_leg_hind_inner_R/depth | 33 | 33 | 61 | 57 | YES |
| v2b_leg_hind_inner_R/clay | 33 | 33 | 61 | 57 | YES |

## 理论覆盖（诚实 bary 岛 · graze=0.20 · **相对 8+V1 基线** · 无遮挡上限）

基线 GY/岛 = **0.9493** · 红/岛 = **0.0507**（写入后工作 coverage）

### L+R 合看

| 指标 | n | % |
|---|---:|---:|
| 诚实红被 V2 N·V≥graze | 43125 | 97.79 |
| 其中相对 8+V1 **新**可吃（prev&lt;graze） | 33760 | 76.55 |
| 背向红（prev&lt;0）可吃 | 3591/3591 | 100.0 |
| legs 红可吃 | 12046/12205 | 98.7 |
| C3_leg_BL 红可吃 | 5525/5599 | 98.68 |
| C4_leg_BR 红可吃 | 5715/5751 | 99.37 |
| 前腿红可吃 | 806/855 | 94.27 |
| 阈值带红可吃 | 30169/30169 | 100.0 |
| face_detail 红可吃（**非本战役标准**） | 13370/13388 | 99.87 |

### 分向

| 向 | 新吃红 n | 新吃% | 估 GY | ΔGY pp | C3% | C4% |
|---|---:|---:|---:|---:|---:|---:|
| `v2b_leg_hind_inner_L` | 23749 | 53.85 | **0.9766** | +2.73 | 88.12 | 42.46 |
| `v2b_leg_hind_inner_R` | 25660 | 58.19 | **0.9788** | +2.95 | 39.44 | 85.24 |
| **L+R** | 33760 | 76.55 | **0.9881** | +3.88 | 98.68 | 99.37 |

### 估算合拢后（L+R）

| 口径 | GY/岛 | 红/岛 | ΔGY |
|---|---:|---:|---:|
| 现在（8+V1 工作） | 0.9493 | 0.0507 | — |
| +V2b L+R **乐观**（无遮挡） | **0.9881** | 0.0119 | **+3.88 pp** |
| 硬门 GY≥0.92 | 已过 → 仍过 | 红门均仍 PASS | — |

**一句话**：V2b L/R yaw=±115 pitch=-10 边距≥16=YES；相对 8+V1 基线 GY=0.9493/红=0.0507；L+R 理论新吃红 33760 (76.55%) → GY 0.9493→0.9881(+3.88pp)；背向红可吃 3591/3591 (100.0%)；C3/C4 红可吃 98.68%/99.37%；建议开SDXL=YES；整条V2停=NO；未开 SDXL/fuse。

## 结论（必读）

- **建议开 SDXL**：**YES（理论明显过线）**（本轮仍**未开**）
- **整条 V2 停**：**NO**（规则：新吃红%<5 OR 背向红可吃≈0）
- 新吃红% = **76.55**；背向红可吃 = **3591/3591** (100.0%)
- ΔGY = **+3.88 pp** → 估 GY **0.9881**
- 旧 `v2_leg_inner_*` 控图保留，标 deprecated / 不开战。

## 非目标

- face_detail / 鼻垫红：**不进本战役成功标准**。
- 旧 8 向 + V1 控图：**未**重渲。
- SDXL / fuse / 冻 / 开 M3：**未**做。

## 产出

- `v2b_leg_hind_inner_control_sheet.png`
- `control_preview/v2b_leg_hind_inner_L|R/`
- `theory_v2b_eat_red_512.png`（青=V2b可吃 · 黄=后腿新吃 · 橙=前腿新吃 · 红=仍盲）
- `theory_v2b_ndotv_on_red_512.png`
- `theory_v2b_leg_hind_inner_coverage.json`

路径：`docs/validation/m2_2_8dir/hold_diag/v2b_leg_hind_inner_control/`
