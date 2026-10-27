#!/usr/bin/env python3
"""
喵汪小镇 · Blender 无界面母版猫生成与标准化流水线 (build_base.py)
===================================================================
用法：
  1. 默认模式（Blender 有机曲面 + Voxel Remesh 一体水密流形母版生成）：
     blender -b -P prototype/tools/blender/build_base.py
  2. 外部 AI 图生 3D 模型导入归一化模式（Tripo / Meshy / 混元3D）：
     blender -b -P prototype/tools/blender/build_base.py -- --input path/to/raw_cat.glb

按方案依次执行 9 步流水线：
  1. 导入外部模型或生成有机 Q 版母版曲面，按包围盒归一化到 Three.js 标准坐标系（地面 y=0，猫朝 +Z，猫左侧 +X）
  2. 体素重建（Voxel Remesh）消除内部穿插和破洞 -> 平滑（Smooth）-> 减面到 4k~6k 三角面 + 解剖细节精修
  3. 部件标签：按 11 个解剖区域写入自定义属性 `_PART`（0..10）
  4. 拆非镜像 UV：绝不左右镜像，嘴套与头部区域纹素密度放大 1.6 倍以上，接缝切分保持焊接法线连续
  5. 同名同层级 26 根骨骼构建与截面中心对齐，导出 `prototype/public/base/bones.json`
  6. 计算平滑骨骼蒙皮权重（躯干/颈部/四肢/尾巴/耳朵连续过渡）
  7. 基于区域掩码与平滑衰减生成 6 个标准形态键：`headRound, weight, earSize, tailFluff, cheekFluff, muzzleSize`
  8. 计算脸部锚点 `eyeL / eyeR / mouth / whiskerL / whiskerR`（位置 + 法线 + 绑定顶点），写入 glTF extras
  9. 导出 `prototype/public/base/cat_base.glb` 与 `assets/cat_base.glb`
"""

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

PART_NAMES = [
    "head",    # 0
    "muzzle",  # 1
    "neck",    # 2
    "body",    # 3
    "fLegL",   # 4
    "fLegR",   # 5
    "hLegL",   # 6
    "hLegR",   # 7
    "earL",    # 8
    "earR",    # 9
    "tail",    # 10
]

# 512x512 非镜像 UV 图集矩形分配 [x, y, w, h]（头部与嘴套分配高密度大区块，放大 >1.6x）
ATLAS_SIZE = 512
PART_RECTS = {
    0: (0, 0, 256, 128),     # head (256x128 高密度区)
    1: (256, 0, 128, 64),    # muzzle (128x64 高密度区)
    2: (384, 0, 128, 64),    # neck
    3: (0, 128, 256, 192),   # body
    4: (256, 64, 64, 96),    # fLegL
    5: (320, 64, 64, 96),    # fLegR
    6: (384, 64, 64, 96),    # hLegL
    7: (448, 64, 64, 96),    # hLegR
    8: (256, 160, 64, 64),   # earL
    9: (320, 160, 64, 64),   # earR
    10: (0, 320, 256, 64),   # tail
}

SHAPE_KEYS = ["headRound", "weight", "earSize", "tailFluff", "cheekFluff", "muzzleSize"]

TAIL_CURVE_PTS = [
    Vector((0.0, 0.64, -0.44)),
    Vector((0.0, 0.60, -0.56)),
    Vector((0.0, 0.58, -0.68)),
    Vector((0.0, 0.62, -0.80)),
    Vector((0.0, 0.70, -0.88)),
    Vector((0.0, 0.80, -0.93)),
    Vector((0.0, 0.90, -0.95)),
]
TAIL_BONE_T = [0.04, 0.20, 0.36, 0.52, 0.68, 0.84]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def catmull_rom(pts: list[Vector], t: float) -> Vector:
    n = len(pts) - 1
    ft = clamp(t, 0.0, 1.0) * n
    i = min(int(math.floor(ft)), n - 1)
    u = ft - i
    p0 = pts[max(0, i - 1)]
    p1 = pts[i]
    p2 = pts[min(n, i + 1)]
    p3 = pts[min(n, i + 2)]
    u2 = u * u
    u3 = u2 * u
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * u
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u3
    )


def catmull_tangent(pts: list[Vector], t: float) -> Vector:
    eps = 1e-3
    p_a = catmull_rom(pts, max(0.0, t - eps))
    p_b = catmull_rom(pts, min(1.0, t + eps))
    d = p_b - p_a
    return d.normalized() if d.length > 1e-8 else Vector((0.0, 0.0, -1.0))


# Three.js (x, y_up, z_fwd) <-> Blender (x, -z_fwd, y_up)
def t2b(v: Vector) -> Vector:
    return Vector((v.x, -v.z, v.y))


def b2t(v: Vector) -> Vector:
    return Vector((v.x, v.z, -v.y))


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


# ---------------------------------------------------------------------------
# 步骤 1 & 2：构建或导入母版网格 + Blender Voxel Remesh 体素重建一体流形 + 减面平滑
# ---------------------------------------------------------------------------

def create_closed_part_object(name: str, seg_s: int, seg_t: int, pos_fn, core_fn) -> bpy.types.Object:
    """
    生成一个两端闭合封顶（Watertight Closed Solid）、且所有三角面法线严格朝外（dot(n, p - core) > 0）的解剖部件网格物体。
    """
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()

    rings = []
    for j in range(1, seg_t):
        t = j / seg_t
        row = []
        for i in range(seg_s):
            s = i / seg_s
            row.append(bm.verts.new(t2b(pos_fn(s, t))))
        rings.append(row)

    # Top cap vertex (t = 0) & bottom cap vertex (t = 1)
    top_avg = sum(( pos_fn(i / seg_s, 0.015) for i in range(seg_s) ), Vector((0.0, 0.0, 0.0))) / seg_s
    bot_avg = sum(( pos_fn(i / seg_s, 0.985) for i in range(seg_s) ), Vector((0.0, 0.0, 0.0))) / seg_s
    v_top = bm.verts.new(t2b(top_avg))
    v_bot = bm.verts.new(t2b(bot_avg))

    # Top cap fan
    for i in range(seg_s):
        ni = (i + 1) % seg_s
        try:
            bm.faces.new((v_top, rings[0][i], rings[0][ni]))
        except ValueError:
            pass

    # Side quads
    for j in range(len(rings) - 1):
        for i in range(seg_s):
            ni = (i + 1) % seg_s
            try:
                bm.faces.new((rings[j][i], rings[j + 1][i], rings[j + 1][ni], rings[j][ni]))
            except ValueError:
                pass

    # Bottom cap fan
    last_ring = rings[-1]
    for i in range(seg_s):
        ni = (i + 1) % seg_s
        try:
            bm.faces.new((last_ring[i], v_bot, last_ring[ni]))
        except ValueError:
            pass

    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.normal_update()

    # 强制每个三角面的绕序法线严格背离部件内部核心线 core_fn（100% 朝外！）
    for f in bm.faces:
        c_three = b2t(f.calc_center_median())
        n_three = b2t(f.normal)
        core_three = core_fn(c_three)
        if n_three.dot(c_three - core_three) < 0.0:
            f.normal_flip()

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


