# 假透空／红区口径重框（选项 A）— abs 近黑 + 连通域

**时间**：2026-10-30 13:34（Asia/Shanghai）  
**tip 起点**：`c6d5d63`  
**fur**：baseline `46e56675a577…`（未改；CANDIDATE_UNFROZEN）  
**脚本**：`pipeline/texture/metric_reframe_abs_dark.py`（独立；不改默认 fuse）  

---

## 新旧口径对照（固定）

| | 旧口径 | 新口径 |
|---|---|---|
| 名称 | 相对暗 / p10（`rel_thr`） | **abs 近黑 + 连通域** |
| 阈值 | `lum ≤ max(p10, 85)` | `lum < 40` |
| 空间过滤 | 无（或仅 ROI/erode） | **4-连通域**，保留 `area ≥ 12 px²`（文档允许带 8–16；本轮固定 **12**） |
| 岛内范围 | 屏：clay∩layer body；UV：torso∩α-erode2（旧发布 ROI 另含 d090 weight>0） | 同左 |
| 目的 | 抓黑底上「看起来暗」的虎斑/相对暗带 | **拆开虎斑相对暗 vs 真近黑假洞** |

> coverage **绿+黄 / 红** 仍是 fuse 看见/盲区硬门，**本轮未重 fuse、数值不变**；「红区」在假透空语境下指近黑标注区，不是 coverage 红盲区。

---

## coverage（基线 · 未改）

| GY 比 | 红盲区 | GY≥0.92 | 红≤0.20 |
|---:|---:|---|---|
| **70.32%** | **29.68%** | FAIL | FAIL |

---

## Layer A 屏指标（制作人 4x 权威 · body=clay_noeye∩layer）

| 向 | body_px | 旧 n_dark_rel | 旧 maxCC≥min | 新 n_abs_dark_raw | **新 n_abs_dark（≥min）** | **新 max_cc** |
|---|---:|---:|---:|---:|---:|---:|
| **d090** | 4112 | 895 | 300 (max 35) | 455 | **67** | **15** |
| **d045** | 5280 | 1005 | 465 (max 61) | 510 | **67** | **15** |
| **d270** | 3988 | 577 | 111 (max 17) | 454 | **81** | **17** |

### d090 vs d045（新旧）

- 旧相对暗：d090 `895` vs d045 `1005` （rel_thr d090=85.0, d045=85.0）
- 新 abs+CC：d090 **`67`** vs d045 **`67`** （raw 455 / 510；max_cc 15 / 15）
- 旧口径把大量 **虎斑相对暗** 算进「假透空」；新口径只留 **近黑连通块**，两侧数量接近且都远小于旧 n_dark_rel。

---

## UV torso（合拢贴图 · 只读）

- 旧发布 `n_dark_inner`（含 d090 weight，`12a1945`）：**6283**
- 本轮旧口径重算（无 d090 weight 过滤）：n_dark_rel=**12989**（rel_thr=91.0）
- 新口径：n_abs_dark_raw=**15** → n_abs_dark(≥12)=**0** （max_cc=7）
- 旧发布相对暗 ROI 上 abs&lt;40：raw=**0**，≥12=**0** （max_cc=0）→ **相对暗带里几乎没有真近黑连通块**

---

## 标注板

- 并排对照（d090+d045）：`docs/validation/m2_2_8dir/hold_diag/metric_reframe_abs_dark/layer_a_d090_d045_old_vs_new_4x.png`
- d090：`docs/validation/m2_2_8dir/hold_diag/metric_reframe_abs_dark/layer_a_d090_old_vs_new_4x.png`
- d045：`docs/validation/m2_2_8dir/hold_diag/metric_reframe_abs_dark/layer_a_d045_old_vs_new_4x.png`
- json：`docs/validation/m2_2_8dir/hold_diag/metric_reframe_abs_dark/metric_reframe_report.json`

图例：品红=保留的连通域（≥min_area）；青=未达面积阈值的碎点 / 旧口径相对暗碎点。

---

## 结论（诚实）

- 旧口径（相对暗）在 Layer A 上 d090/d045 仍报大片暗带（895 / 1005），其中大量是虎斑/中灰相对暗，在黑底上被读成「假透空」。
- 新口径（abs&lt;40+CC≥12）把保留近黑连通块压到 d090 **67** / d045 **67** （max_cc 15 / 15）；两侧接近，说明「假透空」主差不是大块真近黑洞。
- UV 躯干：旧发布相对暗 ROI（n=6283）上 abs+CC≈**0**；本轮 torso 新口径 n_abs_dark=**0** → 合拢贴图岛内几乎无真近黑连通假洞。
- coverage GY/红仍 **70.32% / 29.68%** （硬门 FAIL）——口径重框**不**等于 coverage 过门。

**制作人建议**：可申请将「侧向假透空」从主否决降为**口径说明（CONDITIONAL→申请解该条 HOLD）**：真近黑连通假洞在新口径下很少；旧相对暗把虎斑算进去了。但 **coverage 红盲区仍 FAIL** → **整体仍 HOLD**，不冻、不交用户点2；解的是假透空判定口径，不是冻结放行。

锁：不冻、不开 M3、不交用户点2、不动 fur/源图/EDGE/graze/软降。

