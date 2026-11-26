"""Package one processed pass for the demo viewer (viewer/demo): the surface or row walls, the map texture,
the flags, and each flag's evidence photos with the flagged area boxed.

Pivot crops (corn, potato) read field_map.py + flags.py outputs; the vineyard reads vineyard_map.py output.
Everything written says where it came from; on simulated passes it also says it is simulated.

  python export_viewer.py --crop corn --pass-dir out/corn --work work/corn --hi work/corn_hi --out ../../viewer/demo/data/corn
  python export_viewer.py --crop vineyard --pass-dir out/vineyard --work work/vineyard --out ../../viewer/demo/data/vineyard
"""
import argparse
import base64
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage

ap = argparse.ArgumentParser()
ap.add_argument("--crop", required=True, choices=["corn", "potato", "vineyard"])
ap.add_argument("--pass-dir", type=Path, required=True, help="the pass's photos/ and truth.json")
ap.add_argument("--work", type=Path, required=True, help="output of field_map.py + flags.py, or vineyard_map.py")
ap.add_argument("--hi", type=Path, help="a finer field_map.py run used only for the map texture (pivot crops)")
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--grid", type=float, default=0.2, help="surface grid for the 3D view (m)")
ap.add_argument("--photo-width", type=int, default=960)
a = ap.parse_args()


def euler_xyz(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    return (np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
            @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]))


BL2CV = np.diag([1.0, -1.0, -1.0])


