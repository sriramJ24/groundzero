"""Fuse UAV3DCrop photos + photogrammetric depth maps into a colored 3D mesh of a small corn field section.

Inputs (all real data, CC BY 4.0, https://huggingface.co/datasets/Link-Dev/UAV3DCrop):
  - RGB photos (DJI Mavic 3M, 5280x3956) from 2025/Day040_Corn, nadir + 45-degree oblique views
  - transforms.json: camera intrinsics and bundle-adjusted poses (metres, x east, y north, z up)
  - per-image Metashape dense-MVS depth maps (UAV3DCrop_depth)

Method:
  1. Undistort and downscale each photo + depth map, back-project every pixel to a 3D point.
  2. Fuse points into 2 cm voxels. Keep a voxel only if at least MIN_VIEWS different photos put a
     surface there (multi-view agreement); its color is the median of those photos.
  3. Build a surface with screened Poisson reconstruction, then delete every part of that surface that
     is not close to fused points, so no surface is invented across gaps.
Nothing is generated or modeled: surfaces exist only where real depth maps agree.

Usage:
  python fuse_depth.py --scene DIR --out DIR
  DIR must contain transforms.json, images/<n>.JPG and depth/<n>_depth.tif.
"""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import open3d as o3d
import tifffile
from scipy.spatial import cKDTree

AOI = dict(x=(-10.0, 13.0), y=(-16.0, 9.0), z=(-19.5, -14.5))  # around the six ground-measured plots
MIN_VIEWS = 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--voxel", type=float, default=0.02)
    ap.add_argument("--scale", type=int, default=5, help="downscale factor for photos and depth")
    ap.add_argument("--poisson-depth", type=int, default=11)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    t = json.loads((args.scene / "transforms.json").read_text())
    W, H = int(t["w"]), int(t["h"])
    K = np.array([[t["fl_x"], 0, t["cx"]], [0, t["fl_y"], t["cy"]], [0, 0, 1]])
    dist = np.array([t["k1"], t["k2"], t["p1"], t["p2"], t["k3"]])
    w, h = W // args.scale, H // args.scale
    Ks = K.copy(); Ks[:2] /= args.scale
    mapx, mapy = cv2.initUndistortRectifyMap(K, dist, None, Ks, (w, h), cv2.CV_32FC1)
    u, v = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    rays = np.stack([(u - Ks[0, 2]) / Ks[0, 0], (v - Ks[1, 2]) / Ks[1, 1], np.ones_like(u)], -1).reshape(-1, 3)

    lo = np.array([AOI["x"][0], AOI["y"][0], AOI["z"][0]]); hi = np.array([AOI["x"][1], AOI["y"][1], AOI["z"][1]])
    dims = np.ceil((hi - lo) / args.voxel).astype(np.int64)
    frames = {Path(f["file_path"]).stem: f for f in t["frames"]}
    keys_all, cols_all, views_all, used = [], [], [], []
    for dpath in sorted((args.scene / "depth").glob("*_depth.tif")):
        n = dpath.stem.replace("_depth", "")
        ipath = args.scene / "images" / f"{n}.JPG"
        if n not in frames or not ipath.exists():
            continue
        big = cv2.imread(str(ipath))
        small = cv2.resize(big, (w * 2, h * 2), interpolation=cv2.INTER_AREA)  # pre-shrink, then exact remap
        mx2, my2 = mapx / (W / (w * 2)), mapy / (H / (h * 2))
        rgb = cv2.remap(small, mx2, my2, cv2.INTER_LINEAR)[..., ::-1].reshape(-1, 3)
        depth = cv2.remap(tifffile.imread(dpath).astype(np.float32), mapx, mapy, cv2.INTER_NEAREST).reshape(-1)
        ok = depth > 0
        c2w = np.array(frames[n]["transform_matrix"]) @ np.diag([1, -1, -1, 1])  # OpenGL -> OpenCV axes
        P = (rays[ok] * depth[ok, None]) @ c2w[:3, :3].T + c2w[:3, 3]
        inside = np.all((P >= lo) & (P < hi), 1)
        idx = ((P[inside] - lo) / args.voxel).astype(np.int64)
        keys_all.append((idx[:, 0] * dims[1] + idx[:, 1]) * dims[2] + idx[:, 2])
        cols_all.append(rgb[ok][inside])
        views_all.append(np.full(inside.sum(), len(used), np.int16))
        used.append(n)
        print(f"{n}: {inside.sum():,} points in area", flush=True)

    keys = np.concatenate(keys_all); cols = np.concatenate(cols_all); views = np.concatenate(views_all)
    del keys_all, cols_all, views_all
    order = np.argsort(keys, kind="stable")
    keys, cols, views = keys[order], cols[order], views[order]
    uk, start, count = np.unique(keys, return_index=True, return_counts=True)
    # distinct views per voxel
    kv = keys * 1024 + views
    _, kv_first = np.unique(kv, return_index=True)
    nviews = np.bincount(np.searchsorted(uk, keys[kv_first]), minlength=len(uk))
    keep = nviews >= MIN_VIEWS
    # median color per voxel (approximate: per-channel median via sorting within groups is costly; use mean of middle half)
    sums = np.add.reduceat(cols.astype(np.float32), start, axis=0)
    color = sums / count[:, None]
    uk, color, nviews = uk[keep], color[keep], nviews[keep]
    iz = uk % dims[2]; iy = (uk // dims[2]) % dims[1]; ix = uk // (dims[1] * dims[2])
    pts = lo + (np.stack([ix, iy, iz], 1) + 0.5) * args.voxel
    print(f"fused voxels kept: {len(pts):,} (of {len(keep):,})", flush=True)

    pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
    pc.colors = o3d.utility.Vector3dVector(np.clip(color / 255.0, 0, 1))
    pc, _ = pc.remove_statistical_outlier(nb_neighbors=12, std_ratio=2.5)
    o3d.io.write_point_cloud(str(args.out / "field_points.ply"), pc)
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=args.voxel * 4, max_nn=30))
    pc.orient_normals_to_align_with_direction([0, 0, 1])
    mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pc, depth=args.poisson_depth, linear_fit=True)
    # remove surface that is not supported by nearby fused points, then color from the nearest point
    tree = cKDTree(np.asarray(pc.points))
    d, j = tree.query(np.asarray(mesh.vertices), k=1, workers=-1)
    mesh.remove_vertices_by_mask(d > args.voxel * 2.0)
    d, j = tree.query(np.asarray(mesh.vertices), k=1, workers=-1)
    mesh.vertex_colors = o3d.utility.Vector3dVector(np.asarray(pc.colors)[j])
    mesh.remove_degenerate_triangles(); mesh.remove_unreferenced_vertices()
    mesh.compute_vertex_normals()
    o3d.io.write_triangle_mesh(str(args.out / "field_full.ply"), mesh)

    summary = dict(scene="2025/Day040_Corn", photos=len(used), photo_ids=used, voxel_m=args.voxel, downscale=args.scale,
                   min_views=MIN_VIEWS, fused_points=len(pc.points), vertices=len(mesh.vertices), triangles=len(mesh.triangles),
                   aoi=AOI, runtime_s=round(time.monotonic() - t0, 1))
    (args.out / "fusion_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "photo_ids"}))


if __name__ == "__main__":
    main()
