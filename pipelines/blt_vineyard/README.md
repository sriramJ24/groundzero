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

## Flags (places to look)

```
python flags.py       # after build_row.py; writes $BLT_WORK/site/data/flags.json and ev/*.jpg
```

`build_row.py` also saves `seen_A.npy` / `seen_B.npy`: the texture spots a photo covered, whether it showed leaves or a gap.
`flags.py` measures canopy cover in 0.5 m slices of the row: the share of the 0.55-1.35 m band where the photos show leaves
(not a see-through gap, not sky), counted over covered spots only. A slice is flagged when its cover is under half of that face's
median on both faces, with at least half the band covered on each. Each flag gets the most head-on photo from each alley with
the slice boxed (projected with the recorded pose). Frames 0-4 are never used (the operator is in view).

On the June 22, 2022 sample: 83 slices (41.5 m) were covered from both alleys, 4 flags. Looking at the photos, all four are open
stretches you can see through to the next row or the lawn; two sit at a trellis post. There is no ground truth, so no accuracy figure.

The viewer is `viewer/vineyard/` (copy `$BLT_WORK/site/` there after export.py and flags.py).
