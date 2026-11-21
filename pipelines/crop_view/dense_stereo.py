"""Bounded dense-geometry trial for the GroundZero crop view.

Inputs (all real, nothing generated):
  - the 47 CropDriveSD side-camera PNGs (frames 2940-3078, one continuous 4.6 s segment)
  - the COLMAP attempt-2 sparse model (30 aligned cameras, fixed factory/checkerboard intrinsics)

Method: plane-sweep-free two-view stereo. For pairs of aligned cameras we rectify with the
COLMAP relative pose, run OpenCV semi-global matching, keep pixels that pass a left-right
consistency check, triangulate them, and then fuse everything into a coarse voxel grid.
A voxel is kept only when at least MIN_PAIRS independent image pairs put geometry there.

Scale is arbitrary (no GPS, IMU, odometry, or metric reference in the inputs).
Hard limits: CPU only, no downloads, stops after TIME_LIMIT_S seconds.

Usage:
  python dense_stereo.py --images DIR --sparse DIR --out DIR
"""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

TIME_LIMIT_S = 600
MIN_PAIRS = 3


def qvec_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * w * z, 2 * x * z + 2 * w * y],
        [2 * x * y + 2 * w * z, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * w * x],
        [2 * x * z - 2 * w * y, 2 * y * z + 2 * w * x, 1 - 2 * x * x - 2 * y * y],
    ])


def load_model(sparse):
    cam = None
    for line in (sparse / "cameras.txt").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        p = line.split()
        w, h = int(p[2]), int(p[3])
        fx, fy, cx, cy, k1, k2, p1, p2 = map(float, p[4:12])
        cam = dict(w=w, h=h, K=np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]]),
                   dist=np.array([[k1, k2, p1, p2]]))
    images = {}
    lines = [l for l in (sparse / "images.txt").read_text().splitlines() if not l.startswith("#")]
    for i in range(0, len(lines), 2):
        p = lines[i].split()
        if len(p) < 10:
            continue
        R = qvec_to_R(list(map(float, p[1:5])))
        t = np.array(list(map(float, p[5:8])))
        images[p[9]] = dict(id=int(p[0]), R=R, t=t, C=-R.T @ t)
    pts = []
    for line in (sparse / "points3D.txt").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        p = line.split()
        pts.append(list(map(float, p[1:4])))
    return cam, images, np.array(pts)


