#!/usr/bin/env python3
"""Quick theory probe: compare 1–2 V2b hind-inner camera pairs vs 8+V1.
No control export / no SDXL / no fuse / no fur mutate.
"""
from __future__ import annotations
import hashlib, json, math, sys
from pathlib import Path
import bpy
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MASTER_DIR = ROOT / "art" / "master_cat"
ID_DIR = ROOT / "cats" / "miemie" / "identity_v1"
EXPECTED_UV = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
UV_SIZE = 2048
PITCH_8 = 35.0
V1_YAW, V1_PITCH = 0.0, -30.0
NDOTV_GRAZE = 0.20
DIRECTIONS_8 = {
    "d000": 0.0, "d045": -45.0, "d090": -90.0, "d135": -135.0,
    "d180": 180.0, "d225": 135.0, "d270": 90.0, "d315": 45.0,
}
# Two candidate L/R pairs inside authorized band yaw±110~±120, pitch 0~-20
CANDIDATES = {
    "A_yaw115_pitch_m10": {
        "L": {"yaw_deg": -115.0, "pitch_deg": -10.0},
        "R": {"yaw_deg": 115.0, "pitch_deg": -10.0},
    },
    "B_yaw120_pitch_m15": {
        "L": {"yaw_deg": -120.0, "pitch_deg": -15.0},
        "R": {"yaw_deg": 120.0, "pitch_deg": -15.0},
    },
}

def get_camera_basis(yaw_deg, pitch_deg=PITCH_8):
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cy, sy = math.cos(-yaw), math.sin(-yaw)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    e_u0 = np.array([-1.0, 0.0, 0.0], dtype=np.float64)
    e_v0 = np.array([0.0, -math.sin(pitch), math.cos(pitch)], dtype=np.float64)
    e_w0 = np.array([0.0, math.cos(pitch), math.sin(pitch)], dtype=np.float64)
    return rz @ e_u0, rz @ e_v0, rz @ e_w0

def compute_uv_hash(mesh):
    uv = mesh.uv_layers.active.data
    rows = [[loop.vertex_index, round(uv[loop.index].uv.x, 6), round(uv[loop.index].uv.y, 6)]
            for loop in mesh.loops]
    return "sha256:" + hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()

def raster_ndotv(tris_uv, tris_nrm_u, e_w, out):
    for i in range(len(tris_uv)):
        uv = tris_uv[i]
        u_px = uv[:, 0] * (UV_SIZE - 1)
        v_px = (1.0 - uv[:, 1]) * (UV_SIZE - 1)
        xmin = max(0, int(math.floor(u_px.min())))
        xmax = min(UV_SIZE - 1, int(math.ceil(u_px.max())))
        ymin = max(0, int(math.floor(v_px.min())))
        ymax = min(UV_SIZE - 1, int(math.ceil(v_px.max())))
        if xmax < xmin or ymax < ymin:
            continue
        x0, y0 = u_px[0], v_px[0]
        x1, y1 = u_px[1], v_px[1]
        x2, y2 = u_px[2], v_px[2]
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-10:
            continue
        ndotv = float(tris_nrm_u[i] @ e_w)
        yy, xx = np.meshgrid(np.arange(ymin, ymax + 1) + 0.5, np.arange(xmin, xmax + 1) + 0.5, indexing="ij")
        w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
        w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not np.any(inside):
            continue
        sub = out[ymin:ymax + 1, xmin:xmax + 1]
        better = inside & (ndotv > sub)
        sub[better] = ndotv

def pct(n, d):
    return round(100.0 * n / max(1, d), 2)

