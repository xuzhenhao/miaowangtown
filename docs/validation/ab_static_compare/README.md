# 喵汪小镇 · 静态单帧 A/B 路线实景对比报告

日期：2026-10-28（Asia/Shanghai UTC+8）  
隔离实验目录：`docs/validation/ab_static_compare/`（**未改动**生产目录 `prototype/public/base/` 与 `assets/cat_base.glb`）

---

## 1. 核心结论

在同一套 **HD-2D 微 Q 头身比 3D 底座 (`cat_chibi_base.glb`) + 离屏像素化 + 1px 深褐像素外描边 + 接地阴影** 管线下，完成路线 A 与路线 B 的最小静态单帧实景对比：

- **路线 B（精绘分层 UV 纹理底图 + 真照采样色板与五印记掩码）显著优于路线 A，最接近红框理想参考图**：
  1. **五官与神态**：大杏仁翠绿眼（深褐上眼线、深翠外环、亮翠下月牙、竖瞳、左上纯白高光）与小巧粉鼻在 84×84 像素网格下依然清晰灵动，彻底解决了 v1–v3「写实小头缩成几颗泥巴点 + 外挂绿圆片像眼镜怪」的根因。
  2. **咩咩专属非对称五印记精准还原**：
     - ① **阴阳花生嘴套**：白底嘴套，猫右嘴套（画面左/远端）连鼻暖焦糖斑，猫左嘴套（画面右/近端）干净白脸颊配浅杏下唇边；
     - ② **雪白胸围脖与左肋白云**：胸前白围脖自然向下延伸至肚皮，左肋腹（朝向镜头侧）有一块向上漫延的白云斑；
     - ③ **肚皮小暖橘斑**：腹部白毛边缘带暖橘过渡斑；
     - ④ **四蹄前高后短白袜**：前腿过膝长白袜（含右前腕内侧焦糖小斑）、后腿短白袜 + 大腿深棕虎斑条纹（花裤衩）；
     - ⑤ **背部鲭鱼虎斑与环纹黑尖尾**：暖棕底色配清晰深黑棕鲭鱼竖纹、尾巴环纹与黑褐尾尖。
  3. **全视角稳定性与可扩展性**：路线 B 在 3D 连续表面空间按分层规则与毛簇边界抖动直接烘焙到非对称 UV 图集（`route_b_atlas_1024.png`），360° 无投影拉伸接缝；未来任意新猫只需替换 `CatDNA` 色板与印记掩码参数即可复用同一套精绘像素画风。
- **路线 A（AI 深度/视角受控生成 + 3D 相机反投烘焙 UV）的局限**：
  - 单视角正面/侧前投影虽然能快速贴出毛色，但 AI 生成图在 3D 曲面边缘（如四肢内侧、耳廓背面、背脊转折处）存在视角遮挡与透视拉伸；下采样为低分辨率像素后，虎斑条纹与阴阳嘴套边界不如路线 B 锐利干净。

---

## 2. 关键产物清单

| 文件路径 | 说明 |
|---|---|
| `docs/validation/ab_static_compare/target_redbox_ref.png` | 用户红框理想参考原图归档 |
| `docs/validation/ab_static_compare/ab_town_comparison.png` | **四宫格核心对比总图**（Panel 1 红框原图 + Panel 2 路线 B 实景与 4x 放大 + Panel 3 路线 A 实景与 4x 放大 + Panel 4 咩咩真照五印记对照） |
| `docs/validation/ab_static_compare/route_b_in_town.png` | **路线 B** 合成进小镇石桥/客栈门口高清实景大图（1364×1064） |
| `docs/validation/ab_static_compare/route_a_in_town.png` | **路线 A** 合成进小镇石桥/客栈门口高清实景大图（1364×1064） |
| `docs/validation/ab_static_compare/cat_chibi_base.glb` | 微 Q 头身比（头占全身高 ~42%、圆润脸颊、大立耳、3/4 迈步姿态）一体水密 3D 底座 |
| `docs/validation/ab_static_compare/route_b_atlas_1024.png` | 路线 B 精绘分层 + 真照五印记 1024×1024 非对称 UV 贴图 |
| `docs/validation/ab_static_compare/route_a_atlas_1024.png` | 路线 A AI 视角受控生成 + 相机反投烘焙 1024×1024 UV 贴图 |
| `docs/validation/ab_static_compare/route_b_sprite.png` | 路线 B 离屏像素化 + 1px 外描边 + 像素胡须透明精灵图 |
| `docs/validation/ab_static_compare/route_a_sprite.png` | 路线 A 离屏像素化 + 1px 外描边 + 像素胡须透明精灵图 |
| `docs/validation/ab_static_compare/build_chibi_base.py` | Blender 微 Q 底座生成与非对称 UV 展开脚本 |
| `docs/validation/ab_static_compare/render_route_b.py` | 路线 B 分层 UV 合成与离屏像素化渲染脚本 |
| `docs/validation/ab_static_compare/render_route_a.py` | 路线 A AI 视角相机反投烘焙与离屏像素化渲染脚本 |
| `docs/validation/ab_static_compare/composite_comparison.py` | 小镇实景接地阴影合成与四宫格对比图生成脚本 |
