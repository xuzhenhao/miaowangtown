#!/usr/bin/env python3
"""
Build `cat_chibi_base.glb` in docs/validation/ab_static_compare/:
- HD-2D Chibi-proportioned continuous manifold cat mesh matching the red-box reference cat:
  * Large rounded head (~42% of total height) with full cheeks and turned slightly toward the viewer (+X, +Z)
  * Large upright pointed ears with concave inner concha
  * Smooth neck/bib transition into a compact rounded body
  * Four-paw walking stride matching the red-box cat
  * Relaxed S-curve tail behind the body
- Non-mirrored 1024x1024 UV atlas with dedicated high-density regions for head, muzzle, ears, body, legs, tail.
- Renders a 512x512 clay + depth + normal preview from the exact 3/4 camera angle (`az = -52 deg, el = 20 deg`).
"""
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Euler, Matrix

OUT_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# Three.js (x=left, y=up, z=forward) <-> Blender (x, -z, y)
def t2b(v: Vector) -> Vector:
    return Vector((v.x, -v.z, v.y))


def b2t(v: Vector) -> Vector:
    return Vector((v.x, v.z, -v.y))


# Head yaw angle: turn head slightly toward the viewer (+X left side, +16 degrees around Y)
# so in the 3/4 side-front view (camera at az=-52 deg), BOTH large green eyes and the peanut muzzle are clearly visible!
HEAD_YAW = math.radians(16.0)
HEAD_PIVOT = Vector((0.0, 0.72, 0.32))


def rotate_head_yaw(p: Vector) -> Vector:
    rel = p - HEAD_PIVOT
    c = math.cos(HEAD_YAW)
    s = math.sin(HEAD_YAW)
    # Rotate around Y axis toward +X (left side)
    rx = rel.x * c + rel.z * s
    rz = -rel.x * s + rel.z * c
    return Vector((HEAD_PIVOT.x + rx, p.y, HEAD_PIVOT.z + rz))


def inv_rotate_head_yaw(p: Vector) -> Vector:
    rel = p - HEAD_PIVOT
    c = math.cos(-HEAD_YAW)
    s = math.sin(-HEAD_YAW)
    rx = rel.x * c + rel.z * s
    rz = -rel.x * s + rel.z * c
    return Vector((HEAD_PIVOT.x + rx, p.y, HEAD_PIVOT.z + rz))


# Tail curve in Three.js space: arches out from croup and slopes down-back with a cute curved tip
TAIL_CURVE_PTS = [
    Vector((0.0, 0.48, -0.32)),
    Vector((-0.01, 0.49, -0.44)),
    Vector((-0.02, 0.45, -0.56)),
    Vector((-0.02, 0.37, -0.66)),
    Vector((-0.01, 0.29, -0.75)),
    Vector((0.0, 0.24, -0.82)),
    Vector((0.01, 0.26, -0.88)),
]


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
    pa = catmull_rom(pts, max(0.0, t - eps))
    pb = catmull_rom(pts, min(1.0, t + eps))
    d = pb - pa
    return d.normalized() if d.length > 1e-8 else Vector((0.0, 0.0, -1.0))


def create_closed_part(name: str, seg_s: int, seg_t: int, pos_fn, core_fn) -> bpy.types.Object:
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

    top_avg = sum((pos_fn(i / seg_s, 0.015) for i in range(seg_s)), Vector((0.0, 0.0, 0.0))) / seg_s
    bot_avg = sum((pos_fn(i / seg_s, 0.985) for i in range(seg_s)), Vector((0.0, 0.0, 0.0))) / seg_s
    v_top = bm.verts.new(t2b(top_avg))
    v_bot = bm.verts.new(t2b(bot_avg))

    for i in range(seg_s):
        ni = (i + 1) % seg_s
        try:
            bm.faces.new((v_top, rings[0][i], rings[0][ni]))
        except ValueError:
            pass

    for j in range(len(rings) - 1):
        for i in range(seg_s):
            ni = (i + 1) % seg_s
            try:
                bm.faces.new((rings[j][i], rings[j + 1][i], rings[j + 1][ni], rings[j][ni]))
            except ValueError:
                pass

    last_ring = rings[-1]
    for i in range(seg_s):
        ni = (i + 1) % seg_s
        try:
            bm.faces.new((last_ring[i], v_bot, last_ring[ni]))
        except ValueError:
            pass

    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.normal_update()
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


