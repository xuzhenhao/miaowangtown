# Innerscene Path B · 第三轮调咩咩（耳骨高度 + walk 视觉打磨）

日期：2026-10-28（Asia/Shanghai）  
底座：`docs/validation/innerscene_miemie_v2/` → 隔离精修 `docs/validation/innerscene_miemie_v3/`  
许可：Innerscene Standing Cat **CC0**  
前置：`INNERSCENE_MIEMIE_V2.md`（CONDITIONAL PASS；耳骨 y≈1.18 漂、walk 侧视躯干锯齿）

> **生产母版未覆盖。** 临时 swap `prototype/public/base` → 测完从 `smoke_backup/` 还原；`assets/cat_base.glb` 未改。

---

## 1. 结论（制作人一行）

**CONDITIONAL PASS（第三轮工程门过；建议交用户肉眼；仍不盖生产）。**  
耳骨从误绑尾巴高点（y≈1.176）重定位到真耳根（y≈0.811，part8/9）；`earSize` 形态键从「拉尾巴」改成缩放真耳；walk 侧视躯干锯齿/肩腹衔接经权重软化后目视好于 v2。`skin_audit` seam/shear/belly **维持 0**。生产哈希未变。

| 门 | 结果 |
|---|---|
| 隔离产出（不盖生产） | **PASS** |
| 耳骨贴合耳网格 / 朝向耳尖 | **PASS**（earL/R head≈[±0.100, 0.811, 0.523] → tip） |
| DNA `earSize` 0/mid/1 仍可用 | **PASS**（峰值位移落在 part8 耳尖，不再 part10 尾） |
| walk 侧视明显好于 v2 | **PASS（肉眼）** — 见 `compare_v2_v3_walk.png` / `walk_side_sheet.png` |
| walk/sit 冒烟不碎腿 | **PASS** |
| skin_audit 保持 0 | **PASS**（0 / 0 / 0） |
| 建议交用户肉眼 | **YES** |
| 可推进生产母版替换 | **NO**（见 §8） |
| 生产干净 | **PASS**（§6） |

一句话：**耳骨+earSize+walk 视觉三块达标到可交用户肉眼；通用底座仍留隔离目录，不要盖生产。**

---

## 2. 耳骨根因与修正

**根因（实锤）：** Path B `top-verts` 启发式把 **尾巴 part10**（y 最高达 1.25）当成耳；landmarks 写成 `earL≈(0.04,1.17,-0.60)`。对称化后骨落到 y≈1.176、z≈-0.02 —— 悬空于头上后方。同时：

- 耳网格 part8/9 实际 y∈**[0.754, 0.932]**、z∈**[0.35, 0.63]**
- v2 网格上 **ear 权重 >0.1 的顶点 = 0**（耳全跟 head）
- `earSize` 形态键沿用生产阈值 `y>0.98` → **最大位移在尾巴**（disp≈0.23 @ y≈1.08,z≈-0.65）

**修正（`refine_ears_and_walk.py`）：**

1. 按 `_PART` 8/9 量 tip/base，骨头放在耳根偏上（base→tip 28%），尾朝耳尖  
2. 重绑耳权重（484 verts ear 影响；近 tip 偏 ear、近根偏 head）  
3. 重建 `earSize`：只动 part8/9（+头侧微晕），峰值 disp≈0.032 @ 真耳尖  

| | v2（错） | v3 |
|---|---|---|
| earL head | `[0.082, 1.176, -0.024]` | `[0.100, 0.811, 0.523]` |
| earR head | `[-0.082, 1.176, -0.024]` | `[-0.100, 0.811, 0.523]` |
| earSize 峰值 part | 10（尾） | **8（耳）** |

元数据：`ear_fix_meta.json`。对照：`compare_ear_before_after.png`、`dna_earSize_sheet.png`。

---

## 3. walk 视觉打磨

**未改** `walk.ts` 动作幅度（避免影响生产动作库）。只在隔离底座做权重软化：

