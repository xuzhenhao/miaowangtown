# 喵汪小镇 · 路线 A v4 彻底修复报告（纯净 AI 原生像素 + 零残爪鬼影/零竖条伪影）

日期：2026-10-28（Asia/Shanghai UTC+8）  
隔离目录：`docs/validation/route_a_v4_clean/`（**未改动**生产目录 `prototype/public/base/` 与 `assets/cat_base.glb`）

---

## 1. 上一版 `Route A v3` 四大严重缺陷复盘与 `v4` 彻底修复

| 问题项 | `Route A v3` 被打回根因 | `Route A v4` 彻底修复方案 |
|---|---|---|
| **1. 脚下 4 只「鬼影残爪」与顶部「竖条拉伸」** | 旧背景修补脚本 `make_clean_town_plate.py` 存在两个致命 bug：① 对 `y > 622, x < 785` 跳过修补，导致原图红框猫底部的 4 只白爪（`y ∈ [638..665]`）直接残留在石板地上；② 台阶区使用了 `x % 6` 取模，产生 6px 周期栅栏状竖条伪影 | 全新编写 `build_clean_town_bg.py`：① 将石板地修补区完整覆盖到 `y ∈ [500..690], x ∈ [700..980]`，整块无缝克隆右侧干净石板地纹理，**原猫 4 只残爪与阴影 100% 彻底清除**；② 门廊台阶区（`y ∈ [442..502]`）直接克隆紧邻右侧的真实水平台阶纹理，**100% 消除竖条拉伸伪影** |
| **2. Python 硬画橙色油漆点与死板八字胡** | v3 用脚本在 3D/UV 上硬叠加了椭圆形橘色斑、右腕橘色圆点和深棕八字胡块，缩成像素后像贴了油漆膏药 | **彻底删除一切 Python 椭圆/圆形涂色代码**！直接用 `GenerateImage` 结合红框参考猫与咩咩真照生成原生高水准 AI 精灵底图（`route_a_v4_ai_source.jpg`），右嘴套暖焦糖斑与左白脸颊、胸腹白毛均自然融入毛流笔触 |
| **3. 14 色强制量化导致「迷彩碎斑」** | v3 的 14 色强制聚类把 AI 原生柔和立体的毛发切成了生硬杂乱的深浅棕迷彩块 | **彻底移除 14 色强制量化**！在干净抠除背景后，直接用纯 Nearest 采样到 114×104 逻辑网格并按 2×2 整数像素块输出，100% 保留 AI 原生丰富的毛发过渡与锐利颗粒感 |
| **4. 缺右后腿（仅 3 腿）、爪尖锯齿叉子、死黑尾** | 旧 3D 底座相机角度下右后腿被遮挡，且脚本硬画了爪尖黑竖线、尾巴量化成一团死黑 | 新生成的 `Route A v4` **四条腿与四只白袜完整分离且步态自然**（前长白袜、后短白袜），尾巴具有清晰的深浅棕交替环纹，爪子干净圆润 |

---

## 2. 产物文件清单

| 文件路径 | 说明 |
|---|---|
| `docs/validation/route_a_v4_clean/route_a_v4_comparison.png` | **三联同视野放大特写直比图**（左：Target 红框目标猫特写；中：被打回的 v3 问题暴露图；右：全新修复的 v4 特写） |
| `docs/validation/route_a_v4_clean/route_a_v4_closeup_crop.png` | **与用户打回截图完全同视野的 v4 4x 放大特写图**（供直接核验脚下石板地、头顶台阶、四条腿与毛发质感） |
| `docs/validation/route_a_v4_clean/route_a_v4_in_town.png` | **路线 A v4** 放入干净小镇实景高清完整大图（1364×1064） |
| `docs/validation/route_a_v4_clean/clean_town_bg.png` | 彻底清除 4 只残爪鬼影与顶部竖条伪影后的干净小镇空背景图 |
| `docs/validation/route_a_v4_clean/clean_town_bg_closeup_check.png` | 干净小镇空背景在猫立区域的特写核验图（证明 0 残爪、0 竖条） |
| `docs/validation/route_a_v4_clean/route_a_v4_ai_source.jpg` | AI 原生生成的咩咩高清底图（四腿齐全、环纹尾、自然阴阳嘴套与绿眼） |
| `docs/validation/route_a_v4_clean/route_a_v4_sprite.png` | 路线 A v4 2×2 像素块透明精灵图（228×208） |
| `docs/validation/route_a_v4_clean/build_clean_town_bg.py` | 无缝石板地与水平台阶背景修复脚本 |
| `docs/validation/route_a_v4_clean/build_route_a_v4.py` | 纯净 AI 精灵提取、2×2 逻辑网格对齐与实景合成脚本 |
| `docs/validation/route_a_v4_clean/build_v4_comparison.py` | 三联放大特写对比图生成脚本 |