def build_chibi_parts() -> list[bpy.types.Object]:
    tau = math.pi * 2.0
    objs = []

    # 1. Compact Chibi Torso
    body_center = Vector((0.0, 0.42, -0.02))

    def body_pos(s: float, t: float) -> Vector:
        ph = clamp(t, 0.01, 0.99) * math.pi
        zc = -math.cos(ph)  # -1 rump, +1 chest
        r = math.sin(ph)
        th = (s - 0.5) * tau
        rx = 0.210 * (1.0 - 0.05 * zc + 0.08 * math.sin(ph))
        ry = 0.190 * (1.0 + 0.08 * math.cos((zc - 0.15) * math.pi * 0.8))
        X = math.sin(th) * r * rx
        Y = math.cos(th) * r * ry
        if Y < 0:
            tuck = 0.88 + 0.08 * clamp((zc + 0.7) / 0.6, 0.0, 1.0) if zc < 0 else 1.08
            Y *= tuck
        spine_arc = 0.025 * math.exp(-(((zc + 0.35) / 0.45) ** 2)) + 0.020 * math.exp(-(((zc - 0.45) / 0.40) ** 2))
        chest_puff = 0.065 * clamp((zc - 0.15) / 0.85, 0.0, 1.0) * r if (zc > 0.15 and Y > -0.15) else 0.0
        return Vector((X, body_center.y + spine_arc + Y, body_center.z + zc * 0.36 + chest_puff))

    objs.append(create_closed_part("part_body", 48, 40, body_pos, lambda p: Vector((0.0, 0.42, clamp(p.z, -0.30, 0.30)))))

    # 2. Smooth Thick Neck & Chest Bib (eliminates any collar crease!)
    neck_a = Vector((0.0, 0.44, 0.12))
    neck_b = Vector((0.02, 0.70, 0.32))
    neck_d = (neck_b - neck_a).normalized()
    neck_u = Vector((1.0, 0.0, 0.0))
    neck_w = neck_u.cross(neck_d).normalized()

    def neck_pos(s: float, t: float) -> Vector:
        th = (s - 0.5) * tau
        cap = math.sin(clamp(t, 0.02, 0.98) * math.pi) ** 0.18
        base_r = lerp(0.225, 0.245, t) * cap
        chest_fluff = (1.0 - t * 0.6) * 0.075 * max(0.0, math.cos(th)) * cap
        c = neck_a.lerp(neck_b, t)
        return c + neck_u * (math.sin(th) * base_r * 0.98) + neck_w * (math.cos(th) * (base_r + chest_fluff))

    def neck_core(p: Vector) -> Vector:
        ab = neck_b - neck_a
        t = clamp((p - neck_a).dot(ab) / ab.length_squared, 0.05, 0.95)
        return neck_a.lerp(neck_b, t)

    objs.append(create_closed_part("part_neck", 36, 22, neck_pos, neck_core))

    # 3. Chibi Head (Large, cute, rotated +16 deg toward +X/+Z viewer)
    head_center_local = Vector((0.0, 0.75, 0.35))

    def head_pos(s: float, t: float) -> Vector:
        th = (s - 0.5) * tau
        ph = clamp(t, 0.01, 0.99) * math.pi
        dx = math.sin(ph) * math.sin(th)
        dy = math.cos(ph)
        dz = math.sin(ph) * math.cos(th)
        rx, ry, rz = 0.295, 0.265, 0.270
        crown_taper = 1.0 - 0.08 * clamp((dy - 0.30) / 0.70, 0.0, 1.0) if dy > 0.30 else 1.0
        chin_taper = 1.0 - 0.15 * clamp((-0.45 - dy) / 0.55, 0.0, 1.0) if dy < -0.45 else 1.0
        cheek_bell = math.exp(-(((dy + 0.16) / 0.38) ** 2))
        cheek = 0.13 * cheek_bell * (abs(math.sin(th)) ** 0.75) * math.sin(ph)
        face_flatten = (1.0 - 0.09 * (dz ** 2)) if dz > 0 else 0.95
        forehead_puff = 0.024 * math.exp(-(((dy - 0.22) / 0.30) ** 2)) * clamp(dz, 0.0, 1.0)
        p_local = Vector((
            head_center_local.x + dx * rx * crown_taper * chin_taper * (1.0 + cheek),
            head_center_local.y + dy * ry,
            head_center_local.z + dz * rz * face_flatten + forehead_puff,
        ))
        return rotate_head_yaw(p_local)

    objs.append(create_closed_part("part_head", 56, 40, head_pos, lambda _p: rotate_head_yaw(head_center_local)))

    # 4. Cute Muzzle Pad (also rotated with head)
    muzzle_center_local = Vector((0.0, 0.675, 0.585))

    def muzzle_pos(s: float, t: float) -> Vector:
        th = (s - 0.5) * tau
        ph = clamp(t, 0.02, 0.98) * math.pi
        dx = math.sin(ph) * math.sin(th)
        dy = math.cos(ph)
        dz = math.sin(ph) * math.cos(th)
        pad = 1.0 + 0.18 * (math.sin(2.0 * th) ** 2) * clamp(dy + 0.4, 0.0, 1.0)
        chin = 1.0 - 0.22 * clamp((-0.2 - dy) / 0.8, 0.0, 1.0) if dy < -0.2 else 1.0
        nose_tip = 0.018 * math.exp(-((dx / 0.22) ** 2)) * clamp((dy - 0.1) / 0.6, 0.0, 1.0) * clamp(dz, 0.0, 1.0)
        p_local = Vector((
            muzzle_center_local.x + dx * 0.140 * pad * chin,
            muzzle_center_local.y + dy * 0.084,
            muzzle_center_local.z + dz * 0.076 + nose_tip,
        ))
        return rotate_head_yaw(p_local)

    objs.append(create_closed_part("part_muzzle", 36, 22, muzzle_pos, lambda _p: rotate_head_yaw(muzzle_center_local)))

    # 5. Four Legs in Walking Stride matching Red-Box Cat
    # In the red-box crop (viewed from az=-52 deg, i.e. left-front):
    # - Far front leg (fLegR, -X) steps forward-left (paw at z=+0.45, x=-0.08)
    # - Near front leg (fLegL, +X) steps slightly back (paw at z=+0.17, x=+0.12)
    # - Far hind leg (hLegR, -X) steps forward under belly (paw at z=-0.04, x=-0.08)
    # - Near hind leg (hLegL, +X) trails back (paw at z=-0.34, x=+0.12)
    leg_configs = [
        ("part_fLegR", -0.095, -0.075, 0.28, 0.36, 0.42, 0.46, True),
        ("part_fLegL",  0.115,  0.115, 0.24, 0.19, 0.16, 0.18, True),
        ("part_hLegR", -0.075, -0.080, -0.15, -0.08, -0.05, -0.02, False),
        ("part_hLegL",  0.090,  0.115, -0.20, -0.25, -0.34, -0.32, False),
    ]
    leg_top = 0.48
    paw_y = 0.045
    paw_r = 0.064

    for lname, hx, px_end, hz, kz, az, pz, is_front in leg_configs:
        def make_leg(hx=hx, px_end=px_end, hz=hz, kz=kz, az=az, pz=pz, is_front=is_front):
            tc = 0.82

            def axis_xz(y: float) -> tuple[float, float]:
                u = clamp((leg_top - y) / (leg_top - paw_y), 0.0, 1.0)
                lx = lerp(hx, px_end, u)
                if y >= 0.24:
                    t = clamp((y - 0.24) / (leg_top - 0.24), 0.0, 1.0)
                    lz = lerp(kz, hz, t)
                elif y >= 0.11:
                    t = clamp((y - 0.11) / (0.24 - 0.11), 0.0, 1.0)
                    lz = lerp(az, kz, t)
                else:
                    t = clamp(y / 0.11, 0.0, 1.0)
                    lz = lerp(pz, az, t)
                return lx, lz

            def leg_pos(s: float, t: float) -> Vector:
                th = (s - 0.5) * tau
                if t <= tc:
                    u = t / tc
                    y = lerp(leg_top, paw_y, u)
                    rx_u = 0.080 if is_front else 0.098
                    rz_u = 0.084 if is_front else 0.128
                    r_w = 0.054
                    if y >= 0.25:
                        f = clamp((y - 0.25) / (leg_top - 0.25), 0.0, 1.0)
                        top_cap = math.sin(clamp(u, 0.03, 1.0) * math.pi * 0.5) ** 0.28 if u < 0.15 else 1.0
                        rx = lerp(rx_u * 0.85, rx_u, f) * top_cap
                        rz = lerp(rz_u * 0.85, rz_u, f) * top_cap
                    elif y > 0.12:
                        f = (y - 0.12) / 0.13
                        rx = lerp(r_w, rx_u * 0.85, f)
                        rz = lerp(r_w * 1.06, rz_u * 0.85, f)
                    else:
                        f = clamp((y - paw_y) / (0.12 - paw_y), 0.0, 1.0)
                        toe_widen = 1.0 + 0.18 * (1.0 - f) * max(0.0, math.cos(th))
                        rx = lerp(paw_r * 1.04, r_w, f) * toe_widen
                        rz = lerp(paw_r * 1.24, r_w * 1.06, f)
                else:
                    a = clamp((t - tc) / (1.0 - tc), 0.0, 0.92) * (math.pi / 2.0)
                    y = paw_y - paw_r * math.sin(a) * 0.35
                    c = math.cos(a)
                    toe = 1.0 + 0.18 * max(0.0, math.cos(th)) * (1.0 - c)
                    rx = paw_r * 1.04 * c * toe
                    rz = paw_r * 1.24 * c
                lx, lz = axis_xz(y)
                return Vector((lx + math.sin(th) * rx, y, lz + math.cos(th) * rz))

            def leg_core(p: Vector) -> Vector:
                yc = clamp(p.y, 0.0, leg_top - 0.03)
                lx, lz = axis_xz(yc)
                return Vector((lx, yc, lz))

            return leg_pos, leg_core

        lpos, lcore = make_leg()
        objs.append(create_closed_part(lname, 24, 28, lpos, lcore))

    # 6. Large Upright Cute Cat Ears (rotated with head)
    for side, ename in ((1, "part_earL"), (-1, "part_earR")):
        def make_ear(side=side):
            ear_base = Vector((side * 0.150, 0.94, 0.36))
            axis = Vector((side * 0.22, 1.0, 0.08)).normalized()
            f0 = Vector((0.0, 0.0, 1.0))
            front = (f0 - axis * axis.dot(f0)).normalized()
            sideways = axis.cross(front).normalized()
            h = 0.275

            def ear_pos(s: float, t: float) -> Vector:
                th = (s - 0.5) * tau
                tc = clamp(t, 0.02, 0.98)
                rb = 0.140
                r = rb * ((1.0 - tc) ** 0.76)
                if tc < 0.08:
                    r *= (tc / 0.08) ** 0.28
                if math.cos(th) > 0:
                    cup = 0.28
                    r *= 0.94
                else:
                    cup = 0.62
                c = ear_base + axis * (-0.04 + tc * (h + 0.04))
                side_bias = 1.0 + 0.08 * math.sin(th) * side
                p_local = c + sideways * (math.sin(th) * r * side_bias) + front * (math.cos(th) * r * cup)
                return rotate_head_yaw(p_local)

            def ear_core(p: Vector) -> Vector:
                p_loc = inv_rotate_head_yaw(p)
                proj = clamp((p_loc - ear_base).dot(axis), -0.03, h * 0.88)
                return rotate_head_yaw(ear_base + axis * proj)

            return ear_pos, ear_core

        epos, ecore = make_ear()
        objs.append(create_closed_part(ename, 26, 20, epos, ecore))

    # 7. Tail
    tail_u = Vector((1.0, 0.0, 0.0))

    def tail_pos(s: float, t: float) -> Vector:
        th = (s - 0.5) * tau
        tc = clamp(t, 0.02, 0.98)
        c = catmull_rom(TAIL_CURVE_PTS, tc)
        tan = catmull_tangent(TAIL_CURVE_PTS, tc)
        w = tail_u.cross(tan).normalized()
        r = 0.054 * lerp(1.10, 0.78, tc)
        if tc < 0.07:
            r *= (tc / 0.07) ** 0.28
        if tc > 0.86:
            r *= math.sqrt(max(0.04, 1.0 - ((tc - 0.86) / 0.14) ** 2))
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

    objs.append(create_closed_part("part_tail", 20, 34, tail_pos, tail_core))
    return objs


