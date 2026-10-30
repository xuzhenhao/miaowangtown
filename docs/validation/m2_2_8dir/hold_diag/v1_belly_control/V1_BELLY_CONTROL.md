# V1 腹底控图 + 理论 N·V 覆盖

**时间**：2026-10-30 13:51（Asia/Shanghai）  
**状态**：**控图齐 · SDXL seed2 PASS · 对照 fuse 候选已出**（更新 2026-10-30 17:20:17 Asia/Shanghai）  
**fur**：baseline `46e56675a577…`（未改）

> 硬门不降。禁假绿填红 / 软降 / 拧 EDGE·graze / regen / 冻 / 开 M3。  
> 旧 8 向控图**未**重渲。

## 相机

| 项 | 值 |
|---|---|
| name | `v1_belly`（alias `pitch_m30`） |
| yaw | **0.0°** |
| pitch | **-30.0°**（负=低机位仰视腹底） |
| fit_margin | 0.08 |
| visible_px (hi) | 27048 |
| 路径 | `cats/miemie/identity_v1/control_views/v1_belly/` |
| 文档镜像 | `docs/validation/m2_2_8dir/control_maps/v1_belly/` |

## 边距自检（hi 456×416）

| 图 | T | B | L | R | ≥16 |
|---|---:|---:|---:|---:|:---:|
| depth | 33 | 37 | 164 | 165 | YES |
| clay | 33 | 36 | 164 | 165 | YES |

## 理论覆盖（诚实 bary 岛 · graze=0.20 · **无遮挡上限**）

基线 GY/岛 = **0.8117** · 红/岛 = **0.1882**

| 指标 | n | % |
|---|---:|---:|
| 诚实红被 V1 N·V≥graze | 127521 | 77.91 |
| 其中相对 8 向**新**可吃（best8&lt;graze） | 123007 | 75.15 |
| 背向红（best8&lt;0）可吃 | 73848/88009 | 83.91 |
| belly 红可吃 | 29641/35140 | 84.35 |
| 阈值带红（0≤best8&lt;graze）可吃 | 49159/68744 | 71.51 |
| legs 红可吃 | 36457/47405 | 76.91 |
| face_detail 红可吃（**V1 不吃·非战役标准**） | 39360/48914 | 80.47 |

### 估算合拢后

| 口径 | GY/岛 | 红/岛 | ΔGY |
|---|---:|---:|---:|
| 现在 | 0.8117 | 0.1882 | — |
| +V1 **乐观**（无遮挡·含 face） | **0.9531** | 0.0468 | **+14.14 pp** |
| +V1 **战役**（扣 face_detail） | **0.9079** | 0.0920 | **+9.62 pp** |
| +V1 belly-only 下界 | 0.8458 | — | +3.41 pp |
| 硬门 GY≥0.92 | 乐观过 / 战役差 0.0121 / belly-only 差 0.0742 | 红门均仍 PASS | — |

> face_detail 无遮挡可吃 80.47% 是法线几何假象；下巴/口鼻自遮挡下实收低得多——**明确不进本战役成功标准**。

**一句话**：V1 yaw=0 pitch=-30 边距 T/B/L/R=33/37/164/165≥16；理论新吃红 123007(75.15%) → GY 0.8117→0.9531(+14.14pp，无遮挡上限)；战役扣 face 后 GY≈0.9079(+9.62pp)；背向红可吃 83.91%、belly 红可吃 84.35%；face_detail 理论可吃 80.47%但**不进本战役标准**（实遮挡恐更低）。未开 SDXL/fuse。

## 非目标

- face_detail / 鼻垫红：**V1 不吃（战役口径）**，不进成功标准。
- 旧 8 向控图：**未**重渲。
- SDXL / fuse：**未**开跑。

## 产出

- `v1_belly_control_sheet.png`
- `control_preview/`
- `theory_v1_eat_red_512.png`（青/黄=理论可吃 · 红=仍盲）
- `theory_v1_ndotv_on_red_512.png`
- `theory_v1_belly_coverage.json`

路径：`docs/validation/m2_2_8dir/hold_diag/v1_belly_control/`


## SDXL / 对照 fuse 回写

- seed1 FAIL（80011 / 20341975）；seed2 **PASS**（81011 / 20342080）
- 对照 fuse 诚实岛 GY 0.9493 / 红 0.0507（基线 0.8117 / 0.1882）
- baseline fur `46e56675…` **未改**；候选见 `../v1_belly_sdxl/`
- **未冻 / 未开 M3**
