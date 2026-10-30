# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30（Asia/Shanghai）· ctrl_refit `33ed84f` 后三向重生复审  
**结论**：**仍未完成合拢**。控制图 refit 后仅重生 d090/d225/d315（`--seed-offset 20011`）；制作人 4x 现为 **6 PASS / 1 FAIL**（d225、d315 本轮转 PASS；**d090 仍 FAIL**；既有 d000/d135/d180/d270 PASS **未动**）。**因仍有 1/7 FAIL 继续停合拢**。`fur_albedo.png` 仍为 **M2.1 d045 单向**，整张 UV **不冻**；**未进 M3**。

**本轮参数**：`generate_complementary_sdxl.py --run --views d090,d225,d315 --seed-offset 20011 --merge-report`；log `logs/m22/rerun_ctrlrefit_20261030_120716.log`；旧 FAIL 归档 `complementary_albedos/archive/pre_ctrl_refit_33ed84f/`。CLIP77 截断仍在（印记/向别约束被挤）。

## 4x 互补视角门禁（制作人权威 · 2026-10-30 ctrl_refit 复审）

| view | 结果 | notes（原样） |
|---|---|---|
| d000 | **PASS**（锁） | rerun+seed_offset10007 后 4x：绿眼可读；白爪无大灰边；解剖右焦糖斑/花生嘴套可见（相对首轮白罩改善）；剪影外鬼影已清。CLIP77 截断仍在，风格偏碎面。authority=4x PASS |
| d090 | **FAIL**（ctrl_refit 后仍败） | ctrl_refit+重跑后仍 FAIL：顶裁/翼刺已消，但四肢/尾仍呈断开碎面、非单一干净相机猫形；albedo外溢depth（a_only≈27k，高于PASS/d225/d315）；相对PASS侧向条（d270）像度不够。authority=4x FAIL |
| d135 | **PASS**（锁） | 4x PASS：与 depth 同向动态姿；毛流沿体、白袜清晰、绿眼可读、未见塑料椭圆与明显灰边；侧别印记在可见面守恒。authority=4x |
| d180 | **PASS**（锁） | 4x PASS：背向视图；背纹毛流顺 depth；未见塑料椭圆；背向不要求正脸绿眼全貌。authority=4x |
| d225 | **PASS**（本轮） | ctrl_refit后4x PASS：相对旧版熔融裁切已消；三四分背侧姿完整入画；绿眼可读；白爪/白围脖清晰；未见塑料椭圆与大块灰边；侧别焦糖/虎斑在可见面守恒。authority=4x PASS |
| d270 | **PASS**（锁） | 4x PASS：侧向绿眼/白围脖白爪可读，虎斑顺体；颈后有轻微碎边记入notes但不否决。authority=4x |
| d315 | **PASS**（本轮） | ctrl_refit后4x PASS：碎三角爆炸已消；背斜姿头耳尾对齐；虎斑顺体；白爪可读；无大灰边/塑料椭圆。authority=4x PASS |

**汇总**：6 PASS · 1 FAIL（仅 d090）→ **仍停合拢**。禁止程序化退回充数；可只重跑 d090，勿动已 PASS 六向；**全 PASS 前禁止 fuse / 不冻 fur_albedo / 不开 M3**。

### 制作人下一步建议
- 只针对 **d090**：先查 ControlNet 强度/种子/CLIP77（把五印记+「single clean side profile cat, intact four legs, no floating shards」提到 prompt 头并缩短 base），必要时再看侧向 clay 是否仍有退化折面。
- 通过后再 fuse → coverage → 双层审核板 → 用户肉眼拍板冻结。

---


## 沿用（权重 / 路径 / 诚实原则）
### 已锁定可商用权重（模型卡许可证）

见 `generated/LICENSED_STACK.md`：

| Hugging Face 仓库 | 许可证 |
|---|---|
| `stabilityai/stable-diffusion-xl-base-1.0` | CreativeML OpenRAIL++-M |
| `diffusers/controlnet-depth-sdxl-1.0` | CreativeML OpenRAIL++-M |
| `xinsir/controlnet-union-sdxl-1.0` | Apache-2.0 |
| `h94/IP-Adapter`（`ip-adapter-plus_sdxl_vit-h.bin`） | Apache-2.0 |

### 权重路径约定（2026-10-30 统一）

| 变量 | 权威路径 | 用途 |
|---|---|---|
| `M22_MODELS_ROOT` | `/Users/cloud/dev/models/m22` | **权威**：curl `download_m22.sh` 本地快照；`--run` 优先 `from_pretrained(本地目录)` |
| `HF_HOME` | `/Users/cloud/dev/models/m22/hf_home` | 仅残余按 repo-id 拉取的 hub 缓存 |
| （废弃） | `/Users/cloud/dev/models/huggingface` | 旧 hub orphan blobs；齐套后删除 |
| 禁止 | `~/.cache/huggingface` | 用户硬要求 |

