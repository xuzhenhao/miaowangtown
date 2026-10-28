# Innerscene Path B · 第一轮调咩咩（五印记 + DNA 滑条）

日期：2026-10-28（Asia/Shanghai）  
底座：`docs/validation/innerscene_intake/out_b` → 隔离加工 `docs/validation/innerscene_miemie_v1/`  
许可底座：Innerscene Standing Cat **CC0**（Rest 关已 PASS，见 `INNERSCENE_STANDING_CAT_INTAKE.md`）  
管线：`MIEMIE_PHOTO_EXTRACTED_DNA` → `translateSemanticMarkings(restMap)` → `coatBaker.bakeCoat`；ShapeKey=`headRound/weight/earSize/...`

> **生产母版未覆盖。** 全程临时 swap `prototype/public/base` → 测完从 `smoke_backup/` 还原；`assets/cat_base.glb` 未改。

---

## 1. 结论（制作人一行）

**CONDITIONAL PASS（第一轮对照可过，不建议直接盖生产）。**  
五印记在引擎里**一眼能对上至少 4/5**（肚皮暖橘斑、左腹白云、前白袜+后虎纹短袜、翠绿眼/砖红鼻稳；阴阳嘴套焦糖侧偏弱）。DNA 滑条 `earSize`/`weight` 有可见形态差，`headRound` 有但更轻。脸锚/眼贴片仍漂，权重 shear/belly 未清零。

| 门 | 结果 |
|---|---|
| 隔离产出（不盖生产） | **PASS** |
| 复用 semanticMarkings + coatBaker（非 fillRect 糊弄） | **PASS**（33 条 Marking；atlas 有棕/白/深棕/暖橘） |
| 五印记 ≥3/5 一眼可对 | **PASS（约 4/5）** |
| DNA 滑条可见形态差 | **PASS**（earSize / weight 明显；headRound 弱） |
| 可推进生产母版替换 | **NO**（脸锚、嘴套精调、权重仍欠） |
| 生产干净 | **PASS**（§6 sha256） |

一句话：**Innerscene 站姿底座 + 语义印记烤图路线跑通；像度够开第二轮精调，不够直接上生产线。**

---

## 2. 五印记诚实自评

| # | 印记 | 目视 | 说明 |
|---|---|---|---|
| 1 | 右满左浅嘴套 / 偏左白火焰 + 阴阳嘴套 | **PARTIAL** | 白火焰与不对称可见；猫右焦糖嘴套饱和度/边界弱于真照片 |
| 2 | 左腹通背白云 | **PASS** | `idle_side_left` / 对照拼图清晰 |
| 3 | 肚皮正中央独立小暖橘圆斑 | **PASS** | `belly_view` + atlas 中央暖橘点 |
| 4 | 前过膝白袜（右前内侧暖金）+ 后虎纹花裤衩短白袜 | **PASS** | 前袜、后纹、短袜可读；暖金斑偏淡但在 |
| 5 | 翠绿眼 `#8FB369` + 砖红粉鼻 `#C85A48` | **PASS** | 色值到位；眼 billboard 相对头骨仍有漂/偏（脸锚未重标定） |

参考拼图：`innerscene_miemie_v1/compare_photo_vs_engine.png`、`markings_views_sheet.png`、`compare_front45.png`。

---

## 3. 做了什么（隔离目录）

路径根：`docs/validation/innerscene_miemie_v1/`

| 产物 | 说明 |
|---|---|
| `cat_base.glb` + `bones.json` | Path B 统一单材质 + **按 `_PART` 重排到 PART 图集 UV**（保留 ShapeKey/蒙皮）；原 Innerscene 纯色 UV 无法喂 coatBaker |
| `prepare_unified_base.py` / `remap_uv_to_part_atlas.py` | 可复现加工脚本 |
| `miemie_dna_v1.json` | 目标 shape/眼鼻记录 |
| `miemie_dna_runtime.json` | 引擎提取后完整 DNA（33 markings） |
| `coat_atlas_512.png` / `miemie_coat_atlas.png` | coatBaker 烘焙图集 |
| `idle_*.png` / `belly_view.png` | 引擎隔离截图 |
| `dna_*.png` + `dna_sliders_sheet.png` | headRound / weight / earSize 三档 |
| `compare_photo_vs_engine.png` | 真照片 vs 引擎三机位 |
| `capture_meta.json` / `prepare_meta.json` | 元数据 |

方法：临时 swap `public/base` → Vite + Playwright（`btnExtractPhotoDna` 回退内置 `MIEMIE_PHOTO_EXTRACTED_DNA`，关 faceProj 后 rebake，眼鼻改目标色）→ 还原。

---

## 4. DNA / ShapeKey

| 键 | 0 → mid → 1 | 可见差 |
|---|---|---|
| `earSize` | 小耳 → 默认 → 大耳 | **强** |
| `weight` | 偏瘦 → 默认 → 显圆肚 | **中强** |
| `headRound` | 略方 → 默认 → 略圆 | **弱～中** |

说明：ShapeKey 来自 Path B 调用的 `build_base.add_shape_keys`（按 `_PART` 启发式位移）；幅度与生产母版同量级但解剖对齐仍粗。

---

## 5. 缺什么 / 是否推进生产

**仍缺（挡生产）：**

1. 脸锚按 Innerscene 真实头骨重采样（眼/嘴贴片漂）  
2. 阴阳嘴套焦糖侧与真照片对齐（可开 faceProj 或加 denser muzzle 语义）  
3. Path B 自动权重 shear/belly 未清零（动作库精调另开）  
4. 多视角「一眼咩咩」产品验收（本轮仅工程对照）

**建议：**

- ✅ 继续以 `innerscene_miemie_v1/cat_base.glb` 为**隔离底座**做第二轮：脸锚 + 嘴套精调 + 可选轻量 faceProj  
- ❌ **不要**现在覆盖 `prototype/public/base` / `assets/cat_base.glb`  
- Grab3D 仍只做贴图/解剖对照，不回退迈步 Rest

---

## 6. 生产哈希（还原后）

```
8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0  prototype/public/base/cat_base.glb
1fbf37f76a05437f5aeb0d4e1c67b8361fdb88632e57bc925fe432d87df50bfc  prototype/public/base/bones.json
8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0  assets/cat_base.glb
```

与 intake 前、`smoke_backup/` 一致；`cmp` public↔assets 相同。

---

## 7. 复现摘要

```bash
# 1) 已有 out_b 时：统一材质 + PART atlas UV
blender --background --python docs/validation/innerscene_miemie_v1/prepare_unified_base.py
blender --background --python docs/validation/innerscene_miemie_v1/remap_uv_to_part_atlas.py
# 2) 备份并 swap public/base ← innerscene_miemie_v1/{cat_base.glb,bones.json}
# 3) Playwright：pet=mimi → 点「从 8 张照片提取」→ 设眼#8FB369/鼻#C85A48 → 隔离截图
# 4) 从 smoke_backup 还原 public/base
```
