# 加视角最小计划（半页）

**时间**：2026-10-30 13:51（Asia/Shanghai）  
**状态**：**控图已出 · 等 SDXL 点头**  
**禁**：假绿填红、软降、拧 EDGE/graze、盲 regen、降硬门、冻、开 M3。本轮**未**跑 SDXL / fuse。

---

## 为何要补向

8 向 × pitch=35° 合拢后，诚实岛下剩余红仍由 **几何背向** 主导（腹底 / 腿内侧 / 头侧等），升权与降 graze 吃不到大头（见 `coverage_red_attrib/`、`coverage_island_honest/`）。

## V1 进度

| 项 | 状态 |
|---|---|
| `export_control_views` 负 pitch | **已落地**（`EXTRA_VIEWS.v1_belly`） |
| V1 控图导出 | **已出** `cats/.../control_views/v1_belly/` + docs 镜像 |
| 相机 | yaw=**0°** · pitch=**−30°** · fit_margin=0.08 |
| 边距 | depth T/B/L/R=**33/37/164/165** ≥16 YES |
| 理论 N·V | 见 `v1_belly_control/`：乐观 GY 0.8117→0.9531；战役扣 face≈0.9079；belly 红可吃 84.35%；背向红可吃 83.91% |
| SDXL | **未开** — 等 opus/用户点头后 ≤2 seed |
| face_detail / 鼻垫 | **V1 不吃（战役）** — 不进本战役成功标准 |

## 建议新向（1–2 个）

| # | 建议姿态 | 目标吃红 | 控图 |
|---|---|---|---|
| **V1** | **腹底低 pitch** yaw=0°、pitch=**−30°** | `B4_torso_belly` 真背向红 | **已导出** depth/normal/clay/part_mask |
| **V2**（可选同战役） | **腿内侧**（yaw ≈ ±90° 偏内 10–20°，pitch ≈ 10–20°） | `C3/C4` 后腿内侧 + 部分前腿腋下 | 未导出；等 V1 SDXL 结果 |

## 开跑 SDXL 门槛（全部满足才许）

1. ~~`coverage_island_honest/` 数字已出~~ ✅
2. ~~控图负 pitch 落地并自检边距 ≥16~~ ✅
3. **opus 或用户** 明确点头「开 V1 SDXL」← **当前卡点**
4. 新向：恰好 ≤2 seed 受控重生，FAIL 即停；禁整向假绿。

## 非目标

- 不靠降 GY/红硬门过关。
- 不把 nose_pads / 舌等 face_detail 红指望新腹向吃掉（**不进成功标准**）。
- 不开 M3、不冻 fur。

---

路径：`docs/validation/m2_2_8dir/hold_diag/ADD_VIEW_MIN_PLAN.md`