**补缺**：仓库根 `download_m22.sh` 已入库；权重权威根仍为 `M22_MODELS_ROOT=/Users/cloud/dev/models/m22`。生成脚本分向重跑 knobs 见 tip **`b097819`**。

## 4x 互补视角门禁（制作人权威 · 2026-10-30 rerun 复审）

| view | 结果 | notes（原样） |
|---|---|---|
| d000 | **PASS**（rerun） | rerun+seed_offset10007 后 4x：绿眼可读；白爪无大灰边；解剖右焦糖斑/花生嘴套可见（相对首轮白罩改善）；剪影外鬼影已清。CLIP77 截断仍在，风格偏碎面。authority=4x PASS |
| d090 | **FAIL**（rerun 仍败） | rerun 后仍 FAIL：头颈拉长切片、头胸腿旁漂浮碎片/鬼影，非单一干净相机视图。authority=4x |
| d135 | **PASS**（未动） | 4x PASS：与 depth 同向动态姿；毛流沿体、白袜清晰、绿眼可读、未见塑料椭圆与明显灰边；侧别印记在可见面守恒。authority=4x |
| d180 | **PASS**（未动） | 4x PASS：背向视图；背纹毛流顺 depth；未见塑料椭圆；背向不要求正脸绿眼全貌。authority=4x |
| d225 | **FAIL**（rerun 仍败） | rerun 后仍 FAIL：侧腹/爪旁三角幻影外溢、depth leak、顶部裁切。authority=4x |
| d270 | **PASS**（未动） | 4x PASS：侧向绿眼/白围脖白爪可读，虎斑顺体；颈后有轻微碎边记入notes但不否决。authority=4x |
| d315 | **FAIL**（rerun 仍败） | rerun 后仍 FAIL：albedo 碎三角柱/贴图爆炸，头耳与尾未对齐锚点。authority=4x |

**汇总**：4 PASS（d000 / d135 / d180 / d270）· 3 FAIL（d090 / d225 / d315）→ **仍停合拢**。禁止程序化退回充数；可只重跑仍失败的三向，勿整批假绿；**禁止改动已 PASS 的 d135/d180/d270**。

检查项口径（DEVELOPMENT_PLAN）：毛流自然 / 无塑料椭圆色块 / 五印记侧别守恒 / 白爪零灰边 / 绿眼可读（背面向看得到的印记）。剪影锁不算新轮廓证据；软启发式不得当硬证据。

## 已交付（可复跑）

1. **8 向控制图**（pitch=35°，固定种子 `20261029`）  
   `cats/miemie/identity_v1/control_views/{d000..d315}/{depth,normal,part_mask,clay}*.png`  
   联络板：`control_maps/m2_2_control_depth_normal_sheet.png`
2. **可复现脚本**  
   - `pipeline/texture/export_control_views.py`  
   - `pipeline/texture/generate_complementary_sdxl.py`（tip `b097819`：`--views` / `--seed-offset` / `--merge-report` / VIEW_TUNING / depth bg mask）  
   - `pipeline/texture/gate_complementary_view.py`（ROOT 相对仓库根；Mac PIL 默认字体用 ASCII 标题）  
   - `pipeline/texture/fuse_8dir_albedo.py`（**尚未调用**）  
   - `pipeline/bake/run_m2_2_review.py` / `run_m2_2.py`（合拢后才重出 Layer A/B）
3. **4x 门禁预览板**  
   `docs/validation/m2_2_8dir/gates_preview_{view}_4x.png`
4. **调制前后 4x / 双层审核板合拢态**  
   仍为合拢前占位；**不得**把 N/A 或 genome 中灰格冒充 AI 毛流过门。

## coverage 门禁（诚实 · 合拢前）

沿用 M2.1 d045 单视角（合拢未发生，指标未更新）：

| 指标 | 实测 | 门禁 |
|---|---|---|
| 岛内绿+黄 | **≈30.6%** | 高频身份区 ≥92% → **FAIL** |
| 红盲区 / 岛 | **≈67.4%** | ≤20% → **FAIL** |

## 诚实原则（继承 M2.1）

- 剪影若锁 M1 Alpha：**非新轮廓证据**。  
- 眼 4 要素主计 **Layer A**。  
- 分区启发式偏软，权威 = **4x 肉眼**。  
- M1 `uv_hash` = `sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f` **未变**。  

## 制作人拍板建议

- **不通过冻结 `fur_albedo`**；**不开 M3**。  
- 下一步：仅重跑 FAIL 向（d000 / d090 / d225 / d315），过 4x 后再考虑合拢；全 PASS 前禁止 fuse。  
