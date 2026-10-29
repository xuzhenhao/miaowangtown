#!/usr/bin/env python3
"""
M1 freeze helper: densify hind-knee deformation rings WITHOUT changing Rest silhouette.

Adds 3 bisect planes per hind leg (BL/BR) around the knee along the thigh→ankle axis.
New verts lie on existing surface edges, so Basis envelope / silhouette stay put.
Rewrites art/master_cat/master_topology_cache.npz and remaps landmark_vertices.json indices.
"""
from __future__ import annotations

import json
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path("/workspace/miaowangtown")
MASTER = ROOT / "art" / "master_cat"
TOPO = MASTER / "master_topology_cache.npz"
LANDMARK = MASTER / "landmark_vertices.json"


def _load():
    topo = np.load(TOPO)
    vs = topo["vs_basis"].astype(np.float64).copy()
    tris = topo["tris"].astype(np.int32).copy()
    v_part = topo["v_part"].astype(np.int32).copy()
    return vs, tris, v_part


def _build_bmesh(vs, tris, v_part):
    bm = bmesh.new()
    part_layer = bm.verts.layers.int.new("v_part")
    for i, v in enumerate(vs):
        bv = bm.verts.new((float(v[0]), float(v[1]), float(v[2])))
        bv[part_layer] = int(v_part[i])
    bm.verts.ensure_lookup_table()
    for t in tris:
        try:
            bm.faces.new((bm.verts[int(t[0])], bm.verts[int(t[1])], bm.verts[int(t[2])]))
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return bm, part_layer


