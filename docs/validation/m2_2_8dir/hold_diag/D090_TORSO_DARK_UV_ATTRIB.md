# d090 合拢板躯干暗斑 UV 归因（只读）

**fur file sha**: `46e56675a577…`
**集合**: fur alpha ∩ torso UV(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2. Absolute lum<40 nearly empty — false-hollow is relative on black bg. Authority=4x.
**rel_thr**: 85.33 (p10=85.33)
**n_dark_inner**: 6283（abs&lt;40: 0；d045 对照: 2738）

## 污染源判定（工作结论）

d135 邻向 pull-down 30.05% → 查 EDGE/graze；d090 源均亮 124.7 > rel_thr → 更像邻向拉低/加权平均

## 总写入权重占比（相对暗带上）

- **d135**: 25.52%（mean sample lum=68.98）
- **d180**: 24.66%（mean sample lum=69.54）
- **d090**: 16.77%（mean sample lum=124.65）
- **d225**: 14.39%（mean sample lum=80.47）
- **d045**: 7.78%（mean sample lum=61.13）
- **d270**: 5.31%（mean sample lum=107.03）
- **d000**: 4.12%（mean sample lum=75.98）
- **d315**: 1.46%（mean sample lum=119.88）

## pull-down 占比（源比 fused 更暗 ≥5）

- **d180**: 30.79%
- **d135**: 30.05%
- **d225**: 15.72%
- **d045**: 13.12%
- **d000**: 4.76%
- **d270**: 3.23%
- **d090**: 1.93%
- **d315**: 0.39%

## abs dark_sample（源 lum&lt;40）占比

- **d225**: 52.94%
- **d135**: 31.8%
- **d045**: 4.81%
- **d000**: 4.42%
- **d090**: 4.29%
- **d315**: 1.1%
- **d180**: 0.4%
- **d270**: 0.24%

## 下一步（仍 HOLD）

- 禁止盲降 d090 权重。
- 同向主导 → 重生/修该向源；邻向 pull-down → 小对照 EDGE/graze，保留旧候选。
- d270 维持回滚 PASS `98a81074…`；graze0.35 对照已跑并回退（见 `edge_graze_035/`）。
- overlay: `docs/validation/m2_2_8dir/hold_diag/d090_torso_dark_uv_attrib_overlay.png`
- json: `docs/validation/m2_2_8dir/hold_diag/d090_torso_dark_uv_attrib.json`
