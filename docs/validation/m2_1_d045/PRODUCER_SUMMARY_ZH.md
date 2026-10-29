# M2.1 制作人自审摘要（诚实修订版）

## 结论
**本视角（d045）视觉可进互补方向**；`quantize_mode=none` 仍成立。  
**整张 `fur_albedo.png` 尚未冻结**（背侧 / 对面斜前仍空，留给 M2.2）。

## 三个数字不是新证据（请以 4x 对照板为准）

1. **剪影 max_d 2.0 / IoU 0.9521**  
   Alpha 锁死为 **M1 几何剪影**；M2.1 只换 RGB。轮廓数字与 M1 相同是构造结果，**不是**本阶段新剪影证明。

2. **五印记自动分区**  
   嘴套焦糖 `_R` 41 / 左颊焦糖 52、左肋白云 4、胸前 bib 盒白 69——分区启发式偏软；bib 盒白在 v4.1 也有（约 40），**不能**当成换侧失败。换侧改为相对 v4.1 的花生斑 / 左肋云是否消失。最终以 4x 板肉眼为准。

3. **眼睛 exact 计数**  
   门禁主计数改在 **Layer A（纯 Albedo）**：睑 26 / 外 21 / 内 26 / 瞳 40 / 高光 10。  
   Layer B 叠灯笼光后 exact 瞳孔/睑可到 0，属色相偏移，**不作为否决**。

## 仍成立的验收

| 项 | 结果 |
|---|---|
| 观感 vs v4.1（4x） | 斑纹 / 白围脖 / 白爪 / 绿眼同位，像同一只猫 |
| 白爪灰边 | fringe **2**（≤6） |
| 色板 | **`quantize_mode=none`**（真彩 camo 最优） |
| M1 `uv_hash` | 未变 |
| coverage | 单视角岛内绿+黄 ≈33%，红未见留给 M2.2（预期） |

## 路径
- `cats/miemie/identity_v1/{genome,markings,fur_albedo,coverage}.*`
- `docs/validation/m2_1_d045/` 检视板与 `m2_1_gates_report.json`（含 `honesty_revision`）
- `art/master_cat/render_spec.json` → `quantize_mode=none`
