"""Season timeline for the field viewer: one surface + photo texture per survey date, a crop-height map
(surface minus the bare-soil surface of Day007), and a check of that height against hand measurements.

For each date, only straight-down photos are used (6 per date around the measured plots). Each photo's
Metashape depth map is back-projected; a 4 cm cell's surface height is the median, across photos, of the
highest point each photo puts in that cell. The texture (2 cm/pixel) takes every pixel from the photo where
it is closest to the image centre and the depth map confirms it is visible.

Crop height = surface(date) - ground, where ground = Day007 surface (crop just emerged), median-filtered.
Check: for each hand-measured plot and date, the 95th percentile of photo height within 1 m of the plot
centre (chosen before looking at the results) is compared with the tape-measured canopy height.

Usage: python season.py --season DIR --measurements DIR --out viewer/field3d
  DIR/D<day>/{transforms.json, images/*.JPG, depth/*_depth.tif}
"""
import argparse, base64, csv, json
from pathlib import Path
import cv2
import numpy as np
import tifffile

X0, X1, Y0, Y1 = -10.0, 13.0, -16.0, 9.0
CELL, TEX = 0.04, 0.02
NX, NY = int(round((X1 - X0) / CELL)), int(round((Y1 - Y0) / CELL))
TX, TY = int(round((X1 - X0) / TEX)), int(round((Y1 - Y0) / TEX))


def bilinear(img, u, v):
    u0 = np.floor(u).astype(int); v0 = np.floor(v).astype(int)
    fu = (u - u0)[:, None]; fv = (v - v0)[:, None]
    a = img[v0, u0].astype(np.float32); b = img[v0, u0 + 1].astype(np.float32)
    c = img[v0 + 1, u0].astype(np.float32); d = img[v0 + 1, u0 + 1].astype(np.float32)
    return np.clip((a * (1 - fu) + b * fu) * (1 - fv) + (c * (1 - fu) + d * fu) * fv + 0.5, 0, 255).astype(np.uint8)


