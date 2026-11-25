# Handoff: render-sim-passes

Status: open
From: Sriram
To: Tushar
Opened: 2026-11-24

## Request

**Goal:** Render one simulated pass each of the corn section, the vineyard block and the potato section on the RTX 3070, so the demo pipeline (3D model, flags, dashboard) has photos to run on. Everything here is synthetic and labeled that way.

**Branch / commit to start from:** `main` after PR 8 (vineyard photo spacing) and PR 10 (potato field) merge. PR 6 (corn and vineyard generators) is already merged. Read `pipelines/synthetic/README.md` first.

**Inputs:** none; the scripts build the scenes.

**What to run:**
1. Get Blender 5.x rendering on the GPU: either `pip install bpy==5.3.0 numpy` (Python 3.13) or a Blender 5.x install.
2. Timing check, 3 frames each:
   - `python pipelines/synthetic/corn_field.py --out out/corn --scale 0.5 --samples 32 --gpu --only 0,100,200`
   - `python pipelines/synthetic/vineyard_field.py --out out/vineyard --scale 0.5 --samples 32 --gpu --only 0,150,300`
   - `python pipelines/synthetic/potato_field.py --out out/potato --scale 0.5 --samples 32 --gpu --only 0,100,200`
   - (with a Blender install: `blender -b -P pipelines/synthetic/corn_field.py -- --out out/corn ...`)
   Each frame prints its render time. Check the log says it used the GPU (OptiX or CUDA), not CPU.
3. There are 1,000 frames in all. If a frame takes more than about 9 s, use `--scale 0.4` instead of `0.5` for all three full runs, so the total stays under about 2.5 hours.
4. Full runs (drop `--only`): potato first, then vineyard, then corn. Potato matters most for the demo and corn least, so if time runs short, skip corn.
5. Zip `out/corn`, `out/vineyard` and `out/potato` (photos, `truth.json`, the `.blend`) and upload to Google Drive, shared with Sriram.

**Expected outputs:**
- `out/corn/photos/<device>/*.jpg + .json`: 230 pairs. `out/vineyard/...`: 540 pairs. `out/potato/...`: 230 pairs.
- Drive link(s) to the zips.
- Seconds per frame for each field, total time, GPU used, scale and samples used.

**Done when:** all three zips are on Drive with every photo present (230 corn, 540 vineyard, 230 potato JPEGs), and three random photos from each open and look like crops, not black or noisy frames.

**Limits:** stop after 3 hours and send what finished, plus where it stopped (a field that didn't finish can resume on Friday with `--only`). Don't change the scripts; if something breaks, set Status to `blocked` with the error. Nothing paid.

## Result

_Filled in by Tushar. Then open a PR titled `Handoff result: render-sim-passes` that changes only this file._

**Status:**
**Branch / PR:**
**Outputs:**
**Measured:**
**Run:**
**Notes / questions:**
