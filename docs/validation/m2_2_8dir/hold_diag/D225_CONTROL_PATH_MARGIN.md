# d225 实读 control 路径与画幅边距（只读确认）

**时间**：2026-10-30（Asia/Shanghai）  
**约束**：只读；**不重渲、不重生、不 fuse**。供 opus 拍板是否开 d225 控图重导出 / 1 次 regen。

## 1. 生成器实读路径

| 项 | 值 |
|----|----|
| 脚本 | `pipeline/texture/generate_complementary_sdxl.py` |
| 变量 | `CTRL = ROOT / "cats" / "miemie" / "identity_v1" / "control_views"`（约 L68，硬编码相对 `ROOT`） |
| 加载文件 | 优先 `CTRL/{view}/depth_768.png`，缺失则回退 `depth.png`；normal 同目录 `normal_768.png`（约 L606–614） |
| **实读根** | **`cats/miemie/identity_v1/control_views/`** |

### `.env.m22` 是否覆盖 control 根？

**否。** 本机 `.env.m22` 只设：

- `MIAOWANGTOWN_ROOT`（解析 `ROOT`）
- `M22_MODELS_ROOT` / `HF_HOME` / hub cache / `PYTORCH_ENABLE_MPS_FALLBACK`

**没有** `CONTROL_*` / `control_views` / `control_maps` 类变量；control 子路径不可被 env 改写。

### 非实读副本

| 路径 | 角色 |
|------|------|
| `docs/validation/m2_2_8dir/control_maps/` | `export_control_views.py` 的 `VAL_DIR` 校验副本，**SDXL 不读** |

`export_control_views.py`：`OUT_CTRL`→cats（canonical），`VAL_DIR`→docs（sheet/校验）。

## 2. d225 四边 margin（实读路径）

测量：主体 bbox = depth/clay 前景（depth `>8`；clay 用 alpha）；margin = bbox 到画幅边像素数。

### hi 画幅 `depth.png` / `clay.png`（456×416）— 边距判定用此表

| 图 | top | bottom | left | right | ≥16? |
|----|----:|-------:|-----:|------:|------|
| **depth.png（实读根）** | **34** | **37** | **96** | **96** | **YES** |
| clay.png（同根） | 34 | 37 | 96 | 96 | YES |

### SDXL 优先加载的 `depth_768.png`（768×768 letterbox）

| 图 | top | bottom | left | right | ≥16? |
|----|----:|-------:|-----:|------:|------|
| depth_768.png | 210 | 213 | 252 | 252 | YES（含 pad） |

`export_report.json`：`directions.d225.refit_margin=0.08`；本轮 d225 已带 fit。

## 3. docs 副本对照（**非实读**）

- `docs/.../control_maps/d225/depth.png` 与 cats 实读文件 **`cmp` 字节一致**（sha256 前缀 `0525b625846d9b00`）。
- 四边 margin 与上表相同：34 / 37 / 96 / 96。
- 故先前「cats=0、docs=34/37」的猜测对 **当前磁盘上的 d225 不成立**；当前两边同源且已 ≥16。  
  （贴边风险仍在 **d135/d180** 等向，见 `CONTROL_FRAME_MARGIN_NOTE.md`，那些向本轮不动。）

## 4. 是否需要为本轮「≥16 边距」重导出 d225？

| 问题 | 结论 |
|------|------|
| 实读路径 d225 四边 ≥16？ | **YES** |
| 需要仅为边距门槛重导出？ | **NO**（已达标） |
| tip | 边距阻塞已解除；若仍开「恰好 1 次」d225 受控重生，是为碎斑源图问题，**不是**控图贴边。仍禁盲第三次、禁假绿、禁 soft-down。等 opus 显式拍板后再开跑。 |

## 5. 本轮动作

- 仅写本笔记 + commit/push。
- **未**重渲 control、**未** SDXL、**未**改 fur。
