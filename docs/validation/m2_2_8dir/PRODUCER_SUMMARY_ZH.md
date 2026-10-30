# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-29（Asia/Shanghai）  
**结论**：**未完成合拢**。管线可复跑、许可证已落盘、控制图与 8 向双层审核板已出；**互补视角 AI 毛流因本机无 CUDA GPU 被诚实阻塞**，**严禁**用程序化色块充数。`fur_albedo.png` 仍为 **M2.1 d045 单向**，整张 UV **不冻**。

## 阻塞（硬）

| 项 | 状态 |
|---|---|
| 本机 GPU | **无** `nvidia-smi` / 无 `torch.cuda` |
| SDXL + ControlNet + IP-Adapter | **未跑**（见 `generated/m2_2_generation_BLOCKED.json`） |
| 程序化毛流退回 | **未启用**（按计划禁止当默认交付） |
| 非商用权重（含 FLUX.1-dev） | **未下载、未使用** |

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

**可 `--run` 缺件门槛**（缺任一则拒绝生成）：Depth ControlNet fp16 + config；SDXL `model_index` / unet / text_encoder / text_encoder_2（完整 ≥1.3GB）/ vae / scheduler；tokenizer 小文件建议齐。IP-Adapter `ip-adapter-plus_sdxl_vit-h.bin` 强烈建议（无则弱身份锁定仍可试跑但需在报告标明）。

**补缺（2026-10-30）**：仓库此前引用但不存在的 `download_m22.sh` 已补到仓库根目录；权重权威根仍为 `M22_MODELS_ROOT=/Users/cloud/dev/models/m22`（含 union + IP image_encoder 续传目标）。

解阻（二选一）：
1. **Apple Silicon Mac（MPS）**：仓库拉到含本约定的 commit → 复制 `.env.m22.example` 为 `.env.m22` → 跑完 `download_m22.sh` →  
   `source .env.m22 && .venv-m22/bin/python pipeline/texture/generate_complementary_sdxl.py --run`
2. **CUDA ≥12GB VRAM**：同上装 CUDA 版 torch 后 `--run`

之后每视角 `gate_complementary_view.py --human-pass` →  
`blender -b --python pipeline/texture/fuse_8dir_albedo.py` →  
`blender -b --python pipeline/bake/run_m2_2_review.py`。

脚本已支持 CUDA / Apple MPS、`.env.m22`、`M22_MODELS_ROOT` 本地优先；本 bot 电脑仍无 GPU，生成须在授权机上跑。

## 已交付（本机可复跑）

1. **8 向控制图**（pitch=35°，固定种子 `20261029`）  
   `cats/miemie/identity_v1/control_views/{d000..d315}/{depth,normal,part_mask,clay}*.png`  
   联络板：`control_maps/m2_2_control_depth_normal_sheet.png`
2. **可复现脚本**  
   - `pipeline/texture/export_control_views.py`  
   - `pipeline/texture/generate_complementary_sdxl.py`  
   - `pipeline/texture/gate_complementary_view.py`  
   - `pipeline/texture/fuse_8dir_albedo.py`  
   - `pipeline/bake/run_m2_2_review.py` / `run_m2_2.py`
3. **8 向双层审核板**（标注 INCOMPLETE）  
   - `identity_review.png` / `identity_review_layer_a.png` / `identity_review_layer_b.png`  
   - 非 d045 格为 **genome 种子中灰**，**不是** AI 毛流，不可当过门。
4. **调制前后 4x**  
   `m2_2_modulation_4x_compare.png` → **N/A 占位**（合拢未发生）。

## coverage 门禁（诚实未达标）

沿用 M2.1 d045 单视角：

| 指标 | 实测 | 门禁 |
|---|---|---|
| 岛内绿+黄 | **≈30.6%** | 高频身份区 ≥92% → **FAIL** |
| 红盲区 / 岛 | **≈67.4%** | ≤20% → **FAIL** |

达标需互补 7 向过 4x 毛流/印记门后再反投合拢。

## 诚实原则（继承 M2.1）

- 剪影若锁 M1 Alpha：**非新轮廓证据**。  
- 眼 4 要素主计 **Layer A**。  
- 分区启发式偏软，权威 = **4x 肉眼**。  
- M1 `uv_hash` = `sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f` **未变**。  
- **未 git push**（按任务要求）。

## 制作人拍板建议

- **不通过冻结 `fur_albedo`**。  
- 通过「管线骨架 + 控制图 + 许可证声明」后，请用户拍板：本机 Mac MPS 自跑，或授权租用 CUDA；未授权前不跑生成、不冻 fur_albedo。
