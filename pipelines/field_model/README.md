# Field model pipeline (3D field section viewer)

Builds `viewer/field3d/`: a detailed 3D model of a 23 × 25 m section of a real corn field, shown in a three.js page with a modeled center pivot and PivotCam.

Data: [UAV3DCrop](https://huggingface.co/datasets/Link-Dev/UAV3DCrop) (CC BY 4.0), scene `2025/Day040_Corn`. 72 photos (16 straight down, 56 at 45°) around the six hand-measured plots, their camera poses, and the dataset's photogrammetric depth maps ([UAV3DCrop_depth](https://huggingface.co/datasets/Link-Dev/UAV3DCrop_depth)). Download used: about 1.1 GB.

1. `fuse_depth.py` back-projects every depth pixel, fuses into 2 cm voxels kept only where 2+ photos agree (4.5 million points), and builds a trimmed Poisson mesh.
2. `build_surface.py` makes the web model: a 4 cm canopy surface from the fused points, and a 1 cm orthophoto texture sampled from the full-resolution nadir photos, using each photo's depth map to skip hidden spots.
3. `export_viewer_data.py` adds the six plots' ground measurements (canopy height, leaf area index), 3 × 3 m photo crops, the nearest original photo, and a 0.5 m photo-greenness grid.

```bash
pip install numpy opencv-python-headless open3d tifffile imagecodecs scipy plyfile
python fuse_depth.py --scene <scene dir> --out fused
python build_surface.py --scene <scene dir> --fused fused --out web
python export_viewer_data.py --scene <scene dir> --web web --measurements <dir with ground_plots.csv> --out ../../viewer/field3d
```

Season, height and whole field (about 1.3 GB more downloaded: 6 nadir photos + depth maps per date, and 18 more Day040 nadir photos):

4. `season.py` builds, for each of the 12 dates, a 4 cm surface (median across the straight-down photos of each photo's highest point per cell) and a 2 cm photo texture; crop height = surface minus the Day007 bare-soil surface. It checks photo height (95th percentile within 1 m of each plot centre, chosen before looking at results) against the tape-measured canopy height: 66 plot visits, typical miss 16 cm, photos 15.5 cm lower on average, R² 0.95 across the season. Within a single date the plots differ by only about 10 cm and the photos do not rank them reliably.
5. `wide.py` builds the whole surveyed field on day 40 the same way from 34 nadir photos, at 10 cm surface cells and 4 cm texture pixels.
6. `export_splat.py` converts an OpenSplat Gaussian-splat PLY (trained on CPU from the Day040 photos) into the compact `.splat` layout for the viewer.

```bash
python season.py --season <dir with D007/, D019/, ...> --measurements <dir> --out ../../viewer/field3d
python wide.py --scene <Day040 dir> --select wide_sel.json --out ../../viewer/field3d
```

What is real: the field surface, its colors, and the plot measurements. What is modeled: the pivot span, towers and PivotCam, and the pivot pass (a simulation). Greenness is photo color, not a health score; crop condition is not assessed. The photos come from a drone survey, not from PivotCam.

## Crop flags (no training, CPU only)

`crop_flags.py --viewer viewer/field3d` reads the 12 season photo textures and writes `viewer/field3d/flags/flags.json` plus a 3 × 3 m photo crop for the 12 largest flags on each date. For every 0.5 m cell it measures greenness (excess-green index, shadow pixels skipped) and how much bare soil shows. A cell is flagged "more soil showing" when soil covers at least 25% of it and 15 points more than that date's median, or "paler than the rest" when its greenness is more than 3 robust standard deviations below that date's median; flags are connected patches of at least 0.5 m². Thresholds are relative to the same date. On this evenly managed research field the result is 59 open patches on day 28 (the early stand), none from day 33 to 83 and 2 small pale patches on day 96. Flags are places to look, not diagnoses. The viewer's Greenness layer now covers every date from the same file.

### Original photos for each flag

`flag_pick.py` then `flag_evidence.py` add, for each numbered flag, the two original photos that show it best: the 45° photo and the straight-down photo where the flag sits closest to the image centre. The flag's outline is projected into each photo through the dataset's camera pose and lens model (at the median height of the dataset's sparse points within 1 m), drawn in yellow, and the photo is cropped to about 4 × 4 m around it. It downloads only those photos (26 for the 14 numbered flags, about 330 MB).
