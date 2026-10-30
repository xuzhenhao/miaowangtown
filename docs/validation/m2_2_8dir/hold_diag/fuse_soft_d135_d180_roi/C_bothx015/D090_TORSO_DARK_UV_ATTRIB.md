# d090 合拢板躯干暗斑 UV 归因（只读）

**fur file sha**: `7aa8d978f040…`
**集合**: fur alpha ∩ torso UV(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2. Absolute lum<40 nearly empty — false-hollow is relative on black bg. Authority=4x.
**rel_thr**: 92.33 (p10=92.33)
**n_dark_inner**: 5180（abs&lt;40: 14；d045 对照: 2946）

## 污染源判定（工作结论）

d270 对 d090 可见相对暗带仍有贡献；d090 源均亮 110.9 > rel_thr → 更像邻向拉低/加权平均

## 总写入权重占比（相对暗带上）

- **d180**: 21.03%（mean sample lum=84.37）
- **d135**: 17.21%（mean sample lum=84.54）
- **d225**: 16.62%（mean sample lum=71.26）
- **d090**: 12.86%（mean sample lum=110.91）
- **d045**: 11.13%（mean sample lum=68.39）
- **d000**: 8.47%（mean sample lum=76.92）
- **d270**: 8.39%（mean sample lum=66.69）
- **d315**: 4.28%（mean sample lum=126.05）

## pull-down 占比（源比 fused 更暗 ≥5）

- **d225**: 22.27%
- **d045**: 16.84%
- **d135**: 15.88%
- **d180**: 14.47%
- **d000**: 12.35%
- **d270**: 11.47%
- **d090**: 5.8%
- **d315**: 0.92%

## abs dark_sample（源 lum&lt;40）占比

- **d225**: 65.39%
- **d090**: 14.9%
- **d000**: 5.65%
- **d045**: 4.8%
- **d135**: 4.76%
- **d270**: 3.16%
- **d315**: 1.21%
- **d180**: 0.14%

## 下一步（仍 HOLD）

- 禁止盲降 d090 权重；禁止再拧 view-weight。
- 同向主导 → 重生/修该向源；邻向 pull-down → graze/EDGE 小对照，保留旧候选。
- d270 维持回滚 PASS `98a81074…`；本档只动 NDOTV_GRAZE（EDGE 不动）。
- overlay: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_d180_roi/C_bothx015/d090_torso_dark_uv_attrib_overlay.png`
- json: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_d180_roi/C_bothx015/d090_torso_dark_uv_attrib.json`
