"""Turn a pass's fused points into a top-down field map: canopy height, colour and greenness per cell,
plus, for every cell, the photo that saw it best (the evidence a flag links to).

Heights here are canopy-top heights above the ground plane z = 0 of the pass's frame. On a real field
they'd be measured against a bare-ground survey (as the drone season viewer does with Day 7); in the
simulated passes the ground is known to be z = 0.

  python field_map.py --points work/corn --out work/corn --extent -15 15 -15 15 --cell 0.1
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--points", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--extent", type=float, nargs=4, default=[-15, 15, -15, 15], metavar=("X0", "X1", "Y0", "Y1"))
ap.add_argument("--cell", type=float, default=0.10)
ap.add_argument("--min-points", type=int, default=4)
ap.add_argument("--top", type=float, default=0.9, help="height = this quantile of the points in a cell")
a = ap.parse_args()

d = np.load(a.points / "points.npz")
info = json.loads((a.points / "points.json").read_text())
xyz, rgb, ph = d["xyz"], d["rgb"].astype(np.float32), d["photo"]
x0, x1, y0, y1 = a.extent
nx, ny = int(round((x1 - x0) / a.cell)), int(round((y1 - y0) / a.cell))
ix = np.floor((xyz[:, 0] - x0) / a.cell).astype(int)
iy = np.floor((xyz[:, 1] - y0) / a.cell).astype(int)
ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny) & (xyz[:, 2] > -0.5) & (xyz[:, 2] < 4)
ix, iy, z, rgb, ph = ix[ok], iy[ok], xyz[ok, 2], rgb[ok], ph[ok]
cell = iy * nx + ix

order = np.lexsort((z, cell))
cell, z, rgb, ph = cell[order], z[order], rgb[order], ph[order]
starts = np.r_[0, np.nonzero(np.diff(cell))[0] + 1]
counts = np.diff(np.r_[starts, len(cell)])
ids = cell[starts]
keep = counts >= a.min_points
starts, counts, ids = starts[keep], counts[keep], ids[keep]

height = np.full(nx * ny, np.nan, np.float32)
colour = np.zeros((nx * ny, 3), np.float32)
npts = np.zeros(nx * ny, np.int32)
best = np.full(nx * ny, -1, np.int32)
q = starts + np.floor((counts - 1) * a.top).astype(int)
height[ids] = z[q]
npts[ids] = counts
# colour: mean of the upper half of the points (the canopy the farmer sees from above)
for s, c, i in zip(starts, counts, ids):
    colour[i] = rgb[s + c // 2: s + c].mean(0)
    best[i] = np.bincount(ph[s: s + c]).argmax()

H = height.reshape(ny, nx)
RGB = colour.reshape(ny, nx, 3)
# excess-green greenness on chromatic coordinates, the same measure the drone viewer uses
s = RGB.sum(2) + 1e-6
exg = (2 * RGB[..., 1] - RGB[..., 0] - RGB[..., 2]) / s
exg[np.isnan(H)] = np.nan

a.out.mkdir(parents=True, exist_ok=True)
np.savez_compressed(a.out / "field_map.npz", height=H, rgb=RGB.astype(np.uint8), greenness=exg.astype(np.float32),
                    points=npts.reshape(ny, nx), best_photo=best.reshape(ny, nx))
img = np.flipud(RGB).clip(0, 255).astype(np.uint8)            # north up
cv2.imwrite(str(a.out / "ortho.png"), img[..., ::-1])
hv = np.flipud(H)
norm = np.clip((hv - np.nanpercentile(hv, 2)) / (np.nanpercentile(hv, 98) - np.nanpercentile(hv, 2) + 1e-6), 0, 1)
hc = cv2.applyColorMap((np.nan_to_num(norm) * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
hc[np.isnan(hv)] = 0
cv2.imwrite(str(a.out / "height.png"), hc)
covered = np.isfinite(H).mean()
meta = dict(extent=[x0, x1, y0, y1], cell_m=a.cell, nx=nx, ny=ny, covered_fraction=round(float(covered), 4),
            height_quantile=a.top, height_m=dict(p5=float(np.nanpercentile(H, 5)), p50=float(np.nanpercentile(H, 50)),
                                                  p95=float(np.nanpercentile(H, 95))),
            photos=info["photos"], pose_source=info["pose_source"], rows="south first; images are north up")
(a.out / "field_map.json").write_text(json.dumps(meta, indent=1))
print(json.dumps({k: v for k, v in meta.items() if k != "photos"}))
