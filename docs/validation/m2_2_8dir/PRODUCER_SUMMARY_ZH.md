# M2.2 制作人自审摘要（诚实版）

**时间**：2026-10-30（Asia/Shanghai）· **8 向合拢候选已写出**  
**结论**：互补 7/7 4x PASS（tip `13189b4`）后 **已跑 fuse + coverage + 双层审核板**。  
**`fur_albedo` = 合拢候选，尚未冻结**（供制作人 4x 合拢板自审 + 用户拍板）。**未开 M3**。禁止把本候选说成已冻结。

## 本轮合拢（fuse）

| 项 | 值 |
|---|---|
| 命令 | `blender -b --python pipeline/texture/fuse_8dir_albedo.py` |
| exit | **0**（`m2_2_fuse_report.json` → `"ok": true`） |
| views_used | d000 / d045 / d090 / d135 / d180 / d225 / d270 / d315（8/8；skipped 空） |
| 旧 M2.1 fur_albedo sha256 | `f9294ff916e586f09b39f0581ba65e88d74e298741001b21377ae23aa0ca76e4` |
| **新候选** fur_albedo sha256 | `4cfd06637c9e3ccdc237ba685f5baf61e18755c189719a0251f177eba15a962e` |
| 新 coverage sha256 | `6059749eaccadac0070fff0ed0e21549d2af56eda9a59eb53cc44a1cef3ec858` |
| 产出路径 | `cats/miemie/identity_v1/fur_albedo.png` · `coverage.png` · `fuse_8dir_report.json` |
| 旧版备份 | `cats/miemie/identity_v1/archive/pre_fuse_m21_d045_20261030_122319/` |
| 互补原图 | **未改**（fuse 前/后 sha 一致；只读投影） |
| uv_hash | `sha256:bbbc4394…ef15c27f` **未变** |
| 状态标注 | `fur_albedo_status=CANDIDATE_UNFROZEN` · `frozen=false` · `m3_started=false` |

ROOT 修复：`fuse_8dir_albedo.py` / `run_m2_2_review.py` / `run_m2_2.py` 改为 `Path(__file__).resolve().parents[2]`（与 gate 一致；原 `/workspace/miaowangtown` 在 Mac 不存在）。

## coverage 门禁（诚实 · 合拢后实测）

对照 DEVELOPMENT_PLAN：高频身份区绿+黄 ≥92%；红盲区 ≤20%。

| 指标 | 实测 | 门禁 |
|---|---|---|
| 高频区绿+黄比例 | **70.35%**（706107 / 1003672） | ≥92% → **FAIL** |
| 红盲区 / 岛 | **29.65%**（297565 / 1003672） | ≤20% → **FAIL** |
| 直视(绿) texel | 612562 | — |
| 擦边(黄) texel | 93944 | — |
| 未见→genome 底色 seed（非程序化毛流） | 297565 | — |
| 岛内绿+黄合计 | ≈70.39% | （参考；硬门禁用高频区口径） |

**诚实**：合拢后覆盖相对 M2.1 单视角（≈30.6% / 红≈67.4%）已大幅改善，**仍未过硬门禁**。未见区仅 genome 底色 seed，**未**用程序化毛流充数。制作人过目合拢板时请盯盲区与缝合。

## 双层审核板 / 4x 联络（已重出）

命令：`blender -b --python pipeline/bake/run_m2_2_review.py` · exit **0** · `incomplete=false`（AI complementary fused）。

| 文件 | 绝对路径 |
|---|---|
| 组合板 | `/Users/cloud/dev/game/喵汪小镇/miaowangtown/docs/validation/m2_2_8dir/identity_review.png` |
| Layer A（纯 albedo） | `/Users/cloud/dev/game/喵汪小镇/miaowangtown/docs/validation/m2_2_8dir/identity_review_layer_a.png` |
| Layer B（lantern+AO） | `/Users/cloud/dev/game/喵汪小镇/miaowangtown/docs/validation/m2_2_8dir/identity_review_layer_b.png` |
| 调制前后 4x | `/Users/cloud/dev/game/喵汪小镇/miaowangtown/docs/validation/m2_2_8dir/m2_2_modulation_4x_compare.png` |
| 分向 Layer A/B + 4x crop | `/Users/cloud/dev/game/喵汪小镇/miaowangtown/docs/validation/m2_2_8dir/m2_2_d{000,045,090,135,180,225,270,315}_layer_{a,b}.png` 及 `*_layer_a_4x_crop.png`（脚本覆盖 d045/d090/d135/d180/d225/d270） |
| 报告 JSON | `…/m2_2_fuse_report.json` · `…/m2_2_review_report.json` · `…/m2_2_orchestrator_report.json` |

## 4x 互补视角门禁（制作人权威 · 合拢前已全 PASS · 未改原图）

| view | 结果 |
|---|---|
| d000 / d090 / d135 / d180 / d225 / d270 / d315 | **PASS**（7/7） |
| d045 | M2.1 锚点（用户已批） |

## 制作人拍板建议

1. **打开合拢板**（上表 Layer A/B + 4x crop + modulation）做 4x 肉眼自审。  
2. coverage 硬门禁仍 FAIL → 即使视觉可接受，冻结前须显式接受盲区或另轮补洞。  
3. **在用户拍板前：不冻结 `fur_albedo`；不开 M3。**

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
