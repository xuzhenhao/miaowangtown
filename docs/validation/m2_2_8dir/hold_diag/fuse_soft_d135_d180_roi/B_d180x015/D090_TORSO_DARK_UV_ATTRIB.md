# d090 合拢板躯干暗斑 UV 归因（只读）

**fur file sha**: `437dedde6df6…`
**集合**: fur alpha ∩ torso UV(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2. Absolute lum<40 nearly empty — false-hollow is relative on black bg. Authority=4x.
**rel_thr**: 91.00 (p10=91.00)
**n_dark_inner**: 6022（abs&lt;40: 0；d045 对照: 3101）

## 污染源判定（工作结论）

d135 邻向 pull-down 29.02% → 查 EDGE/graze；d090 源均亮 116.4 > rel_thr → 更像邻向拉低/加权平均

## 总写入权重占比（相对暗带上）

- **d135**: 23.07%（mean sample lum=67.06）
- **d180**: 22.74%（mean sample lum=80.63）
- **d090**: 15.53%（mean sample lum=116.38）
- **d225**: 14.01%（mean sample lum=71.03）
- **d045**: 9.22%（mean sample lum=67.08）
- **d000**: 6.41%（mean sample lum=77.59）
- **d270**: 6.04%（mean sample lum=66.38）
- **d315**: 3.0%（mean sample lum=125.42）

## pull-down 占比（源比 fused 更暗 ≥5）

- **d135**: 29.02%
- **d180**: 21.66%
- **d225**: 16.2%
- **d045**: 12.52%
- **d000**: 7.91%
- **d270**: 7.57%
- **d090**: 4.49%
- **d315**: 0.62%

## abs dark_sample（源 lum&lt;40）占比

- **d225**: 50.21%
- **d135**: 27.85%
- **d090**: 11.29%
- **d000**: 4.23%
- **d045**: 4.0%
- **d270**: 1.29%
- **d315**: 0.92%
- **d180**: 0.2%

## 下一步（仍 HOLD）

- 禁止盲降 d090 权重；禁止再拧 view-weight。
- 同向主导 → 重生/修该向源；邻向 pull-down → graze/EDGE 小对照，保留旧候选。
- d270 维持回滚 PASS `98a81074…`；本档只动 NDOTV_GRAZE（EDGE 不动）。
- overlay: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_d180_roi/B_d180x015/d090_torso_dark_uv_attrib_overlay.png`
- json: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_d180_roi/B_d180x015/d090_torso_dark_uv_attrib.json`