| 操作 | 次数 |
|---|---|
| shoulder↔chest 侧腹/上肢根混合 | 126 |
| hip↔hips+spine 后腹混合 | 12 |
| 中躯单骨尖峰摊平 | 421 |
| body 误带 elbow/knee/paw 迁回 | 403 |

诚实根因：侧视锯齿主要来自 **自动权重在肩/胸/腹侧的硬过渡** + walk 里 hips/spine/chest 的 bob；不是碎腿。清 shear/belly≠侧视完美；v3 目视折痕减轻，肩腹仍可能有轻微分界线（贴图分区+低模）。

元数据：`walk_polish_meta.json`。对照：`compare_v2_v3_walk.png`、`walk_side_sheet.png`、`smoke_sheet.png`。

---

## 4. 冒烟与 DNA

| 项 | 结果 |
|---|---|
| idle / walk / sit 冒烟 | 不碎肢；坐姿正常 |
| earSize 0 / 0.45 / 1 | 耳变大可见，不拉尾 |
| 脸锚 | 继承 v2（眼/嘴未回退） |
| 五印记烤图 | 维持（捕获期 denser 嘴套同 v2） |

---

## 5. 生产哈希（还原后）

```
8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0  prototype/public/base/cat_base.glb
1fbf37f76a05437f5aeb0d4e1c67b8361fdb88632e57bc925fe432d87df50bfc  prototype/public/base/bones.json
8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0  assets/cat_base.glb
```

与 v2 §6 / `smoke_backup/` / `prod_sha_after.json` 一致（`match: true`）。

---

## 6. 产物清单

路径根：`docs/validation/innerscene_miemie_v3/`

| 产物 | 说明 |
|---|---|
| `cat_base.glb` + `bones.json` | 耳骨+权重+earSize 重建后的隔离底座 |
| `cat_base_src.glb` / `bones_src.json` | v2 输入快照 |
| `refine_ears_and_walk.py` | 可复现精修 |
| `ear_fix_meta.json` / `walk_polish_meta.json` | 耳/walk 元数据 |
| `skin_audit_*.json` | 权重审计（终态含耳骨复验） |
| `idle_*.png` / `ear_close_*.png` | idle + 耳特写 |
| `dna_earSize_{0,0p45,1}.png` + `dna_earSize_sheet.png` | DNA 耳滑条 |
| `walk_side_f{0..3}.png` + `walk_side_sheet.png` | walk 侧视多帧 |
| `smoke_{idle,walk,sit}.png` + `smoke_sheet.png` | 动作冒烟 |
| `compare_ear_before_after.png` | 耳骨前后 |
| `compare_v2_v3_idle.png` / `compare_v2_v3_walk.png` | v2↔v3 对照（交肉眼主图） |
| `capture_playwright.mjs` / `capture_meta.json` | 捕获脚本与元数据 |

---

## 7. 是否交用户肉眼 / 仍缺 / 是否盖生产

**建议交用户肉眼：YES。**  
主图：`compare_v2_v3_idle.png`、`compare_ear_before_after.png`、`dna_earSize_sheet.png`、`compare_v2_v3_walk.png`、`walk_side_sheet.png`、`smoke_sheet.png`。

**仍缺（挡生产）：**

1. 其它形态键仍有生产阈值残留（如 `headRound` 峰值曾落在尾侧）— 本轮只重建了 `earSize`  
2. denser 阴阳嘴套仍是捕获期注入，未回写通用 `semanticMarkings` 适配层  
3. walk 侧视折痕减轻但未「产品级无痕」；未做多视角「一眼咩咩」产品验收  
4. 运行时骨骼调试 API 未暴露（捕获里 `skeleton.bones` 为空属探针问题，不影响蒙皮）

**建议：**

- ✅ 把本目录对照图交用户肉眼审「耳是否贴头、走路侧视是否可接受」  
- ❌ **不要**现在覆盖 `prototype/public/base` / `assets/cat_base.glb`

---

## 8. 复现摘要

```bash
blender --background --python docs/validation/innerscene_miemie_v3/refine_ears_and_walk.py
node docs/validation/innerscene_miemie_v3/capture_playwright.mjs
# 脚本 finally 会从 smoke_backup 还原 public/base
```