def evidence(key, corners, name):
    """Copy one photo, resized, with the flagged area boxed. Returns its file name, or None if the area is
    outside the photo."""
    meta = json.loads((a.pass_dir / "photos" / f"{key}.json").read_text())
    img = cv2.imread(str(a.pass_dir / "photos" / f"{key}.jpg"))
    if img is None:
        return None
    sim = meta["simulation"]
    R = euler_xyz(*sim["rotation_euler_xyz_rad"]) @ BL2CV
    C = np.array(sim["position_m"])
    H, W = img.shape[:2]
    f = sim["lens_mm"] / sim["sensor_width_mm"] * W
    pc = (np.asarray(corners) - C) @ R                 # world -> camera (OpenCV axes)
    pc = pc[pc[:, 2] > 0.2]
    if len(pc) < 2:
        return None
    u = f * pc[:, 0] / pc[:, 2] + W / 2
    v = f * pc[:, 1] / pc[:, 2] + H / 2
    x0, x1 = np.clip([u.min(), u.max()], 0, W - 1).astype(int)
    y0, y1 = np.clip([v.min(), v.max()], 0, H - 1).astype(int)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    s = a.photo_width / W
    img = cv2.resize(img, (a.photo_width, int(round(H * s))), interpolation=cv2.INTER_AREA)
    p0, p1 = (int(x0 * s), int(y0 * s)), (int(x1 * s), int(y1 * s))
    cv2.rectangle(img, p0, p1, (0, 0, 0), 5)
    cv2.rectangle(img, p0, p1, (40, 200, 255), 2)
    cv2.imwrite(str(a.out / "photos" / name), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return dict(file=f"photos/{name}", source=key, captured=meta["time"]["utc"], camera_m=[round(float(v), 2) for v in C],
                box=[round(p0[0] / img.shape[1], 4), round(p0[1] / img.shape[0], 4),
                     round(p1[0] / img.shape[1], 4), round(p1[1] / img.shape[0], 4)])


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode()


if a.out.exists():
    shutil.rmtree(a.out)
(a.out / "photos").mkdir(parents=True)
truth = json.loads((a.pass_dir / "truth.json").read_text())
F = json.loads((a.work / "flags.json").read_text())
simulated = "simulation" in F["pose_source"]
metas = [json.loads(p.read_text()) for p in sorted((a.pass_dir / "photos").glob("*/*.json"))]
times = sorted(m["time"]["utc"] for m in metas)
scene = dict(crop=a.crop, simulated=simulated, field_id=metas[0]["field_id"] if metas else None,
             pass_photos=len(metas), pass_devices=sorted({m["device_id"] for m in metas}),
             pass_start=times[0] if times else None, pass_end=times[-1] if times else None,
             camera=dict(height_m=metas[0]["camera"]["height_m"], tilt_deg=metas[0]["camera"]["tilt_deg"]) if metas else None, pose_source=F["pose_source"], note=F["note"],
             pass_stats=F["pass_stats"], measured_blocks=F["measured_blocks"], block_m=F["block_m"])
if "score_on_simulated_data" in F:
    s = F["score_on_simulated_data"]
    scene["score_on_simulated_data"] = {k: s[k] for k in ("note", "planted", "found", "flags", "flags_not_near_a_planted_problem")}
    scene["planted"] = [dict(id=p["id"], kind=p["kind"], found=p["found"], by=p["by"]) for p in s["problems"]]

flags = []
if a.crop != "vineyard":
    M = np.load(a.work / "field_map.npz")
    meta = json.loads((a.work / "field_map.json").read_text())
    x0, x1, y0, y1 = meta["extent"]
    H = M["height"]
    k = int(round(a.grid / meta["cell_m"]))
    ny, nx = H.shape[0] // k, H.shape[1] // k
    with np.errstate(all="ignore"):
        Hb = np.nanpercentile(H[: ny * k, : nx * k].reshape(ny, k, nx, k).transpose(0, 2, 1, 3).reshape(ny, nx, -1), 90, axis=2)
    measured = np.isfinite(Hb)
    # fill unmeasured cells from their nearest measured neighbour so the surface has no holes; the mask
    # goes along so the viewer can say which parts were filled
    dist, idx = ndimage.distance_transform_edt(~measured, return_distances=True, return_indices=True)
    Hf = Hb[tuple(idx)]
    shown = dist <= 3          # small holes are bridged; larger unmeasured areas are left out of the surface
    # light smoothing for display only (single leaves make spikes); flags use the unsmoothed map
    Hf = ndimage.gaussian_filter(ndimage.median_filter(Hf, size=3), 0.8)
    scene.update(kind="surface", extent=[x0, x1, y0, y1], grid_m=a.grid, nx=nx, ny=ny,
                 height_cm_u8=b64(np.clip(np.round(Hf * 100), 0, 255).astype(np.uint8)),
                 measured_u8=b64(measured.astype(np.uint8)), shown_u8=b64(shown.astype(np.uint8)), measured_fraction=round(float(measured.mean()), 3),
                 heights_m=dict(p5=round(float(np.nanpercentile(Hb, 5)), 3), p50=round(float(np.nanpercentile(Hb, 50)), 3),
                                p95=round(float(np.nanpercentile(Hb, 95)), 3)),
                 row_gap_m=truth.get("row_gap_m"), section_m=truth.get("section_m"))
    # map texture: the finer map when there is one, gaps filled from neighbours (inpainting), north up
    src = a.hi or a.work
    Mh = np.load(src / "field_map.npz")
    rgb = Mh["rgb"].astype(np.uint8)
    hole = (~np.isfinite(Mh["height"])).astype(np.uint8)
    tex = cv2.inpaint(np.flipud(rgb)[..., ::-1].copy(), np.flipud(hole).copy(), 3, cv2.INPAINT_TELEA)
    cv2.imwrite(str(a.out / "map.jpg"), tex, [cv2.IMWRITE_JPEG_QUALITY, 88])
    scene["texture"] = dict(file="map.jpg", cell_m=json.loads((src / "field_map.json").read_text())["cell_m"],
                            note="colour from the photos; gaps between measured cells are filled from neighbours")
    for f in F["flags"]:
        bx0, bx1, by0, by1 = f["bbox"]
        top = float(np.nanmax(Hb)) if np.isfinite(Hb).any() else 1.0
        corners = [(x, y, z) for x in (bx0, bx1) for y in (by0, by1) for z in (0.0, min(top, 2.0))]
        ev = [e for i, key in enumerate(f["photos"]) if (e := evidence(key, corners, f"{f['id']}_{i + 1}.jpg"))]
        flags.append(dict({k: v for k, v in f.items() if k != "photos"}, evidence=ev))
else:
    z0, z1 = truth["canopy_m"]
    faces = []
    for fc in F["faces"]:
        img = cv2.imread(str(a.work / fc["image"]))
        alpha = (img.max(2) > 0).astype(np.uint8) * 255          # unmeasured cells are transparent
        cv2.imwrite(str(a.out / fc["image"]), np.dstack([img, alpha]))
        faces.append(dict(fc, fill=round(fc["fill"], 3) if fc["fill"] is not None else None))
    scene.update(kind="rows", section_m=truth["section_m"], rows_x_m=truth["row_x_m"], vines_y_m=truth["vine_y_m"],
                 canopy_m=[z0, z1], faces=faces, alleys_x_m=truth["cameras"]["alleys_x_m"],
                 note_faces="Each row face that a camera drove past is mapped; the other face of the row was not photographed.")
    for f in F["flags"]:
        x = f["x"]
        corners = [(x, y, z) for y in f["y_range"] for z in (z0, z1)]
        ev = [e for i, key in enumerate(f["photos"]) if (e := evidence(key, corners, f"{f['id']}_{i + 1}.jpg"))]
        flags.append(dict({k: v for k, v in f.items() if k != "photos"}, evidence=ev))
scene["flags"] = flags
(a.out / "scene.json").write_text(json.dumps(scene, separators=(",", ":")))
size = sum(p.stat().st_size for p in a.out.rglob("*") if p.is_file())
print(f"{a.crop}: {len(flags)} flags, {sum(len(f['evidence']) for f in flags)} evidence photos, {size / 1e6:.1f} MB")