def classify_chibi_part(p: Vector) -> int:
    p_head = inv_rotate_head_yaw(p)
    # 8: earL, 9: earR
    for side, pid in ((1, 8), (-1, 9)):
        ear_base = Vector((side * 0.150, 0.94, 0.36))
        axis = Vector((side * 0.22, 1.0, 0.08)).normalized()
        rel = p_head - ear_base
        proj = rel.dot(axis)
        if proj > -0.01 and p_head.y > 0.89 and side * p_head.x > 0.03 and p_head.z > 0.14:
            perp = (rel - axis * proj).length
            if perp < 0.155:
                return pid

    # 1: muzzle
    mc = Vector((0.0, 0.675, 0.585))
    if p_head.z > 0.53 and 0.58 <= p_head.y <= 0.75 and abs(p_head.x) <= 0.15:
        dx = (p_head.x - mc.x) / 0.15
        dy = (p_head.y - mc.y) / 0.088
        dz = (p_head.z - mc.z) / 0.088
        if dx * dx + dy * dy + dz * dz <= 1.15:
            return 1

    # 0: head
    hc = Vector((0.0, 0.75, 0.35))
    hdx = (p_head.x - hc.x) / 0.33
    hdy = (p_head.y - hc.y) / 0.285
    hdz = (p_head.z - hc.z) / 0.305
    if (p_head.y > 0.60 and p_head.z > 0.10) or ((hdx * hdx + hdy * hdy + hdz * hdz) < 1.02 and p_head.y > 0.55):
        return 0

    # 2: neck
    if p.y > 0.48 and p.z > 0.12 and (p.y + (p.z - 0.14) * 0.6) > 0.53:
        return 2

    # 10: tail
    if p.z < -0.32 and p.y > 0.18:
        return 10

    # 4, 5, 6, 7: legs
    if p.y < 0.34:
        if p.z > 0.08:
            return 4 if p.x >= 0.0 else 5
        else:
            return 6 if p.x >= 0.0 else 7

    # 3: body
    return 3


