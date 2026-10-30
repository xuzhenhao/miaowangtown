# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30（Asia/Shanghai）· opus 纠偏后  
**结论**：**CONDITIONAL HOLD · 禁止交用户冻结拍板**。2D 互补门禁里 d090 曾标 PASS，但合拢重投影否决更权威 → d090 = **PASS_WITH_HOLD / 合拢否决向**。**2D PASS ≠ 合拢过门**。coverage 硬门 FAIL。**未冻 fur_albedo、未开 M3**。

## 状态总表

| 项 | 状态 |
|---|---|
| 互补 2D 门禁 | d000/d135/d180/d225/d270/d315 **PASS**；**d090 = PASS_WITH_HOLD**（合拢板否决） |
| fuse 候选 | tip `dff7e17`，fur_albedo sha `4cfd0663…`，`CANDIDATE_UNFROZEN` |
| coverage 绿+黄 | **70.35%**（≥92% FAIL） |
| coverage 红盲区 | **29.65%**（≤20% FAIL） |
| 合拢板 4x/8x | d045 OK；d090 颈拉长+眼游离+躯干透空 → **HOLD** |
| 冻结 / M3 | **否** |

## 诊断进行中（opus 优先级）
a. clay vs 合拢重投影同机位  
b. fur_albedo alpha 与 coverage 红区  
c. 眼网格绑定  
d. 必要时降 d090 权重对照 fuse（不删归档）  
侧向不透空之前不做程序化补盲冲 92%。

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
| `M22_MODELS_ROOT` | `/Users/cloud/dev/models/m22` | **权威**：curl `download_m22.sh` 本地快照 |
| `HF_HOME` | `/Users/cloud/dev/models/m22/hf_home` | 残余 hub 缓存 |
| 禁止 | `~/.cache/huggingface` | 用户硬要求 |

## 诚实原则（继承 M2.1）

- 剪影若锁 M1 Alpha：**非新轮廓证据**。  
- 眼 4 要素主计 **Layer A**。  
- 分区启发式偏软，权威 = **4x 肉眼**。  
- M1 `uv_hash` = `sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f` **未变**。  
- 未见 UV：**仅 genome 底色 seed**，禁止程序化毛流充数。  
