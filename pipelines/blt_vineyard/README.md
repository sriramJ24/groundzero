# Vineyard row from the BLT sample (real photos)

Builds a 3D view of one real vine row from `viewer/demo-data/blt_sample/` (220 side-camera frames with depth, GPS and pose
from the Bacchus Long-Term dataset, University of Lincoln, CC BY 4.0).

```
export BLT_WORK=/tmp/blt_work/ && mkdir -p $BLT_WORK
python build_row.py   # fuses depth into the two faces of the row, writes geo.npz and textures (2.5 mm/pixel)
python export.py      # writes $BLT_WORK/site/data/ (scene.json + texture tiles) for viewer/demo-data/blt_row_preview.html
```

`export2.py` is an alternative (each photo draped on its own depth). It looked sparser with the 320x180 depth in the repo copy, so it is not used.

What it measures: the canopy surface position from the ZED depth, and the photo colour of each spot from the photo that saw it most head-on.
Holes are where the camera saw through the canopy (depth far behind the surface) or saw sky. Only the band the side camera sees
(about 0.5 to 1.4 m up) exists. The camera mount comes from the robot model in the bag (an inference; both row faces line up 0.3 m apart, which supports it).
