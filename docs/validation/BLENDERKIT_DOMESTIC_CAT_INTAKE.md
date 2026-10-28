# BlenderKit Domestic Cat (Rigged) · 最快工程验证 Intake

日期：2026-10-28（Asia/Shanghai）  
资产：BlenderKit / Blendkit — **Domestic cat (rigged)**  
作者：Paweł Wałasiewicz  
Asset ID：`731d9ed6-cbe6-4ab5-b9cc-105f021457ba`  
来源页：https://www.blendkit.com/asset-gallery-detail/6b3bbcc7-db99-4424-9436-8e6678ee9354/

> 产品定位：开源/可商用写实四足猫底座 + DNA/形态键，开放给用户调自家猫。  
> BlenderKit 本轮是**最快工程验证**，不是终局唯一母版。诚实记录问题。

---

## 1. 许可证

| 项 | 内容 |
|---|---|
| 许可证 | **Royalty Free（BlenderKit Free Asset）**，**不是 CC0** |
| 商用游戏内使用 | 一般允许（按 BlenderKit free 条款） |
| 原样二次分发 `.blend` | **需再核条款** — 不建议把未改 `.blend` 当开源母版公开镜像 |
| 对本项目 | 适合闭源/游戏内工程验证；若以后要「用户可下载底座源文件」，优先换真正 CC0（如 Grab3D / Innerscene） |

本地说明：`reference/open_cat_bases/blenderkit_domestic_cat_rigged/LICENSE.txt`

---

## 2. 原始资产快照

路径：`reference/open_cat_bases/blenderkit_domestic_cat_rigged/`

| 文件 | 说明 |
|---|---|
| `domestic_cat_rigged.blend` | 主文件（Blender 3.6.11 写入，本机 4.3.2 打开） |
| `textures_1k_resolution.blend` | 原误标为 `textures_1k.zip`；实为 **zstd 压缩 .blend**，已改名 |
| `domestic_cat_clean.glb` | 本轮清理导出（仅网格 + 漫反射） |
| `LICENSE.txt` | 许可证笔记 |

### 审计摘要（详见 `docs/validation/blenderkit_domestic_cat_audit.json`）

| 对象 | 类型 | 顶点数 | 三角面≈ | 备注 |
|---|---|---:|---:|---|
| `sculpt.001` | MESH | 9024 | 18016 | 身体；带 Subdivision（未 Apply）+ **5 套 HAIR 粒子** |
| `Eye1` | MESH | 1928 | 3840 | 独立眼球；打包眼贴图 2048² |
| `Armature.001` | ARMATURE | — | — | **32 骨**（含 IK 控制/极向） |

毛发粒子：`BODY / HEAD·PAWS / FACE / UNDERFUR / whiskers`（各约 5k 或 20 根须）— **不进 Web**。

材质贴图（主文件内已 packed）：

- `CAT_TEX_C` 漫反射（审计见 4096² packed）
- `WHITE_MASK`（1024²）
- `EyeV2_C`（2048²）

### 默认姿态判断

- **四足站立**，脚贴地（`min_z ≈ 0`）
- 四肢几何分离（单网格、腿部拓扑分开），**非**粘连手脚
- **非 A/T pose**
- 视觉上为**略带迈步**的自然站姿（一前爪略前伸），不是完美对称中性 Rest

### 原骨骼名（32，与项目 26 骨不同）

```
leg3_control_R/L, feet_R/L, paw_control_R/L, paw3_R/L,
CONTROLLER, pelvis, Bone.001, Bone.002, Bone.004,
tail1..tail5,
leg1/2/3_R|L, paw1/2_R|L,
leg2_pole2_R|L, paw_pole_R|L
```

---

## 3. 清理步骤（已完成）

脚本：本机一次性 `/tmp/clean_export_blenderkit_cat.py`（结果已落盘）

1. 删除全部 HAIR 粒子系统与 PARTICLE_SYSTEM 修改器  
2. **不 Apply** Subdivision，直接删除（避免面数爆炸）  
3. Apply Armature 修改器 → 把当前站立姿态烘焙进网格  
4. 合并 `Eye1` → 身体  
5. Apply Location/Rotation/Scale；脚底微调到 `z=0`  
6. 三角化后 Decimate → **约 10000 三角面 / 5023 顶点**  
7. 导出 `domestic_cat_clean.glb`（仅网格 + 材质漫反射；**不含**原 32 骨）

元数据：`docs/validation/blenderkit_intake/clean_export_meta.json`

---

## 4. `build_base.py --input` 结果

命令：

```bash
cd prototype
blender --background --python tools/blender/build_base.py -- \
  --input /workspace/miaowangtown/reference/open_cat_bases/blenderkit_domestic_cat_rigged/domestic_cat_clean.glb \
  --out-dir /workspace/miaowangtown/docs/validation/blenderkit_intake/out
```

| 项 | 结果 |
|---|---|
| 是否成功 | **是**（exit 0） |
| 产出 | `docs/validation/blenderkit_intake/out/cat_base.glb`（6205–6208 顶点 / **11292** 三角面） |
|  | `docs/validation/blenderkit_intake/out/bones.json`（标准 **26 骨** + faceAnchors + parts） |
| 蒙皮审计 | seam=**0** / shear=**0** / belly=**0** → `docs/validation/blenderkit_intake/skin_audit.json` |
| `npm run check` | **通过**（解耦门禁；测的是未覆盖的现有 `public/base`） |

### 故意未覆盖生产母版

