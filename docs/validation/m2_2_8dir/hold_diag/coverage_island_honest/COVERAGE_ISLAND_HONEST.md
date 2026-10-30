# coverage 岛诚实（计量对照）

**时间**：2026-10-30 13:44（Asia/Shanghai）
**fur**：baseline `46e56675a577390d…`（**未改**）
**coverage.png SHA**：`347ca029da640ce5…`（本轮**未改写**；仅重算门禁分母/分子）
**UV**：`sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f`

> 假透空口径已解。本轮只改 **coverage 岛计量**：剔除 PIL vs 重心光栅差（bary_miss fringe）。
> 硬门阈值不变：GY≥0.92 / 红≤0.20。禁假绿填红 / 软降 / 拧 EDGE·graze / regen / 降硬门。

## 口径

| 模式 | 岛定义 | 红计数 |
|---|---|---|
| **OLD (pil)** | PIL polygon fill（`uv_occ`） | `coverage==0 ∩ PIL岛` |
| **NEW (bary / honest)** | 重心命中（texel 中心 bary） | `coverage==0 ∩ bary岛`（剔除 fringe） |

fuse 开关：`--island-mode bary|pil`（默认 `bary`）/ 环境变量 `M22_ISLAND_MODE`。
种子填色仍用 PIL `uv_occ`（防 fur 留洞）；**仅门禁统计 + 红着色**切诚实岛。
顺手修了 `region_masks_from_manifest` 识别 `u_range/v_range`（旧 fuse 因漏解析把 hf 退化成整岛）。

## 新旧对照（fuse 可比 = 整岛 GY/红）

| | 岛 | 红 | GY/岛 | 红/岛 | GY门(整岛) | 红门 | 双过 |
|---|---:|---:|---:|---:|:---:|:---:|:---:|
| OLD pil | 1004071 | 297967 | 0.7032 | 0.2968 | FAIL | FAIL | NO |
| NEW bary | 869905 | 163686 | 0.8117 | 0.1882 | FAIL | **PASS** | NO |

参考（真 hf 子集，修解析后）：OLD hf GY=0.7471 / NEW hf GY=0.8757（仍 FAIL，差 0.0443）。

- 剔除 fringe（bary_miss）：**134281**（占旧红 45.07%，占旧岛 13.37%）
- 红门翻转 PASS；GY 整岛差 **0.1083** 未过

## 剩余诚实红结构

### 类型

| 类型 | n | 占诚实红% |
|---|---:|---:|
| 真相机盲（背向） | 88009 | 53.77 |
| 阈值过严（0≤N·V&lt;0.20） | 68744 | 42.0 |
| 异常（N·V≥graze 仍红） | 6933 | 4.24 |

### 部件桶（诚实红）

| 桶 | n_red | 占诚实红% | 桶内红/诚实岛 |
|---|---:|---:|---:|
| **face_detail** | 48914 | 29.88 | 0.44 |
| **legs** | 47405 | 28.96 | 0.2185 |
| **belly** | 35140 | 21.47 | 0.6518 |
| **head** | 22533 | 13.77 | 0.1043 |
| **tail** | 9328 | 5.7 | 0.1856 |
| **torso_side** | 366 | 0.22 | 0.0034 |
| **torso_back** | 0 | 0.0 | 0.0 |
| **reserved** | 0 | 0.0 | 0.0 |

焦点：背向 53.77% · legs 28.96% · belly 21.47%
（face_detail=29.88% 仍高，腹向新视角几乎吃不到鼻垫类）

## 判定

修岛后（fuse可比·整岛）：GY 0.8117 FAIL（差 0.1083）/ 红 0.1882 PASS；剔除 fringe 134281（旧红 45.07%）。真 hf 子集 GY=0.8757 仍 FAIL。剩余诚实红：背向 53.77% + legs 28.96% + belly 21.47% （face_detail 仍 29.88%）。不降硬门；见 ADD_VIEW_MIN_PLAN。

## 产出

- `island_old_vs_honest_512.png`
- `island_old_vs_honest_2048.png`
- `honest_red_class_512.png`
- `honest_red_by_part_512.png`
- `island_honest_board_512.png`
- `coverage_island_honest.json`
- `COVERAGE_ISLAND_HONEST.md`

相关：`ADD_VIEW_MIN_PLAN.md`（半页计划，**未执行**）。

锁：fur baseline；不冻不开 M3；不交用户点2。
