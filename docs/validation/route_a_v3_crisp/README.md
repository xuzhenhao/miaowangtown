# 喵汪小镇 · 路线 A v3 (Crisp HD-2D Edition) 去糊锐化精调报告

日期：2026-10-28（Asia/Shanghai UTC+8）  
隔离目录：`docs/validation/route_a_v3_crisp/`（**未改动**生产目录 `prototype/public/base/` 与 `assets/cat_base.glb`）

---

## 1. 为什么上一版 `Route A v2` 看着「有点糊糊的」？（精准量化诊断）

通过脚本对左上角理想参考图（`target_redbox_ref.png`）与上一版 `route_a_v2` 做逐像素差分与网格自相关测量，定位出三个定量根因：

| 诊断维度 | 左上角红框理想猫 (`Target`) | 上一版 `Route A v2`（偏糊） | 本次 `Route A v3 Crisp`（去糊锐化） |
|---|---|---|---|
| **画布包围盒与像素块尺度** | 包围盒约 **236×208 画布像素**，单个逻辑像素块严格为 **2×2 画布像素**（有效逻辑分辨率 **~118×104**），与桥上小人像素密度完全一致 | 先在 92×92 下生成、放大 3x 到 276×276，合成时又做了一次非整数缩放（276→210），导致原本的像素块出现 **2px 与 3px 混杂错位** | 严格锁定 **118×118 逻辑像素网格**，按 **整数倍 2×2 Nearest** 输出（净猫体 **220×200** 画布像素），**1:1 原生贴入小镇**，零二次缩放 |
| **采样与边缘过渡（邻域差分 `<3.0` 比例）** | **47.2%**（仅在 2×2 逻辑块内部相同，跨逻辑块边界干脆利落，无灰蒙过渡） | **76.1%**（因采用 `Bilinear` 双线性下采样，相邻像素块之间全是半透明灰蒙过渡色 / pillow-shading） | **纯 Nearest 逻辑网格采样 + 14 色保体积色阶吸附 + 孤立噪点滤除**，彻底消灭双线性软糊边，同时保留每块毛色 3~4 档自然 AI 立体明暗 |
| **1px 像素微结构细节** | 翠绿眼锐利双高光与深黑上眼睑线、倒 Y 鼻嘴线、**四只白爪尖清晰的 1px 深褐分趾小竖线** | 爪子是平糊的一团白、鼻下嘴线发虚、条纹与白毛边界发软 | 补齐 **四足爪尖 1px 深褐分趾竖线**、锐利双高光翠绿眼（上深翠/下亮翡翠绿）、清晰倒 Y 鼻嘴线与 1px 实心深褐外描边（`#1b100a`） |

---

## 2. 产物文件清单

| 文件路径 | 说明 |
|---|---|
| `docs/validation/route_a_v3_crisp/route_a_v2_vs_v3_crisp_comparison.png` | **四宫格对比总图**（Panel 1 左上角红框参考 + Panel 2 路线 A v2 偏糊版 + Panel 3 路线 A v3 Crisp 去糊锐化版 + Panel 4 Target vs v2 vs v3 局部 6x 超清并排直比） |
| `docs/validation/route_a_v3_crisp/route_a_v3_in_town.png` | **路线 A v3 Crisp** 1:1 整数像素块合成入小镇实景高清大图（1364×1064） |
| `docs/validation/route_a_v3_crisp/route_a_v3_sprite.png` | 路线 A v3 Crisp 2×2 像素块精灵图（236×236） |
| `docs/validation/route_a_v3_crisp/route_a_v3_sprite_118.png` | 路线 A v3 Crisp 118×118 原生 1:1 逻辑像素精灵图 |
| `docs/validation/route_a_v3_crisp/route_a_v3_atlas_1024.png` | 路线 A v3 Crisp 高反差保频调制 1024×1024 UV 贴图 |
| `docs/validation/route_a_v3_crisp/route_a_v3_highres_render.png` | 路线 A v3 Crisp 离屏像素化前 512×512 3D 渲染图 |
| `docs/validation/route_a_v3_crisp/render_route_a_v3.py` | 路线 A v3 Crisp 渲染、14色保体积色阶吸附与 1px 微结构精修脚本 |
| `docs/validation/route_a_v3_crisp/composite_v2_v3.py` | 1:1 整数像素块实景合成与 4x/6x 对比总图生成脚本 |
