# Handoff: render-sim-passes

Status: open
From: Sriram
To: Tushar
Opened: 2026-11-24

## Request

**Goal:** Render one simulated pass of the corn section and one of the vineyard block on the RTX 3070, so the demo pipeline (3D model, flags, dashboard) has photos to run on. Everything here is synthetic and labeled that way.

**Branch / commit to start from:** `cloud/synthetic-field` at `b0b967d` (PR 6). Read `pipelines/synthetic/README.md` first.

**Inputs:** none; the scripts build the scenes.

**What to run:**
1. Get Blender 5.x rendering on the GPU: either `pip install bpy==5.3.0 numpy` (Python 3.13) or a Blender 5.x install.
2. Timing check, 3 frames each:
   - `python pipelines/synthetic/corn_field.py --out out/corn --scale 0.5 --samples 32 --gpu --only 0,100,200`
   - `python pipelines/synthetic/vineyard_field.py --out out/vineyard --scale 0.5 --samples 32 --gpu --only 0,150,300`
   - (with a Blender install: `blender -b -P pipelines/synthetic/corn_field.py -- --out out/corn ...`)
   Each frame prints its render time. Check the log says it used the GPU (OptiX or CUDA), not CPU.
3. If a frame takes more than about 12 s, use `--scale 0.4` instead of `0.5` for both full runs, so the total stays under about 2.5 hours.
4. Full runs (drop `--only`): corn first, then vineyard.
5. Zip `out/corn` and `out/vineyard` (photos, `truth.json`, the `.blend`) and upload to Google Drive, shared with Sriram.

**Expected outputs:**
- `out/corn/photos/<device>/*.jpg + .json`: 230 pairs. `out/vineyard/photos/<device>/*.jpg + .json`: 396 pairs.
- Drive link(s) to the zips.
- Seconds per frame for each field, total time, GPU used, scale and samples used.

**Done when:** both zips are on Drive with every photo present (230 and 396 JPEGs), and three random photos from each open and look like crops, not black or noisy frames.

**Limits:** stop after 3 hours and send what finished, plus where it stopped. Don't change the scripts; if something breaks, set Status to `blocked` with the error. Nothing paid.

## Result

_Filled in by Tushar. Then open a PR titled `Handoff result: render-sim-passes` that changes only this file._

**Status:**
**Branch / PR:**
**Outputs:**
**Measured:**
**Run:**
**Notes / questions:**