PART_RECTS_1024 = {
    0: (0, 0, 512, 256),      # head (512x256 high density)
    1: (512, 0, 256, 128),    # muzzle
    2: (768, 0, 256, 128),    # neck
    3: (0, 256, 512, 384),    # body
    4: (512, 128, 128, 192),  # fLegL
    5: (640, 128, 128, 192),  # fLegR
    6: (768, 128, 128, 192),  # hLegL
    7: (896, 128, 128, 192),  # hLegR
    8: (512, 320, 128, 128),  # earL
    9: (640, 320, 128, 128),  # earR
    10: (0, 640, 512, 128),   # tail
}
ATLAS_SIZE_1024 = 1024


def compute_chibi_part_uv(pid: int, p: Vector) -> tuple[float, float]:
    tau = math.pi * 2.0
    p_head = inv_rotate_head_yaw(p)
    if pid == 0:
        hc = Vector((0.0, 0.75, 0.35))
        d = p_head - hc
        th = math.atan2(d.x, d.z)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        t = clamp(math.acos(clamp(d.y / max(d.length, 1e-5), -1.0, 1.0)) / math.pi, 0.0, 1.0)
        return s, t
    if pid == 1:
        mc = Vector((0.0, 0.675, 0.55))
        d = p_head - mc
        th = math.atan2(d.x, max(0.01, d.z + 0.04))
        s = clamp(0.5 + th / (math.pi * 1.15), 0.0, 1.0)
        t = clamp(0.5 - d.y / 0.16, 0.0, 1.0)
        return s, t
    if pid == 2:
        na = Vector((0.0, 0.44, 0.12))
        nb = Vector((0.02, 0.70, 0.32))
        ab = nb - na
        t = clamp((p - na).dot(ab) / ab.length_squared, 0.0, 1.0)
        c = na.lerp(nb, t)
        d = p - c
        th = math.atan2(d.x, d.z)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        return s, t
    if pid == 3:
        bc = Vector((0.0, 0.42, -0.02))
        d = p - bc
        th = math.atan2(d.x, d.y)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        zc = clamp((p.z - bc.z) / 0.40, -1.0, 1.0)
        t = clamp(math.acos(-zc) / math.pi, 0.0, 1.0)
        return s, t
    if pid in (4, 5, 6, 7):
        lx = 0.115 if pid in (4, 6) else -0.085
        lz = (0.18 if pid == 4 else 0.42) if pid in (4, 5) else (-0.28 if pid == 6 else -0.06)
        dx = p.x - lx
        dz = p.z - lz
        th = math.atan2(dx, dz)
        s = clamp(0.5 + th / tau, 0.0, 1.0)
        t = clamp((0.36 - p.y) / 0.36, 0.0, 1.0)
        return s, t
    if pid in (8, 9):
        side = 1 if pid == 8 else -1
        ear_base = Vector((side * 0.150, 0.94, 0.36))
        axis = Vector((side * 0.22, 1.0, 0.08)).normalized()
        f0 = Vector((0.0, 0.0, 1.0))
        front = (f0 - axis * axis.dot(f0)).normalized()
        sideways = axis.cross(front).normalized()
        rel = p_head - ear_base
        proj = rel.dot(axis)
        t = clamp((proj + 0.02) / 0.29, 0.0, 1.0)
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


