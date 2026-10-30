# V1 腹底 SDXL + 对照 fuse 报告

**时间**：2026-10-30 17:20:17 Asia/Shanghai  
**状态**：**seed2 PASS · 对照 fuse 已出 · baseline fur 未冻未改**  
**禁**：假绿填红 / 软降 / 拧 EDGE·graze / 冻 / 开 M3。未交用户点冻结。

## Seeds（恰好 2）

| try | seed-offset | 实际 seed | CLIP | 4x 结论 |
|---|---:|---:|---:|---|
| 1 | 80011 | 20341975 | 76 | **FAIL** — 下半身碎块/后腿不完整；已归档 `archive_seed1/` |
| 2 | 81011 | 20342080 | 76 | **PASS** — 腹底白围兜连续、四腿可读、剪影外鬼影 0 / 单连通；足端锯齿与 clay 控图同形 |

## 对照 fuse（island=bary · v1_belly 权 0.85）

| 口径 | 基线 | +V1 候选 | Δ |
|---|---:|---:|---:|
| 诚实岛 GY | 0.8117 | **0.9493** | **+13.76 pp** |
| 诚实岛 红 | 0.1882 | **0.0507** | **-13.75 pp** |
| 高频 GY（报告） | — | 0.9676 | — |

- 硬门 GY≥0.92 / 红≤0.20：**过**（诚实岛与高频均过）
- 战役 GY≥0.90 + 肚皮/背向红下降：**过**（face_detail 不进成功标准）
- 区域红（覆盖 RGB 启发式，相对基线 coverage）：肚皮 −85.13%；背 −100%；腿 −87.42%；face_detail −76.4%（实收、非战役门槛）

## Baseline 保护

- 对照前备份 → 对照后另存候选 → **已 restore** `fur_albedo.png` sha `46e56675a577…`
- 候选：`fur_albedo_v1_belly_candidate.png` / `coverage_v1_belly_candidate.png`
- **未冻**、**未开 M3**

## 脚本最小改动

- `generate_complementary_sdxl.py`：`EXTRA_VIEWS=["v1_belly"]`；默认 `--run` 仍只跑 COMPLEMENTARY
- `fuse_8dir_albedo.py`：`EXTRA_VIEW_CAMERAS.v1_belly` pitch−30 + export_report 内参；权 0.85；旧 8 向内参不变

## 非目标 / 阻塞

- 无阻塞开下一动作；是否冻 fur / 是否开 M3 **须制作人审后另授权**（本报告不请用户冻结）
- face_detail 红虽降，**不进本仗成功标准**

路径：`docs/validation/m2_2_8dir/hold_diag/v1_belly_sdxl/`
