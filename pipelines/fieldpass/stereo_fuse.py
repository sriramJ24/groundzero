"""3D from one pass: stereo depth between neighbouring photos of the same camera, fused into world points.

For each camera (device) the photos are taken in order along a path, so photo i and photo i+k see the
same ground from slightly different places. We rectify each pair from the camera poses, compute dense
disparity (OpenCV semi-global matching), turn it into 3D points, keep points that a second pair confirms,
and write them with their colours, plus which photos saw each point (so every flag can link back to its
original photos).

Camera poses: real Pi passes will need poses from the photos themselves (structure from motion) or from
pivot angle + GPS. For the demo's simulated passes we use the exact pose stored in each JSON's
"simulation" block, and the output says so.

  python stereo_fuse.py --pass-dir out/corn --out work/corn --pair-step 2 --num-disp 256
  python stereo_fuse.py --pass-dir out/vineyard --out work/vineyard --pair-step 1 --min-disp 48 --num-disp 384
"""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--pass-dir", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--pair-step", type=int, default=2, help="pair photo i with photo i+k of the same camera")
ap.add_argument("--min-disp", type=int, default=0)
ap.add_argument("--num-disp", type=int, default=256, help="multiple of 16, at the working width")
ap.add_argument("--work-width", type=int, default=1152, help="photos are resized to this width for matching")
ap.add_argument("--max-range", type=float, default=16.0, help="drop points farther than this from the camera (m)")
ap.add_argument("--stride", type=int, default=2, help="keep every Nth pixel's point")
a = ap.parse_args()


