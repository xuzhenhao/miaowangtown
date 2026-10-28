# 喵汪小镇 · 路线 A v2 静态单帧精调报告（保频毛发五印记 + 翠绿大眼精修）

日期：2026-10-28（Asia/Shanghai UTC+8）  
隔离目录：`docs/validation/route_a_v2_polish/`（**未改动**生产目录 `prototype/public/base/` 与 `assets/cat_base.glb`）

---

## 1. 精调目标与技术路径

根据用户对上一轮四宫格对比的反馈：
- **锁死「路线 A（AI 视角生成 + 3D 相机投影烘焙 UV + 离屏像素化）」的自然体积柔光与真猫毛发层次感**；
- **严禁使用生硬纯色块覆盖**，全部采用**基于 AI 毛发明度的高频保留色彩/明度调制（Frequency-Preserving Fur Tint & Luma Modulation）**，在 100% 保留原有 AI 绒毛笔触与体积过渡的前提下，将咩咩的五印记与翠绿大眼神态打磨到位。

---

## 2. 五印记与眼神精修清单（Route A v1 → Route A v2）

| 序号 | 特征项 | Route A v1（精调前） | Route A v2（本次精调后） |
|---|---|---|---|
| **①** | **阴阳花生嘴套** | AI 默认生成偏对称白嘴套，右嘴套缺少焦糖花生斑 | 猫右嘴套（画面左侧，鼻翼至右嘴角）保频调制出温暖焦糖花生斑（带深褐胡须垫微点），猫左嘴套（画面右侧脸颊）提亮为干净奶油白，还原「右满左浅」非对称神态 |
| **②** | **雪白胸围脖 + 左肋腹白云斑** | 胸前有白毛，但左肋腹完全被连续深棕条纹覆盖 | 胸围脖向下自然连到肚皮，并在正对镜头的左肋腹（`+X` 中下腹）向上柔和漫延出一朵毛绒边缘的浅白「白云」斑，自然托起侧身虎斑 |
| **③** | **腹缘小暖橘过渡斑** | 无暖橘过渡，白毛与深棕条纹直接交界 | 在左肋腹白云斑后上缘与深棕虎斑交界处，保频晕染出一抹温暖的杏橘/暖橘棕过渡斑（对齐真照 `miemie_ref_08`） |
| **④** | **前高后低四蹄白袜 + 后腿花裤衩** | 四足白袜高度接近，后腿偏白 | 前腿拉高为过膝白袜（右前腕内侧带暖焦糖小斑），后腿收短为脚踝踩雪白袜，后大腿外侧強化深褐虎斑横纹（花裤衩） |
| **⑤** | **翠绿杏仁大眼 + 砖红粉鼻** | 绿眼偏暗、竖瞳与高光在缩成像素后不够通透 | 加深上眼睑深棕眼线与垂直细竖瞳，虹膜做「上深翠→下亮翡翠绿」通透渐变，点亮左上纯白主高光 + 右下次高光；鼻头润色为温润砖红粉（`#d66856`） |
| **像素层** | **网格分辨率与描边** | 84×84 最近邻下采样 | 升级为 **92×92 混合采样（毛发区双线性保柔和体积 + 眼部/高光区最近邻保锐利眼神）** + 1px 深褐外描边（`#1b100a`）+ 左侧嘴边 2 根清晰白像素胡须 |

---

## 3. 产物文件清单

| 文件路径 | 说明 |
|---|---|
| `docs/validation/route_a_v2_polish/route_a_v1_vs_v2_comparison.png` | **四宫格对比总图**（Panel 1 红框原图 + Panel 2 路线 A v1 + Panel 3 路线 A v2 含 ①~⑤ 标注 + Panel 4 咩咩真照五印记对照） |
| `docs/validation/route_a_v2_polish/route_a_v2_in_town.png` | **路线 A v2** 放入小镇石桥/客栈门口高清实景图（1364×1064） |
| `docs/validation/route_a_v2_polish/route_a_v2_atlas_1024.png` | 路线 A v2 保频调制后的 1024×1024 UV 贴图 |
| `docs/validation/route_a_v2_polish/route_a_v2_highres_render.png` | 路线 A v2 离屏像素化前的 512×512 3D 渲染图 |
| `docs/validation/route_a_v2_polish/route_a_v2_sprite.png` | 路线 A v2 92×92 像素化 + 1px 深褐描边 + 像素胡须精灵图（3x 放大展示） |
| `docs/validation/route_a_v2_polish/route_a_v2_sprite_lowres.png` | 路线 A v2 原生 92×92 1:1 像素精灵图 |
| `docs/validation/route_a_v2_polish/render_route_a_v2.py` | 路线 A v2 保频 UV 烘焙、眼神精修与混合像素化脚本 |
| `docs/validation/route_a_v2_polish/composite_v1_v2.py` | 实景接地阴影合成与四宫格对比图生成脚本 |