def build_organic_part_objects() -> list[bpy.types.Object]:
    """
    Stage 1 写实家猫解剖母版：按 CAT_ANATOMY_AND_MIEMIE_SCULPT_SPEC G-01~G-07
    生成眉弓/额鼻台阶、花生形口套、内凹耳廓、肩胛/深胸/收腰/圆臀、趾行四肢与平底四趾猫掌。
    """
    tau = math.pi * 2.0
    objs: list[bpy.types.Object] = []

    # 1. 躯干 G-04：肩胛峰 / 深胸腔 / 后腹收腰 / 圆润十字部
    body_center = Vector((0.0, 0.50, 0.0))

    def body_pos(s: float, t: float) -> Vector:
        ph = clamp(t, 0.01, 0.99) * math.pi
        zc = -math.cos(ph)  # -1 臀, +1 胸
        r = math.sin(ph)
        th = (s - 0.5) * tau
        # 肩胸更宽、腰肋收、后臀圆
        width_profile = 1.0 - 0.10 * zc + 0.10 * math.sin(ph) + 0.05 * math.exp(-(((zc + 0.45) / 0.38) ** 2))
        height_profile = 1.0 + 0.10 * math.cos((zc - 0.18) * math.pi * 0.85)
        rx = 0.238 * width_profile
        ry = 0.248 * height_profile
        X = math.sin(th) * r * rx
        Y = math.cos(th) * r * ry
        if Y < 0:
            # 后腹收腰（Abdominal Tuck）：腹线向后上收
            tuck = 0.82 + 0.10 * clamp((zc + 0.75) / 0.55, 0.0, 1.0) if (-0.75 < zc < -0.05) else 1.0
            # 深胸腔：前下胸向下鼓出
            brisket = 1.12 if (zc > 0.25) else 1.0
            Y *= tuck * brisket
        # 背线：肩胛峰(withers) / 鞍区微凹 / 十字部(croup)
        spine_arc = (
            0.048 * math.exp(-(((zc - 0.48) / 0.32) ** 2))   # withers ~ z=0.24
            + 0.040 * math.exp(-(((zc + 0.48) / 0.34) ** 2))  # croup ~ z=-0.24
            - 0.022 * math.exp(-((zc / 0.30) ** 2))           # thoracolumbar dip
        )
        chest_bib_z = 0.055 * clamp((zc - 0.25) / 0.75, 0.0, 1.0) * r if (zc > 0.25 and Y > -0.18) else 0.0
        return Vector((X, body_center.y + spine_arc + Y, zc * 0.495 + chest_bib_z))

    objs.append(create_closed_part_object("part_body", 48, 40, body_pos, lambda p: Vector((0.0, 0.50, clamp(p.z, -0.38, 0.38)))))

    # 2. 脖子与胸前围脖
    neck_a = Vector((0.0, 0.52, 0.22))
    neck_b = Vector((0.0, 0.88, 0.52))
    neck_d = (neck_b - neck_a).normalized()
    neck_u = Vector((1.0, 0.0, 0.0))
    neck_w = neck_u.cross(neck_d).normalized()

    def neck_pos(s: float, t: float) -> Vector:
        th = (s - 0.5) * tau
        cap = math.sin(clamp(t, 0.02, 0.98) * math.pi) ** 0.25
        base_r = lerp(0.230, 0.172, t) * cap
        chest_fluff = (1.0 - t) * 0.070 * max(0.0, math.cos(th)) * cap
        c = neck_a.lerp(neck_b, t)
        return c + neck_u * (math.sin(th) * base_r * 0.95) + neck_w * (math.cos(th) * (base_r + chest_fluff))

    def neck_core(p: Vector) -> Vector:
        ab = neck_b - neck_a
        t = clamp((p - neck_a).dot(ab) / ab.length_squared, 0.05, 0.95)
        return neck_a.lerp(neck_b, t)

    objs.append(create_closed_part_object("part_neck", 32, 20, neck_pos, neck_core))

    # 3. 头颅 G-01：眉弓 / 浅凹眼窝 / 额鼻台阶(Stop) / 平直鼻梁
    head_center = Vector((0.0, 0.90, 0.54))

    def head_pos(s: float, t: float) -> Vector:
        th = (s - 0.5) * tau
        ph = clamp(t, 0.01, 0.99) * math.pi
        dx = math.sin(ph) * math.sin(th)
        dy = math.cos(ph)
        dz = math.sin(ph) * math.cos(th)
        rx, ry, rz = 0.275, 0.268, 0.258
        crown_taper = 1.0 - 0.10 * clamp((dy - 0.25) / 0.75, 0.0, 1.0) if dy > 0.25 else 1.0
        chin_taper = 1.0 - 0.20 * clamp((-0.40 - dy) / 0.60, 0.0, 1.0) if dy < -0.40 else 1.0
        cheek_bell = math.exp(-(((dy + 0.10) / 0.34) ** 2))
        cheek = 0.055 * cheek_bell * (abs(math.sin(th)) ** 0.80) * math.sin(ph)
        # 眉弓 + 额鼻台阶：双目上方向前微凸，鼻梁根部下凹台阶
        brow = 0.0
        if dz > 0.15 and -0.05 < dy < 0.42:
            brow = 0.022 * math.exp(-(((dy - 0.18) / 0.16) ** 2)) * clamp((dz - 0.15) / 0.55, 0.0, 1.0)
            # Stop 台阶：眉心正中略向前，再向下收成鼻梁起点
            if abs(dx) < 0.35:
                brow += 0.012 * math.exp(-((dx / 0.22) ** 2)) * math.exp(-(((dy - 0.12) / 0.14) ** 2))
        # 浅凹眼窝平面（Orbital sockets）
        orbit = 0.0
        for sx in (1.0, -1.0):
            ox = sx * 0.38  # 单位球上眼窝方位
            oy = 0.05
            oz = 0.72
            d2 = (dx - ox) ** 2 + (dy - oy) ** 2 + (dz - oz) ** 2
            orbit -= 0.028 * math.exp(-(d2 / 0.085)) * clamp(dz, 0.0, 1.0)
        # 鼻梁骨脊：从眉心向前下伸出平直微翘平面
        nasal = 0.0
        if dz > 0.35 and abs(dx) < 0.22 and -0.55 < dy < 0.20:
            ridge = math.exp(-((dx / 0.10) ** 2)) * clamp((dz - 0.35) / 0.50, 0.0, 1.0)
            nasal = 0.030 * ridge * math.exp(-(((dy + 0.15) / 0.28) ** 2))
        face_flatten = (1.0 - 0.04 * dz * dz) if dz > 0 else 0.97
        return Vector((
            head_center.x + dx * rx * crown_taper * chin_taper * (1.0 + cheek),
            head_center.y + dy * ry,
            head_center.z + dz * rz * face_flatten + brow + orbit + nasal,
        ))

    objs.append(create_closed_part_object("part_head", 52, 36, head_pos, lambda _p: head_center))

    # 4. 嘴套 G-02：左右花生形胡须垫 + 人中浅沟 + 独立下巴颏
    muzzle_center = Vector((0.0, 0.820, 0.760))

    def muzzle_pos(s: float, t: float) -> Vector:
        th = (s - 0.5) * tau
        ph = clamp(t, 0.02, 0.98) * math.pi
        dx = math.sin(ph) * math.sin(th)
        dy = math.cos(ph)
        dz = math.sin(ph) * math.cos(th)
        # 花生形分瓣：两侧鼓、正中人中浅沟
        pad = 1.0 + 0.22 * (math.sin(2.0 * th) ** 2) * clamp(dy + 0.45, 0.0, 1.0)
        philtrum = 1.0 - 0.16 * math.exp(-((math.sin(th) / 0.28) ** 2)) * clamp(dz, 0.0, 1.0) * clamp(1.0 - abs(dy), 0.0, 1.0)
        # 独立下巴颏：下半收窄并略向前
        chin = 1.0
        chin_fwd = 0.0
        if dy < -0.15:
            chin = 1.0 - 0.28 * clamp((-0.15 - dy) / 0.85, 0.0, 1.0)
            chin_fwd = 0.018 * clamp((-0.20 - dy) / 0.70, 0.0, 1.0) * clamp(dz, 0.0, 1.0)
        # 倒三角鼻头凸起（鼻梁末端）
        nose_tip = 0.0
        if dy > 0.15 and abs(dx) < 0.35 and dz > 0.2:
            nose_tip = 0.022 * math.exp(-((dx / 0.18) ** 2)) * clamp((dy - 0.15) / 0.55, 0.0, 1.0) * clamp(dz, 0.0, 1.0)
        return Vector((
            muzzle_center.x + dx * 0.138 * pad * chin * philtrum,
            muzzle_center.y + dy * 0.082,
            muzzle_center.z + dz * 0.088 + chin_fwd + nose_tip,
        ))

    objs.append(create_closed_part_object("part_muzzle", 36, 22, muzzle_pos, lambda _p: muzzle_center))

    # 5. 四肢 G-05/G-06/G-07：趾行折角 + 平底楔形四趾猫掌
    legs = [
        ("part_fLegL", 0.145, True),
        ("part_fLegR", -0.145, True),
        ("part_hLegL", 0.155, False),
        ("part_hLegR", -0.155, False),
    ]
    leg_top = 0.56
    paw_y = 0.055
    paw_r = 0.068

    def front_axis_z(y: float) -> float:
        # 肩 z=0.33 → 肘 z=0.27,y=0.30 → 腕 z=0.31,y=0.11 → 掌 z=0.35
        if y >= 0.30:
            t = clamp((y - 0.30) / (0.52 - 0.30), 0.0, 1.0)
            return lerp(0.27, 0.33, t)
        if y >= 0.11:
            t = clamp((y - 0.11) / (0.30 - 0.11), 0.0, 1.0)
            return lerp(0.31, 0.27, t)
        t = clamp(y / 0.11, 0.0, 1.0)
        return lerp(0.35, 0.31, t)

    def hind_axis_z(y: float) -> float:
        # 髋 z=-0.22 → 膝 z=-0.15,y=0.33 → 飞节 z=-0.29,y=0.17 → 掌 z=-0.21
        if y >= 0.33:
            t = clamp((y - 0.33) / (0.52 - 0.33), 0.0, 1.0)
            return lerp(-0.15, -0.22, t)
        if y >= 0.17:
            t = clamp((y - 0.17) / (0.33 - 0.17), 0.0, 1.0)
            return lerp(-0.29, -0.15, t)
        t = clamp(y / 0.17, 0.0, 1.0)
        return lerp(-0.21, -0.29, t)

    for lname, lx, is_front in legs:
        def make_leg(lx=lx, is_front=is_front):
            tc = 0.80
            axis_z = front_axis_z if is_front else hind_axis_z

            def leg_pos(s: float, t: float) -> Vector:
                th = (s - 0.5) * tau
                if t <= tc:
                    u = t / tc
                    y = lerp(leg_top, paw_y, u)
                    if is_front:
                        rx_u, rz_u, r_w = 0.086, 0.092, 0.052
                    else:
                        # 宽厚大腿股部
                        rx_u, rz_u, r_w = 0.105, 0.155, 0.052
                    if y >= 0.34:
                        f = clamp((y - 0.34) / (leg_top - 0.34), 0.0, 1.0)
                        top_cap = math.sin(clamp(u, 0.03, 1.0) * math.pi * 0.5) ** 0.28 if u < 0.14 else 1.0
                        rx = lerp(rx_u * 0.86, rx_u, f) * top_cap
                        rz = lerp(rz_u * 0.86, rz_u, f) * top_cap
                    elif y > 0.14:
                        f = (y - 0.14) / 0.20
                        rx = lerp(r_w, rx_u * 0.86, f)
                        rz = lerp(r_w * 1.05, rz_u * 0.86, f)
                    else:
                        f = clamp((y - paw_y) / (0.14 - paw_y), 0.0, 1.0)
                        # 前端微宽的四趾楔形掌
                        toe_widen = 1.0 + 0.18 * (1.0 - f) * max(0.0, math.cos(th))
                        rx = lerp(paw_r * 1.05, r_w, f) * toe_widen
                        rz = lerp(paw_r * 1.28, r_w * 1.05, f)
                else:
                    a = clamp((t - tc) / (1.0 - tc), 0.0, 0.92) * (math.pi / 2.0)
                    # 平底贴地：底面压平而非半球
                    y = paw_y - paw_r * math.sin(a) * 0.35
                    c = math.cos(a)
                    toe = 1.0 + 0.20 * max(0.0, math.cos(th)) * (1.0 - c)
                    rx = paw_r * 1.05 * c * toe
                    rz = paw_r * 1.30 * c
                lz = axis_z(y)
                return Vector((lx + math.sin(th) * rx, y, lz + math.cos(th) * rz))

            def leg_core(p: Vector) -> Vector:
                yc = clamp(p.y, 0.0, leg_top - 0.04)
                return Vector((lx, yc, axis_z(yc)))

            return leg_pos, leg_core

        lpos, lcore = make_leg()
        objs.append(create_closed_part_object(lname, 24, 28, lpos, lcore))

    # 6. 双耳 G-03：外凸内凹真猫耳廓（Concha + 薄耳缘）
    for side, ename in ((1, "part_earL"), (-1, "part_earR")):
        def make_ear(side=side):
            ear_base = Vector((side * 0.125, 1.08, 0.62))
            axis = Vector((side * 0.32, 1.0, 0.12)).normalized()
            f0 = Vector((0.0, 0.0, 1.0))
            front = (f0 - axis * axis.dot(f0)).normalized()
            sideways = axis.cross(front).normalized()
            h = 0.245

            def ear_pos(s: float, t: float) -> Vector:
                th = (s - 0.5) * tau
                tc = clamp(t, 0.02, 0.98)
                rb = 0.122
                r = rb * ((1.0 - tc) ** 0.82)
                if tc < 0.08:
                    r *= (tc / 0.08) ** 0.28
                # 前表面大幅内凹成耳窝，后表面圆润外凸；薄耳缘
                if math.cos(th) > 0:
                    cup = 0.22  # 内耳窝深凹
                    r *= 0.92   # 薄耳缘略收
                else:
                    cup = 0.58  # 圆润耳背
                c = ear_base + axis * (-0.040 + tc * (h + 0.040))
                # 内耳缘较直、外耳缘弧线
                side_bias = 1.0 + 0.08 * math.sin(th) * side
                return c + sideways * (math.sin(th) * r * side_bias) + front * (math.cos(th) * r * cup)

            def ear_core(p: Vector) -> Vector:
                proj = clamp((p - ear_base).dot(axis), -0.03, h * 0.88)
                return ear_base + axis * proj

            return ear_pos, ear_core

        epos, ecore = make_ear()
        objs.append(create_closed_part_object(ename, 24, 18, epos, ecore))

    # 7. 尾巴：从十字部自然延伸
    tail_u = Vector((1.0, 0.0, 0.0))

    def tail_pos(s: float, t: float) -> Vector:
        th = (s - 0.5) * tau
        tc = clamp(t, 0.02, 0.98)
        c = catmull_rom(TAIL_CURVE_PTS, tc)
        tan = catmull_tangent(TAIL_CURVE_PTS, tc)
        w = tail_u.cross(tan).normalized()
        r = 0.052 * lerp(1.12, 0.70, tc)
        if tc < 0.07:
            r *= (tc / 0.07) ** 0.28
        if tc > 0.88:
            r *= math.sqrt(max(0.02, 1.0 - ((tc - 0.88) / 0.12) ** 2))
        return c + tail_u * (math.sin(th) * r) + w * (math.cos(th) * r)

    def tail_core(p: Vector) -> Vector:
        best_p = TAIL_CURVE_PTS[0]
        best_d = 1e9
        for i in range(49):
            cp = catmull_rom(TAIL_CURVE_PTS, i / 48.0)
            d = (p - cp).length_squared
            if d < best_d:
                best_d = d
                best_p = cp
        return best_p

    objs.append(create_closed_part_object("part_tail", 18, 34, tail_pos, tail_core))
    return objs



