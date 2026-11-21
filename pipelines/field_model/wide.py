"""Whole surveyed field for the viewer's zoomed-out level of detail (Day040 only).

Same method as season.py (median of per-photo highest points per cell, texture from the most central
photo where the depth map confirms visibility), over the full ~57 x 67 m nadir-covered area, at 10 cm
surface cells and 4 cm texture pixels. Photos: 34 nadir photos chosen greedily to cover the area.

Usage: python wide.py --scene DIR --select sel.json --out viewer/field3d
"""
import argparse, json
from pathlib import Path
import cv2
import numpy as np
from season import build_date, b64u16

ap = argparse.ArgumentParser()
ap.add_argument("--scene", type=Path, required=True)
ap.add_argument("--select", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
sel = json.loads(a.select.read_text())
X0, X1, Y0, Y1 = sel["bounds"]
dsm, tex, names, hf, uc = build_date(a.scene, (X0, X1, Y0, Y1), 0.10, 0.04, set(sel["all"]))
out = a.out / "wide"; out.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(out / "wide_texture.jpg"), tex, [cv2.IMWRITE_JPEG_QUALITY, 82])
ny, nx = dsm.shape
(out / "wide_heights.json").write_text(json.dumps(dict(nx=nx, ny=ny, row0="south", offset_m=-20.0, scale_m=0.001,
    uint16_le_base64=b64u16(dsm, -20.0, 0.001))))
(out / "wide.json").write_text(json.dumps(dict(scene="2025/Day040_Corn", x0=X0, x1=X1, y0=Y0, y1=Y1, cell_m=0.10, texture_cell_m=0.04,
    photos=names, holes_filled=round(hf, 4), texture_uncovered=round(uc, 4)), indent=1))
print(len(names), dsm.shape, tex.shape, hf, uc)
