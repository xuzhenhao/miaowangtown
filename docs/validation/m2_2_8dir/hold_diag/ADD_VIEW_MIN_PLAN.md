# 加视角最小计划（半页）

**时间**：2026-10-30 17:20:17 Asia/Shanghai  
**状态**：**V1 SDXL seed2 PASS · 对照 fuse 候选已出 · baseline fur 未改未冻**  
**禁**：假绿填红、软降、拧 EDGE/graze、盲 regen、降硬门、冻、开 M3。

---

## V1 进度

| 项 | 状态 |
|---|---|
| 控图 yaw0 pitch−30 | ✅ |
| SDXL ≤2 seed | ✅ seed1 FAIL / **seed2 PASS**（81011→20342080） |
| 对照 fuse（bary） | ✅ 候选 GY **0.9493** / 红 **0.0507**；baseline `46e56675…` 已还原 |
| 硬门 0.92 / 红 0.20 | ✅ 过（诚实岛） |
| 战役 GY≥0.90 + 肚皮/背向红降 | ✅ |
| 冻 fur / 开 M3 | **未做** — 等制作人审 |

## 非目标

- face_detail 不进本仗成功标准。
- 不请用户冻结。

详报：`hold_diag/v1_belly_sdxl/V1_BELLY_SDXL_REPORT.md`
