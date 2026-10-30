# d270 重生状态（制作人待审）

**时间**：2026-10-30（Asia/Shanghai）  
**tip 起点**：`07e872d`  
**结论**：**仍 CONDITIONAL HOLD**。未冻、未开 M3、未程序化填红、**未**自动 fuse、**未**自行 PASS。

## A. d270 重生

| 项 | 旧 | 新 |
|---|---|---|
| archive | `complementary_albedos/archive/pre_d270_regen_07e872d/` | — |
| size | 1194725 | 223255 |
| sha256 | `98a8107477fd…` | `567f2b113630…` |
| seed | 20261754（旧报告） | **20302032** |
| seed_offset | （初跑/无 offset） | **40011** |
| CLIP | — | tokens=**77**, truncated_at_77=**False**（硬头保住） |
| torso dark&lt;40 率（depth+ROI+内缩2） | **6.29%** | **6.24%**（几乎未降） |
| torso dark&lt;25 率 | 2.25% | **1.04%**（有改善） |
| torso lum p05 / p50 | 36.7 / 100.3 | 37.3 / **128.0** |

- 4x preview：`docs/validation/m2_2_8dir/gates_preview_d270_4x.png`
- gate JSON：**pass=false**（等制作人 `--human-pass`）
- log：`logs/m22/regen_d270_20261030_123722.log`

## PASS 锁（其它六向未变）

见 `logs/m22/pass_sha_before_d270_regen_07e872d.txt` ↔ `logs/m22/pass_sha_after_d270_regen.txt`：  
d000/d090/d135/d180/d225/d315 **sha 全匹配**。d045 锚点未动。

## B. Fuse 边缘笔记

`hold_diag/FUSE_EDGE_SAMPLING_NOTE.md`：EDGE_ERODE=10 只挡外轮廓；岛内近黑/邻向 graze 仍可写入。最小改法：先脏源→归因→再考虑 EDGE/graze 小对照；**禁止再拧权重**。

## C. d090 躯干相对暗斑 UV 归因

- 报告：`hold_diag/D090_TORSO_DARK_UV_ATTRIB.md` + `d090_torso_dark_uv_attrib.json`
- 集合：d090 可见躯干 UV 上 fused_lum ≤ max(p10,85)≈**85.3**（绝对 lum&lt;40 几乎为空 → 假透空是相对暗）
- **污染源**：d090 源均亮 **124.7**；pull-down 主责 **d180≈30.8% / d135≈30.1%**（其次 d225/d045）；**禁止盲降 d090**
- 权重榜（相对暗带）：d135 25.5% / d180 24.7% / d090 16.8%

## 下一步

1. 制作人审 `gates_preview_d270_4x.png`（本代理不自 PASS）
2. 按归因：优先查 **d135/d180** 是否把暗采样打进侧视躯干（EDGE/graze），而非降 d090
3. d270 门禁通过后再决定是否默认权重对照 fuse；旧候选 `46e56675…` 保留
4. 两硬门+合拢无 HOLD 前不交用户冻结