def build_date(ddir, bounds=(X0, X1, Y0, Y1), cell=CELL, texcell=TEX, only=None):
    X0, X1, Y0, Y1 = bounds
    NX, NY = int(round((X1 - X0) / cell)), int(round((Y1 - Y0) / cell))
    TX, TY = int(round((X1 - X0) / texcell)), int(round((Y1 - Y0) / texcell))
    CELL, TEX = cell, texcell
    t = json.loads((ddir / "transforms.json").read_text())
    K = np.array([[t["fl_x"], 0, t["cx"]], [0, t["fl_y"], t["cy"]], [0, 0, 1]])
    dist = np.array([t["k1"], t["k2"], t["p1"], t["p2"], t["k3"]])
    W, H = int(t["w"]), int(t["h"])
    frames = {Path(f["file_path"]).stem: f for f in t["frames"]}
    names = sorted(p.stem.replace("_depth", "") for p in (ddir / "depth").glob("*_depth.tif"))
    names = [n for n in names if (only is None or n in only) and (ddir / "images" / f"{n}.JPG").exists() and np.array(frames[n]["transform_matrix"])[2, 2] > 0.95]
    # --- surface ---
    s = 4
    w, h = W // s, H // s
    Ks = K.copy(); Ks[:2] /= s
    mx, my = cv2.initUndistortRectifyMap(K, dist, None, Ks, (w, h), cv2.CV_32FC1)
    uu, vv = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    rays = np.stack([(uu - Ks[0, 2]) / Ks[0, 0], (vv - Ks[1, 2]) / Ks[1, 1], np.ones_like(uu)], -1).reshape(-1, 3)
    stack = []
    for n in names:
        dep = cv2.remap(tifffile.imread(ddir / "depth" / f"{n}_depth.tif").astype(np.float32), mx, my, cv2.INTER_NEAREST).reshape(-1)
        ok = dep > 0
        c2w = np.array(frames[n]["transform_matrix"]) @ np.diag([1, -1, -1, 1])
        P = (rays[ok] * dep[ok, None]) @ c2w[:3, :3].T + c2w[:3, 3]
        ix = ((P[:, 0] - X0) / CELL).astype(int); iy = ((P[:, 1] - Y0) / CELL).astype(int)
        m = (ix >= 0) & (ix < NX) & (iy >= 0) & (iy < NY)
        top = np.full((NY, NX), np.nan, np.float32)
        tmp = np.full((NY, NX), -np.inf, np.float32)
        np.maximum.at(tmp, (iy[m], ix[m]), P[m, 2].astype(np.float32))
        top[np.isfinite(tmp)] = tmp[np.isfinite(tmp)]
        stack.append(top)
    dsm = np.nanmedian(np.stack(stack), 0)
    holes = np.isnan(dsm)
    if holes.any():
        lo, hi = np.nanmin(dsm), np.nanmax(dsm)
        q = ((np.nan_to_num(dsm, nan=lo) - lo) / max(hi - lo, 1e-3) * 255).astype(np.uint8)
        f = cv2.inpaint(q, holes.astype(np.uint8), 3, cv2.INPAINT_TELEA)
        dsm = np.where(holes, lo + f.astype(np.float32) / 255 * (hi - lo), dsm)
    dsm = cv2.medianBlur(dsm.astype(np.float32), 3)
    # --- texture ---
    gx = X0 + (np.arange(TX) + 0.5) * TEX
    gy = Y1 - (np.arange(TY) + 0.5) * TEX
    MX, MY = np.meshgrid(((gx - X0) / CELL - 0.5).astype(np.float32), ((gy - Y0) / CELL - 0.5).astype(np.float32))
    Z = cv2.remap(dsm, MX, MY, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    GX, GY = np.meshgrid(gx, gy)
    world = np.stack([GX, GY, Z], -1).reshape(-1, 3)
    tex = np.zeros((TY * TX, 3), np.uint8); best = np.full(TY * TX, np.inf, np.float32)
    for n in names:
        w2c = np.linalg.inv(np.array(frames[n]["transform_matrix"]) @ np.diag([1, -1, -1, 1]))
        cam = world @ w2c[:3, :3].T + w2c[:3, 3]
        rvec, _ = cv2.Rodrigues(w2c[:3, :3])
        uv = cv2.projectPoints(world, rvec, w2c[:3, 3], K, dist)[0].reshape(-1, 2)
        ok = (cam[:, 2] > 0) & (uv[:, 0] >= 0) & (uv[:, 0] < W - 1) & (uv[:, 1] >= 0) & (uv[:, 1] < H - 1)
        depth = tifffile.imread(ddir / "depth" / f"{n}_depth.tif").astype(np.float32)
        idx = np.nonzero(ok)[0]
        dm = depth[uv[idx, 1].astype(int), uv[idx, 0].astype(int)]
        idx = idx[(dm > 0) & (np.abs(dm - cam[idx, 2]) < 0.2)]
        score = np.hypot(uv[idx, 0] - W / 2, uv[idx, 1] - H / 2).astype(np.float32)
        b = score < best[idx]; idx, score = idx[b], score[b]
        tex[idx] = bilinear(cv2.imread(str(ddir / "images" / f"{n}.JPG")), uv[idx, 0], uv[idx, 1]); best[idx] = score
    cov = np.isfinite(best).reshape(TY, TX); tex = tex.reshape(TY, TX, 3)
    if (~cov).any():
        tex = cv2.inpaint(tex, (~cov).astype(np.uint8), 5, cv2.INPAINT_TELEA)
    return dsm, tex, names, float(holes.mean()), float((~cov).mean())


def b64u16(a, offset, scale):
    q = np.clip(np.round((a - offset) / scale), 0, 65535).astype("<u2")
    return base64.b64encode(q.tobytes()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=Path, required=True)
    ap.add_argument("--measurements", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = a.out / "season"; out.mkdir(parents=True, exist_ok=True)
    days = sorted(p.name[1:] for p in a.season.glob("D*") if (p / "depth").exists())
    dsms, info = {}, {}
    for d in days:
        dsm, tex, names, hf, uc = build_date(a.season / f"D{d}")
        dsms[d] = dsm
        cv2.imwrite(str(out / f"tex_{d}.jpg"), tex, [cv2.IMWRITE_JPEG_QUALITY, 84])
        info[d] = dict(photos=names, holes_filled=round(hf, 4), texture_uncovered=round(uc, 4))
        print(d, names, round(hf, 3), round(uc, 3), flush=True)
    ground = cv2.medianBlur(dsms["007"].astype(np.float32), 5)
    ground = cv2.GaussianBlur(ground, (0, 0), 3)
    # measurements
    plots = {r["plot_id"]: (float(r["x_m"]), float(r["y_m"])) for r in csv.DictReader(open(a.measurements / "ground_plots.csv")) if r["group"] == "2025/Corn"}
    meas = [r for r in csv.DictReader(open(a.measurements / "ground_measurements.csv")) if r["group"] == "2025/Corn"]
    yy, xx = np.mgrid[0:NY, 0:NX]
    cxs, cys = X0 + (xx + 0.5) * CELL, Y0 + (yy + 0.5) * CELL
    pairs, per_date = [], {}
    for d in days:
        hgt = np.clip(dsms[d] - ground, 0, None)
        if d != "007":
            (out / f"h_{d}.json").write_text(json.dumps(dict(nx=NX, ny=NY, row0="south", offset_m=0.0, scale_m=0.001, uint16_le_base64=b64u16(hgt, 0.0, 0.001))))
        (out / f"s_{d}.json").write_text(json.dumps(dict(nx=NX, ny=NY, row0="south", offset_m=-20.0, scale_m=0.001, uint16_le_base64=b64u16(dsms[d], -20.0, 0.001))))
        rows = []
        for pid, (px, py) in plots.items():
            r = np.hypot(cxs - px, cys - py) < 1.0
            photo = float(np.percentile(hgt[r], 95)) * 100
            hand = [float(m["value"]) for m in meas if m["plot_id"] == pid and m["matched_scene"] == f"2025/Day{d}_Corn" and m["variable"] == "canopy_height"]
            lai = [float(m["value"]) for m in meas if m["plot_id"] == pid and m["matched_scene"] == f"2025/Day{d}_Corn" and m["variable"] == "LAI"]
            off = [int(m["day_offset_to_scene"]) for m in meas if m["plot_id"] == pid and m["matched_scene"] == f"2025/Day{d}_Corn" and m["variable"] == "canopy_height"]
            row = dict(plot=pid, photo_cm=round(photo, 1), hand_cm=hand[0] if hand else None, lai=lai[0] if lai else None, day_offset=off[0] if off else None)
            rows.append(row)
            if hand and d != "007":
                pairs.append((d, pid, photo, hand[0]))
        per_date[d] = dict(plots=rows, mean_photo_cm=round(float(np.mean(hgt)) * 100, 1), **info[d])
    P = np.array([p[2] for p in pairs]); Hh = np.array([p[3] for p in pairs])
    err = P - Hh
    r2 = 1 - ((Hh - P) ** 2).sum() / ((Hh - Hh.mean()) ** 2).sum()
    check = dict(n=len(pairs), mae_cm=round(float(np.abs(err).mean()), 1), bias_cm=round(float(err.mean()), 1),
                 rmse_cm=round(float(np.sqrt((err ** 2).mean())), 1), r2=round(float(r2), 3),
                 method="95th percentile of photo height within 1 m of plot centre vs. hand-measured canopy height (mean of 5 readings); ground = Day007 surface",
                 pairs=[dict(day=d, plot=p, photo_cm=round(ph, 1), hand_cm=hd) for d, p, ph, hd in pairs])
    (out / "season.json").write_text(json.dumps(dict(days=days, ground_day="007", grid=dict(nx=NX, ny=NY, cell_m=CELL, x0=X0, y0=Y0, x1=X1, y1=Y1),
                                                     texture_cell_m=TEX, dates=per_date, height_check=check), separators=(",", ":")))
    print(json.dumps({k: v for k, v in check.items() if k != "pairs"}))


if __name__ == "__main__":
    main()
