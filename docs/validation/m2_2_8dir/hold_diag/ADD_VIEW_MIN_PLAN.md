# 加视角最小计划（半页 · **未执行**）

**时间**：2026-10-30（Asia/Shanghai）  
**状态**：只文档。等 **coverage 岛诚实数字** + **opus / 用户点头** 再开跑。  
**禁**：假绿填红、软降、拧 EDGE/graze、盲 regen、降硬门、冻、开 M3。

---

## 为何要补向

8 向 × pitch=35° 合拢后，诚实岛下剩余红仍由 **几何背向** 主导（腹底 / 腿内侧 / 头侧等），升权与降 graze 吃不到大头（见 `coverage_red_attrib/`、`coverage_island_honest/`）。

## 建议新向（1–2 个）

| # | 建议姿态 | 目标吃红 | 控图 |
|---|---|---|---|
| **V1** | **腹底低 pitch**（yaw≈0° 或 ±20°，pitch ≈ **−25°～−35°**，相机自下往上看肚皮） | `B4_torso_belly` 真背向红 | 要：**新** depth/normal/clay/part_mask（现管线无负 pitch 导出） |
| **V2**（可选同战役） | **腿内侧**（yaw ≈ ±90° 偏内 10–20°，pitch ≈ 10–20° 略俯，或随 V1 一次低机位兼扫后腿内侧） | `C3/C4` 后腿内侧 + 部分前腿腋下 | 可先试复用现 control 改 yaw；若遮挡重再单渲 |

优先 **只开 V1**；V2 仅当修岛后 belly 红已降、legs 仍顶占比时再加。

## 预期能吃哪块红

- V1：诚实红里 belly 桶（旧归因 ~15% 全红；修岛后占比见对照报告）+ 部分腿根腹侧。
- V2：legs 桶剩余内侧；对 face_detail / 鼻垫类红 **几乎无效**（那是 UV 部件朝向问题，另案）。

## 控图管线要不要动

| 项 | 要不要 |
|---|---|
| `export_control_views.py` 支持 **负 pitch / 低机位** | **要**（V1 阻塞） |
| 现有 8 向 control 重渲 | **不要**（本计划不加视角战役前不动） |
| SDXL `--views` 扩白名单 + gate 模板 | **要**（新向才生成） |
| fuse `DIRECTIONS` / camera basis | **要**（登记新 yaw+pitch） |
| 边距 | 新向仍要顶底左右 **≥16px**（见 `CONTROL_FRAME_MARGIN_NOTE.md`） |

## 开跑门槛（全部满足才许）

1. `coverage_island_honest/` 新旧 GY/红数字已出，且确认剩余红仍是几何腹/腿（非 fringe）。
2. **opus 或用户** 明确点头「开 V1」。
3. 控图导出负 pitch 已落地并自检边距。
4. 新向：**恰好有限次** 受控重生（建议 ≤2 seed），FAIL 即停来同步；禁整向假绿。

## 非目标

- 不靠降 GY/红硬门过关。
- 不把 nose_pads / 舌等 face_detail 红指望新腹向吃掉。
- 不开 M3、不冻 fur。

---

路径：`docs/validation/m2_2_8dir/hold_diag/ADD_VIEW_MIN_PLAN.md`