def euler_xyz(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx                      # Blender XYZ euler: X applied first


BL2CV = np.diag([1.0, -1.0, -1.0])           # Blender camera looks down -Z with Y up; OpenCV looks down +Z with Y down


def load_pass(d):
    cams = {}
    for jp in sorted((d / "photos").glob("*/*.json")):
        img = jp.with_suffix(".jpg")
        if not img.is_file():
            continue
        m = json.loads(jp.read_text())
        sim = m.get("simulation")
        if not sim:
            raise SystemExit(f"{jp}: no pose. Real passes need structure from motion first (not built yet).")
        R = euler_xyz(*sim["rotation_euler_xyz_rad"]) @ BL2CV   # camera (OpenCV axes) -> world
        C = np.array(sim["position_m"], float)
        seq = int(m["capture_id"].split("_")[1])
        cams.setdefault(m["device_id"], []).append(dict(seq=seq, img=img, R=R, C=C, meta=m, sim=sim,
                                                         key=f'{m["device_id"]}/{m["capture_id"]}'))
    for v in cams.values():
        v.sort(key=lambda p: p["seq"])
    return cams


def intrinsics(meta, sim, width):
    W0, H0 = meta["camera"]["resolution"]
    s = width / W0
    W, H = width, int(round(H0 * s))
    fx = sim["lens_mm"] / sim["sensor_width_mm"] * W
    return np.array([[fx, 0, W / 2], [0, fx, H / 2], [0, 0, 1]]), (W, H)


def pair_points(A, B, K, size):
    # X_b = R X_a + T
    R = B["R"].T @ A["R"]
    T = B["R"].T @ (A["C"] - B["C"])
    if T[0] > 0:                             # make A the left camera (OpenCV expects T_x < 0)
        A, B = B, A
        R = B["R"].T @ A["R"]
        T = B["R"].T @ (A["C"] - B["C"])
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(K, np.zeros(5), K, np.zeros(5), size, R, T.reshape(3, 1), alpha=0, flags=cv2.CALIB_ZERO_DISPARITY)
    m1 = cv2.initUndistortRectifyMap(K, None, R1, P1, size, cv2.CV_32FC1)
    m2 = cv2.initUndistortRectifyMap(K, None, R2, P2, size, cv2.CV_32FC1)
    ia = cv2.resize(cv2.imread(str(A["img"])), size, interpolation=cv2.INTER_AREA)
    ib = cv2.resize(cv2.imread(str(B["img"])), size, interpolation=cv2.INTER_AREA)
    ra = cv2.remap(ia, *m1, cv2.INTER_LINEAR)
    rb = cv2.remap(ib, *m2, cv2.INTER_LINEAR)
    sg = cv2.StereoSGBM_create(minDisparity=a.min_disp, numDisparities=a.num_disp, blockSize=5,
                               P1=8 * 3 * 25, P2=32 * 3 * 25, disp12MaxDiff=1, uniquenessRatio=10,
                               speckleWindowSize=100, speckleRange=2, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    ga, gb = cv2.cvtColor(ra, cv2.COLOR_BGR2GRAY), cv2.cvtColor(rb, cv2.COLOR_BGR2GRAY)
    disp = sg.compute(ga, gb).astype(np.float32) / 16
    # left-right check: match back from B to A and keep pixels that agree
    sgr = cv2.StereoSGBM_create(minDisparity=-(a.min_disp + a.num_disp), numDisparities=a.num_disp, blockSize=5,
                                P1=8 * 3 * 25, P2=32 * 3 * 25, uniquenessRatio=10, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    dr = -sgr.compute(gb, ga).astype(np.float32) / 16
    h, w = disp.shape
    xs = np.arange(w)[None, :] - np.clip(disp, 0, None)
    back = cv2.remap(dr, xs.astype(np.float32), np.repeat(np.arange(h, dtype=np.float32)[:, None], w, 1), cv2.INTER_NEAREST)
    ok = (disp > a.min_disp + 1) & (np.abs(back - disp) <= 1.5)
    ok[:, : a.min_disp + a.num_disp] = False          # left band has no match range
    pts = cv2.reprojectImageTo3D(disp, Q)            # in rectified camera-A frame
    sel = np.zeros_like(ok)
    sel[:: a.stride, :: a.stride] = True
    ok &= sel & np.isfinite(pts).all(2) & (pts[..., 2] > 0.3) & (np.linalg.norm(pts, axis=2) < a.max_range)
    P = pts[ok] @ R1                                 # rectified -> camera A (R1 rotates A into rectified)
    world = P @ A["R"].T + A["C"]
    col = ra[ok][:, ::-1]                            # BGR -> RGB
    return world.astype(np.float32), col, ok.mean()


cams = load_pass(a.pass_dir)
a.out.mkdir(parents=True, exist_ok=True)
allp, allc, allv, photos = [], [], [], []
t0 = time.time()
npairs = 0
for dev, seq in cams.items():
    K, size = intrinsics(seq[0]["meta"], seq[0]["sim"], a.work_width)
    for i in range(len(seq) - a.pair_step):
        A, B = seq[i], seq[i + a.pair_step]
        if abs(B["seq"] - A["seq"]) != a.pair_step:     # skip across gaps (partial renders)
            continue
        if np.linalg.norm(B["C"] - A["C"]) > 3:          # the tractor turned at the headland
            continue
        w, c, frac = pair_points(A, B, K, size)
        photos.append(A["key"])
        allp.append(w); allc.append(c); allv.append(np.full(len(w), len(photos) - 1, np.int32))
        npairs += 1
        print(f"{dev} pair {A['seq']}-{B['seq']}: {len(w)} points ({frac:.0%} of pixels matched)", flush=True)
P = np.concatenate(allp); Cc = np.concatenate(allc); V = np.concatenate(allv)
np.savez_compressed(a.out / "points.npz", xyz=P, rgb=Cc, photo=V)
info = dict(pass_dir=str(a.pass_dir), pairs=npairs, points=int(len(P)), photos=photos,
            pose_source="simulation (exact rendered poses)", pair_step=a.pair_step, work_width=a.work_width,
            seconds=round(time.time() - t0, 1))
(a.out / "points.json").write_text(json.dumps(info, indent=1))
print(json.dumps({k: v for k, v in info.items() if k != "photos"}))