def normalize_imported_mesh(obj: bpy.types.Object):
    obj.data.materials.clear()
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    verts = [v.co.copy() for v in obj.data.vertices]
    min_v = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    max_v = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    size = max_v - min_v
    scale = 1.25 / max(size.z, 1e-4)
    center_x = 0.5 * (min_v.x + max_v.x)
    center_y = 0.5 * (min_v.y + max_v.y)

    for v in obj.data.vertices:
        v.co.x = (v.co.x - center_x) * scale
        v.co.y = (v.co.y - center_y) * scale
        v.co.z = (v.co.z - min_v.z) * scale


def build_manifold_mesh(input_path: str | None = None) -> bpy.types.Object:
    if input_path and os.path.exists(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=input_path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=input_path)
        else:
            raise ValueError(f"Unsupported input format: {ext}")
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        bpy.ops.object.select_all(action="DESELECT")
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        if len(meshes) > 1:
            bpy.ops.object.join()
        obj = bpy.context.active_object
        obj.name = "cat_base"
        normalize_imported_mesh(obj)
    else:
        part_objs = build_organic_part_objects()
        obj = part_objs[0]
        obj.name = "cat_base"
        bpy.context.view_layer.objects.active = obj
        # 先用 EXACT Boolean Union 将各闭合解剖子体融合为无内部自交的单外壳水密体
        for sub_obj in part_objs[1:]:
            mod = obj.modifiers.new(name=f"Union_{sub_obj.name}", type="BOOLEAN")
            mod.operation = "UNION"
            mod.solver = "EXACT"
            mod.object = sub_obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(sub_obj, do_unlink=True)

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # 步骤 2：Blender Voxel Remesh 体素重建（融合成 100% 单一连通水密流形网格）
    remesh = obj.modifiers.new(name="VoxelRemesh", type="REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = 0.0100
    remesh.adaptivity = 0.0
    remesh.use_smooth_shade = True
    bpy.ops.object.modifier_apply(modifier=remesh.name)

    # 平滑体素过渡（消除头颈、四肢与躯干交界折痕）
    # 轻量平滑：只抹掉体素台阶，尽量保留解剖折角
    smooth = obj.modifiers.new(name="OrganicSmooth", type="SMOOTH")
    smooth.factor = 0.22
    smooth.iterations = 2
    bpy.ops.object.modifier_apply(modifier=smooth.name)

    # 减面到 4k~6k 三角面（目标约 5200 三角面）
    bm_tmp = bmesh.new()
    bm_tmp.from_mesh(obj.data)
    bmesh.ops.triangulate(bm_tmp, faces=bm_tmp.faces)
    bm_tmp.to_mesh(obj.data)
    bm_tmp.free()
    current_tris = len(obj.data.polygons)
    target_tris = 4800
    if current_tris > target_tris:
        dec = obj.modifiers.new(name="DecimateTo5k", type="DECIMATE")
        dec.decimate_type = "COLLAPSE"
        dec.ratio = clamp(target_tris / float(current_tris), 0.10, 0.95)
        bpy.ops.object.modifier_apply(modifier=dec.name)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()

    # Stage 1 解剖精修（Remesh 后二次雕刻，把被体素抹平的骨相折角重新抠回来）
    for v in obj.data.vertices:
        p = b2t(v.co)
        # G-07：四掌底面严格贴合地面 + 前端四趾微鼓
        if p.y < 0.030:
            p.y = max(0.0, p.y * 0.15)
            for side_x, lz_base in ((0.145, 0.35), (-0.145, 0.35), (0.155, -0.21), (-0.155, -0.21)):
                if abs(p.x - side_x) < 0.09 and abs(p.z - lz_base) < 0.10:
                    # 四趾：沿 x 做正弦微鼓
                    toe = 0.006 * abs(math.sin(((p.x - side_x) / 0.07) * math.pi * 2.0))
                    if p.z * math.copysign(1.0, lz_base) > abs(lz_base) - 0.04:
                        p.z += math.copysign(toe, lz_base) if abs(lz_base) > 0.25 else toe
        # G-03：耳窝 Concha 深度
        for side in (1, -1):
            ear_b = Vector((side * 0.125, 1.08, 0.62))
            axis = Vector((side * 0.32, 1.0, 0.12)).normalized()
            front = (Vector((0.0, 0.0, 1.0)) - axis * axis.dot(Vector((0.0, 0.0, 1.0)))).normalized()
            sideways = axis.cross(front)
            rel = p - ear_b
            proj = rel.dot(axis)
            if proj > -0.02 and proj < 0.26 and side * p.x > 0.04 and p.y > 1.00:
                fz = rel.dot(front)
                sx = rel.dot(sideways)
                if fz > -0.01 and abs(sx) < 0.11:
                    depth = 0.038 * clamp(1.0 - abs(sx) / 0.11, 0.0, 1.0) * clamp(1.0 - abs(proj - 0.11) / 0.13, 0.0, 1.0)
                    p -= front * depth
        # G-01：眉弓凸起 + 眼窝深凹 + 鼻梁骨脊
        for sx in (1.0, -1.0):
            eye = Vector((sx * 0.108, 0.895, 0.755))
            d = p - eye
            if d.length < 0.085 and p.z > 0.66:
                p -= Vector((d.x, d.y * 0.4, d.z)).normalized() * (0.018 * clamp(1.0 - d.length / 0.085, 0.0, 1.0))
        # 眉弓
        if abs(p.x) < 0.16 and 0.90 < p.y < 0.98 and 0.68 < p.z < 0.82:
            p.z += 0.014 * math.exp(-((p.x / 0.12) ** 2)) * math.exp(-(((p.y - 0.94) / 0.05) ** 2))
        # 鼻梁中轴微凸 + Stop 台阶（眉心下方向后微收再向前伸出）
        if abs(p.x) < 0.040 and 0.84 < p.y < 0.94 and 0.68 < p.z < 0.86:
            stop = 0.016 * clamp(1.0 - abs(p.x) / 0.040, 0.0, 1.0)
            if p.y > 0.90:
                p.z += stop * 0.6
            else:
                p.z += stop
        # G-02：花生形口套两侧鼓起 + 人中沟 + 下巴颏
        for sx in (1.0, -1.0):
            pad = Vector((sx * 0.055, 0.815, 0.80))
            d = p - pad
            if d.length < 0.070 and p.z > 0.74:
                p += Vector((sx * 0.012, 0.0, 0.010)) * clamp(1.0 - d.length / 0.070, 0.0, 1.0)
        if abs(p.x) < 0.020 and 0.78 < p.y < 0.84 and p.z > 0.78:
            p.z -= 0.012 * clamp(1.0 - abs(p.x) / 0.020, 0.0, 1.0)
        if abs(p.x) < 0.06 and 0.72 < p.y < 0.78 and p.z > 0.74:
            p.z += 0.010 * clamp(1.0 - abs(p.x) / 0.06, 0.0, 1.0)
            p.y -= 0.004
        # G-04：肩胛峰 / 十字部 / 收腰
        if abs(p.x) < 0.12 and p.y > 0.62 and 0.10 < p.z < 0.36:
            p.y += 0.016 * math.exp(-((p.x / 0.10) ** 2)) * math.exp(-(((p.z - 0.24) / 0.12) ** 2))
        if abs(p.x) < 0.12 and p.y > 0.60 and -0.36 < p.z < -0.10:
            p.y += 0.014 * math.exp(-((p.x / 0.10) ** 2)) * math.exp(-(((p.z + 0.24) / 0.12) ** 2))
        if abs(p.x) < 0.18 and p.y < 0.42 and -0.28 < p.z < -0.02:
            # 后腹上收
            p.y += 0.012 * clamp(1.0 - abs(p.x) / 0.18, 0.0, 1.0) * clamp((-0.02 - p.z) / 0.20, 0.0, 1.0)
        # G-05/G-06：强化肘后收、膝前伸、飞节后折的表面折角
        for side_x in (0.145, -0.145):
            if abs(p.x - side_x) < 0.09:
                # 肘区 y≈0.30 向后推
                if 0.26 < p.y < 0.34 and 0.20 < p.z < 0.38:
                    p.z -= 0.018 * math.exp(-(((p.y - 0.30) / 0.04) ** 2))
                # 腕区 y≈0.11 微前
                if 0.08 < p.y < 0.15 and 0.22 < p.z < 0.40:
                    p.z += 0.012 * math.exp(-(((p.y - 0.11) / 0.035) ** 2))
        for side_x in (0.155, -0.155):
            if abs(p.x - side_x) < 0.12:
                # 膝前伸 y≈0.33
                if 0.28 < p.y < 0.38 and -0.28 < p.z < -0.05:
                    p.z += 0.022 * math.exp(-(((p.y - 0.33) / 0.045) ** 2))
                # 飞节后折 y≈0.17
                if 0.12 < p.y < 0.22 and -0.38 < p.z < -0.12:
                    p.z -= 0.028 * math.exp(-(((p.y - 0.17) / 0.04) ** 2))
                    p.y += 0.006 * math.exp(-(((p.y - 0.17) / 0.04) ** 2))
        v.co = t2b(p)

    obj.data.validate(verbose=False)
    obj.data.update()
    return obj


# ---------------------------------------------------------------------------
# 步骤 3 & 4：解剖部件分类 (`_PART`)、焊接平滑法线保持、非镜像高密度 UV 展开
# ---------------------------------------------------------------------------

def classify_point_part(p: Vector) -> int:
    """
    给定 Three.js 静止空间坐标 p(x, y, z)，返回所属解剖部件编号 0..10：
    0:head, 1:muzzle, 2:neck, 3:body, 4:fLegL, 5:fLegR, 6:hLegL, 7:hLegR, 8:earL, 9:earR, 10:tail
    """
    # 双耳 (8: earL, 9: earR)
    for side, pid in ((1, 8), (-1, 9)):
        ear_base = Vector((side * 0.125, 1.08, 0.62))
        axis = Vector((side * 0.34, 1.0, 0.10)).normalized()
        rel = p - ear_base
        proj = rel.dot(axis)
        if proj > -0.015 and p.y > 1.00 and side * p.x > 0.035 and p.z > 0.34:
            perp = (rel - axis * proj).length
            if perp < 0.135:
                return pid

    # 嘴套 (1: muzzle) —— 严格限定在眼窝下方口鼻垫区域 (y <= 0.858, |x| <= 0.128)
    mc = Vector((0.0, 0.820, 0.760))
    mdx = (p.x - mc.x) / 0.140
    mdy = (p.y - mc.y) / 0.070
    mdz = (p.z - mc.z) / 0.090
    if p.z > 0.740 and 0.735 <= p.y <= 0.870 and abs(p.x) <= 0.140 and (mdx * mdx + mdy * mdy + mdz * mdz) <= 1.10:
        return 1

    # 头部 (0: head)
    hc = Vector((0.0, 0.90, 0.54))
    hdx = (p.x - hc.x) / 0.315
    hdy = (p.y - hc.y) / 0.285
    hdz = (p.z - hc.z) / 0.305
    if (p.y > 0.745 and p.z > 0.24) or ((hdx * hdx + hdy * hdy + hdz * hdz) < 0.96 and p.y > 0.68):
        return 0

    # 脖子 (2: neck)
    if p.y > 0.575 and p.z > 0.23 and (p.y + (p.z - 0.25) * 0.65) > 0.66:
        return 2

    # 尾巴 (10: tail)
    if p.z < -0.430 and p.y > 0.48:
        return 10

    # 四肢柱体判定：保留肚皮正中央底面 (|x| <= 0.058 且 y > 0.255) 为 body(3)，避免迈步拉扯肚皮；
    # 同时将大腿/肩臂外侧上沿延伸至 y < 0.435，让肩/胯关节完整带动整条腿摆动
    in_belly_midline = (abs(p.x) <= 0.058 and p.y > 0.255)
    if not in_belly_midline:
        # 前腿 (4: fLegL, 5: fLegR)
        flx = 0.145 if p.x >= 0.0 else -0.145
        fl_r = math.hypot((p.x - flx) / 0.100, (p.z - 0.30) / 0.130)
        if p.z > 0.04 and ((p.y < 0.36) or (p.y < 0.460 and fl_r <= 1.12)):
            return 4 if p.x >= 0.0 else 5

        # 后腿 (6: hLegL, 7: hLegR) —— 含飞节后折空间
        hlx = 0.155 if p.x >= 0.0 else -0.155
        hl_r = math.hypot((p.x - hlx) / 0.115, (p.z - (-0.22)) / 0.175)
        if p.z <= 0.04 and ((p.y < 0.36) or (p.y < 0.460 and hl_r <= 1.15)):
            return 6 if p.x >= 0.0 else 7

    # 躯干 (3: body)
    return 3


def compute_part_uv(part_id: int, p: Vector, n: Vector) -> tuple[float, float]:
    tau = math.pi * 2.0
    if part_id == 0:  # head
        hc = Vector((0.0, 0.90, 0.54))
        d = p - hc
        th = math.atan2(d.x, d.z)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        t = clamp(math.acos(clamp(d.y / max(d.length, 1e-5), -1.0, 1.0)) / math.pi, 0.0, 1.0)
        return s, t
    if part_id == 1:  # muzzle
        mc = Vector((0.0, 0.812, 0.725))
        d = p - mc
        th = math.atan2(d.x, max(0.01, d.z + 0.04))
        s = clamp(0.5 + th / (math.pi * 1.15), 0.0, 1.0)
        t = clamp(0.5 - d.y / 0.14, 0.0, 1.0)
        return s, t
    if part_id == 2:  # neck
        neck_a = Vector((0.0, 0.55, 0.25))
        neck_b = Vector((0.0, 0.85, 0.50))
        ab = neck_b - neck_a
        t = clamp((p - neck_a).dot(ab) / ab.length_squared, 0.0, 1.0)
        c = neck_a.lerp(neck_b, t)
        d = p - c
        th = math.atan2(d.x, d.z)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        return s, t
    if part_id == 3:  # body
        bc = Vector((0.0, 0.50, 0.0))
        d = p - bc
        th = math.atan2(d.x, d.y)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        zc = clamp(p.z / 0.50, -1.0, 1.0)
        t = clamp(math.acos(-zc) / math.pi, 0.0, 1.0)
        return s, t
    if part_id in (4, 5, 6, 7):  # legs
        lx = 0.145 if part_id == 4 else (-0.145 if part_id == 5 else (0.155 if part_id == 6 else -0.155))
        lz = 0.31 if part_id in (4, 5) else -0.23
        dx = p.x - lx
        dz = p.z - lz
        th = math.atan2(dx, dz)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        t = clamp((0.40 - p.y) / 0.40, 0.0, 1.0)
        return s, t
    if part_id in (8, 9):  # ears
        side = 1 if part_id == 8 else -1
        ear_base = Vector((side * 0.125, 1.08, 0.62))
        axis = Vector((side * 0.34, 1.0, 0.10)).normalized()
        f0 = Vector((0.0, 0.0, 1.0))
        front = (f0 - axis * axis.dot(f0)).normalized()
        sideways = axis.cross(front).normalized()
        rel = p - ear_base
        proj = rel.dot(axis)
        t = clamp((proj + 0.02) / 0.25, 0.0, 1.0)
        sx = rel.dot(sideways)
        fz = rel.dot(front)
        th = math.atan2(sx, fz)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        return s, t
    # tail (10)
    best_t = 0.0
    best_d = 1e9
    for i in range(65):
        tt = i / 64.0
        cp = catmull_rom(TAIL_CURVE_PTS, tt)
        dist = (p - cp).length_squared
        if dist < best_d:
            best_d = dist
            best_t = tt
    cp = catmull_rom(TAIL_CURVE_PTS, best_t)
    tan = catmull_tangent(TAIL_CURVE_PTS, best_t)
    tail_u = Vector((1.0, 0.0, 0.0))
    tail_w = tail_u.cross(tan).normalized()
    rel = p - cp
    th = math.atan2(rel.dot(tail_u), rel.dot(tail_w))
    s = clamp(0.5 + th / tau, 0.0, 1.0)
    return s, best_t


def assign_parts_and_unwrap_non_mirrored_uv(obj: bpy.types.Object) -> tuple[bpy.types.Object, list[Vector]]:
    mesh = obj.data
    for poly in mesh.polygons:
        poly.use_smooth = True

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    welded_normals_three = [b2t(v.normal).normalized() for v in bm.verts]
    verts_three = [b2t(v.co) for v in bm.verts]

    face_parts = []
    for f in bm.faces:
        c = sum((verts_three[v.index] for v in f.verts), Vector((0.0, 0.0, 0.0))) / len(f.verts)
        face_parts.append(classify_point_part(c))

    for _ in range(3):
        next_parts = list(face_parts)
        for fi, f in enumerate(bm.faces):
            nbr_parts = [face_parts[fi]]
            for e in f.edges:
                for lf in e.link_faces:
                    if lf.index != fi:
                        nbr_parts.append(face_parts[lf.index])
            counts = {}
            for pid in nbr_parts:
                counts[pid] = counts.get(pid, 0) + 1
            best_pid = max(counts.items(), key=lambda kv: kv[1])[0]
            if counts[best_pid] >= len(nbr_parts) // 2 + 1:
                next_parts[fi] = best_pid
        face_parts = next_parts

    new_positions_bl: list[Vector] = []
    new_normals_three: list[Vector] = []
    new_normals_bl: list[Vector] = []
    new_uvs: list[tuple[float, float]] = []
    new_parts: list[int] = []
    new_tris: list[tuple[int, int, int]] = []
    vert_cache: dict[tuple[int, int, int], int] = {}
    seen_tris: set[tuple[int, int, int]] = set()

    for fi, f in enumerate(bm.faces):
        if len(f.verts) != 3:
            continue
        pid = face_parts[fi]
        rx, ry, rw, rh = PART_RECTS[pid]
        pad = 2.5
        transpose = (pid == 10)

        v_indices = [v.index for v in f.verts]
        if len(set(v_indices)) < 3:
            continue
        raw_st = [compute_part_uv(pid, verts_three[vi], welded_normals_three[vi]) for vi in v_indices]

        s_vals = [st[0] for st in raw_st]
        spans_seam = (max(s_vals) - min(s_vals)) > 0.55

        tri_new_indices = []
        for k, vi in enumerate(v_indices):
            s, t = raw_st[k]
            wrap = 1 if (spans_seam and s < 0.35) else 0
            key = (vi, pid, wrap)
            if key not in vert_cache:
                s_adj = min(1.0, s + (1.0 if wrap else 0.0))
                a = t if transpose else s_adj
                b = s_adj if transpose else t
                px = rx + pad + a * (rw - 2.0 * pad)
                py = ry + pad + b * (rh - 2.0 * pad)
                u = clamp(px / ATLAS_SIZE, 0.001, 0.999)
                v_uv = clamp(1.0 - py / ATLAS_SIZE, 0.001, 0.999)

                idx = len(new_positions_bl)
                vert_cache[key] = idx
                new_positions_bl.append(bm.verts[vi].co.copy())
                n_three = welded_normals_three[vi]
                new_normals_three.append(n_three)
                new_normals_bl.append(t2b(n_three).normalized())
                new_uvs.append((u, v_uv))
                new_parts.append(pid)
            tri_new_indices.append(vert_cache[key])

        t_key = tuple(sorted(tri_new_indices))
        if len(set(tri_new_indices)) == 3 and t_key not in seen_tris:
            seen_tris.add(t_key)
            new_tris.append((tri_new_indices[0], tri_new_indices[1], tri_new_indices[2]))

    bm.free()

    new_mesh = bpy.data.meshes.new("cat_base_unified")
    new_mesh.from_pydata(new_positions_bl, [], new_tris)
    for poly in new_mesh.polygons:
        poly.use_smooth = True
    new_mesh.validate(verbose=False)
    new_mesh.update()

    # 设置焊接连续法线
    new_mesh.normals_split_custom_set_from_vertices(new_normals_bl[: len(new_mesh.vertices)])

    uv_layer = new_mesh.uv_layers.new(name="UVMap")
    for poly in new_mesh.polygons:
        for li in poly.loop_indices:
            vi = new_mesh.loops[li].vertex_index
            uv_layer.data[li].uv = new_uvs[vi]

    part_attr = new_mesh.attributes.new(name="_PART", type="FLOAT", domain="POINT")
    for vi in range(len(new_mesh.vertices)):
        part_attr.data[vi].value = float(new_parts[vi])

    old_mesh = obj.data
    obj.data = new_mesh
    bpy.data.meshes.remove(old_mesh)
    return obj, new_normals_three


# ---------------------------------------------------------------------------
# 步骤 5 & 6：同名同层级 26 根骨骼构建、bones.json 导出与平滑骨骼权重
# ---------------------------------------------------------------------------

def get_bone_defs() -> list[tuple[str, str | None, Vector]]:
    """26 根同名骨骼，轴心对齐 Stage 1 趾行解剖折角（肩/肘/腕、髋/膝/飞节）。"""
    defs: list[tuple[str, str | None, Vector]] = [
        ("root", None, Vector((0.0, 0.0, 0.0))),
        ("hips", "root", Vector((0.0, 0.52, -0.22))),
        ("spine", "hips", Vector((0.0, 0.54, 0.02))),
        ("chest", "spine", Vector((0.0, 0.56, 0.28))),
        ("neck", "chest", Vector((0.0, 0.70, 0.42))),
        ("head", "neck", Vector((0.0, 0.90, 0.54))),
        ("earL", "head", Vector((0.125, 1.08, 0.62))),
        ("earR", "head", Vector((-0.125, 1.08, 0.62))),
    ]
    for side, x in (("L", 0.145), ("R", -0.145)):
        defs.extend([
            (f"shoulder{side}", "chest", Vector((x, 0.48, 0.33))),  # 肩
            (f"elbow{side}", f"shoulder{side}", Vector((x, 0.30, 0.27))),  # 肘微后收
            (f"fpaw{side}", f"elbow{side}", Vector((x, 0.11, 0.31))),  # 腕/掌
        ])
    for side, x in (("L", 0.155), ("R", -0.155)):
        defs.extend([
            (f"hip{side}", "hips", Vector((x, 0.48, -0.22))),  # 髋
            (f"knee{side}", f"hip{side}", Vector((x, 0.33, -0.15))),  # 膝(Stifle)前伸
            (f"hpaw{side}", f"knee{side}", Vector((x, 0.17, -0.29))),  # 飞节(Hock)后折
        ])
    for i, t in enumerate(TAIL_BONE_T):
        parent = "hips" if i == 0 else f"tail{i - 1}"
        defs.append((f"tail{i}", parent, catmull_rom(TAIL_CURVE_PTS, t)))
    return defs


def chain_weights(v: float, stops: list[tuple[str, float]]) -> list[tuple[str, float]]:
    if v <= stops[0][1]:
        return [(stops[0][0], 1.0)]
    for i in range(len(stops) - 1):
        a, va = stops[i]
        b, vb = stops[i + 1]
        if v <= vb:
            if a == b:
                return [(a, 1.0)]
            f = (v - va) / max(1e-6, vb - va)
            f = f * f * (3.0 - 2.0 * f)
            return [(a, 1.0 - f), (b, f)]
    return [(stops[-1][0], 1.0)]


def smooth01(x: float) -> float:
    c = clamp(x, 0.0, 1.0)
    return c * c * (3.0 - 2.0 * c)


def merge_weights(w1: dict[str, float], w2: list[tuple[str, float]], factor: float) -> dict[str, float]:
    f = clamp(factor, 0.0, 1.0)
    if f <= 1e-5:
        return w1
    if f >= 1.0 - 1e-5:
        out: dict[str, float] = {}
        for k, v in w2:
            out[k] = out.get(k, 0.0) + v
        return out
    out = {k: v * (1.0 - f) for k, v in w1.items()}
    for k, v in w2:
        out[k] = out.get(k, 0.0) + v * f
    return out


def compute_smooth_skin_weights(_part_id: int, p: Vector) -> list[tuple[str, float]]:
    """
    纯 3D 空间坐标 p=(x,y,z) 的 C1 连续蒙皮权重场（完全不依赖 _part_id）：
    保证任何因非镜像 UV 接缝切分而产生在相同 3D 坐标上的两个顶点拥有 100% 相同的骨骼权重，
    从数学上彻底杜绝迈步、转头、摇尾时在部件 UV 接缝处裂开缝隙！
    """
    # 1. 躯干脊柱基底权重
    w: dict[str, float] = {}
    for k, v in chain_weights(p.z, [("hips", -0.22), ("spine", 0.05), ("chest", 0.28)]):
        w[k] = w.get(k, 0.0) + v

    # 2. 颈部 -> 头部 -> 双耳 连续空间过渡
    nh_coord = p.y + 0.36 * (p.z - 0.24)
    m_neck_head = smooth01((nh_coord - 0.52) / 0.10) * smooth01((p.z - 0.12) / 0.14)
    if m_neck_head > 1e-4:
        nh_chain = chain_weights(nh_coord, [
            ("chest", 0.52),
            ("neck", 0.68),
            ("head", 0.85),
        ])
        w = merge_weights(w, nh_chain, m_neck_head)

    # 双耳（在头部上方 y > 1.03 平滑过渡到 earL / earR）
    if p.y > 1.02 and p.z > 0.42 and abs(p.x) > 0.03:
        ear_bone = "earL" if p.x >= 0.0 else "earR"
        ear_cx = 0.122 if p.x >= 0.0 else -0.122
        d_ear = math.hypot((p.x - ear_cx) / 0.14, (p.z - 0.67) / 0.14)
        m_ear = smooth01((p.y - 1.04) / 0.12) * smooth01(1.35 - d_ear)
        if m_ear > 1e-4:
            w = merge_weights(w, [(ear_bone, 1.0)], m_ear)

    # 3. 尾巴连续空间过渡（p.z < -0.36 且 p.y > 0.40）
    if p.z < -0.35 and p.y > 0.39:
        m_tail = smooth01((-0.36 - p.z) / 0.10) * smooth01((p.y - 0.40) / 0.08)
        if m_tail > 1e-4:
            _, t_tail = compute_part_uv(10, p, Vector((0.0, 1.0, 0.0)))
            stops: list[tuple[str, float]] = [("hips", 0.0)]
            for i, bt in enumerate(TAIL_BONE_T):
                nxt = TAIL_BONE_T[i + 1] if i + 1 < len(TAIL_BONE_T) else 1.0
                stops.append((f"tail{i}", 0.5 * (bt + nxt)))
            w = merge_weights(w, chain_weights(t_tail, stops), m_tail)

    # 4. 四肢连续空间过渡（适配 Stage 1 趾行轴线 front_axis_z / hind_axis_z）
    if p.y < 0.520:
        side = "L" if p.x >= 0.0 else "R"
        is_front = p.z >= 0.04

        def front_axis_z(y: float) -> float:
            if y >= 0.30:
                t = clamp((y - 0.30) / (0.52 - 0.30), 0.0, 1.0)
                return lerp(0.27, 0.33, t)
            if y >= 0.11:
                t = clamp((y - 0.11) / (0.30 - 0.11), 0.0, 1.0)
                return lerp(0.31, 0.27, t)
            t = clamp(y / 0.11, 0.0, 1.0)
            return lerp(0.35, 0.31, t)

        def hind_axis_z(y: float) -> float:
            if y >= 0.33:
                t = clamp((y - 0.33) / (0.52 - 0.33), 0.0, 1.0)
                return lerp(-0.15, -0.22, t)
            if y >= 0.17:
                t = clamp((y - 0.17) / (0.33 - 0.17), 0.0, 1.0)
                return lerp(-0.29, -0.15, t)
            t = clamp(y / 0.17, 0.0, 1.0)
            return lerp(-0.21, -0.29, t)

        if is_front:
            lx = 0.145 if p.x >= 0.0 else -0.145
            lz = front_axis_z(p.y)
            d_leg = math.hypot((p.x - lx) / 0.105, (p.z - lz) / 0.140)
            # 平台权重：肘轴心上方只吃 shoulder，杜绝反向剪切
            leg_chain = chain_weights(p.y, [
                (f"fpaw{side}", 0.055),
                (f"fpaw{side}", 0.095),
                (f"elbow{side}", 0.130),
                (f"elbow{side}", 0.275),
                (f"shoulder{side}", 0.320),
                (f"shoulder{side}", 0.455),
                ("chest", 0.510),
            ])
        else:
            lx = 0.155 if p.x >= 0.0 else -0.155
            lz = hind_axis_z(p.y)
            d_leg = math.hypot((p.x - lx) / 0.120, (p.z - lz) / 0.175)
            # 飞节(hpaw) 在 y≈0.17；膝轴心上方只吃 hip
            leg_chain = chain_weights(p.y, [
                (f"hpaw{side}", 0.060),
                (f"hpaw{side}", 0.145),
                (f"knee{side}", 0.185),
                (f"knee{side}", 0.305),
                (f"hip{side}", 0.350),
                (f"hip{side}", 0.470),
                ("hips", 0.520),
            ])

        m_radial = smooth01((1.20 - d_leg) / 0.40)
        m_low = smooth01((0.300 - p.y) / 0.050)
        m_leg = max(m_radial, m_low) * smooth01((0.515 - p.y) / 0.040)
        # 腹底正中硬门禁：|x|<0.075 且位于胸腹下表面时，四肢权重强制为 0
        if abs(p.x) < 0.075 and 0.18 < p.y < 0.42 and abs(p.z) < 0.30:
            # 仅当点更靠近腹中而非腿轴时清零
            if d_leg > 0.55:
                m_leg = 0.0
            else:
                m_leg *= smooth01((abs(p.x) - 0.055) / 0.020) * smooth01((d_leg - 0.35) / 0.25)
        if m_leg > 1e-4:
            w = merge_weights(w, leg_chain, m_leg)

    return [(k, val) for k, val in w.items() if val > 1e-4]


def build_armature_and_weights(obj: bpy.types.Object) -> tuple[bpy.types.Object, dict]:
    bone_defs = get_bone_defs()
    arm_data = bpy.data.armatures.new("cat_armature_data")
    arm_obj = bpy.data.objects.new("cat_armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = {}
    bones_json = {}
    for name, parent, pos_three in bone_defs:
        eb = arm_data.edit_bones.new(name)
        head_bl = t2b(pos_three)
        eb.head = head_bl
        eb.tail = head_bl + Vector((0.0, 0.0, 0.05))
        eb.roll = 0.0
        if parent and parent in edit_bones:
            eb.parent = edit_bones[parent]
        edit_bones[name] = eb
        bones_json[name] = {
            "parent": parent,
            "pos": [round(pos_three.x, 5), round(pos_three.y, 5), round(pos_three.z, 5)],
        }

    bpy.ops.object.mode_set(mode="OBJECT")

    obj.parent = arm_obj
    arm_mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    arm_mod.object = arm_obj

    vgroups = {}
    for name, _, _ in bone_defs:
        vgroups[name] = obj.vertex_groups.new(name=name)

    mesh = obj.data
    part_attr = mesh.attributes["_PART"]
    limb_bones = {n for n, _, _ in bone_defs if any(k in n for k in ("shoulder", "elbow", "fpaw", "hip", "knee", "hpaw"))}
    for vi, v in enumerate(mesh.vertices):
        pid = int(round(part_attr.data[vi].value))
        p_three = b2t(v.co)
        weights = compute_smooth_skin_weights(pid, p_three)
        # 工程硬门禁：腹底正中线剥离四肢权重
        if abs(p_three.x) <= 0.055 and 0.20 < p_three.y < 0.40 and abs(p_three.z) < 0.25:
            weights = [(b, w) for b, w in weights if b not in limb_bones]
            if not weights:
                weights = [("spine", 1.0)]
        total = sum(w for _, w in weights) or 1.0
        for bname, w in weights:
            if w > 1e-4:
                vgroups[bname].add([vi], w / total, "REPLACE")

    return arm_obj, bones_json


# ---------------------------------------------------------------------------
# 步骤 7：基于解剖掩码与平滑衰减生成 6 个标准形态键
# ---------------------------------------------------------------------------

def shape_delta_three(key: str, p: Vector, pid: int) -> Vector:
    hc = Vector((0.0, 0.90, 0.54))
    mc = Vector((0.0, 0.812, 0.738))
    bc = Vector((0.0, 0.50, 0.0))

    if key == "headRound":
        w = clamp((p.y - 0.68) / 0.16, 0.0, 1.0) * clamp((1.10 - p.y) / 0.12, 0.0, 1.0)
        if pid in (8, 9):
            w *= 0.25
        d = p - hc
        return Vector((d.x * 0.085 * w, -d.y * 0.02 * w, d.z * 0.03 * w))

    if key == "weight":
        # 严禁影响四肢下段 y<0.34 与头部；只丰满胸腹围脖与垂腹
        if p.y < 0.34 or p.y > 0.78:
            return Vector((0.0, 0.0, 0.0))
        # 排除四肢柱体
        if abs(p.x) > 0.10 and p.y < 0.50 and (p.z > 0.12 or p.z < -0.08):
            return Vector((0.0, 0.0, 0.0))
        w_body = clamp((0.76 - p.y) / 0.14, 0.0, 1.0) * clamp((p.y - 0.34) / 0.12, 0.0, 1.0)
        belly_drop = -0.055 * clamp((0.48 - p.y) / 0.20, 0.0, 1.0) * clamp(1.0 - abs(p.z) / 0.45, 0.0, 1.0) if p.y < 0.50 else 0.0
        ruff = 0.035 * clamp((p.z - 0.18) / 0.30, 0.0, 1.0) * w_body if p.z > 0.15 else 0.0
        return Vector((p.x * 0.18 * w_body, (p.y - bc.y) * 0.08 * w_body + belly_drop, ruff))

    if key == "earSize":
        if p.y < 0.98:
            return Vector((0.0, 0.0, 0.0))
        w = clamp((p.y - 1.00) / 0.08, 0.0, 1.0)
        side = 1.0 if p.x >= 0.0 else -1.0
        ear_base = Vector((side * 0.125, 1.08, 0.62))
        rel = p - ear_base
        return Vector((rel.x * 0.22 * w + side * 0.012 * w, rel.y * 0.36 * w, rel.z * 0.18 * w))

    if key == "tailFluff":
        if p.z > -0.38:
            return Vector((0.0, 0.0, 0.0))
        w = clamp((-0.40 - p.z) / 0.10, 0.0, 1.0)
        _, t = compute_part_uv(10, p, Vector((0.0, 1.0, 0.0)))
        cp = catmull_rom(TAIL_CURVE_PTS, t)
        rad = p - cp
        scale = (0.50 + 0.22 * math.sin(math.pi * t)) * w
        return rad * scale

    if key == "cheekFluff":
        # 只横向发腮；鼻梁中轴 |x|<0.04 保持 Stop 台阶不被抹平
        mid = smooth01((abs(p.x) - 0.030) / 0.025)
        w_y = math.exp(-(((p.y - 0.84) / 0.11) ** 2))
        w_z = clamp((p.z - 0.35) / 0.25, 0.0, 1.0)
        w = w_y * w_z * mid
        return Vector((p.x * 0.16 * w, -0.006 * w, 0.008 * w))

    if key == "muzzleSize":
        dist = (p - mc).length
        w = math.exp(-((dist / 0.16) ** 2))
        d = p - mc
        return Vector((d.x * 0.16 * w, d.y * 0.12 * w, max(0.0, d.z) * 0.22 * w + 0.010 * w))

    return Vector((0.0, 0.0, 0.0))


def add_shape_keys(obj: bpy.types.Object):
    mesh = obj.data
    part_attr = mesh.attributes["_PART"]
    obj.shape_key_add(name="Basis", from_mix=False)
    for key in SHAPE_KEYS:
        sk = obj.shape_key_add(name=key, from_mix=False)
        for vi, v in enumerate(mesh.vertices):
            p_three = b2t(v.co)
            pid = int(round(part_attr.data[vi].value))
            delta_three = shape_delta_three(key, p_three, pid)
            sk.data[vi].co = t2b(p_three + delta_three)


# ---------------------------------------------------------------------------
# 步骤 8：计算脸部锚点 (eyeL, eyeR, mouth, whiskerL, whiskerR) 并写入 glTF extras
# ---------------------------------------------------------------------------

def compute_face_anchors(obj: bpy.types.Object, arm_obj: bpy.types.Object, normals_three: list[Vector]) -> dict:
    """
    在 Blender 母版网格表面动态采样五官锚点的真实前表面 Z 坐标，确保五官贴片严丝合缝贴在表面绝不陷入网格内部。
    """
    mesh = obj.data
    part_attr = mesh.attributes["_PART"]
    verts_three = [b2t(v.co) for v in mesh.vertices]

    def sample_front_z(tx: float, ty: float, rad: float) -> float:
        zs = [p.z for p in verts_three if math.hypot(p.x - tx, p.y - ty) <= rad and p.z > 0.55]
        return max(zs) if zs else 0.79

    eye_z = max(sample_front_z(0.108, 0.895, 0.028), sample_front_z(-0.108, 0.895, 0.028)) + 0.003
    mouth_z = sample_front_z(0.0, 0.820, 0.028) + 0.003
    whisker_z = max(sample_front_z(0.165, 0.812, 0.030), sample_front_z(-0.165, 0.812, 0.030)) + 0.003

    targets = {
        "eyeL": (Vector((0.108, 0.895, eye_z)), (0,), Vector((0.28, 0.04, 0.96)).normalized()),
        "eyeR": (Vector((-0.108, 0.895, eye_z)), (0,), Vector((-0.28, 0.04, 0.96)).normalized()),
        "mouth": (Vector((0.0, 0.820, mouth_z)), (1, 0), Vector((0.0, 0.02, 0.9998)).normalized()),
        "whiskerL": (Vector((0.165, 0.812, whisker_z)), (0,), Vector((0.64, -0.04, 0.767)).normalized()),
        "whiskerR": (Vector((-0.165, 0.812, whisker_z)), (0,), Vector((-0.64, -0.04, 0.767)).normalized()),
    }

    anchors = {}
    for name, (target_p, allowed_parts, ideal_n) in targets.items():
        best_vi = 0
        best_dist = 1e9
        for vi, p in enumerate(verts_three):
            pid = int(round(part_attr.data[vi].value))
            if pid not in allowed_parts:
                continue
            d = (p - target_p).length_squared
            if d < best_dist:
                best_dist = d
                best_vi = vi

        empty = bpy.data.objects.new(f"anchor_{name}", None)
        empty.empty_display_type = "SINGLE_ARROW"
        empty.empty_display_size = 0.05
        empty.location = t2b(target_p)
        empty.parent = arm_obj
        empty["anchorName"] = name
        empty["normal"] = [round(ideal_n.x, 5), round(ideal_n.y, 5), round(ideal_n.z, 5)]
        empty["vertexIndex"] = best_vi
        bpy.context.collection.objects.link(empty)

        anchors[name] = {
            "vertexIndex": best_vi,
            "pos": [round(target_p.x, 5), round(target_p.y, 5), round(target_p.z, 5)],
            "normal": [round(ideal_n.x, 5), round(ideal_n.y, 5), round(ideal_n.z, 5)],
        }

    obj["faceAnchors"] = json.dumps(anchors)
    obj.data["faceAnchors"] = json.dumps(anchors)
    return anchors


def main():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Build standardized HD-2D cat_base.glb in headless Blender")
    parser.add_argument("--input", type=str, default=None, help="Optional raw AI-generated cat GLB/OBJ")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory for cat_base.glb and bones.json")
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    proto_dir = script_dir.parent.parent
    repo_dir = proto_dir.parent
    out_dir = Path(args.out_dir) if args.out_dir else (proto_dir / "public" / "base")
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = repo_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    print("[build_base] Step 1-2: Building unified manifold cat mesh (Voxel Remesh + Smooth + Decimate)...")
    clear_scene()
    cat_obj = build_manifold_mesh(args.input)

    print("[build_base] Step 3-4: Tagging _PART (0..10) & unwrapping non-mirrored high-density UV...")
    cat_obj, normals_three = assign_parts_and_unwrap_non_mirrored_uv(cat_obj)

    print("[build_base] Step 5-6: Building 26-bone Armature & smooth skin weights...")
    arm_obj, bones_json = build_armature_and_weights(cat_obj)

    print("[build_base] Step 7: Generating 6 anatomical ShapeKeys...")
    add_shape_keys(cat_obj)

    print("[build_base] Step 8: Computing surface face anchors (eyeL, eyeR, mouth, whiskerL, whiskerR)...")
    anchors = compute_face_anchors(cat_obj, arm_obj, normals_three)
    arm_obj["faceAnchors"] = json.dumps(anchors)

    meta_payload = {
        "bones": bones_json,
        "anchors": anchors,
        "parts": [
            {"id": pid, "name": PART_NAMES[pid], "rect": list(PART_RECTS[pid])}
            for pid in range(len(PART_NAMES))
        ],
    }
    bones_json_path = out_dir / "bones.json"
    with open(bones_json_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, ensure_ascii=False, indent=2)
    print(f"[build_base] Wrote {bones_json_path}")

    glb_path = out_dir / "cat_base.glb"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_attributes=True,
        export_morph=True,
        export_morph_normal=False,
        export_skins=True,
        export_all_influences=False,
        export_animations=False,
        export_extras=True,
    )
    shutil.copyfile(glb_path, assets_dir / "cat_base.glb")

    num_verts = len(cat_obj.data.vertices)
    num_tris = len(cat_obj.data.polygons)
    print(f"[build_base] Done! Exported {glb_path} ({num_verts} verts, {num_tris} tris)")


if __name__ == "__main__":
    main()
