# Fuse 边缘 / N·V 采样短注（只读诊断）

**时间**：2026-10-30（Asia/Shanghai）  
**脚本**：`pipeline/texture/fuse_8dir_albedo.py`  
**约束**：本轮**不**再降权 fuse；0.4 对照已够；归因结论前禁止盲降 d090。

## 可疑参数（默认）

| 符号 | 值 | 作用 |
|---|---|---|
| `EDGE_ERODE` | **10** | 对 body silhouette mask 做 4-邻域反复腐蚀；只有 `edge_ok` 内才写入 accum |
| `NDOTV_GRAZE` | **0.20** | `N·V < 0.20` 的三角直接 skip（不写入 RGB） |
| `NDOTV_DIRECT` | **0.50** | coverage 绿（direct）门槛；`[0.20,0.50)` → 黄 graze |
| 权重 | `max(N·V,0)^2 * view_weight` | FUSED §4.2；默认 `view_weight=1.0` |
| 采样 | `round(px*sx), round(py*sy)` | 最近邻从视图 albedo 取 texel；**无**双线性 |
| alpha 门槛 | `sampled.a > 128` | 半透明/灰底边缘若 alpha 高仍可写入 |
| `dark_reject_lum` | 默认 **0** | 仅当 `view_weight<0.999` 时启用（对照实验） |

## 边缘路径怎么写进侧向躯干

1. **`build_edge_ok`**：先画视图分辨率下的 body mask（三角填充 → resize BILINEAR 到 albedo），再 **腐蚀 10 次**，并与 `anchor.a>128` 相交。  
   - 腐蚀目的：挡掉剪影外 1–2px 的背景灰/黑。  
   - 风险：腐蚀**只**吃外轮廓；**轮廓内**的近黑碎斑、深度洞、SDXL 脏躯干 **不会**被挡。
2. **`project_view_into_accum`**：对每个正面三角，用重心坐标把 UV texel 映到视图 `(ax,ay)`，`sampled = anchor[ay,ax]`。  
   - 若 `edge_ok[ay,ax]` 为假 → **不写 RGB**，但仍可能抬 `best_ndotv`（coverage graze 记账）。  
   - 若 `edge_ok` 真且 alpha 过线 → 按 `N·V²` 加权累加。
3. **多向竞争**：同一 UV 被多向写入后做加权平均。侧视可见躯干 UV 上，**主写者通常是同向（d090 或 d270）**，但邻向（d045/d135 或 d225/d315）在 `N·V` 仍 ≥0.20 时也会掺入；若邻向采样落在该向的浅 graze / 近边缘灰带，可能把偏暗或灰 texel 带进侧向绿区。
4. **不会主动把「画布外背景」写入**：未腐蚀掉且 alpha>128 的像素才写；更常见污染是 **源 albedo 岛内近黑碎斑**（已在 d270 源预检证实 torso dark≈6%）或 **邻向 graze 采样到弱质 texel**，不是纯黑底透过来。

## 与假透空的关系

- 降权对照（d090=d270=0.4 + dark_reject=40）**几乎不改**合拢板假透空 → 说明问题不全是「侧向权重过大」，更可能是 **源图脏（尤其 d270）** 和/或 **同向/邻向在绿区内写入的近黑 RGB**。  
- `body-only dark_opaque@lum<40` 会被黑底轮廓 1px 污染（d045 也≈476）→ **不能当主指标**；权威 = **4x 肉眼**；若计数需 mask 内缩 2px 或躯干 ROI vs d045。

## 最小改法建议（尚未改代码）

1. **先重生脏源**（本轮：d270）→ 制作人 4x 门禁后再 fuse；**不要**再拧权重。  
2. **UV 归因**（并行）：对 d090 合拢板躯干暗斑 texel，统计各向 `accum_w` 贡献占比，点名污染源后再决定重生哪向或动 EDGE。  
3. 若归因指向 **边缘邻向掺入**：可试 `EDGE_ERODE` 12–14，或对 graze 带提高 `NDOTV_GRAZE`（如 0.25）——**小对照**，保留旧候选 sha。  
4. 若归因指向 **同向源碎斑**：重生该向；可选在 fuse 加 **全局**（非仅降权向）`dark_reject_lum` 或采样前对源做 depth-mask 内缩，避免只靠权重。  
5. **禁止**：程序化填红、盲降 d090、为冲 coverage 编毛流。

## 本轮动作

- ✅ 只读笔记（本文）  
- ✅ d270 源归档 + 只重生 d270（seed-offset 40011）  
- ✅ d090 暗斑 UV 归因脚本/报告写入 `hold_diag/`  
- ❌ 不降权 fuse；d270 新图 **暂不自动 fuse**，等归因摘要 + 制作人门禁
