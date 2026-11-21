"""Turn the fused UAV3DCrop points into a web-ready field model: a canopy surface + a photo texture.

  1. Canopy surface (DSM): highest fused point per 4 cm cell, small holes filled from neighbours
     (filled cells are recorded in a mask), lightly median-filtered.
  2. Photo texture (orthophoto, 1 cm per pixel): every texel is projected into the nadir photos at full
     resolution; it takes its color from the photo where it is closest to the image centre and where the
     photo's own depth map confirms the spot is visible (not hidden by a nearer leaf).
Outputs: field.bin (float32 heights; the viewer reads field_heights.json, the same grid as uint16 mm), field_texture.jpg, field.json (grid, bounds, provenance).

Usage: python build_surface.py --scene DIR --fused DIR --out DIR
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import open3d as o3d
import tifffile

GEO_CELL = 0.04  # m, surface grid
TEX_CELL = 0.01  # m, texture pixel


def bilinear(img, u, v):
    u0 = np.floor(u).astype(int); v0 = np.floor(v).astype(int)
    fu = (u - u0)[:, None]; fv = (v - v0)[:, None]
    a = img[v0, u0].astype(np.float32); b = img[v0, u0 + 1].astype(np.float32)
    c = img[v0 + 1, u0].astype(np.float32); d = img[v0 + 1, u0 + 1].astype(np.float32)
    return np.clip((a * (1 - fu) + b * fu) * (1 - fv) + (c * (1 - fu) + d * fu) * fv + 0.5, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--fused", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    summ = json.loads((args.fused / "fusion_summary.json").read_text())
    aoi = summ["aoi"]
    x0, x1 = aoi["x"]; y0, y1 = aoi["y"]
    pts = np.asarray(o3d.io.read_point_cloud(str(args.fused / "field_points.ply")).points)

    # 1. DSM
    nx, ny = int(round((x1 - x0) / GEO_CELL)), int(round((y1 - y0) / GEO_CELL))
    ix = np.clip(((pts[:, 0] - x0) / GEO_CELL).astype(int), 0, nx - 1)
    iy = np.clip(((pts[:, 1] - y0) / GEO_CELL).astype(int), 0, ny - 1)
    dsm = np.full((ny, nx), -np.inf, np.float32)
    np.maximum.at(dsm, (iy, ix), pts[:, 2].astype(np.float32))
    holes = ~np.isfinite(dsm)
    zmin, zmax = float(np.percentile(dsm[~holes], 0.5)), float(np.percentile(dsm[~holes], 99.9))
    dsm = np.clip(np.where(holes, zmin, dsm), zmin, zmax)
    norm = ((dsm - zmin) / (zmax - zmin) * 65535).astype(np.uint16)
    filled = cv2.inpaint((norm >> 8).astype(np.uint8), holes.astype(np.uint8), 3, cv2.INPAINT_TELEA)
    dsm = np.where(holes, zmin + filled.astype(np.float32) / 255 * (zmax - zmin), dsm)
    dsm = cv2.medianBlur(dsm.astype(np.float32), 3)
    print(f"surface grid {nx}x{ny}, holes filled {holes.mean():.1%}, z {zmin:.2f}..{zmax:.2f}")

    # 2. Orthophoto texture from nadir photos
    t = json.loads((args.scene / "transforms.json").read_text())
    K = np.array([[t["fl_x"], 0, t["cx"]], [0, t["fl_y"], t["cy"]], [0, 0, 1]])
    dist = np.array([t["k1"], t["k2"], t["p1"], t["p2"], t["k3"]])
    W, H = int(t["w"]), int(t["h"])
    frames = {Path(f["file_path"]).stem: f for f in t["frames"]}
    tx, ty = int(round((x1 - x0) / TEX_CELL)), int(round((y1 - y0) / TEX_CELL))
    gx = x0 + (np.arange(tx) + 0.5) * TEX_CELL
    gy = y1 - (np.arange(ty) + 0.5) * TEX_CELL  # image row 0 = north edge
    # texel heights from the DSM (bilinear)
    mx = ((gx - x0) / GEO_CELL - 0.5).astype(np.float32)
    my = ((gy - y0) / GEO_CELL - 0.5).astype(np.float32)
    MX, MY = np.meshgrid(mx, my)
    Z = cv2.remap(dsm, MX, MY, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    GX, GY = np.meshgrid(gx, gy)
    world = np.stack([GX, GY, Z], -1).reshape(-1, 3)

    tex = np.zeros((ty * tx, 3), np.uint8)
    best = np.full(ty * tx, np.inf, np.float32)
    nadir = []
    for n in summ["photo_ids"]:
        M = np.array(frames[n]["transform_matrix"])
        if M[2, 2] < 0.95:  # camera looking almost straight down only (OpenGL: view dir = -z column)
            continue
        nadir.append(n)
        c2w = M @ np.diag([1, -1, -1, 1])
        w2c = np.linalg.inv(c2w)
        cam = world @ w2c[:3, :3].T + w2c[:3, 3]
        rvec, _ = cv2.Rodrigues(w2c[:3, :3])
        uv, _ = cv2.projectPoints(world, rvec, w2c[:3, 3], K, dist)
        uv = uv.reshape(-1, 2)
        ok = (cam[:, 2] > 0) & (uv[:, 0] >= 0) & (uv[:, 0] < W - 1) & (uv[:, 1] >= 0) & (uv[:, 1] < H - 1)
        depth = tifffile.imread(args.scene / "depth" / f"{n}_depth.tif").astype(np.float32)
        ui, vi = uv[ok, 0].astype(int), uv[ok, 1].astype(int)
        dmap = depth[vi, ui]
        vis = (dmap > 0) & (np.abs(dmap - cam[ok, 2]) < 0.15)
        idx = np.nonzero(ok)[0][vis]
        score = np.hypot(uv[idx, 0] - W / 2, uv[idx, 1] - H / 2).astype(np.float32)
        better = score < best[idx]
        idx, score = idx[better], score[better]
        img = cv2.imread(str(args.scene / "images" / f"{n}.JPG"))
        tex[idx] = bilinear(img, uv[idx, 0], uv[idx, 1])
        best[idx] = score
        print(f"nadir {n}: textured {len(idx):,} texels", flush=True)
    covered = np.isfinite(best).reshape(ty, tx)
    tex = tex.reshape(ty, tx, 3)
    if (~covered).any():
        tex = cv2.inpaint(tex, (~covered).astype(np.uint8), 5, cv2.INPAINT_TELEA)
    cv2.imwrite(str(args.out / "field_texture.jpg"), tex, [cv2.IMWRITE_JPEG_QUALITY, 88])
    cv2.imwrite(str(args.out / "field_texture_small.jpg"), cv2.resize(tex, (tx // 4, ty // 4), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])

    dsm.astype(np.float32).tofile(args.out / "field.bin")
    q = np.clip(np.round((dsm - zmin) * 1000), 0, 65535).astype("<u2")
    import base64
    (args.out / "field_heights.json").write_text(json.dumps(dict(nx=nx, ny=ny, row0="south", offset_m=zmin, scale_m=0.001,
                                                                 uint16_le_base64=base64.b64encode(q.tobytes()).decode())))
    meta = dict(
        grid=dict(nx=nx, ny=ny, cell_m=GEO_CELL, x0=x0, y0=y0, x1=x1, y1=y1, z_min=zmin, z_max=zmax, row0="south"),
        texture=dict(width=tx, height=ty, cell_m=TEX_CELL, row0="north", nadir_photos=nadir,
                     uncovered_fraction=round(float((~covered).mean()), 4)),
        holes_filled_fraction=round(float(holes.mean()), 4),
        fusion={k: v for k, v in summ.items() if k != "photo_ids"},
    )
    (args.out / "field.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta["texture"]), meta["holes_filled_fraction"])


if __name__ == "__main__":
    main()
