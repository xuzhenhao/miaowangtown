# d090 合拢板躯干暗斑 UV 归因（只读）

**fur file sha**: `7c5292bfd1e2…`
**集合**: fur alpha ∩ torso UV(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2. Absolute lum<40 nearly empty — false-hollow is relative on black bg. Authority=4x.
**rel_thr**: 90.67 (p10=90.67)
**n_dark_inner**: 6228（abs&lt;40: 1；d045 对照: 2861）

## 污染源判定（工作结论）

d135 邻向 pull-down 23.7% → 查 EDGE/graze；d090 源均亮 116.0 > rel_thr → 更像邻向拉低/加权平均

## 总写入权重占比（相对暗带上）

- **d180**: 24.64%（mean sample lum=69.58）
- **d135**: 22.25%（mean sample lum=75.29）
- **d225**: 16.44%（mean sample lum=83.08）
- **d090**: 13.88%（mean sample lum=116.04）
- **d045**: 7.94%（mean sample lum=65.06）
- **d270**: 6.76%（mean sample lum=71.11）
- **d000**: 5.5%（mean sample lum=78.21）
- **d315**: 2.6%（mean sample lum=124.27）

## pull-down 占比（源比 fused 更暗 ≥5）

- **d180**: 29.4%
- **d135**: 23.7%
- **d225**: 15.8%
- **d045**: 11.81%
- **d270**: 7.62%
- **d000**: 7.08%
- **d090**: 4.01%
- **d315**: 0.59%

## abs dark_sample（源 lum&lt;40）占比

- **d225**: 59.47%
- **d135**: 14.6%
- **d090**: 13.37%
- **d000**: 4.97%
- **d045**: 4.7%
- **d270**: 1.42%
- **d315**: 1.12%
- **d180**: 0.35%

## 下一步（仍 HOLD）

- 禁止盲降 d090 权重；禁止再拧 view-weight。
- 同向主导 → 重生/修该向源；邻向 pull-down → graze/EDGE 小对照，保留旧候选。
- d270 维持回滚 PASS `98a81074…`；本档只动 NDOTV_GRAZE（EDGE 不动）。
- overlay: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_roi/x035/d090_torso_dark_uv_attrib_overlay.png`
- json: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_roi/x035/d090_torso_dark_uv_attrib.json`