def main():
    cov = np.array(Image.open(ID_DIR / "coverage.png").convert("RGB"))
    green = (cov[:,:,0]==40)&(cov[:,:,1]==200)&(cov[:,:,2]==70)
    yellow = (cov[:,:,0]==230)&(cov[:,:,1]==200)&(cov[:,:,2]==40)
    red_pil = (cov[:,:,0]==200)&(cov[:,:,1]==50)&(cov[:,:,2]==50)
    gy = green | yellow
    n_gy = int(gy.sum())

    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    body = bpy.data.objects["CAT_BODY"]
    measured = compute_uv_hash(body.data)
    if measured != EXPECTED_UV:
        raise RuntimeError(f"uv_hash mismatch {measured}")
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active.data
    vs = np.array([list(ev.matrix_world @ v.co) for v in mesh.vertices], dtype=np.float64)
    tris_uv, tris_nrm = [], []
    for lt in mesh.loop_triangles:
        i0, i1, i2 = lt.vertices
        l0, l1, l2 = lt.loops
        uvs = np.array([[uv_layer[l0].uv.x, uv_layer[l0].uv.y],
                        [uv_layer[l1].uv.x, uv_layer[l1].uv.y],
                        [uv_layer[l2].uv.x, uv_layer[l2].uv.y]], dtype=np.float64)
        pos = np.array([vs[i0], vs[i1], vs[i2]], dtype=np.float64)
        nrm = np.cross(pos[1]-pos[0], pos[2]-pos[0])
        tris_uv.append(uvs); tris_nrm.append(nrm)
    tris_uv = np.array(tris_uv); tris_nrm = np.array(tris_nrm)
    nlen = np.linalg.norm(tris_nrm, axis=1, keepdims=True)
    tris_nrm_u = tris_nrm / np.maximum(nlen, 1e-12)

    uv_hit = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for i in range(len(tris_uv)):
        uv = tris_uv[i]
        u_px = uv[:,0]*(UV_SIZE-1); v_px = (1.0-uv[:,1])*(UV_SIZE-1)
        xmin=max(0,int(math.floor(u_px.min()))); xmax=min(UV_SIZE-1,int(math.ceil(u_px.max())))
        ymin=max(0,int(math.floor(v_px.min()))); ymax=min(UV_SIZE-1,int(math.ceil(v_px.max())))
        if xmax<xmin or ymax<ymin: continue
        x0,y0=u_px[0],v_px[0]; x1,y1=u_px[1],v_px[1]; x2,y2=u_px[2],v_px[2]
        denom=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(denom)<1e-10: continue
        yy,xx=np.meshgrid(np.arange(ymin,ymax+1)+0.5, np.arange(xmin,xmax+1)+0.5, indexing="ij")
        w0=((y1-y2)*(xx-x2)+(x2-x1)*(yy-y2))/denom
        w1=((y2-y0)*(xx-x2)+(x0-x2)*(yy-y2))/denom
        w2=1.0-w0-w1
        inside=(w0>=-1e-4)&(w1>=-1e-4)&(w2>=-1e-4)
        if np.any(inside):
            uv_hit[ymin:ymax+1, xmin:xmax+1] |= inside

    island = uv_hit | gy
    red = red_pil & uv_hit
    n_island = int(island.sum()); n_red = int(red.sum())
    gy_now = n_gy / max(1, n_island); red_now = n_red / max(1, n_island)
    print(f"island={n_island} gy={n_gy} red={n_red} GY={gy_now:.4f} red_r={red_now:.4f}", flush=True)

    best_prev = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    for dname, yaw in DIRECTIONS_8.items():
        _, _, e_w = get_camera_basis(yaw, PITCH_8)
        raster_ndotv(tris_uv, tris_nrm_u, e_w, best_prev)
        print(f"ndotv8 {dname}", flush=True)
    v1 = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    _, _, e_w_v1 = get_camera_basis(V1_YAW, V1_PITCH)
    raster_ndotv(tris_uv, tris_nrm_u, e_w_v1, v1)
    best_prev = np.maximum(best_prev, v1)
    print("ndotv V1 folded", flush=True)

    geo_blind = red & (best_prev < 0.0)
    n_geo = int(geo_blind.sum())
    results = {}
    for label, pair in CANDIDATES.items():
        best = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
        for side, spec in pair.items():
            m = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
            _, _, e_w = get_camera_basis(spec["yaw_deg"], spec["pitch_deg"])
            raster_ndotv(tris_uv, tris_nrm_u, e_w, m)
            best = np.maximum(best, m)
            print(f"ndotv {label}/{side} yaw={spec['yaw_deg']} pitch={spec['pitch_deg']}", flush=True)
        covers = red & (best >= NDOTV_GRAZE)
        newly = covers & (best_prev < NDOTV_GRAZE)
        n_newly = int(newly.sum())
        n_geo_eaten = int((geo_blind & (best >= NDOTV_GRAZE)).sum())
        gy_est = (n_gy + n_newly) / max(1, n_island)
        results[label] = {
            "cameras": pair,
            "n_newly": n_newly,
            "pct_honest_red_newly": pct(n_newly, n_red),
            "backface_red_n": n_geo,
            "backface_red_eaten": n_geo_eaten,
            "pct_backface_red_eaten": pct(n_geo_eaten, n_geo),
            "GY_est": round(gy_est, 4),
            "delta_GY_pp": round((gy_est - gy_now) * 100, 2),
        }
    # also old V2 for reference in same run
    old = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    for yaw, pitch in [(-75.0, 15.0), (75.0, 15.0)]:
        m = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
        _, _, e_w = get_camera_basis(yaw, pitch)
        raster_ndotv(tris_uv, tris_nrm_u, e_w, m)
        old = np.maximum(old, m)
    covers = red & (old >= NDOTV_GRAZE)
    newly = covers & (best_prev < NDOTV_GRAZE)
    n_newly = int(newly.sum())
    n_geo_eaten = int((geo_blind & (old >= NDOTV_GRAZE)).sum())
    gy_est = (n_gy + n_newly) / max(1, n_island)
    results["OLD_v2_yaw75_pitch15"] = {
        "cameras": {"L": {"yaw_deg": -75.0, "pitch_deg": 15.0}, "R": {"yaw_deg": 75.0, "pitch_deg": 15.0}},
        "n_newly": n_newly,
        "pct_honest_red_newly": pct(n_newly, n_red),
        "backface_red_n": n_geo,
        "backface_red_eaten": n_geo_eaten,
        "pct_backface_red_eaten": pct(n_geo_eaten, n_geo),
        "GY_est": round(gy_est, 4),
        "delta_GY_pp": round((gy_est - gy_now) * 100, 2),
    }

    # pick: maximize (backface_eaten, then newly)
    scored = sorted(
        [(k, v) for k, v in results.items() if k.startswith(("A_", "B_"))],
        key=lambda kv: (kv[1]["backface_red_eaten"], kv[1]["n_newly"]),
        reverse=True,
    )
    winner = scored[0][0]
    out = {
        "baseline": {"GY": round(gy_now, 4), "red": round(red_now, 4), "n_red": n_red, "n_island": n_island},
        "candidates": results,
        "winner": winner,
        "winner_reason": "max (backface_red_eaten, n_newly) among A/B",
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    out_path = ROOT / "logs" / "m22" / "theory_v2b_cam_probe.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    ev.to_mesh_clear()
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
