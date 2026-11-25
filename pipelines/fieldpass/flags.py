"""Flags from a top-down field map: places that look different from the rest of the same pass, each with
the original photos that show it. Flags are places to look, not diagnoses; no health score is made up.

Kinds (all relative to the same pass, so lighting and growth stage cancel out):
  - "shorter than the rest": canopy top more than max(0.25 m, 3 robust SD) below the pass median
  - "soil showing": most of the block's visible surface is soil-coloured (gaps, missing plants)
  - "paler than the rest": greenness more than 3 robust SD below the pass median

With --truth (simulated passes only), also scores the flags against the planted problems and says so.

  python flags.py --map work/corn --out work/corn [--truth out/corn/truth.json]
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

ap = argparse.ArgumentParser()
ap.add_argument("--map", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--truth", type=Path)
ap.add_argument("--block", type=float, default=0.5, help="flag cell size (m)")
ap.add_argument("--min-area", type=float, default=0.5, help="smallest flag (m2)")
ap.add_argument("--min-coverage", type=float, default=0.25, help="ignore blocks with less of their area measured")
a = ap.parse_args()

M = np.load(a.map / "field_map.npz")
meta = json.loads((a.map / "field_map.json").read_text())
H, RGB, G, best = M["height"], M["rgb"].astype(np.float32), M["greenness"], M["best_photo"]
cell = meta["cell_m"]
x0, x1, y0, y1 = meta["extent"]
k = int(round(a.block / cell))
ny, nx = H.shape[0] // k, H.shape[1] // k


def blocks(arr):
    return arr[: ny * k, : nx * k].reshape(ny, k, nx, k).transpose(0, 2, 1, 3).reshape(ny, nx, k * k)


Hb, Gb = blocks(H), blocks(G)
measured = np.isfinite(Hb)
cov = measured.mean(2)
valid = cov >= a.min_coverage
with np.errstate(all="ignore"):
    top = np.nanpercentile(Hb, 90, axis=2)          # canopy top within the block
    green = np.nanmean(Gb, axis=2)
    # soil: a measured cell whose colour isn't green (excess green below 0.05) and that sits low
    soil = np.nanmean(np.where(measured, ((Gb < 0.05) & (Hb < 0.5)).astype(float), np.nan), axis=2)
top[~valid] = np.nan; green[~valid] = np.nan; soil[~valid] = np.nan


def robust(v):
    v = v[np.isfinite(v)]
    med = float(np.median(v))
    return med, float(1.4826 * np.median(np.abs(v - med)))


h_med, h_sd = robust(top)
g_med, g_sd = robust(green)
s_med, _ = robust(soil)
rules = {
    "shorter than the rest": top < h_med - max(0.25, 3 * h_sd),
    "soil showing": soil > max(0.5, s_med + 0.3),
    "paler than the rest": green < g_med - 3 * g_sd,
}
flags = []
min_blocks = max(1, int(np.ceil(a.min_area / a.block ** 2 - 1e-9)))
for kind, mask in rules.items():
    mask = np.nan_to_num(mask).astype(bool) & valid
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    for i in range(1, n + 1):
        jj, ii = np.nonzero(lab == i)
        if len(jj) < min_blocks:
            continue
        # evidence: the photos that saw this patch best, most cells first
        sub = np.zeros_like(lab, bool); sub[jj, ii] = True
        fine = np.kron(sub, np.ones((k, k), bool))
        bp = best[: ny * k, : nx * k][fine]
        bp = bp[bp >= 0]
        ev = [meta["photos"][int(p)] for p, _ in sorted(zip(*np.unique(bp, return_counts=True)), key=lambda t: -t[1])[:3]] if len(bp) else []
        cx = x0 + (ii.mean() + 0.5) * a.block
        cy = y0 + (jj.mean() + 0.5) * a.block
        f = dict(kind=kind, x=round(float(cx), 2), y=round(float(cy), 2), area_m2=round(len(jj) * a.block ** 2, 2),
                 bbox=[round(x0 + ii.min() * a.block, 2), round(x0 + (ii.max() + 1) * a.block, 2),
                       round(y0 + jj.min() * a.block, 2), round(y0 + (jj.max() + 1) * a.block, 2)],
                 photos=ev)
        if kind == "shorter than the rest":
            f["canopy_top_m"] = round(float(np.nanmedian(top[jj, ii])), 2); f["pass_median_m"] = round(h_med, 2)
        elif kind == "paler than the rest":
            f["greenness"] = round(float(np.nanmean(green[jj, ii])), 3); f["pass_median"] = round(g_med, 3)
        else:
            f["soil_fraction"] = round(float(np.nanmean(soil[jj, ii])), 2); f["pass_median"] = round(s_med, 2)
        flags.append(f)
flags.sort(key=lambda f: -f["area_m2"])
for i, f in enumerate(flags):
    f["id"] = f"F{i + 1}"

out = dict(note="Places that look different from the rest of this pass. Not a diagnosis; crop health is not assessed.",
           block_m=a.block, measured_blocks=int(valid.sum()), total_blocks=int(valid.size),
           pass_stats=dict(canopy_top_median_m=round(h_med, 3), canopy_top_robust_sd_m=round(h_sd, 3),
                           greenness_median=round(g_med, 4), greenness_robust_sd=round(g_sd, 4)),
           pose_source=meta["pose_source"], flags=flags)

if a.truth:
    T = json.loads(a.truth.read_text())
    probs = T["problems"]

    def region(p):
        if "r" in p:
            return [p["x"] - p["r"], p["x"] + p["r"], p["y"] - p["r"], p["y"] + p["r"]]
        if "length" in p:
            return [p["x"] - p["length"] / 2, p["x"] + p["length"] / 2, p["y"] - 1.2, p["y"] + 1.2]
        ys = p["y"]
        return [p["x"] - 0.6, p["x"] + 0.6, min(ys) - 0.75, max(ys) + 0.75]

    def overlaps(b, r, pad=0.5):
        return not (b[1] < r[0] - pad or b[0] > r[1] + pad or b[3] < r[2] - pad or b[2] > r[3] + pad)

    found, matched = [], set()
    for p in probs:
        r = region(p)
        hits = [f["id"] for f in flags if overlaps(f["bbox"], r)]
        matched |= set(hits)
        inside = (x0 <= p["x"] <= x1) and (y0 <= (p["y"] if not isinstance(p["y"], list) else p["y"][0]) <= y1)
        found.append(dict(id=p["id"], kind=p["kind"], found=bool(hits), by=hits, in_mapped_area=inside))
    out["score_on_simulated_data"] = dict(
        note="Scored against the problems planted in the simulated field. Says nothing about real fields.",
        planted=len(probs), found=sum(f["found"] for f in found), problems=found,
        flags=len(flags), flags_not_near_a_planted_problem=len([f for f in flags if f["id"] not in matched]))

a.out.mkdir(parents=True, exist_ok=True)
(a.out / "flags.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "flags"}, indent=1))
for f in flags[:10]:
    print(f["id"], f["kind"], f["x"], f["y"], f["area_m2"], "m2")
