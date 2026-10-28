# Grab3D Tabby Cat（CC0）· Intake + walk/sit 冒烟

日期：2026-10-28（Asia/Shanghai）  
资产：[Grab3D Cat](https://grab3d.com/models/animals/cat/) · Light GLB  
许可证：**CC0 1.0**（https://grab3d.com/license/ · 本地 `reference/open_cat_bases/grab3d_tabby_cat/LICENSE.txt`）  
对照：BlenderKit Domestic Cat（RF，非 CC0）— 只读，**未修其 Rest**

> 产品目标：开放给用户调自家猫 → 底座需可再分发。Grab3D 本轮是 **CC0 并行验证**；BlenderKit 仅对照。

---

## 1. 结论（制作人一行）

**相对 BlenderKit：许可证更好，Path B 留 UV/贴图更好，骨网尺度错位减轻；但 mid-stride Rest 同病 → 仍 HOLD，不可直接调咩咩。**

| 门 | 结果 |
|---|---|
| CC0 可复现落盘 | **PASS**（light + LICENSE + clean） |
| Path A `--input` Remesh | **PASS**（4336v / 7550t，skin 0/0/0，灰模） |
| Path B 轻量（跳 Remesh + 按截面贴骨） | **PASS 管线**（9620v / 10000t，UV+狸花保留）；skin 审计 seam/shear/belly **非 0**（自动权重） |
| 引擎 idle/walk/sit 可挂 | **PASS**（A/B 均 `source=glb`） |
| 静帧/步态可当生产 | **HOLD**（对角迈步 Rest；B sit 碎裂/拉扯） |
| 可直接进咩咩 | **NO** |
| 生产 `public/base` / `assets` 干净 | **PASS**（§7） |

---

## 2. 原始资产

| 文件 | 说明 |
|---|---|
| `reference/open_cat_bases/grab3d_tabby_cat/cat-light.glb` | ~11MB / ~382k 三角 / 1K baseColor+ORM |
| `cat_clean.glb` | Decimate → **10000** 三角 / 10052 顶点；**保留 UV + 材质** |
| `LICENSE.txt` | CC0 1.0 |

审计：`docs/validation/grab3d_intake/grab3d_tabby_audit.json`

| 项 | 值 |
|---|---|
| 骨骼 | **无**（静态网格） |
| UV / 贴图 | 有（1024² Image_0 sRGB + Image_1 Non-Color） |
| 姿态 | **static mid-stride（对角迈步）** — Grab3D 文档已知；触地簇 **FR+HL 主导，FL≈0** |
| 不对称粗测 | median≈0.084，**p90≈0.209**，max≈0.233（Blender 空间） |
| 触地 | `min_z=0` |

---

## 3. 两条 Intake

输出根：`docs/validation/grab3d_intake/`（**未盖**生产）

### Path A — 现有 `build_base.py --input`（Remesh）

```bash
cd prototype
blender --background --python tools/blender/build_base.py -- \
  --input reference/open_cat_bases/grab3d_tabby_cat/cat_clean.glb \
  --out-dir docs/validation/grab3d_intake/out_a
# 注意：脚本仍会 copy → assets/cat_base.glb；本轮已立即从备份还原
```

| 项 | 结果 |
|---|---|
| 产出 | `out_a/cat_base.glb`（4336v / **7550**t）+ `bones.json`（**模板 26 骨位姿未变**） |
| 材质/UV | Remesh 后 **灰模**；材质清空 |
| 蒙皮审计 | seam=**0** / shear=**0** / belly=**0** → `skin_audit_a.json` |
| 网格 z 跨度（Three） | ≈ **1.03**（比 BlenderKit intake 的 ≈2.62 短很多） |
| 骨 z 跨度 | 仍 ≈模板（fpaw z=0.31，尾骨到 ≈-0.93）→ **骨比网长**（与 BlenderKit「网比骨长」方向相反，仍错位） |

### Path B — 轻量（跳 Voxel Remesh + 按截面重算 26 骨）

临时脚本：`/tmp/grab3d_work/path_b_light_intake.py`（本轮未强制合入 `build_base`；差异见下）

| 项 | 结果 |
|---|---|
| 产出 | `out_b/cat_base.glb`（9620v / **10000**t）+ fitted `bones.json` |
| 材质/UV | **保留**狸花 baseColor |
| 归一化 | 同 A：身高 → 1.25，脚底 y=0；**不清材质** |
| 骨骼 | 按网格截面/触地点放置；**反映对角迈步**（`fpawL` 无触地 → 回退估计；`fpawR`/`hpawL` 来自触地簇） |
| 权重 | Blender `ARMATURE_AUTO` |
| 蒙皮审计 | seam=**16** / shear=**47** / belly=**114** → `skin_audit_b.json`（无腹中线硬门禁） |
| 元数据 | `path_b_meta.json` |

与 `build_base` 差异（诚实）：

1. **跳过** Voxel Remesh / Smooth / 解剖二次雕刻  
2. **跳过** 非镜像 UV 图集重建（保留原 UV）  
3. `_PART` 仅粗标，不重建图集矩形  
4. 26 骨 **fit-to-mesh**，非模板常量  
5. 权重用自动热权重，非 `compute_smooth_skin_weights`  
6. **不** copy 到 `assets/`

建议后续旗标（本轮未大重构）：`--no-remesh` / `--keep-materials` / `--fit-bones-to-mesh`。

---

## 4. 引擎 walk/sit 冒烟

方法：临时 swap `prototype/public/base/{cat_base.glb,bones.json}` → Vite + Playwright 隔离截图 → **还原**。

| 截图 | 路径 |
|---|---|
| Path B（主） | `grab3d_intake/smoke_b_{idle,walk,sit}.png`（亦拷为 `smoke_*.png`） |
| Path A | `grab3d_intake/smoke_a_{idle,walk,sit}.png` |
| 拼图 | `grab3d_intake/smoke_sheet.png` |

### 现象（诚实）

1. **mid-stride Rest — 确认（同 BlenderKit）**  
   - idle 侧视已是对角迈步；触地审计 FL 空。  
   - Path B 贴骨把不对称写进了 `bones.json`（左右爪位不同），动作库当 Rest 用会**固化瘸步**。

2. **UV/贴图 — Path B 胜**  
   - B idle/walk 可见狸花条纹与白袜；A 为灰模+投影噪声。  
   - 相对 BlenderKit Remesh 掉 UV：**明确更好**。

3. **骨网尺度 — 相对 BlenderKit 减轻，未根除**  
   - Grab3D 身高归一后身长 ≈1.03，不再出现 BlenderKit「网 z≈2.62 vs 骨≈1.55」那种极端爪骨够不着。  
   - A 仍套模板骨（尾骨超出网格）；B 贴骨后尺度对齐，但 Rest 不对称。

4. **walk**  
   - B：能驱动；后躯/尾有撕裂与块状伪影；步态像「带着迈步 Rest 扭」。  
   - A：灰模可动；轮廓更「母版化」但仍非中性站立。

5. **sit**  
   - B：**明显碎裂/平面化**，剪影不可接受（自动权重 + 迈步 Rest 叠加）。  
   - A：可辨坐势但仍畸变。

6. **脚穿地**  
   - 隔离帧无地板网格；未见经典整脚没入；B 有离体碎块。

---

## 5. 与 BlenderKit 对照表

| 维度 | BlenderKit Domestic Cat | Grab3D Tabby Light |
|---|---|---|
| 许可证 | Royalty Free ≠ CC0 | **CC0 1.0** |
| 开源再分发底座 | 风险 | **适合** |
| 默认姿态 | 略迈步站立 | **明确 mid-stride** |
| 原骨骼 | 32 骨 IK（不可直映射） | 无 |
| Path A Remesh | ~11k 三角，掉 UV | ~7.5k 三角，掉 UV |
| Path B 留 UV | （BlenderKit 轮未做完） | **本轮做了**，狸花可见 |
| 网/骨尺度 | 网远长于模板骨 → 碎腿 | 网更短；A 骨偏长 / B 已贴网 |
| skin 审计（A） | 0/0/0 | 0/0/0 |
| walk/sit | HOLD | **仍 HOLD** |
| 调咩咩 | NO | **NO** |

一句话：**Grab3D 在「可开放分发 + 留贴图」上优于 BlenderKit；在「中性 Rest」上同病，不能靠换资产蒙混过关。**

---

## 6. BLOCKER / 风险

| ID | 级别 | 说明 |
|---|---|---|
| G1 | **姿态** | mid-stride Rest：不对称化到中性四足站立前，动作库必瘸 |
| G2 | **Path B 权重** | 自动权重 belly/shear 超标；sit 碎裂 |
| G3 | **Path A 贴图** | Remesh 灰模，不能验收花色/调咩咩印记 |
| G4 | **build_base 副作用** | `--out-dir` 仍写 `assets/cat_base.glb`（已回滚） |
| G5 | **Innerscene 旁路** | 站姿 CC0 候选页可开，但本轮未拿到免登录直链下载（见 §8） |

非阻塞：CC0 清晰；clean 可复现；A/B 均可被引擎 `source=glb` 加载；生产哈希未变。

---

## 7. 生产未脏证明

测前 / 测后一致：

| 文件 | sha256 |
|---|---|
| `prototype/public/base/cat_base.glb` | `8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0` |
| `prototype/public/base/bones.json` | `1fbf37f76a05437f5aeb0d4e1c67b8361fdb88632e57bc925fe432d87df50bfc` |
| `assets/cat_base.glb` | 同上 GLB（cmp 相同） |

备份：`docs/validation/grab3d_intake/smoke_backup/`（本地，**不入库**）。

---

## 8. Innerscene Standing cat（可选旁路，未替代主结论）

- 页：https://www.innerscene.com/tools/library/3d-parts/standing-cat-cda42538  
- 宣称：**CC0**、**alert standing**、~4.7MB GLB、`cat-original.glb`  
- 本轮：页面 HTML/`__NEXT_DATA__` **未暴露**可 curl 的直链；常见 `/downloads/`、`/api/.../glb` 均 404。  
- **未下载、未 intake**。目录 `reference/open_cat_bases/innerscene_standing_cat/` 仍空。  
- 价值：若后续用浏览器会话拿到 GLB，是验证「真站姿 Rest」的最佳旁路对照；**不改变** Grab3D「mid-stride 同病」主结论。

---

## 9. 建议下一步

1. **优先找/做对称中性站立 CC0**（Innerscene Standing / 自对称化脚本），再 intake。  
2. 若继续 Grab3D：Blender 对称化四足站立（镜像平均或 sculpt）→ 再跑 Path B 贴骨 + 把腹中线硬门禁接到自动权重后处理。  
3. 给 `build_base.py` 加 `--no-remesh --keep-materials --fit-bones-to-mesh --skip-assets-copy`。  
4. **不要**覆盖 `public/base`；**不要**开始调咩咩。

---

## 10. 文件索引

```
reference/open_cat_bases/grab3d_tabby_cat/{LICENSE.txt,cat-light.glb,cat_clean.glb}
docs/validation/GRAB3D_TABBY_INTAKE.md
docs/validation/grab3d_tabby_intake_sheet.png
docs/validation/grab3d_intake/
  grab3d_tabby_audit.json
  clean_export_meta.json
  path_b_meta.json
  skin_audit_{a,b}.json
  out_a/{cat_base.glb,bones.json}
  out_b/{cat_base.glb,bones.json}
  smoke_{a,b}_{idle,walk,sit}.png
  smoke_{idle,walk,sit}.png          # = Path B
  smoke_sheet.png
```
