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

What is real: the field surface, its colors, and the plot measurements. What is modeled: the pivot span, towers and PivotCam. Greenness is photo color, not a health score; crop condition is not assessed. The photos come from a drone 12 to 18 m up, not from PivotCam.