def _fill_new_vert_parts(bm, part_layer, default_part):
    """Assign part for verts still at 0 that are brand-new and near a default_part region,
    by majority of linked neighbour parts. Only touch verts with no edges yet handled —
    actually: verts created by bisect start with layer default 0. Prefer neighbour vote.
    """
    for v in bm.verts:
        # Only reassign if isolated default and has neighbours with non-ambiguous part
        linked = [e.other_vert(v) for e in v.link_edges]
        if not linked:
            continue
        # If this vert already has a non-zero part, keep; if 0, may be torso OR new —
        # new cut verts on hind leg will have hind-leg neighbours.
        parts = [ov[part_layer] for ov in linked]
        # If any neighbour matches default_part (the leg we are cutting), and current is 0
        # but most neighbours are default_part, set it.
        if v[part_layer] == 0 and parts.count(default_part) >= max(1, len(parts) // 2):
            # avoid stealing true torso cuff: only if majority is the leg part
            v[part_layer] = default_part


def _leg_geom(bm, part_layer, part_id, knee_co, radius=0.055):
    verts = []
    for v in bm.verts:
        d = (v.co - knee_co).length
        pid = int(v[part_layer])
        if pid == part_id or d < radius:
            if pid == 0 and d > radius * 0.85:
                continue
            verts.append(v)
    vset = set(verts)
    edges = [e for e in bm.edges if e.verts[0] in vset and e.verts[1] in vset]
    faces = [f for f in bm.faces if all(vv in vset for vv in f.verts)]
    return verts + edges + faces


def _bisect_knee(bm, part_layer, part_id, thigh_co, knee_co, ankle_co, offsets_m):
    axis = (ankle_co - thigh_co).normalized()
    if axis.length < 1e-6:
        axis = Vector((0.0, 0.0, -1.0))
    n_before = len(bm.verts)
    for off in offsets_m:
        plane_co = knee_co + axis * float(off)
        geom = _leg_geom(bm, part_layer, part_id, knee_co)
        if not geom:
            continue
        bmesh.ops.bisect_plane(
            bm,
            geom=geom,
            dist=1e-5,
            plane_co=plane_co,
            plane_no=axis,
            use_snap_center=False,
            clear_inner=False,
            clear_outer=False,
        )
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        _fill_new_vert_parts(bm, part_layer, part_id)
        faces = [f for f in bm.faces if len(f.verts) > 3]
        # limit triangulate to leg neighbourhood
        leg_faces = [
            f for f in faces
            if any(int(v[part_layer]) == part_id or (v.co - knee_co).length < 0.06 for v in f.verts)
        ]
        if leg_faces:
            bmesh.ops.triangulate(bm, faces=leg_faces)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
    return len(bm.verts) - n_before


def _export(bm, part_layer, old_vs, old_part):
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    vs = np.array([[v.co.x, v.co.y, v.co.z] for v in bm.verts], dtype=np.float64)
    parts_layer = np.array([int(v[part_layer]) for v in bm.verts], dtype=np.int32)
    tris = []
    for f in bm.faces:
        vids = [v.index for v in f.verts]
        if len(vids) == 3:
            tris.append(vids)
        elif len(vids) == 4:
            tris.append([vids[0], vids[1], vids[2]])
            tris.append([vids[0], vids[2], vids[3]])
        else:
            for i in range(1, len(vids) - 1):
                tris.append([vids[0], vids[i], vids[i + 1]])
    tris = np.array(tris, dtype=np.int32)

    # Fix any remaining 0-part verts that are clearly on a hind/front leg by nearest old
    need = np.where(parts_layer == 0)[0]
    if len(need):
        for i in range(0, len(need), 256):
            idxs = need[i : i + 256]
            chunk = vs[idxs]
            d = ((chunk[:, None, :] - old_vs[None, :, :]) ** 2).sum(axis=2)
            nn = d.argmin(axis=1)
            # only overwrite if old part was non-zero OR keep 0 for torso
            for local, gi in enumerate(idxs):
                op = int(old_part[nn[local]])
                # if nearest old is torso, keep 0; else adopt
                if parts_layer[gi] == 0 and op != 0:
                    # only if very close
                    if d[local, nn[local]] < (0.004 ** 2):
                        parts_layer[gi] = op

    # For verts that are still ambiguous but near hind legs after cut, nearest-old always:
    for i in range(0, len(vs), 256):
        chunk = vs[i : i + 256]
        d = ((chunk[:, None, :] - old_vs[None, :, :]) ** 2).sum(axis=2)
        nn = d.argmin(axis=1)
        for local in range(len(chunk)):
            gi = i + local
            # Prefer layer if non-zero; else nearest old
            if parts_layer[gi] == 0:
                parts_layer[gi] = int(old_part[nn[local]])

    mirror_target = vs.copy()
    mirror_target[:, 0] *= -1.0
    mirror_idx = np.zeros(len(vs), dtype=np.int64)
    for i in range(0, len(vs), 256):
        chunk = mirror_target[i : i + 256]
        d = ((chunk[:, None, :] - vs[None, :, :]) ** 2).sum(axis=2)
        mirror_idx[i : i + len(chunk)] = d.argmin(axis=1)
    return vs, tris, parts_layer, mirror_idx


def _remap_landmarks(old_vs, new_vs, points):
    new_points = {}
    for name, idxs in points.items():
        if not isinstance(idxs, list):
            new_points[name] = idxs
            continue
        remapped = []
        for i in idxs:
            if not isinstance(i, int):
                remapped.append(i)
                continue
            p = old_vs[int(i)]
            d = ((new_vs - p) ** 2).sum(axis=1)
            remapped.append(int(d.argmin()))
        new_points[name] = remapped
    return new_points


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    old_vs, old_tris, old_part = _load()
    doc = json.loads(LANDMARK.read_text(encoding="utf-8"))
    pts = doc["points"]

    def co(name):
        i = pts[name][0]
        return Vector((float(old_vs[i, 0]), float(old_vs[i, 1]), float(old_vs[i, 2])))

    bm, part_layer = _build_bmesh(old_vs, old_tris, old_part)
    offsets = (-0.014, -0.005, 0.008)

    for side, part_id in (("BL", 4), ("BR", 3)):
        thigh = co(f"thigh_{side}")
        knee = co(f"knee_{side}")
        ankle = co(f"ankle_{side}")
        n = _bisect_knee(bm, part_layer, part_id, thigh, knee, ankle, offsets)
        print(f"[add_hind_knee_loops] {side} part={part_id} new_verts≈{n}")

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    nontri = [f for f in bm.faces if len(f.verts) != 3]
    if nontri:
        bmesh.ops.triangulate(bm, faces=nontri)

    vs, tris, part, mirror_idx = _export(bm, part_layer, old_vs, old_part)
    bm.free()

    dmin = []
    for i in range(0, len(old_vs), 128):
        chunk = old_vs[i : i + 128]
        d = ((chunk[:, None, :] - vs[None, :, :]) ** 2).sum(axis=2).min(axis=1)
        dmin.append(d)
    dmin = np.concatenate(dmin)
    print(
        f"[add_hind_knee_loops] old→new coverage max_dist={float(np.sqrt(dmin.max()))*1000:.4f} mm "
        f"mean={float(np.sqrt(dmin.mean()))*1000:.4f} mm"
    )
    print(f"[add_hind_knee_loops] verts {len(old_vs)} → {len(vs)}, tris {len(old_tris)} → {len(tris)}")
    print(f"[add_hind_knee_loops] parts { {int(p): int((part==p).sum()) for p in np.unique(part)} }")

    new_points = _remap_landmarks(old_vs, vs, pts)
    for k in ("knee_BL", "knee_BR", "thigh_BL", "thigh_BR", "ankle_BL", "ankle_BR"):
        oi, ni = pts[k][0], new_points[k][0]
        err = float(np.linalg.norm(old_vs[oi] - vs[ni]))
        print(f"  landmark {k}: {oi}→{ni} err={err*1000:.4f} mm")

    # Ring density check around knees
    from collections import defaultdict
    adj = defaultdict(set)
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            adj[u].add(v)
            adj[v].add(u)
    for side in ("BL", "BR"):
        knee = new_points[f"knee_{side}"][0]
        # count verts within 1.5cm of knee on same part
        kp = vs[knee]
        pid = int(part[knee])
        near = np.where((part == pid) & (np.linalg.norm(vs - kp, axis=1) < 0.018))[0]
        print(f"  densify check {side}: verts within 18mm of knee (same part) = {len(near)}")

    np.savez_compressed(
        TOPO,
        vs0=vs.copy(),
        vs_basis=vs,
        tris=tris,
        v_part=part,
        mirror_idx=mirror_idx,
    )
    doc["points"] = new_points
    doc["mesh_version"] = int(doc.get("mesh_version", 1)) + 1
    doc["hind_knee_loops_note"] = (
        "M1 freeze: added 3 bisect rings per hind knee (BL/BR) along thigh→ankle; "
        "Rest envelope unchanged (cuts on-surface)."
    )
    LANDMARK.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"[add_hind_knee_loops] wrote {TOPO} and remapped {LANDMARK}")


if __name__ == "__main__":
    main()
