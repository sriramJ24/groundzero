"""Export the dense-trial voxels, cameras, photos and row sections for the dashboard's Row Scan view.

Writes frontend/public/scan/scan.json and frontend/public/scan/photos/*.jpg.
Photos are the original decoded CropDriveSD PNGs re-encoded as JPEG (quality 85) for the browser;
no other change is made to the pixels.

Usage:
  python export_scan.py --dense DIR --images DIR --scene scene.json --out frontend/public/scan
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

N_SECTIONS = 4  # aligned photos are split into this many sections along the direction of travel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dense", type=Path, required=True)
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--scene", type=Path, required=True, help="scene.json from the reconstruction experiment (frame times)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    d = json.loads((args.dense / "dense_voxels.json").read_text())
    scene = json.loads(args.scene.read_text())
    frames = {f["name"]: f for f in scene["frames"]}
    cams = {c["name"]: np.array(c["position"]) for c in d["cameras"]}
    origin, vs = np.array(d["origin"]), d["voxel_size"]
    vox = np.array(d["voxels"], dtype=float)
    centers = origin + (vox[:, :3] + 0.5) * vs

    # Estimated ground: low percentile of reconstructed height (camera orientation gives "up"; not measured gravity)
    ground_y = float(np.percentile(centers[:, 1], 2))

    all_names = sorted(frames)  # file names sort in capture order
    aligned = [n for n in all_names if n in cams]
    unaligned = [n for n in all_names if n not in cams]
    # direction of travel along x (+1 or -1); sections are ordered in capture order
    sign = 1.0 if cams[aligned[-1]][0] >= cams[aligned[0]][0] else -1.0

    chunks = np.array_split(np.array(aligned), N_SECTIONS)
    sections = []
    for i, ch in enumerate(chunks):
        xs = [cams[n][0] for n in ch]
        sections.append(dict(id=f"S{i + 1}", label=f"Section {i + 1}", lo=min(xs), hi=max(xs), photos=[str(n) for n in ch], reconstructed=True))
    # boundaries halfway between neighbouring sections; outer edges padded by half a typical gap
    pad = 0.5 * np.median(np.abs(np.diff([cams[n][0] for n in aligned])))
    for i, s in enumerate(sections):
        prev_edge = sections[i - 1] if i > 0 else None
        nxt = sections[i + 1] if i < N_SECTIONS - 1 else None
        if sign > 0:
            s["x0"] = (prev_edge["hi"] + s["lo"]) / 2 if prev_edge else s["lo"] - pad
            s["x1"] = (s["hi"] + nxt["lo"]) / 2 if nxt else s["hi"] + pad
        else:
            s["x1"] = (prev_edge["lo"] + s["hi"]) / 2 if prev_edge else s["hi"] + pad
            s["x0"] = (s["lo"] + nxt["hi"]) / 2 if nxt else s["lo"] - pad
    for s in sections:
        s["x0"], s["x1"] = float(s.pop("x0")), float(s.pop("x1"))
        del s["lo"], s["hi"]
    # Photos that could not be aligned: real coverage, but no 3D position. Shown just past the last
    # aligned section in the direction of travel, with an assumed width equal to the mean section width.
    w = float(np.mean([s["x1"] - s["x0"] for s in sections]))
    last = sections[-1]
    x0, x1 = (last["x1"], last["x1"] + w) if sign > 0 else (last["x0"] - w, last["x0"])
    sections.append(dict(id=f"S{N_SECTIONS + 1}", label=f"Section {N_SECTIONS + 1}", x0=x0, x1=x1,
                         photos=unaligned, reconstructed=False, position_assumed=True))

    # Keep voxels within the travelled stretch (plus a small margin) so the view shows the photographed row
    margin = 0.25 * w
    xmin = min(s["x0"] for s in sections[:N_SECTIONS]) - margin
    xmax = max(s["x1"] for s in sections[:N_SECTIONS]) + margin
    keep = (centers[:, 0] >= xmin) & (centers[:, 0] <= xmax)
    out_vox = []
    for (x, y, z), v in zip(centers[keep], vox[keep]):
        sec = next((s["id"] for s in sections[:N_SECTIONS] if s["x0"] <= x < s["x1"]), None)
        out_vox.append([round(float(x), 3), round(float(y), 3), round(float(z), 3), int(v[3]), int(v[5]), int(v[6]), int(v[7]), sec])

    def ts(name):
        return datetime.fromtimestamp(frames[name]["t_ns"] / 1e9, tz=timezone.utc).isoformat(timespec="milliseconds")

    for s in sections:
        s["voxels"] = sum(1 for v in out_vox if v[7] == s["id"])
        s["start"], s["end"] = ts(s["photos"][0]), ts(s["photos"][-1])

    photos_dir = args.out / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    photos = []
    for n in all_names:
        img = cv2.imread(str(args.images / n))
        jpg = n.replace(".png", ".jpg")
        cv2.imwrite(str(photos_dir / jpg), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        photos.append(dict(name=n, src=f"photos/{jpg}", frame=frames[n]["frame"], time=ts(n), sha256=frames[n]["sha256"],
                           aligned=n in cams, position=[round(float(c), 3) for c in cams[n]] if n in cams else None))

    out = dict(
        title="Corn row scan",
        source=dict(dataset="CropDriveSD", authors="Sainath Reddy Gummi and Kundana Reddy Gummi (2026)",
                    license="CC BY 4.0", url="https://huggingface.co/datasets/Sainath001/CropDriveSD",
                    revision=scene.get("revision"), run=scene.get("run"), camera="side RGB, about 28 cm above ground",
                    changes="Frames decoded from the released H.264 video; re-encoded as JPEG for the browser."),
        method=d["summary"], voxel_size=vs, ground_y=ground_y,
        travel_sign=sign, photos=photos, sections=sections, voxels=out_vox,
    )
    (args.out / "scan.json").write_text(json.dumps(out, separators=(",", ":")))
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in out.items() if k in ("photos", "sections", "voxels")}),
          [(s["id"], len(s["photos"]), s["voxels"]) for s in sections])


if __name__ == "__main__":
    main()
