# 喵汪小镇 · Route A v4.1 终极静态标杆版报告

日期：2026-10-28（Asia/Shanghai UTC+8）  
隔离目录：`docs/validation/route_a_v4_1_ultimate/`（**未改动**生产目录 `prototype/public/base/` 与 `assets/cat_base.glb`）

---

## 1. 三项视觉精修升级（Route A v4 → Route A v4.1）

在 **100% 守护 `Route A v4` 的纯正 AI 原生毛流、零脚本硬画几何色块、零 14 色强制迷彩量化、零残爪鬼影** 的基础上，精准落地三项终极静态打磨：

| 升级项 | `Route A v4`（基础通过版） | `Route A v4.1`（终极静态标杆版） | 定量/视觉提升 |
|---|---|---|---|
| **升级 1：掩码内预滤波 + 区域积分采样（去跳采飞点与爪边灰刺）** | 从 `901×823` 直接一步 `NEAREST` 跳采到 `114×104`（每 8×8 像素只抽 1 点），深棕虎斑内偶有孤立跳采飞点（Luma 孤立离群点 **222 个**），白爪边缘偶见半透明灰刺 | 先向掩码外延展填充 16px 前景毛色，经 3×3 保边中值滤波后，采用 **`BOX` 区域积分均值采样 + 适度 UnsharpMask + 眼部高光保锐 + 4邻域孤立飞点滤除**，并配合 `alpha > 162` 硬边掩码 | 单像素孤立离群飞点从 **222 个降至 57 个（减少 74.3%，剩余均为眼部真实高光点）**，虎斑条纹如丝绸般凝练，白爪紧贴 `#1b100a` 深褐外描边，零灰刺 |
| **升级 2：顺毛流柔化强化「咩咩非对称五印记」** | 四足白袜高度较接近，左脸颊与左肋腹白云斑对比可更鲜明 | 在 `901×823` 高分图上用大半径（`r=15~22px`）无边界高斯场乘以局部毛流明度比（`fur_detail_ratio`）做柔化微调：① 提亮左脸颊奶油白、温润右嘴套暖焦糖花生斑；② 左肋腹白云自然向上漫延，上后缘带出柔和暖杏橘毛根过渡；③ 前腿白袜拉高过腕、后腿收短至脚踝 | 放大 4x 核验**零人工几何边界**，五印记完全长在原生毛流笔触中，前高后低白袜与阴阳嘴套一眼可辨 |
| **升级 3：HD-2D 小镇环境光影与腹底 AO 融合** | 猫体受光偏均匀平面 | 叠加匹配小镇右上暖灯笼与夕阳方向的 **头顶/耳背/背脊暖琥珀受光层（`+5.5% R, +2.5% G`）** 与 **下颌底/肚皮下沿/内侧腿柔和环境闭塞压暗层（`-11% Soft AO`）**，并升级四足双层接地投影 | 猫体与古镇石板街的暖光氛围浑然一体，立体感显著提升 |

---

## 2. 产物文件清单

| 文件路径 | 说明 |
|---|---|
| `docs/validation/route_a_v4_1_ultimate/route_a_v4_vs_v4_1_comparison.png` | **三联同视野 4x 放大特写直比图**（左：Target 红框猫 | 中：Route A v4 | 右：Route A v4.1 终极标杆版） |
| `docs/validation/route_a_v4_1_ultimate/route_a_v4_1_closeup_crop.png` | **与用户截图同视野的 `Route A v4.1` 4x 放大特写图** |
| `docs/validation/route_a_v4_1_ultimate/route_a_v4_1_in_town.png` | **`Route A v4.1` 小镇实景完整高清大图（1364×1064）** |
| `docs/validation/route_a_v4_1_ultimate/route_a_v4_1_sprite.png` | `Route A v4.1` 2×2 像素块透明精灵图（228×208） |
| `docs/validation/route_a_v4_1_ultimate/route_a_v4_1_sprite_logical.png` | `Route A v4.1` 原生 1:1 逻辑网格精灵图（114×104） |
| `docs/validation/route_a_v4_1_ultimate/build_route_a_v4_1.py` | `Route A v4.1` 掩码外延预滤波、顺毛流五印记柔化、环境光影融合与合成脚本 |