def build_unified_chibi_mesh() -> bpy.types.Object:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    part_objs = build_chibi_parts()
    obj = part_objs[0]
    obj.name = "cat_chibi_base"
    bpy.context.view_layer.objects.active = obj

    for sub in part_objs[1:]:
        mod = obj.modifiers.new(name=f"Union_{sub.name}", type="BOOLEAN")
        mod.operation = "UNION"
        mod.solver = "EXACT"
        mod.object = sub
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(sub, do_unlink=True)

    remesh = obj.modifiers.new(name="VoxelRemesh", type="REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = 0.0085
    remesh.adaptivity = 0.0
    remesh.use_smooth_shade = True
    bpy.ops.object.modifier_apply(modifier=remesh.name)

    smooth = obj.modifiers.new(name="Smooth", type="SMOOTH")
    smooth.factor = 0.32
    smooth.iterations = 5
    bpy.ops.object.modifier_apply(modifier=smooth.name)

    bm_tmp = bmesh.new()
    bm_tmp.from_mesh(obj.data)
    bmesh.ops.triangulate(bm_tmp, faces=bm_tmp.faces)
    bm_tmp.to_mesh(obj.data)
    bm_tmp.free()

    cur_tris = len(obj.data.polygons)
    if cur_tris > 6800:
        dec = obj.modifiers.new(name="Decimate", type="DECIMATE")
        dec.decimate_type = "COLLAPSE"
        dec.ratio = clamp(6800.0 / float(cur_tris), 0.1, 0.95)
        bpy.ops.object.modifier_apply(modifier=dec.name)

    # Flatten bottom of paws at y=0 and carve ear concha
    for v in obj.data.vertices:
        p = b2t(v.co)
        if p.y < 0.025:
            p.y = max(0.0, p.y * 0.15)
        p_head = inv_rotate_head_yaw(p)
        for side in (1, -1):
            ear_b = Vector((side * 0.150, 0.94, 0.36))
            axis = Vector((side * 0.22, 1.0, 0.08)).normalized()
            front = (Vector((0.0, 0.0, 1.0)) - axis * axis.dot(Vector((0.0, 0.0, 1.0)))).normalized()
            sideways = axis.cross(front)
            rel = p_head - ear_b
            proj = rel.dot(axis)
            if 0.0 < proj < 0.25 and side * p_head.x > 0.04 and p_head.y > 0.89:
                fz = rel.dot(front)
                sx = rel.dot(sideways)
                if fz > -0.01 and abs(sx) < 0.115:
                    depth = 0.032 * clamp(1.0 - abs(sx) / 0.115, 0.0, 1.0) * clamp(1.0 - abs(proj - 0.11) / 0.13, 0.0, 1.0)
                    p_head -= front * depth
                    p = rotate_head_yaw(p_head)
        v.co = t2b(p)

    obj.data.update()

    # Unwrap non-mirrored UV and assign _PART
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    welded_normals_three = [b2t(v.normal).normalized() for v in bm.verts]
    verts_three = [b2t(v.co) for v in bm.verts]

    face_parts = []
    for f in bm.faces:
        c = sum((verts_three[v.index] for v in f.verts), Vector((0.0, 0.0, 0.0))) / len(f.verts)
        face_parts.append(classify_chibi_part(c))

    for _ in range(3):
        nxt = list(face_parts)
        for fi, f in enumerate(bm.faces):
            nbr = [face_parts[fi]]
            for e in f.edges:
                for lf in e.link_faces:
                    if lf.index != fi:
                        nbr.append(face_parts[lf.index])
            counts = {}
            for pid in nbr:
                counts[pid] = counts.get(pid, 0) + 1
            best = max(counts.items(), key=lambda kv: kv[1])[0]
            if counts[best] >= len(nbr) // 2 + 1:
                nxt[fi] = best
        face_parts = nxt

    new_pos_bl = []
    new_norm_bl = []
    new_uvs = []
    new_parts = []
    new_tris = []
    v_cache = {}
    seen = set()

    for fi, f in enumerate(bm.faces):
        if len(f.verts) != 3:
            continue
        pid = face_parts[fi]
        rx, ry, rw, rh = PART_RECTS_1024[pid]
        pad = 4.0
        transpose = (pid == 10)
        vis = [v.index for v in f.verts]
        if len(set(vis)) < 3:
            continue
        raw_st = [compute_chibi_part_uv(pid, verts_three[vi]) for vi in vis]
        s_vals = [st[0] for st in raw_st]
        spans_seam = (max(s_vals) - min(s_vals)) > 0.55

        tri = []
        for k, vi in enumerate(vis):
            s, t = raw_st[k]
            wrap = 1 if (spans_seam and s < 0.35) else 0
            key = (vi, pid, wrap)
            if key not in v_cache:
                s_adj = min(1.0, s + (1.0 if wrap else 0.0))
                a = t if transpose else s_adj
                b = s_adj if transpose else t
                px = rx + pad + a * (rw - 2.0 * pad)
                py = ry + pad + b * (rh - 2.0 * pad)
                u = clamp(px / ATLAS_SIZE_1024, 0.001, 0.999)
                v_uv = clamp(1.0 - py / ATLAS_SIZE_1024, 0.001, 0.999)
                idx = len(new_pos_bl)
                v_cache[key] = idx
                new_pos_bl.append(bm.verts[vi].co.copy())
                new_norm_bl.append(t2b(welded_normals_three[vi]).normalized())
                new_uvs.append((u, v_uv))
                new_parts.append(pid)
            tri.append(v_cache[key])

        tk = tuple(sorted(tri))
        if len(set(tri)) == 3 and tk not in seen:
            seen.add(tk)
            new_tris.append((tri[0], tri[1], tri[2]))

    bm.free()

    new_mesh = bpy.data.meshes.new("cat_chibi_mesh")
    new_mesh.from_pydata(new_pos_bl, [], new_tris)
    for poly in new_mesh.polygons:
        poly.use_smooth = True
    new_mesh.validate(verbose=False)
    new_mesh.update()
    new_mesh.normals_split_custom_set_from_vertices(new_norm_bl[: len(new_mesh.vertices)])

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
    return obj


def render_preview(obj: bpy.types.Object):
    mat = bpy.data.materials.new("Clay")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.86, 0.80, 0.74, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.65
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    # Note: Prior to glTF export, Blender coordinates are t2b:
    # +X_bl = +X_three (cat left side)
    # -Y_bl = +Z_three (cat front)
    # +Z_bl = +Y_three (up)
    # So camera at (+X_bl, -Y_bl, +Z_bl) views the cat from its left-front (+X_three, +Z_three),
    # which puts the cat's nose pointing LEFT on screen and tail pointing RIGHT on screen!
    target = Vector((-0.02, 0.08, 0.56))
    az = math.radians(52.0)   # sin(52)>0 -> +X_bl, -cos(52)<0 -> -Y_bl
    el = math.radians(20.0)
    dist = 4.0
    loc = Vector((
        target.x + dist * math.cos(el) * math.sin(az),
        target.y - dist * math.cos(el) * math.cos(az),
        target.z + dist * math.sin(el),
    ))
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 1.62
    direction = target - loc
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="SUN", location=(2.5, -2.5, 3.5))
    sun = bpy.context.active_object
    sun.data.energy = 3.2
    sun.rotation_euler = Euler((math.radians(48), 0, math.radians(35)), "XYZ")

    bpy.ops.object.light_add(type="AREA", location=(-2.0, -2.0, 2.0))
    fill = bpy.context.active_object
    fill.data.energy = 120.0
    fill.data.size = 2.5

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.film_transparent = True
    scene.render.filepath = str(OUT_DIR / "chibi_clay_preview.png")
    bpy.ops.render.render(write_still=True)


def main():
    obj = build_unified_chibi_mesh()
    glb_path = OUT_DIR / "cat_chibi_base.glb"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_attributes=True,
        export_texcoords=True,
        export_normals=True,
    )
    print(f"[chibi_base] Exported {glb_path} ({len(obj.data.vertices)} verts, {len(obj.data.polygons)} tris)")
    render_preview(obj)


if __name__ == "__main__":
    main()
