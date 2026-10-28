# Innerscene Standing Cat（CC0）· Path B Intake + walk/sit 冒烟

日期：2026-10-28（Asia/Shanghai）  
资产：[Innerscene Standing cat](https://www.innerscene.com/tools/library/3d-parts/standing-cat-cda42538)  
许可证：**CC0 1.0**（本地 `reference/open_cat_bases/innerscene_standing_cat/LICENSE.txt`）  
对照：Grab3D Tabby（CC0，mid-stride HOLD）· BlenderKit Domestic Cat（RF，迈步 Rest HOLD）

> 本轮目标：**验证真站姿 Rest 能否破开**「开源写实猫底座」门禁。Grab3D / BlenderKit 只读对照，未再修其 Rest。

---

## 1. 结论（制作人一行）

**Rest 关已破开（PASS）。** 四爪对称触地 + 低不对称；Path B idle 为对称站立（非迈步）；walk/sit 可挂且未见 Grab3D 级碎腿。**可进入第一轮调咩咩**（在 Path B 灰模/纯色材质底座上；权重与脸锚仍需打磨，**不**直接盖生产母版）。

| 门 | 结果 |
|---|---|
| CC0 可复现落盘 | **PASS**（original + LICENSE + clean） |
| Rest 对称四足站立 | **PASS**（四爪触地均衡；p90_norm≈0.037 ≪ 0.08；idle 目视站立） |
| Path B 轻量（跳 Remesh + fit 26 骨 + L/R 对称） | **PASS 管线**（5153v / 10000t；UV+多材质槽保留；骨 L/R 全对称） |
| Path A `--input` Remesh | **PASS 管线**（~2920v / 5000t；灰模；skin 0/0/0） |
| 引擎 idle/walk/sit 可挂 | **PASS**（`source=glb`；B/A 均截图） |
| walk 不碎腿 / sit 可用 | **CONDITIONAL PASS**（相对 Grab3D 明显更好；B 自动权重 shear/belly 非 0；sit 后肢/尾需再调） |
| 可直接进咩咩第一轮 | **YES（调形/对照）** — 不替换生产 `public/base` |
| 生产干净 | **PASS**（§7 sha256） |

一句话：**Rest 关破开；可开第一轮调咩咩；生产母版未动。**

---

## 2. 相对 Grab3D / BlenderKit 对照

| 项 | Innerscene Standing | Grab3D Tabby | BlenderKit Domestic |
|---|---|---|---|
| 许可 | **CC0** | CC0 | Royalty Free（非 CC0） |
| 文档姿态 | alert standing | mid-stride | 略迈步 Rest |
| 触地簇 | **FL=FR≈624, HL=HR≈572** | FL=**0**, FR/HL/HR 不均 | 对角迈步主导 |
| 不对称 p90 | **0.029**（norm 0.037） | 0.209 | 高（见 BK 笔记） |
| Rest 门 | **PASS** | HOLD | HOLD |
| Path B UV/材质 | UV + **8 纯色材质槽**（无贴图图） | UV + 狸花贴图 | Remesh 掉 UV |
| 骨网尺度 | 贴骨 + 对称；身高→1.25 | 贴骨但写进迈步 | Remesh 后网/骨错位严重 |
| idle 目视 | **对称站立** | 对角瘸步 | 瘸步 |
| walk/sit | 可动，不碎级 | sit 碎裂/拉扯 | 后肢碎裂 |

根因一句话（承接 Grab3D 笔记）：**Rest 必须是对称四足站立**；Innerscene 首次同时满足 CC0 + 真站姿。

---

## 3. 原始资产与审计

| 文件 | 说明 |
|---|---|
| `reference/open_cat_bases/innerscene_standing_cat/cat-original.glb` | ~4.7MB / **102328** 顶点 / **203538** 三角 |
| `cat_clean.glb` | Decimate → **10000** 三角 / **5153** 顶点；保 UV/材质；脚底 z=0 |
| `LICENSE.txt` | CC0 1.0 |

审计：`docs/validation/innerscene_intake/innerscene_standing_cat_audit.json`  
清洁元数据：`clean_export_meta.json`

| 项 | 值 |
|---|---|
| 骨骼 | **无**（静态网格） |
| UV | 有（`UVMap`） |
| 材质 | 8 个 Principled 纯色槽（RGB 名 / white / black）；**无** baseColor 贴图 |
| 毛发粒子 | 无 |
| 姿态 | **alert standing** — 四爪触地 |
| 不对称 | median≈0.013，**p90≈0.029**，p90_norm≈**0.037** |
| Rest 启发式 | `four_paws=true` ∧ `p90_norm<0.08` → **likely_symmetric_standing=true** |

---

## 4. 两条 Intake

输出根：`docs/validation/innerscene_intake/`（**未盖**生产）

### Path B — 主路径（轻量）

脚本：`innerscene_intake/path_b_light_intake.py`（自 Grab3D Path B 改；**额外强制 L/R 骨对称**；不 copy `assets/`）

| 项 | 结果 |
|---|---|
| 产出 | `out_b/cat_base.glb` + fitted `bones.json`（26 骨） |
| 跳过 | Voxel Remesh / Smooth / 解剖雕刻 / UV 图集重建 |
| 归一化 | 身高 → 1.25，脚底 y=0；**保留材质** |
| 骨骼 | 按截面/触地点 fit；再 **symmetrize** 成对骨 + 中线 x=0 |
| 触地 paw（Three） | fpawL/R n=47；hpawL/R n=47；已 symmetrized |
| 权重 | `ARMATURE_AUTO` |
| 蒙皮审计 | seam=**0** / shear=**30** / belly=**72** → `skin_audit_b.json` |
| bbox Three span | ≈ [0.52, 1.25, 1.33] |

### Path A — 对照（现有 `build_base.py --input`）

```bash
cd prototype
blender --background --python tools/blender/build_base.py -- \
  --input reference/open_cat_bases/innerscene_standing_cat/cat_clean.glb \
  --out-dir docs/validation/innerscene_intake/out_a
# 脚本会 copy → assets/cat_base.glb；本轮已立即从备份还原（见 §7）
```

| 项 | 结果 |
|---|---|
| 产出 | `out_a/cat_base.glb`（~2920v / **5000**t）+ 模板位姿 `bones.json` |
| 材质/UV | Remesh 后 **灰模**（引擎 DNA 涂层仍可画在上面） |
| 蒙皮审计 | seam=**0** / shear=**0** / belly=**0** → `skin_audit_a.json` |

---

## 5. 引擎 walk/sit 冒烟

方法：临时 swap `prototype/public/base/{cat_base.glb,bones.json}` → Vite + Playwright → **还原**。

| 截图 | 路径 |
|---|---|
| Path B（主） | `innerscene_intake/smoke_b_{idle,walk,sit}.png`（亦 `smoke_*.png`） |
| Path A | `innerscene_intake/smoke_a_{idle,walk,sit}.png` |
| 拼图 | `innerscene_intake/smoke_sheet.png` |

### 现象（诚实）

1. **Rest — PASS（相对 Grab3D/BlenderKit 的关键突破）**  
   - B idle 侧视：四足站立、左右对齐，**不是**对角 mid-stride。  
   - 审计触地簇与骨 L/R 对称互证。  
   - 尾尖自带上扬 S 弯（资产 alert 造型），属网格造型而非迈步 Rest。

2. **walk — CONDITIONAL PASS**  
   - 动作库挂上后出现迈步相位；相对 Grab3D「爪骨够不着 / 碎腿」明显改善。  
   - 自动权重仍有 upper_leg_shear=30，腿部剪影偏硬，需权重/关节再调后才能当生产步态。

3. **sit — CONDITIONAL PASS**  
   - 后臀下降、前腿仍触地，动作语义正确。  
   - 脸部绿方块/白条为引擎 face 锚/投影叠层（各底座常见），非网格撕开；后肢/尾形需继续打磨。

4. **材质**  
   - Path B 保留纯色槽 → 引擎里呈棕灰短毛色块（非狸花贴图）。  
   - 调咩咩第一轮可用程序/DNA 涂层；若要写实贴图需另寻 CC0 贴图或投影。

---

## 6. BLOCKER / 非 blocker

### 已清除（相对前两轮）
- ~~迈步 Rest~~ → **对称站立**
- ~~非 CC0~~ → **CC0**
- ~~骨网极端错位~~ → Path B 贴骨 + 对称

### 仍存在（不挡「第一轮调咩咩」，挡「直接当生产母版」）
1. Path B 自动权重 shear/belly 非 0（不如 Path A 的 0/0/0 平滑皮）  
2. 无 baseColor 贴图（仅纯色材质）— 写实狸花观感弱于 Grab3D Path B  
3. 脸锚/投影与站姿头骨未精调  
4. 尾 Rest 上扬造型与现有动作库尾相位可能打架  
5. Path A Remesh 灰模丢失原色块分区

### 明确不做本轮
- 不覆盖 `prototype/public/base/*` / `assets/cat_base.glb`  
- 不把 Innerscene 宣布为最终生产底座（先调咩咩验证观感与动作）

---

## 7. 生产哈希（swap 前后一致）

```
8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0  prototype/public/base/cat_base.glb
1fbf37f76a05437f5aeb0d4e1c67b8361fdb88632e57bc925fe432d87df50bfc  prototype/public/base/bones.json
8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0  assets/cat_base.glb
```

Path A 跑完曾短暂写入 `assets/cat_base.glb`，已从 `/tmp/innerscene_work/bak/` 还原；上表为终态。

---

## 8. 关键路径

| 路径 | 用途 |
|---|---|
| `reference/open_cat_bases/innerscene_standing_cat/` | 原 GLB + clean + LICENSE |
| `docs/validation/INNERSCENE_STANDING_CAT_INTAKE.md` | 本笔记 |
| `docs/validation/innerscene_intake/` | 审计 JSON、out_a/out_b、smoke、脚本 |
| `docs/validation/innerscene_intake/out_b/cat_base.glb` | **调咩咩建议输入** |
| `docs/validation/innerscene_intake/out_b/bones.json` | fitted 26 骨 |

---

## 9. 建议下一步

1. **第一轮调咩咩**：以 `out_b` 为临时底座（仍用 swap 或独立预览，不盖生产），对标咩咩参考图调比例/耳/脸。  
2. 权重：把 Path A 的平滑皮思路迁到 Path B keep-materials 网格，压 shear/belly。  
3. 若调形满意，再讨论是否升格生产母版 + 动作库尾相位适配。
