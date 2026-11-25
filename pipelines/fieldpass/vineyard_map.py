"""Vineyard canopy-wall maps and flags from a tractor pass's fused points.

A vine row is a wall of leaves, so instead of a top-down map each photographed row face gets an
elevation map: along the row (y) by height (z), with colour, greenness and how solid the canopy is
(the share of the canopy zone where leaves were measured on this face). Flags are 0.5 m stretches of a
row face that look different from the rest of the pass:
  - "thin or missing canopy": canopy fill far below the pass median (below min(median - 4 SD, 0.6 x median)),
    or more than 2.5 robust SD below it along at least 1.5 m of the same face
  - "paler than the rest": greenness more than 3 robust SD below the pass median, or more than 2 SD below
    it along at least 1.5 m of the same face
Flags are places to look, not diagnoses. With --truth (simulated passes only) they're scored against
the planted problems.

  python vineyard_map.py --points work/vineyard --rows-from out/vineyard/truth.json --out work/vineyard --truth out/vineyard/truth.json
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage

ap = argparse.ArgumentParser()
ap.add_argument("--points", type=Path, required=True)
ap.add_argument("--rows-from", type=Path, required=True, help="JSON with row_x_m and canopy_m (the block layout)")
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--truth", type=Path)
ap.add_argument("--cell", type=float, default=0.05)
ap.add_argument("--block", type=float, default=0.5)
ap.add_argument("--band", type=float, default=0.4, help="keep points within this distance of the row line (m)")
a = ap.parse_args()

layout = json.loads(a.rows_from.read_text())
ROWS = np.array(layout["row_x_m"])
z0, z1 = layout["canopy_m"]
d = np.load(a.points / "points.npz")
info = json.loads((a.points / "points.json").read_text())
xyz, rgb, ph = d["xyz"], d["rgb"].astype(np.float32), d["photo"]

ri = np.abs(xyz[:, 0][:, None] - ROWS[None, :]).argmin(1)
off = xyz[:, 0] - ROWS[ri]
cam_x = np.array([c[0] for c in info["camera_positions"]])
gap = float(layout.get("row_gap_m", np.min(np.diff(np.sort(ROWS))) if len(ROWS) > 1 else 2.5))
# only the row next to the camera's alley: rows further away are glimpsed through gaps in the near row,
# which would make their faces look thin when they were simply not photographed
near = np.abs(cam_x[ph] - ROWS[ri]) < 0.75 * gap
keep = near & (np.abs(off) < a.band) & (xyz[:, 2] > z0 - 0.15) & (xyz[:, 2] < z1 + 0.15)
xyz, rgb, ph, ri, off = xyz[keep], rgb[keep], ph[keep], ri[keep], off[keep]
side = np.where(cam_x[ph] < ROWS[ri], "W", "E")   # the face is the side the photo was taken from

y_lo = float(np.floor(xyz[:, 1].min())) if len(xyz) else -11
y_hi = float(np.ceil(xyz[:, 1].max())) if len(xyz) else 11
ny = int(round((y_hi - y_lo) / a.cell)); nz = int(round((z1 - z0) / a.cell))
k = int(round(a.block / a.cell))
a.out.mkdir(parents=True, exist_ok=True)
faces, stats = [], []
for r in range(len(ROWS)):
    for s in ("W", "E"):
        m = (ri == r) & (side == s)
        if m.sum() < 500:
            continue
        iy = np.clip(((xyz[m, 1] - y_lo) / a.cell).astype(int), 0, ny - 1)
        iz = np.clip(((xyz[m, 2] - z0) / a.cell).astype(int), 0, nz - 1)
        cnt = np.zeros((nz, ny)); np.add.at(cnt, (iz, iy), 1)
        col = np.zeros((nz, ny, 3)); np.add.at(col, (iz, iy), rgb[m])
        best = np.full((nz, ny), -1)
        best[iz, iy] = ph[m]                   # any photo that saw the cell; refined per block below
        col = col / np.maximum(cnt, 1)[..., None]
        filled = cnt > 0
        # where along the row this face was photographed at all (the camera path covers part of the row)
        seen_cols = filled.any(0)
        ssum = col.sum(2) + 1e-6
        exg = np.where(filled, (2 * col[..., 1] - col[..., 0] - col[..., 2]) / ssum, np.nan)
        img = np.flipud(col).clip(0, 255).astype(np.uint8)
        cv2.imwrite(str(a.out / f"row{r:02d}_{s}.png"), img[..., ::-1])
        nb = ny // k
        for b in range(nb):
            sl = slice(b * k, (b + 1) * k)
            if seen_cols[sl].mean() < 0.6:
                continue
            with np.errstate(all="ignore"):
                stats.append(dict(row=r, side=s, b=b, y=y_lo + (b + 0.5) * a.block, fill=float(filled[:, sl].mean()),
                                  green=float(np.nanmean(exg[:, sl])), photos=best[:, sl][best[:, sl] >= 0].tolist()))
        faces.append(dict(row=r, side=s, image=f"row{r:02d}_{s}.png", y_range=[y_lo, y_hi], z_range=[z0, z1],
                          cell_m=a.cell, fill=float(filled[:, seen_cols].mean()) if seen_cols.any() else None))


def robust(v):
    v = np.asarray([x for x in v if np.isfinite(x)])
    med = float(np.median(v))
    return med, float(1.4826 * np.median(np.abs(v - med)))


f_med, f_sd = robust([s["fill"] for s in stats])
g_med, g_sd = robust([s["green"] for s in stats])

def sustained(soft, n=3):
    """Blocks that sit in a run of at least n neighbouring blocks on one face that all pass the softer test."""
    by_face = {}
    for s in stats:
        by_face.setdefault((s["row"], s["side"]), {})[s["b"]] = s
    out = set()
    for d in by_face.values():
        run = []
        for b in sorted(d) + [None]:
            if b is not None and soft(d[b]) and (not run or b == run[-1] + 1):
                run.append(b); continue
            if len(run) >= n:
                out |= {id(d[q]) for q in run}
            run = [b] if b is not None and soft(d[b]) else []
    return out


# a block is flagged if it is far off on its own, or mildly off over at least 1.5 m of the same face
thin_strong = lambda s: s["fill"] < min(f_med - 4 * f_sd, 0.6 * f_med)
pale_strong = lambda s: np.isfinite(s["green"]) and s["green"] < g_med - 3 * g_sd
thin_run = sustained(lambda s: s["fill"] < f_med - 2.5 * f_sd)
pale_run = sustained(lambda s: np.isfinite(s["green"]) and s["green"] < g_med - 2 * g_sd)
flags = []
for kind, test in (("thin or missing canopy", lambda s: thin_strong(s) or id(s) in thin_run),
                   ("paler than the rest", lambda s: pale_strong(s) or id(s) in pale_run)):
    hit = [s for s in stats if test(s)]
    hit.sort(key=lambda s: (s["row"], s["side"], s["b"]))
    run = []
    for s in hit + [None]:                     # merge neighbouring blocks on the same face
        if run and (s is None or s["row"] != run[-1]["row"] or s["side"] != run[-1]["side"] or s["b"] != run[-1]["b"] + 1):
            ys = [q["y"] for q in run]
            ph_all = [p for q in run for p in q["photos"]]
            ev = [info["photos"][int(p)] for p, _ in sorted(zip(*np.unique(ph_all, return_counts=True)), key=lambda t: -t[1])[:3]] if ph_all else []
            f = dict(kind=kind, row=run[0]["row"], face=run[0]["side"], x=round(float(ROWS[run[0]["row"]]), 2),
                     y=round(float(np.mean(ys)), 2), y_range=[round(min(ys) - a.block / 2, 2), round(max(ys) + a.block / 2, 2)],
                     length_m=round(len(run) * a.block, 2), photos=ev)
            if kind.startswith("thin"):
                f["canopy_fill"] = round(float(np.mean([q["fill"] for q in run])), 2); f["pass_median"] = round(f_med, 2)
            else:
                f["greenness"] = round(float(np.mean([q["green"] for q in run])), 3); f["pass_median"] = round(g_med, 3)
            flags.append(f)
            run = []
        if s is not None:
            run.append(s)
flags.sort(key=lambda f: -f["length_m"])
for i, f in enumerate(flags):
    f["id"] = f"F{i + 1}"

out = dict(note="Stretches of row that look different from the rest of this pass. Not a diagnosis; vine health is not assessed.",
           block_m=a.block, measured_blocks=len(stats),
           pass_stats=dict(canopy_fill_median=round(f_med, 3), canopy_fill_robust_sd=round(f_sd, 3),
                           greenness_median=round(g_med, 4), greenness_robust_sd=round(g_sd, 4)),
           pose_source=info["pose_source"], faces=faces, flags=flags)
if a.truth:
    T = json.loads(a.truth.read_text())
    res, matched = [], set()
    for p in T["problems"]:
        lo, hi = min(p["y"]) - 0.75, max(p["y"]) + 0.75
        hits = [f["id"] for f in flags if f["row"] == p["row"] and not (f["y_range"][1] < lo - 0.25 or f["y_range"][0] > hi + 0.25)]
        matched |= set(hits)
        res.append(dict(id=p["id"], kind=p["kind"], row=p["row"], found=bool(hits), by=hits))
    out["score_on_simulated_data"] = dict(
        note="Scored against the problems planted in the simulated vineyard. Says nothing about real vineyards.",
        planted=len(res), found=sum(r["found"] for r in res), problems=res, flags=len(flags),
        flags_not_near_a_planted_problem=len([f for f in flags if f["id"] not in matched]))
(a.out / "flags.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k not in ("flags", "faces")}, indent=1))
for f in flags[:10]:
    print(f["id"], f["kind"], "row", f["row"], f["face"], f["y_range"], f.get("canopy_fill", f.get("greenness")))
