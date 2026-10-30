# d135 受控重生状态（两次 FAIL · 已停）

**时间**：2026-10-30 13:01（Asia/Shanghai）  
**tip 起点**：`12a1945`  
**结论**：**仍 CONDITIONAL HOLD**。按 opus 拍板只动 d135；**两次 seed 均 FAIL**，已回滚 PASS，**已停等 opus**（不做第三次、不 fuse、不解锁 d180、不冻、不开 M3）。

## A. 执行范围（锁）

| 项 | 状态 |
|---|---|
| d135 | 仅此向重生尝试；现已回滚 PASS `acabf10c…` |
| d180 | **一字未改** sha `246b51a2…` |
| d045/d090/d270 及其余 PASS | **全锁** |
| fur | 保持 `46e56675…`（未 fuse） |
| graze / EDGE / view-weight | **未拧** |

## B. VIEW_TUNING（写进 prompt，非 LUT）

- `prompt_extra`: `, lift black torso blotches to mid gray-brown fur`
- `negative_extra`: crushed black / flat bright / plastic ellipse / shards…
- `omit_view_style_tail: true` → 正词 **tokens=77, truncated_at_77=False**（硬头+抬亮+五印记 ≤77）
- control `[1.05,0.8]` / ip `0.62` / guidance `5.2`

## C. 两次尝试

| try | seed_offset | seed | albedo sha | CLIP | 4x 门禁 | 主因 |
|---:|---:|---:|---|---|---|---|
| 1 | **50011** | **20311360** | `4830e4d7…` | 77 / False | **FAIL** | 头旁浮空暗碎块；头顶硬切；断爪碎片；近黑未明显抬升 |
| 2 | **60011** | **20321052** | `f0830671…` | 77 / False | **FAIL** | 头旁浮空白圆碎片；头顶方切；躯干压黑块仍平重 |

归档：
- PASS 备份：`complementary_albedos/archive/pre_d135_regen_12a1945/`
- FAIL try1：`…/archive/failed_d135_regen_try1_50011/`
- FAIL try2：`…/archive/failed_d135_regen_try2_60011/`

## D. 回滚后工作树

- d135 albedo / gate / 4x preview → 旧 PASS
- 未对照 fuse（规则：仅 PASS 后才 fuse）
- d180 未动；不交用户点2

## E. 请 opus 拍板

1. 是否改控制图/姿态再试（头切边像 depth 框裁）  
2. 是否加强负向「浮空碎片/硬切」或略升 depth scale  
3. 是否放弃 d135 源重生、改查投影结构  
4. **仍禁**整向假绿 / 程序化提亮贴图 / 自动解锁 d180
