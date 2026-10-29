# M2.1 制作人自审摘要

## 结论
M2.1 本地已跑通，**四条门禁全 PASS**，色板定案 **`quantize_mode=none`**。未 push，请过目三张主检视板后拍板是否进 M2.2。

## 路径
- 基因/印记：`cats/miemie/identity_v1/{genome,markings}.json`
- 反照率/覆盖：`cats/miemie/identity_v1/{fur_albedo,coverage}.png`
- 门禁报告：`docs/validation/m2_1_d045/m2_1_gates_report.json`
- 渲染规格：`art/master_cat/render_spec.json`（`quantize_mode` 已非 `pending_m2_1_experiment`）

## 四条门禁数值
1. 头身剪影 max_d **2.0** px / outliers **0** / IoU **0.9521**
2. 五印记零换侧 **PASS**（`_R` 焦糖画面左；`_L` 白云侧未互换）
3. 白爪灰边 **2** px（阈值宽松通过）
4. 眼 睑**26** / 外翠**21** / 内亮**26** / 瞳**40** / 高光**10**

## 色板定案
`none`（真彩）优于 lut36/lut48；`dither=none`；2048 `fur_albedo` 不量化。

## 制作人自审备注
- Layer B 与 v4.1 同机位观感接近；灯笼暖光 + 腹底 AO 只加一次。
- d045 单视角 coverage 绿+黄约占岛内 32.6%，红未见留给 M2.2 互补视角，符合计划。
- M1 拓扑 / `uv_hash` 未动。
