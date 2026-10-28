# Innerscene Path B · 第二轮调咩咩（脸锚 + 阴阳嘴套 + 权重）

日期：2026-10-28（Asia/Shanghai）  
底座：`docs/validation/innerscene_miemie_v1/` → 隔离精修 `docs/validation/innerscene_miemie_v2/`  
许可：Innerscene Standing Cat **CC0**  
前置：`INNERSCENE_MIEMIE_V1.md`（CONDITIONAL PASS，五印记约 4/5，嘴套焦糖弱，脸锚漂，shear/belly 非 0）

> **生产母版未覆盖。** 临时 swap `prototype/public/base` → 测完从 `smoke_backup/` 还原；`assets/cat_base.glb` 未改。

---

## 1. 结论（制作人一行）

**CONDITIONAL PASS（第二轮工程门过，仍不建议直接盖生产）。**  
脸锚按 Innerscene 头骨重采样后眼贴片明显贴面（不再套生产模板 y=0.895/z≈0.79）；阴阳嘴套焦糖侧一眼好于 v1；`skin_audit` **shear 33→0 / belly 97→0 / seam 0**。walk/sit 能挂、不碎腿级，但侧视仍有自动权重带来的躯干锯齿。生产哈希未变。

| 门 | 结果 |
|---|---|
| 隔离产出（不盖生产） | **PASS** |
| 脸锚贴 Innerscene 头/嘴表面 | **PASS**（眼 ±0.086 / y≈0.771 / z≈0.625；嘴 y≈0.677 / z≈0.668） |
| 嘴套焦糖一眼好于 v1 | **PASS**（见 `muzzle_before_after.png`） |
| 五印记 | **约 5/5 可读**（嘴套从 PARTIAL→PASS；其余维持） |
| skin_audit shear/belly → 0 | **PASS**（0 / 0） |
| walk/sit 冒烟不碎腿 | **PASS（有条件）** — 不碎肢；侧视躯干仍锯齿 |
| 可推进生产母版替换 | **NO**（耳骨高度异常、walk 视觉打磨、产品多视角验收未做） |
| 生产干净 | **PASS**（§6） |

一句话：**脸锚+嘴套+权重审计三块达标；通用底座可继续当隔离母版打第三轮（耳骨/walk 视觉），不要盖生产。**

---

## 2. 五印记诚实自评（相对 v1）

| # | 印记 | v1 | v2 | 说明 |
|---|---|---|---|---|
| 1 | 右满左浅嘴套 / 偏左白火焰 + 阴阳嘴套 | PARTIAL | **PASS** | denser caramel blobs + 修正 mouth 锚后烤点落在真嘴套；特写可见焦糖侧 |
| 2 | 左腹通背白云 | PASS | **PASS** | `idle_side_left` |
| 3 | 肚皮正中央独立小暖橘圆斑 | PASS | **PASS** | `belly_view` |
| 4 | 前白袜 + 后虎纹短袜 | PASS | **PASS** | 维持 |
| 5 | 翠绿眼 + 砖红鼻 | PASS（眼漂） | **PASS** | 色值同；眼锚贴面，漂明显改善（billboard+DECAL_LIFT 仍有微抬） |

参考：`muzzle_before_after.png`、`compare_photo_vs_engine.png`、`markings_views_sheet.png`。

---

## 3. 脸锚重标定

| | v1（错） | v2（按网格） |
|---|---|---|
| eyeL | `[0.108, 0.895, 0.793]` | `[0.0864, 0.77126, 0.62479]` |
| eyeR | `[-0.108, 0.895, 0.793]` | `[-0.0864, 0.77126, 0.62479]` |
| mouth | `[0, 0.82, 0.60859]` | `[0, 0.67661, 0.6683]` |

根因：v1/Path B 调用 `build_base.compute_face_anchors`，目标点写死生产母版尺度；Innerscene 头 bbox 仅 y∈[0.65,0.87]、zmax≈0.66，锚点落在网格外 → 眼贴片漂、嘴套语义中心错位。

