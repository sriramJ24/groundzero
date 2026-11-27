# BLT vineyard sample (transfer copy)

Real vineyard photos, not simulated: 220 side-camera frames, one per 0.5 m along 110 m of two vine rows
(Ktima Gerovassiliou, Greece, 2022-06-22, 11:02–11:05 UTC, 207 s).

**Source and credit:** Bacchus Long-Term (BLT) dataset, Lincoln Centre for Autonomous Systems, University of Lincoln,
Polvara et al. (2024), Journal of Field Robotics, CC BY 4.0. Bag `blt_dataset/06_june/rosbag_compressed_2022-06-22-13-02-08.bag`
from https://bltdataset.zrok.lcas.group/. Credit the University of Lincoln wherever these images are shown.

This is a reduced copy sized to fit in the repo (44 MB). The full-resolution set (1920x1080 original JPEGs, 1920x1080 depth)
is outside the repo at `~/Code/Hackathons/GroundZero/blt_sample/` on Sriram's Mac. Its README has the full details.

- `rgb/NNNN.jpg`: 1280x720, re-encoded JPEG quality 70 (down from the 1920x1080 originals).
- `depth/NNNN.png`: 320x180, **uint16 PNG, millimetres, 0 = no depth**, nearest-neighbour downscale of the ZED depth.
  It was cut to 320 px to fit the 45 MB limit.
- `meta/NNNN.json`: timestamp, GPS (`/gps/fix` lat/lon/alt with 1-sigma; `/gps/filtered`), map-frame pose of `base_link`
  (`pose_map` from `/odometry/gps`), `pose_quality`, ZED visual odometry, distance along the track.
- `camera.json`: intrinsics (full-res `K`, plus `K_rgb_scaled` and `K_depth_scaled` for these files) and camera-to-base transforms.

Caveats (details in the full README):
- Depth is typically 50–100 ms off the RGB frame (`depth_minus_rgb_s`).
- 50 frames have a pose bridged across gaps in `/odometry/gps`. They agree with GPS to within 0.17 m (see `pose_quality`).
- The bag's own camera-to-base transform is identity. `camera_to_base.urdf_candidate` (0.93 m up, 0.30 m left, facing left)
  comes from the robot URDF in the same bag, and treating it as this camera is an inference.
