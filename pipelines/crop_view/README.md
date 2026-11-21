# Crop view pipeline (Row Scan)

Builds the coarse 3D crop shape behind the dashboard's **Real row scan** page (`#/scan`).

Inputs: the 47 CropDriveSD side-camera photos and the 30-camera COLMAP model from the earlier RGB reconstruction experiment. Nothing is downloaded.

1. `dense_stereo.py` rectifies pairs of aligned photos with the COLMAP poses, runs OpenCV semi-global matching with a left-right check, and fuses the result into voxels. A voxel is kept only where at least 3 independent photo pairs agree. CPU only, 10-minute cap (the current run takes about 9 s).
2. `export_scan.py` writes `frontend/public/scan/scan.json` and the browser photos, splitting the row into 4 reconstructed sections plus a 5th "photos only" section for the 17 photos that could not be aligned.

```bash
pip install numpy opencv-python-headless
python dense_stereo.py --images <images-dense> --sparse <results/attempt2/sparse/0> --out <work>
python export_scan.py --dense <work> --images <images-dense> --scene <public/scene.json> --out ../../frontend/public/scan
```

Limits: scale is arbitrary (no GPS, IMU or measured distance), "up" comes from camera orientation rather than measured gravity, and section 5's position is assumed. The blocks show where photos agree crop exists, not plant counts, heights or health. No crop-condition method exists yet, so the page shows "not assessed".
