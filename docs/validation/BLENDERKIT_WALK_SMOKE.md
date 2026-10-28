# BlenderKit Domestic Cat · 引擎 walk/sit 冒烟

日期：2026-10-28（Asia/Shanghai）  
对象：`docs/validation/blenderkit_intake/out/cat_base.glb`（~6208v / 11292t，标准 26 骨）  
方法：临时 swap `prototype/public/base/{cat_base.glb,bones.json}` → Vite + Playwright 隔离截图（隐藏城镇网格）→ **测完还原**  
生产母版：**未覆盖**（见 §6）

截图：

| 文件 | 动作 | 机位 |
|---|---|---|
| `docs/validation/blenderkit_intake/smoke_idle.png` | `idle`（近 Rest 静帧） | 侧视，城镇隐藏 |
| `docs/validation/blenderkit_intake/smoke_walk.png` | `walk`（周期约 0.27s ≈ 32%） | 侧视 |
| `docs/validation/blenderkit_intake/smoke_sit.png` | `sit`（已 force + 推进 ~1.2s） | ¾ 前侧视 |

> 引擎 console 大量 `THREE.Material: parameter 'map' has value of undefined` —— 与 intake 文档一致：Voxel Remesh **抹掉原 UV**，毛色投影失真（白斑/接缝噪声），**不代表**生产母版状态。

---

## 1. 结论（制作人一行）

**HOLD（管线可接，画面不可当生产）**：`--input` 产物能被现有引擎以 `source=glb` 加载，idle / walk / sit **三个 clip 都能 force 驱动**；但 Rest 略迈步不对称 + 网格比标准骨更长 + 无 UV，导致走/坐出现后肢碎裂、颈肩塌陷、坐姿驼背拉腿。**不建议**直接调咩咩；优先 **对称 Rest + 骨/网对齐**，并开 **轻量 intake（跳 Remesh、留 UV）**。

| 门 | 结果 |
|---|---|
| 引擎加载 intake GLB | **PASS**（6208 v，`cat.source === 'glb'`） |
| idle / walk / sit clip 可播放 | **PASS**（动作库零改） |
| 静帧/步态视觉可接受 | **HOLD / FAIL** |
| 可直接进咩咩调成 | **NO** |
| 生产 `public/base` / `assets` 干净 | **PASS**（§6） |

---

## 2. 现象（诚实记录）

### 2.1 略迈步 Rest · 左右不对称 — **确认**

- idle 侧视已呈**对角迈步**（一前一后支撑），不是对称中性站立。
- Blender 量测 intake 网格（Three 坐标）：最低触地簇近似 **FR + HL** 对角着地；`FL`/`HR` 低点簇空。
- 镜像不对称粗测（800 点子样）：median ≈ 0.038，**p90 ≈ 0.30**，max ≈ 0.43 —— 远大于「可忽略的雕刻噪声」。
- 与 intake 文档「非 A/T、略带迈步自然站姿」一致，且在引擎 idle 下被动作库直接当 Rest 用，**放大为永久步态偏置**。

### 2.2 网格 vs 标准 26 骨尺度 — **错位（根因级）**

| | z 跨度 | 备注 |
|---|---:|---|
| intake 网格 | **≈ 2.62** | `z ∈ [-1.31, 1.31]` |
| 生产母版网格 | ≈ 1.84 | `z ∈ [-0.98, 0.86]` |
| intake / 生产 `bones.json` 骨头 | ≈ 1.55 | 两套骨 **位姿数值相同**（模板骨） |

爪尖区域网格远伸到 z≈0.88～1.18，而 `fpaw*` 骨头停在 z≈0.31 —— **热权重蒙皮可以把 seam/shear 审计打到 0，但腿骨够不着真实脚掌体积**。这能解释走/坐时下肢「漂、碎、拉丝」。

### 2.3 脚穿地

- 隔离帧无地面网格，无法用「脚陷进地板」直接判穿地。
- Rest `min_y ≈ 0.0002`（贴地）；动画帧中后肢白块有**离体漂浮**，更像蒙皮/骨网错位，而非单纯穿地。
- **暂记：未见经典「整脚没入地面」；有后肢离体/碎裂。**

### 2.4 腿反向折断 / 碎裂 — **walk 严重，sit 中等**