- 备份：`docs/validation/blenderkit_intake/backup_before/{cat_base.glb,bones.json}`  
- `prototype/public/base/*` **未改**  
- 注意：`build_base.py` 在自定义 `--out-dir` 时仍会 `copy` 到 `assets/cat_base.glb` — 本轮已从备份**还原** `assets/`。建议主 agent 后续给 `--out-dir` 加「跳过 assets 复制」开关。

### 管线行为（对写实底座的影响）

`--input` 路径会：

1. `normalize_imported_mesh` → **清空材质**（原狸花漫反射丢失）  
2. Voxel Remesh + Smooth + Decimate（目标 4800，本输入最终约 11k，因后续解剖精修顶点位移/拓扑）  
3. 重建 **26 骨** 与 ShapeKeys（`headRound/weight/earSize/tailFluff/cheekFluff/muzzleSize`）

因此：**工程验证通了「能进管线」**；「保留写实贴图/原拓扑锐度」需要另开「轻量 intake」模式（跳过 Remesh 或 Remesh 后重投影贴图）。

---

## 5. 与现有 26 骨命名映射

| miaowangtown 26 | BlenderKit 近似 | 状态 |
|---|---|---|
| root / hips / spine / chest / neck / head | CONTROLLER / pelvis / Bone.001·002·004 | 语义可对，名称不同 |
| earL / earR | （无独立耳骨） | **缺失** — 靠权重刷或补骨 |
| shoulder/elbow/fpaw L·R | leg1/2/3 + paw*（前肢） | 可手工映射，层级/轴需重校准 |
| hip/knee/hpaw L·R | leg* + paw*（后肢）+ feet_* | 同上；含额外 IK 控制骨 |
| tail0..tail5 | tail1..tail5（少 1） | 接近；缺 tail0/根骨约定 |
| — | poles / *_control_* | 引擎不用，应丢弃 |

**结论**：不能直接复用 BlenderKit 骨架驱动现有动作库。当前 `--input` 策略（丢弃原骨、按包围盒重建 26 骨）是正确的最快路径；若要保留原 IK 手感，需单独做 retarget，工作量远大于验证目标。

---

## 6. BLOCKER / 风险清单（诚实）

| ID | 级别 | 说明 |
|---|---|---|
| B1 | **许可证** | Royalty-Free ≠ CC0；开源分发「用户可下底座源文件」前必须换 CC0 或取得明确再分发权 |
| B2 | **姿态** | 默认略迈步，非中性对称 Rest；动作库假设的站立/绑骨截面可能出现左右不对称残留 |
| B3 | **原骨不可直用** | 32 骨 IK 命名与 26 骨动作库不兼容；耳骨缺失 |
| B4 | **Remesh 抹锐** | Voxel Remesh 会吃掉写实解剖棱线与原 UV/贴图；`--input` 后变成「写实轮廓的灰模母版」，不是带狸花贴图的游戏网格 |
| B5 | **面数偏高** | Intake 产出 ~11k 三角（现有手搓母版 ~9.2k / 目标常写 4–6k）；Web 包体可再压 |
| B6 | **毛发不可进 Web** | 已剥离；视觉「蓬松感」需靠贴图/法线/后期毛发卡（非粒子） |
| B7 | **build_base 副作用** | `--out-dir` 仍写 `assets/cat_base.glb`（已回滚）；合并前勿直接跑覆盖生产 |

非阻塞：蒙皮三项审计全 0；解耦 `npm run check` 通过；clean GLB 可被 Blender/gltf 正常打开。

---

## 7. 对照图

`docs/validation/blenderkit_domestic_cat_intake_sheet.png`

六格：Intake 白模正/左/右 · Clean 纹理正 · 原 BlenderKit 站立正（关毛发）· 现有母版白模正（未覆盖对照）

---

## 8. 下一步：「调成咩咩」建议

1. **不要立刻覆盖** `prototype/public/base/cat_base.glb`；先在 `docs/validation/blenderkit_intake/out/` 上做动作冒烟（walk/sit）再决定。  
2. 开一条 **轻量 intake**（可选 flag）：跳过 Voxel Remesh，只做坐标归一化 + 26 骨自动蒙皮 + 保留原 UV，把狸花漫反射带进引擎做「写实预览」。  
3. 用现有 6 个 ShapeKey + 新 DNA 字段，先做「胖瘦/头圆/耳长」滑条；咩咩五印记走贴图层（正面阴阳嘴套、左肋通背白、等），而不是雕刻死。  
4. 若产品要「用户上传照片 → 自家猫」，底座选 CC0 写实站姿更稳；BlenderKit 可继续当**内部参考/对照**，或仅发行衍生低模。  
5. 并行可试 Grab3D Tabby（CC0、写实上限高）走同一套 `--input`，对比 Remesh 后解剖谁更耐看。

---

## 9. 文件索引（本轮产出，未 push）

```
docs/validation/blenderkit_domestic_cat_audit.json
docs/validation/BLENDERKIT_DOMESTIC_CAT_INTAKE.md
docs/validation/blenderkit_domestic_cat_intake_sheet.png
docs/validation/blenderkit_intake/backup_before/{cat_base.glb,bones.json}
docs/validation/blenderkit_intake/clean_export_meta.json
docs/validation/blenderkit_intake/skin_audit.json
docs/validation/blenderkit_intake/out/{cat_base.glb,bones.json}
reference/open_cat_bases/blenderkit_domestic_cat_rigged/domestic_cat_clean.glb
reference/open_cat_bases/blenderkit_domestic_cat_rigged/textures_1k_resolution.blend  # 由 zip 改名
```

**未执行** `git push`。生产 `prototype/public/base` 与 `assets/cat_base.glb` 保持备份原样。
