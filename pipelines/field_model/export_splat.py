"""Convert an OpenSplat Gaussian-splat PLY (trained on the Day040 photos, original coordinates kept) into
the compact .splat layout (32 bytes per Gaussian) for the web viewer, cropped to the measured section and
moved into the viewer's scene frame (X east, Y up from ground, Z south). Written as base64 JSON because the
artifact host serves only standard web types.

Usage: python export_splat.py --ply splat.ply --scene viewer/field3d/scene.json --out viewer/field3d/splat
"""
import argparse, base64, json
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--ply", type=Path, required=True)
ap.add_argument("--scene", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--max", type=int, default=600000)
a = ap.parse_args()

raw = a.ply.read_bytes()
end = raw.index(b"end_header\n") + len(b"end_header\n")
head = raw[:end].decode().splitlines()
n = int(next(l for l in head if l.startswith("element vertex")).split()[-1])
props = [l.split()[-1] for l in head if l.startswith("property")]
V = np.frombuffer(raw[end:end + n * 4 * len(props)], "<f4").reshape(n, len(props))
col = {p: V[:, i] for i, p in enumerate(props)}
xyz = np.stack([col["x"], col["y"], col["z"]], 1)

S = json.loads(a.scene.read_text()); G = S["grid"]
cx, cy, gz = (G["x0"] + G["x1"]) / 2, (G["y0"] + G["y1"]) / 2, S["ground_z"]
keep = (xyz[:, 0] > G["x0"] - 1) & (xyz[:, 0] < G["x1"] + 1) & (xyz[:, 1] > G["y0"] - 1) & (xyz[:, 1] < G["y1"] + 1) & (xyz[:, 2] > gz - 1.5) & (xyz[:, 2] < gz + 4)
scale = np.exp(np.stack([col["scale_0"], col["scale_1"], col["scale_2"]], 1))
opacity = 1 / (1 + np.exp(-col["opacity"]))
keep &= (opacity > 0.03) & (scale.max(1) < 1.0)
idx = np.nonzero(keep)[0]
order = np.argsort(-(scale[idx].prod(1) ** (1 / 3) * opacity[idx]))[: a.max]
idx = idx[order]

pos = np.stack([xyz[idx, 0] - cx, xyz[idx, 2] - gz, -(xyz[idx, 1] - cy)], 1).astype("<f4")
C0 = 0.28209479177387814
rgb = np.clip((0.5 + C0 * np.stack([col["f_dc_0"], col["f_dc_1"], col["f_dc_2"]], 1)[idx]) * 255, 0, 255)
rgba = np.concatenate([rgb, opacity[idx, None] * 255], 1).round().astype(np.uint8)
q = np.stack([col["rot_0"], col["rot_1"], col["rot_2"], col["rot_3"]], 1)[idx]  # w, x, y, z
q /= np.linalg.norm(q, axis=1, keepdims=True)
# world -> scene frame is a -90 degree rotation about X: r = (cos -45, sin -45, 0, 0); new = r * q
rw, rx = np.cos(-np.pi / 4), np.sin(-np.pi / 4)
w, x, y, z = q.T
nq = np.stack([rw * w - rx * x, rw * x + rx * w, rw * y - rx * z, rw * z + rx * y], 1)
rot = np.clip(nq * 128 + 128, 0, 255).round().astype(np.uint8)

buf = np.zeros(len(idx), dtype=[("p", "<f4", 3), ("s", "<f4", 3), ("c", "u1", 4), ("r", "u1", 4)])
buf["p"], buf["s"], buf["c"], buf["r"] = pos, scale[idx].astype("<f4"), rgba, rot
a.out.mkdir(parents=True, exist_ok=True)
comment = next((l for l in head if l.startswith("comment")), "")
(a.out / "section_splat.json").write_text(json.dumps(dict(format="splat", count=int(len(idx)), source=comment,
    frame="scene: x east, y up from ground_z, z south", splat_base64=base64.b64encode(buf.tobytes()).decode())))
print(n, "->", len(idx), "gaussians,", round(buf.nbytes / 1e6, 1), "MB")
