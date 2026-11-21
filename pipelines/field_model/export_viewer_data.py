"""Export plot evidence, measured ground data and a photo-greenness grid for the field viewer.

Writes into OUT: scene.json, plots/<id>.jpg (texture crops), photos/<id>.jpg (original nadir photo, downscaled).
Greenness is the excess-green index (2g - r - b on chromaticity) of the orthophoto pixels in 0.5 m cells.
It measures photo color only; it is not a health score.

Usage: python export_viewer_data.py --scene DIR --web DIR --measurements DIR --out DIR
"""
import argparse, csv, json
from pathlib import Path
import cv2
import numpy as np

CELL = 0.5
DAY = "Day040"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--web", type=Path, required=True)
    ap.add_argument("--measurements", type=Path, required=True, help="dir with ground_plots.csv and ground_measurements.csv")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    (a.out / "plots").mkdir(parents=True, exist_ok=True); (a.out / "photos").mkdir(exist_ok=True)
    meta = json.loads((a.web / "field.json").read_text())
    g, tx = meta["grid"], meta["texture"]
    tex = cv2.imread(str(a.web / "field_texture.jpg"))
    dsm = np.fromfile(a.web / "field.bin", np.float32).reshape(g["ny"], g["nx"])

    # greenness grid (row 0 = north, like the texture)
    f = tex.astype(np.float32) + 1
    s = f.sum(2); b, gg, r = f[..., 0] / s, f[..., 1] / s, f[..., 2] / s
    exg = 2 * gg - r - b
    k = int(CELL / tx["cell_m"])
    H, W = exg.shape[0] // k, exg.shape[1] // k
    grid = exg[:H * k, :W * k].reshape(H, k, W, k).mean((1, 3))
    p5, p50, p95 = np.percentile(grid, [5, 50, 95])
    low = grid < np.percentile(grid, 3)

    plots = {r["plot_id"]: r for r in csv.DictReader(open(a.measurements / "ground_plots.csv")) if r["group"] == "2025/Corn"}
    meas = [r for r in csv.DictReader(open(a.measurements / "ground_measurements.csv")) if r["group"] == "2025/Corn" and r["day"] == DAY]
    t = json.loads((a.scene / "transforms.json").read_text())
    frames = {Path(fr["file_path"]).stem: fr for fr in t["frames"]}
    out_plots = []
    for pid, p in sorted(plots.items()):
        x, y = float(p["x_m"]), float(p["y_m"])
        vals = {r["variable"]: float(r["value"]) for r in meas if r["plot_id"] == pid}
        # texture crop 3 m x 3 m
        cx = int((x - g["x0"]) / tx["cell_m"]); cy = int((g["y1"] - y) / tx["cell_m"]); h = 150
        crop = tex[max(cy - h, 0):cy + h, max(cx - h, 0):cx + h]
        cv2.imwrite(str(a.out / "plots" / f"{pid}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
        # greenness around plot (1.5 m radius)
        gi, gj = int((g["y1"] - y) / CELL), int((x - g["x0"]) / CELL)
        win = grid[max(gi - 3, 0):gi + 3, max(gj - 3, 0):gj + 3]
        # nearest nadir photo whose centre looks at the plot
        best, bn = 1e9, None
        for n in tx["nadir_photos"]:
            M = np.array(frames[n]["transform_matrix"]); d = np.hypot(M[0, 3] - x, M[1, 3] - y)
            if d < best: best, bn = d, n
        img = cv2.imread(str(a.scene / "images" / f"{bn}.JPG"))
        cv2.imwrite(str(a.out / "photos" / f"{bn}.jpg"), cv2.resize(img, (1320, 989), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 84])
        zi, zj = int((y - g["y0"]) / g["cell_m"]), int((x - g["x0"]) / g["cell_m"])
        top = float(np.median(dsm[max(zi - 12, 0):zi + 12, max(zj - 12, 0):zj + 12]))
        out_plots.append(dict(id=pid, x=x, y=y, canopy_height_cm=vals.get("canopy_height"), lai=vals.get("LAI"),
                              greenness=round(float(win.mean()), 4), canopy_top_z=round(top, 3),
                              crop=f"plots/{pid}.jpg", photo=f"photos/{bn}.jpg", photo_id=bn, photo_offset_m=round(best, 1)))
    hts = [p["canopy_height_cm"] for p in out_plots if p["canopy_height_cm"]]
    ground_z = float(np.median([p["canopy_top_z"] for p in out_plots]) - np.mean(hts) / 100)
    scene = dict(
        title="Corn field section", scene="UAV3DCrop 2025/Day040_Corn", day=DAY,
        source=dict(dataset="UAV3DCrop", url="https://huggingface.co/datasets/Link-Dev/UAV3DCrop",
                    authors="Zhou, Li, Qiu, Qiao, Jia, Yang, Zhang, Yin, You, Kumar, Mulla, Yang, Jin and Liu (2026)",
                    paper="https://arxiv.org/abs/2608.06404", license="CC BY 4.0",
                    camera="DJI Mavic 3M RGB, 12-18 m above ground, nadir and 45-degree oblique, RTK positioned"),
        grid=g, texture=dict(width=tx["width"], height=tx["height"], cell_m=tx["cell_m"]),
        ground_z=round(ground_z, 3), fusion=meta["fusion"], holes_filled_fraction=meta["holes_filled_fraction"],
        greenness=dict(cell_m=CELL, rows=H, cols=W, p5=round(float(p5), 4), p50=round(float(p50), 4), p95=round(float(p95), 4),
                       values=[round(float(v), 4) for v in grid.ravel()], low_cells=[int(i) for i in np.nonzero(low.ravel())[0]],
                       low_rule="lowest 3% of 0.5 m cells in this section"),
        plots=out_plots,
    )
    (a.out / "scene.json").write_text(json.dumps(scene, separators=(",", ":")))
    print(json.dumps([(p["id"], p["canopy_height_cm"], p["lai"], p["greenness"]) for p in out_plots]), round(ground_z, 2), len(scene["greenness"]["low_cells"]))

if __name__ == "__main__":
    main()
