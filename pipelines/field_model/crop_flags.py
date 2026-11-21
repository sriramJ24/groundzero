"""Basic crop flags for the field viewer, computed from the season photo textures. No training, CPU only.

For every survey date with a crop up (median canopy cover well under full soil), each 0.5 m cell of the
detailed section gets two numbers from the 2 cm orthophoto texture:
  - greenness: mean excess-green index (2g - r - b on chromaticity) of the lit pixels (shadow pixels skipped)
  - open fraction: share of lit pixels that are bare soil or residue (excess green below 0.06)
Two kinds of flag are drawn from them, each grouped into connected patches of at least 2 cells (0.5 m2):
  - "open": cells where soil shows through far more than is usual for that date
           (open fraction at least 0.25 and at least 0.15 above the date's median)
  - "pale": cells much less green than the rest of the section on that date
           (more than 3 robust standard deviations below the date's median greenness)
Thresholds are relative to the same date because light, growth stage and senescence change the whole
field together. Flags are places to look, not diagnoses: nothing here has been checked against a cause.

Writes <viewer>/flags/flags.json and a 3 x 3 m photo crop for each of the 12 largest flags per date (<viewer>/flags/<day>_<n>.jpg).
Usage: python3 crop_flags.py --viewer viewer/field3d
"""
import argparse, base64, json
from pathlib import Path
import numpy as np
from PIL import Image

CELL = 0.5
OPEN_MIN, OPEN_MARGIN, PALE_SIGMA, MIN_CELLS = 0.25, 0.15, 3.0, 2


def components(mask):
    ny, nx = mask.shape; seen = np.zeros_like(mask, bool); out = []
    for r0 in range(ny):
        for c0 in range(nx):
            if not mask[r0, c0] or seen[r0, c0]: continue
            stack, cells = [(r0, c0)], []; seen[r0, c0] = True
            while stack:
                r, c = stack.pop(); cells.append((r, c))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < ny and 0 <= cc < nx and mask[rr, cc] and not seen[rr, cc]:
                            seen[rr, cc] = True; stack.append((rr, cc))
            out.append(cells)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--viewer", type=Path, required=True); a = ap.parse_args()
    V = a.viewer; out = V / "flags"; out.mkdir(exist_ok=True)
    for f in out.glob("*.jpg"): f.unlink()
    sea = json.loads((V / "season/season.json").read_text()); G = sea["grid"]
    res = {"cell_m": CELL, "rules": {
        "open": f"soil shows in at least {OPEN_MIN:.0%} of the cell and {OPEN_MARGIN * 100:.0f} points more than the date's median",
        "pale": f"greenness more than {PALE_SIGMA:g} robust standard deviations below the date's median"},
        "method": "excess-green index (2g - r - b) of the 2 cm orthophoto, shadow pixels skipped, 0.5 m cells", "dates": {}}
    for d in sea["days"]:
        im = Image.open(V / f"season/tex_{d}.jpg"); tex_cell = (G["x1"] - G["x0"]) / im.size[0]
        k = round(CELL / tex_cell); t = np.asarray(im).astype(np.float32)
        ny, nx = t.shape[0] // k, t.shape[1] // k; t = t[:ny * k, :nx * k]
        s = t.sum(2) + 3; exg = (2 * (t[..., 1] + 1) - (t[..., 0] + 1) - (t[..., 2] + 1)) / s
        lit = s >= 90
        blk = lambda v: v.reshape(ny, k, nx, k).sum((1, 3))
        nlit = np.maximum(blk(lit), 1)
        green = blk(np.where(lit, exg, 0)) / nlit
        openf = blk(lit & (exg < 0.06)) / nlit
        med_open = float(np.median(openf)); med_g = float(np.median(green))
        sig = float(1.4826 * np.median(np.abs(green - med_g)))
        p5, p95 = np.percentile(green, [5, 95])
        q = np.clip(np.round(255 * (green - p5) / max(p95 - p5, 1e-6)), 0, 255).astype(np.uint8)
        entry = {"rows": ny, "cols": nx, "green_p5": round(float(p5), 4), "green_p95": round(float(p95), 4),
                 "green_median": round(med_g, 4), "open_median": round(med_open, 3),
                 "green_u8_base64": base64.b64encode(q.tobytes()).decode(), "flags": []}
        if d == sea["ground_day"] or med_open > 0.5:
            entry["skipped"] = "bare soil" if d == sea["ground_day"] else "crop too small: most of the ground is still open"
            res["dates"][d] = entry; print(d, entry["skipped"]); continue
        masks = {"open": (openf >= OPEN_MIN) & (openf >= med_open + OPEN_MARGIN),
                 "pale": green < med_g - PALE_SIGMA * sig}
        flags = []
        for kind, m in masks.items():
            for cells in components(m):
                if len(cells) < MIN_CELLS: continue
                rs = np.array([c[0] for c in cells]); cs = np.array([c[1] for c in cells])
                x = G["x0"] + (cs.mean() + 0.5) * CELL; y = G["y1"] - (rs.mean() + 0.5) * CELL
                flags.append(dict(kind=kind, x=round(float(x), 2), y=round(float(y), 2), cells=len(cells),
                                  area_m2=round(len(cells) * CELL * CELL, 2),
                                  open_pct=round(100 * float(openf[rs, cs].mean())),
                                  green=round(float(green[rs, cs].mean()), 3),
                                  green_pct_of_median=round(100 * float(green[rs, cs].mean()) / med_g),
                                  cells_rc=[[int(r), int(c)] for r, c in cells]))
        flags.sort(key=lambda f: -f["cells"])
        for i, f in enumerate(flags):
            f["id"] = f"{d}-{i + 1}"
            if i >= 12: continue  # photo crops for the 12 largest patches only
            px = int((f["x"] - G["x0"]) / tex_cell); py = int((G["y1"] - f["y"]) / tex_cell); h = int(1.5 / tex_cell)
            crop = im.crop((max(px - h, 0), max(py - h, 0), min(px + h, im.size[0]), min(py + h, im.size[1])))
            crop.convert("RGB").save(out / f"{d}_{i + 1}.jpg", quality=82); f["crop"] = f"flags/{d}_{i + 1}.jpg"
        entry["flags"] = flags
        res["dates"][d] = entry
        print(d, "open median", round(med_open, 3), "green median", round(med_g, 3), "sigma", round(sig, 3),
              "flags", {kk: sum(f['kind'] == kk for f in flags) for kk in masks}, [(f["kind"], f["area_m2"]) for f in flags[:5]])
    (out / "flags.json").write_text(json.dumps(res, separators=(",", ":")))


if __name__ == "__main__":
    main()
