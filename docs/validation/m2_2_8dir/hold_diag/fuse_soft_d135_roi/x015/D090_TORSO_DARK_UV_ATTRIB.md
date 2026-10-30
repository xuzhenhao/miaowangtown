# d090 合拢板躯干暗斑 UV 归因（只读）

**fur file sha**: `0bdade2ad2fe…`
**集合**: fur alpha ∩ torso UV(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2. Absolute lum<40 nearly empty — false-hollow is relative on black bg. Authority=4x.
**rel_thr**: 90.67 (p10=90.67)
**n_dark_inner**: 5969（abs&lt;40: 10；d045 对照: 2678）

## 污染源判定（工作结论）

d135 邻向 pull-down 22.23% → 查 EDGE/graze；d090 源均亮 115.0 > rel_thr → 更像邻向拉低/加权平均

## 总写入权重占比（相对暗带上）

- **d180**: 24.7%（mean sample lum=69.57）
- **d135**: 21.73%（mean sample lum=77.05）
- **d225**: 16.8%（mean sample lum=82.43）
- **d090**: 13.47%（mean sample lum=115.05）
- **d045**: 7.98%（mean sample lum=65.33）
- **d270**: 6.97%（mean sample lum=71.04）
- **d000**: 5.66%（mean sample lum=77.94）
- **d315**: 2.7%（mean sample lum=124.28）

## pull-down 占比（源比 fused 更暗 ≥5）

- **d180**: 29.15%
- **d135**: 22.23%
- **d225**: 16.62%
- **d045**: 11.97%
- **d270**: 7.71%
- **d000**: 7.47%
- **d090**: 4.24%
- **d315**: 0.62%

## abs dark_sample（源 lum&lt;40）占比

- **d225**: 60.62%
- **d090**: 13.65%
- **d135**: 12.96%
- **d000**: 5.07%
- **d045**: 4.72%
- **d270**: 1.45%
- **d315**: 1.15%
- **d180**: 0.38%

## 下一步（仍 HOLD）

- 禁止盲降 d090 权重；禁止再拧 view-weight。
- 同向主导 → 重生/修该向源；邻向 pull-down → graze/EDGE 小对照，保留旧候选。
- d270 维持回滚 PASS `98a81074…`；本档只动 NDOTV_GRAZE（EDGE 不动）。
- overlay: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_roi/x015/d090_torso_dark_uv_attrib_overlay.png`
- json: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_roi/x015/d090_torso_dark_uv_attrib.json`
