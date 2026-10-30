# d225 受控重生状态（1 次 FAIL · 整条源重生停）

**时间**：2026-10-30 13:27（Asia/Shanghai）  
**tip 起点**：`bf13e9a`  
**结论**：**仍 CONDITIONAL HOLD**。按 opus 拍板 `bf13e9a` **恰好 1 次** d225 受控重生 → **FAIL**；已回滚 PASS；**整条源重生停**（禁第二次、不 fuse、不软降、不假绿）。不冻、不开 M3、不交用户点2。

## A. 执行范围（锁）

| 项 | 状态 |
|---|---|
| d225 | 仅此向 1 次重生；现已回滚 PASS `f3ec8950…` |
| 其它向（含 d135/d180） | **一字未改** |
| fur | 保持 baseline `46e56675…`（未 fuse） |
| 控图 | **未重导出**（实读 `control_views`，margin ≥16 已确认） |
| graze / EDGE / view-weight / ROI 软降 | **未拧** |

## B. VIEW_TUNING（写进 prompt，非 LUT）

- `prompt_extra`: `, flank fur readable mid gray-brown, no crushed ribs`
- **禁** `lift black blotches` / 任何全局提亮词（避 d135 try2 白圆覆辙）
- `negative_extra`: floating shards / hard head crop / disconnected paw / plastic ellipse / flat bright wash / crushed near-black rib patches + 旧负向
- `omit_view_style_tail: true` → 正词 **tokens=77, truncated_at_77=False**
- control / ip / guidance **保持 PASS 档**：`[1.2, 1.0]` / `0.58` / `5.0`（**未升 depth**）

## C. 唯一一次尝试

| try | seed_offset | seed | albedo sha | CLIP | 4x 门禁 | 主因 |
|---:|---:|---:|---|---|---|---|
| 1 | **70011** | **20331396** | `1db95dd9…` | 77 / False | **FAIL** | 头后竖条/硬切；下半身层状碎块；断爪浮空；前肢塑料椭圆块 |

定量旁注（非门禁主指标）：
- 近黑 `frac abs<40`：旧 PASS 11.0% → 新 0.3%（压黑目标表面改善）
- 但几何门禁（碎块/头切/断爪）权威 FAIL → 不得进 fuse

归档：
- PASS 备份：`complementary_albedos/archive/pre_d225_regen_bf13e9a/`
- FAIL try1：`…/archive/failed_d225_regen_try1_70011/`
- 对照板：`hold_diag/d225_regen_old_vs_new.png`（亦在 fail archive）

## D. 回滚后工作树

- d225 albedo / gate / 4x preview → 旧 PASS `f3ec8950…`
- fur 仍 `46e56675…`（CANDIDATE_UNFROZEN）
- **未**对照 fuse
- **整条源重生停**；等 opus 写给用户的 HOLD 选项

## E. 请 opus 拍板（下一结构，本轮不开跑）

1. 是否放弃源重生、改投影/加权结构或其它非 seed 路径  
2. HOLD 选项如何对用户表述（不交点2 直至拍板）  
3. **仍禁**整向假绿 / 程序化填红 / LUT 提亮 / 自动第二次 seed