方法：`refine_face_and_weights.py` 按 `_PART` head/muzzle 表面重采样 + 强制眼距 ±0.085 + 注入 glTF `extras.faceAnchors`。元数据：`face_anchors_meta.json`。

---

## 4. 权重清理

| 指标 | before（v1 底座） | after（v2） |
|---|---|---|
| `uv_seam_weight_mismatches` | 0 | **0** |
| `upper_leg_shear` | **33** | **0** |
| `belly_midline_leakage` | **97** | **0** |

做法：上腿 paw 权重迁到 elbow/knee+shoulder/hip；肚皮中线肢权重迁到 spine/hips/chest；UV 缝副本权重平均。审计定义同 `render_validation.audit_weights`。

诚实下限：审计带是启发式区间；清零≠walk 侧视完美。`smoke_walk`/`smoke_sit` 仍见躯干/衔接锯齿（自动权重遗留 + 贴图分区），但不属「碎腿」。

产物：`skin_audit_before.json` / `skin_audit_after.json` / `skin_audit_final.json`。

---

## 5. 嘴套精调

在 `btnExtractPhotoDna` 语义印记之上，捕获脚本按**新 mouth/eye 锚**追加 denser caramel / 胡须点 / 左火焰强化 / 左唇浅杏（+7 blobs → 共 40 markings）。未永久改 `semanticMarkings.ts`。

---

## 6. 生产哈希（还原后）

```
8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0  prototype/public/base/cat_base.glb
1fbf37f76a05437f5aeb0d4e1c67b8361fdb88632e57bc925fe432d87df50bfc  prototype/public/base/bones.json
8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0  assets/cat_base.glb
```

与 v1 §6 / `smoke_backup/` / `prod_sha_after.json` 一致。

---

## 7. 产物清单

路径根：`docs/validation/innerscene_miemie_v2/`

| 产物 | 说明 |
|---|---|
| `cat_base.glb` + `bones.json` | 脸锚重标定 + 权重清理后的隔离底座 |
| `refine_face_and_weights.py` | 可复现精修 |
| `face_anchors_meta.json` | 新旧锚对比 |
| `skin_audit_*.json` | 权重前后 |
| `idle_*.png` / `belly_view.png` / `muzzle_close_*.png` | 引擎截图 |
| `smoke_{idle,walk,sit}.png` + `smoke_sheet.png` | 动作冒烟 |
| `muzzle_before_after.png` | 真照片 / v1 / v2 嘴套对照 |
| `compare_photo_vs_engine.png` | 五印记机位对照 |
| `capture_playwright.mjs` / `capture_meta.json` | 捕获脚本与元数据 |
| `miemie_dna_runtime.json` / `coat_atlas_512.png` | 运行时 DNA + 烤图 |

---

## 8. 仍缺 / 是否推进生产

**仍缺（挡生产）：**

1. Path B 耳骨 y≈1.18 vs 耳网格 y≈0.75–0.93（`earSize` 滑条与耳皮可能漂）  
2. walk/sit 侧视躯干锯齿的视觉打磨（非审计指标）  
3. 多视角「一眼咩咩」产品验收  
4. denser muzzle 仍是捕获期注入，未回写通用 `semanticMarkings` 适配层

**建议：**

- ✅ 继续以 `innerscene_miemie_v2/cat_base.glb` 为隔离母版开第三轮：修耳骨高度 + walk 视觉  
- ❌ **不要**现在覆盖 `prototype/public/base` / `assets/cat_base.glb`

---

## 9. 复现摘要

```bash
blender --background --python docs/validation/innerscene_miemie_v2/refine_face_and_weights.py
# （可选）widen eyes 已写入当前 cat_base.glb
# 备份并 swap public/base ← innerscene_miemie_v2/{cat_base.glb,bones.json}
node docs/validation/innerscene_miemie_v2/capture_playwright.mjs
# 脚本 finally 会从 smoke_backup 还原 public/base
```
