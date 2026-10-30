# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30（Asia/Shanghai）· 合拢板制作人 4x  
**结论**：**互补 7/7 PASS 且已 fuse 出候选**（tip `dff7e17`），但制作人对合拢板自审为 **CONDITIONAL HOLD · 不建议冻结 `fur_albedo`**。coverage 硬门未过；侧向合拢重投影有透空/眼球游离。**未开 M3**。

## 制作人合拢自审（authority=4x/8x）

| 项 | 结论 |
|---|---|
| 互补 7 向 2D 门禁 | **7/7 PASS**（此前已锁） |
| `uv_hash` | 未变 `bbbc4394…c27f` |
| coverage 绿+黄 | **70.35%**（门 ≥92%）→ **FAIL** |
| coverage 红盲区 | **29.65%**（门 ≤20%）→ **FAIL** |
| d045 Layer A 8x | 可读微 Q 猫、绿眼、虎斑 — **OK** |
| d090 Layer A 8x | 颈拉长、眼珠游离、躯干透空 — **HOLD** |
| d270 Layer A 8x | 剪影连续但眼点游离、质感碎 — **弱** |
| d180 Layer A 8x | 背向灰底占比高、形可读性差 — **弱** |
| 冻结 | **否**（候选 `fur_albedo` sha `4cfd0663…`，status=CANDIDATE_UNFROZEN） |

**下一步（制作人）**：不冻、不开 M3；优先诊断侧向透空是 114×104 薄面采样还是 UV 盲区透底，再考虑补盲/加重投影；coverage 未达硬门前不交「冻结拍板」。

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
