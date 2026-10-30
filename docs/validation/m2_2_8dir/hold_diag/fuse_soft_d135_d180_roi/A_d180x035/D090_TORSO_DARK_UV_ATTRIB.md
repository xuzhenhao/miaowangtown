# d090 合拢板躯干暗斑 UV 归因（只读）

**fur file sha**: `4bff2093c2da…`
**集合**: fur alpha ∩ torso UV(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2. Absolute lum<40 nearly empty — false-hollow is relative on black bg. Authority=4x.
**rel_thr**: 91.00 (p10=91.00)
**n_dark_inner**: 6110（abs&lt;40: 0；d045 对照: 3158）

## 污染源判定（工作结论）

d135 邻向 pull-down 29.55% → 查 EDGE/graze；d090 源均亮 116.6 > rel_thr → 更像邻向拉低/加权平均

## 总写入权重占比（相对暗带上）

- **d135**: 23.1%（mean sample lum=67.12）
- **d180**: 22.76%（mean sample lum=80.16）
- **d090**: 15.54%（mean sample lum=116.61）
- **d225**: 14.01%（mean sample lum=71.9）
- **d045**: 9.17%（mean sample lum=67.03）
- **d000**: 6.38%（mean sample lum=77.36）
- **d270**: 6.03%（mean sample lum=66.47）
- **d315**: 3.0%（mean sample lum=125.41）

## pull-down 占比（源比 fused 更暗 ≥5）

- **d135**: 29.55%
- **d180**: 21.77%
- **d225**: 15.84%
- **d045**: 12.37%
- **d000**: 7.85%
- **d270**: 7.63%
- **d090**: 4.38%
- **d315**: 0.61%

## abs dark_sample（源 lum&lt;40）占比

- **d225**: 50.14%
- **d135**: 27.86%
- **d090**: 11.27%
- **d000**: 4.23%
- **d045**: 4.04%
- **d270**: 1.29%
- **d315**: 0.92%
- **d180**: 0.25%

## 下一步（仍 HOLD）

- 禁止盲降 d090 权重；禁止再拧 view-weight。
- 同向主导 → 重生/修该向源；邻向 pull-down → graze/EDGE 小对照，保留旧候选。
- d270 维持回滚 PASS `98a81074…`；本档只动 NDOTV_GRAZE（EDGE 不动）。
- overlay: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_d180_roi/A_d180x035/d090_torso_dark_uv_attrib_overlay.png`
- json: `docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_d180_roi/A_d180x035/d090_torso_dark_uv_attrib.json`