- **walk**：后肢白袜区域出现**碎片化、与大腿脱离**；前肢腕/掌有压扁；关节处锐角折点。
- **sit**：前腿异常拉长下插；后肢蜷压缩、角度生硬。
- 不像「膝盖反折成卡通」单一问题，而是 **骨网错位 + Remesh 拓扑** 叠加的撕裂。

### 2.5 脊柱塌 — **sit 明显，walk/idle 有台阶感**

- **sit**：背中段强烈拱起/驼峰，头相对肩塌低，**不是**干净坐姿剪影。
- idle/walk：背线有锯齿/台阶剪切（像素管线会加重，但轮廓本身不平滑）。

### 2.6 尾异常 — **有**

- idle：尾中段折线/锯齿，根部分段错位。
- walk：尾短、块状水平伸出。
- sit：尾几乎看不见，疑似卷入后躯或压进体积。

### 2.7 其他

- 五官面片（绿眼镜式投影）在 `faceProj=0` 下仍可能残留锚点精灵观感；Remesh 后面锚不可靠。
- 毛色仍能「看起来像狸花」，但是错误 UV/烘焙投影，**不能**当贴图验收。

---

## 3. 方法备忘（可复现）

1. 备份生产：`docs/validation/blenderkit_intake/smoke_backup/`（与测前 `public/base` 哈希一致）。
2. 复制 `out/cat_base.glb` + `out/bones.json` → `prototype/public/base/`。
3. Playwright + Vite（参考历史 `/tmp/recapture_walk.mjs`）：`action=idle|walk|sit`，`ui=0`，evaluate 内隐藏非猫网格、锁位、`stepSimulation` 推进后截 `#view`。
4. **立即**从 `smoke_backup` 还原；`sha256sum` / `cmp` 核对生产。

未改业务源码；未重跑 `--input`；未提交 `.blend`。

---

## 4. 与上一轮 intake 的衔接

| intake 已记 | 本轮冒烟 |
|---|---|
| Royalty Free ≠ CC0 | 不变；仍只适合内部验证 |
| Remesh 掉 UV | 引擎 `map=undefined` + 毛色失真 **实锤** |
| 重建 26 骨、skin 审计 0 | 动作**能挂上**；但模板骨未贴合加长网格 → 动起来炸 |
| 略迈步 Rest | idle 侧视 + 触地簇对角 **实锤** |

---

## 5. 建议下一步（优先级）

1. **先对称 Rest / 对齐骨网（必做）**  
   - 把网格重目标到对称站立（或四足平均站），再 **按截面重算 26 骨位置**（或均匀缩网格到现有骨跨度）。  
   - 不对称迈步 Rest 不修，动作库会一直「带着瘸走」。
2. **开轻量 intake（跳 Voxel Remesh，保留 UV + 锐边）**  
   - 用 `domestic_cat_clean.glb` 路线做减面/焊接，保留狸花漫反射，便于第一轮调咩咩看花色。
3. **再调咩咩**  
   - 仅当 1+2 后 walk/sit 侧视不再碎腿、坐姿剪影可辨。

**不建议**：把当前 `out/cat_base.glb` 推进 `public/base` 或开始 DNA/形态键精调。

---

## 6. 生产未脏证明

测前 / 测后哈希一致：

| 文件 | sha256 |
|---|---|
| `prototype/public/base/cat_base.glb` | `8b3cd01e56c63e503c025da5738e46c2e4d85909e3317f677aaed92e516c2bc0` |
| `prototype/public/base/bones.json` | `1fbf37f76a05437f5aeb0d4e1c67b8361fdb88632e57bc925fe432d87df50bfc` |
| `assets/cat_base.glb` | 与 `public/base/cat_base.glb` **cmp 相同** |

临时 swap 期间用过 intake：

| 文件 | sha256 |
|---|---|
| intake `out/cat_base.glb` | `259ded09ce944d1c5db4ce1ebb35b18ad3df968a522360691015cad5018d408c` |
| intake `out/bones.json` | `3d2a0f22bf11aadcd5301332e11b783fe1da677f48abe5f2adbddea687917f1f` |

还原源：`docs/validation/blenderkit_intake/smoke_backup/`（本地备份，**不入库**亦可；与 `backup_before/` 同内容）。