def lr_disparity(r1, r2, num_disp, block):
    common = dict(blockSize=block, P1=8 * 3 * block * block, P2=32 * 3 * block * block,
                  disp12MaxDiff=1, uniquenessRatio=12, speckleWindowSize=80, speckleRange=2,
                  mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    left = cv2.StereoSGBM_create(minDisparity=0, numDisparities=num_disp, **common)
    dl = left.compute(r1, r2).astype(np.float32) / 16.0
    # right disparity via horizontal flip trick
    right = cv2.StereoSGBM_create(minDisparity=0, numDisparities=num_disp, **common)
    dr = right.compute(cv2.flip(r2, 1), cv2.flip(r1, 1)).astype(np.float32) / 16.0
    dr = cv2.flip(dr, 1)
    h, w = dl.shape
    xs = np.arange(w)[None, :].repeat(h, 0)
    xr = np.clip(np.round(xs - dl).astype(int), 0, w - 1)
    back = np.take_along_axis(dr, xr, axis=1)
    ok = (dl > 0.5) & (dr[np.arange(h)[:, None], xr] > 0.5) & (np.abs(dl - back) <= 1.0)
    return dl, ok


def run_pair(cam, a, b, img_a, img_b, depth_lo, depth_hi):
    K, dist, size = cam["K"], cam["dist"], (cam["w"], cam["h"])
    R = b["R"] @ a["R"].T
    T = (b["t"] - R @ a["t"]).reshape(3, 1)
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(K, dist, K, dist, size, R, T, alpha=0,
                                                flags=cv2.CALIB_ZERO_DISPARITY)
    # Only handle the horizontal-baseline case (robot drives along the row, camera looks sideways).
    if abs(P2[1, 3]) > abs(P2[0, 3]):
        return None
    m1 = cv2.initUndistortRectifyMap(K, dist, R1, P1, size, cv2.CV_32FC1)
    m2 = cv2.initUndistortRectifyMap(K, dist, R2, P2, size, cv2.CV_32FC1)
    r1 = cv2.remap(img_a, *m1, cv2.INTER_LINEAR)
    r2 = cv2.remap(img_b, *m2, cv2.INTER_LINEAR)
    swap = P2[0, 3] > 0  # second camera is to the left: swap roles
    if swap:
        r1, r2 = r2, r1
    fb = abs(P2[0, 3])  # f * baseline in rectified pixels
    max_disp = fb / depth_lo
    num_disp = int(min(256, max(32, np.ceil(max_disp / 16) * 16)))
    g1, g2 = cv2.cvtColor(r1, cv2.COLOR_BGR2GRAY), cv2.cvtColor(r2, cv2.COLOR_BGR2GRAY)
    disp, ok = lr_disparity(g1, g2, num_disp, 5)
    if swap:
        # geometry is expressed in the rectified frame of camera b
        Rrect, cam_ref, Qm = R2, b, Q.copy()
        Qm[3, 3] = -Qm[3, 3]
        Qm[3, 2] = -Qm[3, 2]
    else:
        Rrect, cam_ref, Qm = R1, a, Q
    depth = np.where(ok, fb / np.maximum(disp, 1e-3), 0)
    ok &= (depth > depth_lo) & (depth < depth_hi)
    v, u = np.nonzero(ok)
    if len(u) == 0:
        return None
    f, cx, cy = P1[0, 0], P1[0, 2], P1[1, 2]
    z = depth[v, u]
    x = (u - cx) * z / f
    y = (v - cy) * z / f
    p_rect = np.stack([x, y, z], 1)
    p_cam = p_rect @ Rrect  # Rrect^T applied to row vectors
    p_world = (p_cam - cam_ref["t"]) @ cam_ref["R"]
    colors = r1[v, u][:, ::-1]  # BGR -> RGB
    return p_world, colors, len(u) / ok.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--sparse", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--voxels", type=int, default=72, help="voxels along the longest axis")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    cam, images, sparse_pts = load_model(args.sparse)
    names = sorted(images)
    # per-camera depth range from the sparse points it can see (robust percentiles)
    def depth_range(im):
        d = (sparse_pts @ im["R"].T + im["t"])[:, 2]
        d = d[d > 0]
        return np.percentile(d, 2) * 0.6, np.percentile(d, 98) * 1.5

    pairs = [(names[i], names[i + s]) for s in (2, 3, 4) for i in range(len(names) - s)]
    all_pts, all_col, all_pair, stats = [], [], [], []
    cache = {}
    def img(n):
        if n not in cache:
            cache[n] = cv2.imread(str(args.images / n), cv2.IMREAD_COLOR)
        return cache[n]

    for k, (na, nb) in enumerate(pairs):
        if time.monotonic() - t0 > TIME_LIMIT_S:
            stats.append(dict(stopped="time limit"))
            break
        a, b = images[na], images[nb]
        lo, hi = depth_range(a)
        res = run_pair(cam, a, b, img(na), img(nb), lo, hi)
        if res is None:
            stats.append(dict(pair=[na, nb], kept=0))
            continue
        p, c, frac = res
        # subsample to keep memory bounded
        sel = np.random.default_rng(k).choice(len(p), size=min(len(p), 40000), replace=False)
        all_pts.append(p[sel]); all_col.append(c[sel]); all_pair.append(np.full(len(sel), k))
        stats.append(dict(pair=[na, nb], valid_fraction=round(float(frac), 4)))

    P = np.concatenate(all_pts); C = np.concatenate(all_col).astype(np.float32); K_ = np.concatenate(all_pair)

    # Frame: x = travel direction (PCA of camera centres), y = up (opposite mean camera image-down axis)
    centres = np.array([images[n]["C"] for n in names])
    travel = np.linalg.svd(centres - centres.mean(0))[2][0]
    down = np.mean([images[n]["R"][1] for n in names], 0)  # camera +y in world
    up = -down / np.linalg.norm(down)
    travel -= up * (travel @ up); travel /= np.linalg.norm(travel)
    side = np.cross(up, travel)
    look = np.mean([images[n]["R"][2] for n in names], 0)
    if side @ look < 0:
        side = -side
    B = np.stack([travel, up, side])  # rows: new axes
    origin = centres.mean(0)
    Pn = (P - origin) @ B.T
    Cn = (centres - origin) @ B.T

    # Keep the central 98% to drop far outliers, then voxelise
    lo_b = np.percentile(Pn, 1, 0); hi_b = np.percentile(Pn, 99, 0)
    inside = np.all((Pn >= lo_b) & (Pn <= hi_b), 1)
    Pn, C, K_ = Pn[inside], C[inside], K_[inside]
    vs = (hi_b - lo_b).max() / args.voxels
    idx = np.floor((Pn - lo_b) / vs).astype(int)
    keys = idx[:, 0] * 1_000_000 + idx[:, 1] * 1_000 + idx[:, 2]
    order = np.argsort(keys)
    keys, idx, C, K_ = keys[order], idx[order], C[order], K_[order]
    uniq, start, counts = np.unique(keys, return_index=True, return_counts=True)
    vox = []
    for s, n in zip(start, counts):
        pairs_here = len(np.unique(K_[s:s + n]))
        if pairs_here < MIN_PAIRS:
            continue
        col = np.median(C[s:s + n], 0)
        i, j, kk = idx[s]
        vox.append([int(i), int(j), int(kk), int(pairs_here), int(n), *[int(x) for x in col]])

    vox = np.array(vox)
    summary = dict(
        method="two-view SGBM on COLMAP-rectified pairs, left-right check, voxel fusion",
        pairs_tried=len(pairs), pairs_with_geometry=int(len(np.unique(np.concatenate(all_pair)))),
        fused_points=int(len(Pn)), voxel_size_model_units=float(vs), voxels_kept=int(len(vox)),
        min_pairs_per_voxel=MIN_PAIRS, runtime_s=round(time.monotonic() - t0, 1),
        scale="arbitrary (no metric reference)", axes="x = travel, y = up (from camera orientation), z = away from camera",
    )
    out = dict(summary=summary, origin=lo_b.tolist(), voxel_size=float(vs),
               grid=[int(x) for x in idx.max(0) + 1],
               cameras=[dict(name=n, position=c.tolist()) for n, c in zip(names, Cn)],
               voxels=vox.tolist(), pair_stats=stats)
    (args.out / "dense_voxels.json").write_text(json.dumps(out))
    np.save(args.out / "fused_points.npy", np.concatenate([Pn, C], 1).astype(np.float32))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
