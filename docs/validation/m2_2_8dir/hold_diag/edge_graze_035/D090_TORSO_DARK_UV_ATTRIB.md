# d090 合拢板躯干暗斑 UV 归因（只读）

**fur file sha**: `1dc3b5b5551a…`
**集合**: fur alpha ∩ torso UV(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2. Absolute lum<40 nearly empty — false-hollow is relative on black bg. Authority=4x.
**rel_thr**: 87.67 (p10=87.67)
**n_dark_inner**: 5534（abs&lt;40: 3；d045 对照: 1875）

## 污染源判定（工作结论）

d135 邻向 pull-down 28.45% → 查 EDGE/graze；d090 源均亮 116.6 > rel_thr → 更像邻向拉低/加权平均

## 总写入权重占比（相对暗带上）

- **d180**: 25.92%（mean sample lum=70.32）
- **d135**: 25.81%（mean sample lum=70.08）
- **d225**: 15.68%（mean sample lum=77.87）
- **d090**: 15.39%（mean sample lum=116.59）
- **d045**: 6.24%（mean sample lum=62.65）
- **d270**: 5.95%（mean sample lum=71.16）
- **d000**: 3.83%（mean sample lum=78.11）
- **d315**: 1.19%（mean sample lum=121.87）

## pull-down 占比（源比 fused 更暗 ≥5）

- **d180**: 30.8%
- **d135**: 28.45%
- **d225**: 16.06%
- **d045**: 9.13%
- **d270**: 6.14%
- **d000**: 4.81%
- **d090**: 4.33%
- **d315**: 0.29%

## abs dark_sample（源 lum&lt;40）占比

- **d225**: 54.3%
- **d135**: 25.2%
- **d090**: 12.35%
- **d000**: 4.24%
- **d045**: 3.33%
- **d180**: 0.23%
- **d315**: 0.2%
- **d270**: 0.14%

## 下一步（仍 HOLD）

- 禁止盲降 d090 权重；禁止再拧 view-weight。
- 同向主导 → 重生/修该向源；邻向 pull-down → graze/EDGE 小对照，保留旧候选。
- d270 维持回滚 PASS `98a81074…`；本档只动 NDOTV_GRAZE（EDGE 不动）。
- overlay: `docs/validation/m2_2_8dir/hold_diag/edge_graze_035/d090_torso_dark_uv_attrib_overlay.png`
- json: `docs/validation/m2_2_8dir/hold_diag/edge_graze_035/d090_torso_dark_uv_attrib.json`
