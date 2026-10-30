# HOLD 选项 · M2.2 fuse（一页纸 · 等用户拍板）

**时间**：2026-10-30 13:30（Asia/Shanghai）  
**tip 起点**：`27b50aa`  
**状态**：仍 **CONDITIONAL HOLD**（整体）。用户已拍板 **A** 并已执行口径重框（见 `METRIC_REFRAME_ABS_DARK.md`）。不冻、不开 M3、不交用户点2；未再开 fuse/软降/regen。

---

## 状态摘要（短）

| 项 | 状态 |
|---|---|
| tip | `27b50aa`：d225 **恰好 1 次** FAIL → **整条源重生停** |
| fur | 锁 baseline `46e56675…`（`CANDIDATE_UNFROZEN`） |
| 禁继续 | 不 fuse / 不软降 / 不二次 seed / 不冻 / 不开 M3 |
| d225 控图 | 实读 `control_views` 边距已 ≥16（`bf13e9a`）——**未**因贴边重渲 |

### 已排除（本回合）

| 路径 | 结果 |
|---|---|
| 拧 graze / EDGE / 全局 view-weight | 无效或回退（假透空几乎不变 / coverage 更差） |
| ROI 软降 A/B/C（d135±d180） | 门槛 **NO**（UV 偶过、4x 假透空不过；整条软降权停） |
| d135 受控重生 ×2 | 两败（碎块/头切）；禁第三次盲试 |
| d225 受控重生 ×1 | 一败（近黑表面↓ 但几何门禁 FAIL）；整条源重生停 |

---

## 用户拍板三选项

| 选项 | 含义 |
|---|---|
| **A** | **先改假透空判定口径**：改 4x 假透空 / 红区口径（abs 近黑 + 连通域），把**虎斑相对暗**与**真假洞**拆开，再评 baseline（不先动源图 / 不先 fuse） |
| **B** | **控图管线加大画幅边距**：重渲**多向** control（尤其贴边向：d135/d180/d270 等）统一 **≥16px** 后再开**有限次**重生战役 |
| **C** | **暂停合拢过关**：暂停 M2.2 fuse 过关，先做别的里程碑；本 HOLD 文档归档 |

### 选项 B 备注（重要）

d225 **单向**实读边距已 ≥16（`bf13e9a`）。若选 **B**，指的是**多向 / 贴边向统一**边距战役，**非仅 d225**。

---

## 锁（待命期间）

- 不开新实验（含：盲 seed、软降、拧 knobs、假绿整向、程序化填红、LUT 提亮）
- fur 保持 baseline；源 PASS 不重写
- 制作人待命，等用户选 **A / B / C**（或 opus 转发的新指令）

## 相关路径

- 本页：`docs/validation/m2_2_8dir/hold_diag/HOLD_OPTIONS_M22_FUSE.md`
- d225 FAIL：`hold_diag/D225_REGEN_STATUS.md`
- 边距：`hold_diag/CONTROL_FRAME_MARGIN_NOTE.md` · `hold_diag/D225_CONTROL_PATH_MARGIN.md`
- 制作人摘要：`docs/validation/m2_2_8dir/PRODUCER_SUMMARY_ZH.md`

---

## 选项 A 执行记录（2026-10-30 13:35）

- 脚本：`pipeline/texture/metric_reframe_abs_dark.py`
- 报告：`METRIC_REFRAME_ABS_DARK.md` + `metric_reframe_abs_dark/`
- 结论摘要：新口径下真近黑连通假洞很少（d090/d045 n_abs_dark=67/67）；
  旧相对暗把虎斑算进假透空。**可申请解「假透空」该条 HOLD 口径**；coverage 红仍 FAIL → **整体仍 HOLD**，不冻。

