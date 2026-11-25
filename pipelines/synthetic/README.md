# Simulated fields for the demo

Every photo these scripts make is **synthetic**: rendered in Blender, not taken by a camera. Each JSON
sidecar says `"synthetic": true` and carries a `simulation` block with the exact camera pose. Use these
only for the demo and for testing the pipeline, never as farm data.

| Script | Field | Camera | Photos per pass |
|---|---|---|---|
| `corn_field.py` | 30 × 30 m corn (rows 0.76 m, ~V12, 1.7 m tall), about 13,500 plants | 3 Camera Module 3 units on the pivot span (146, 156, 166 m out), 4 m up, 35° down, looking outward, a photo every 0.5 m | 230 |
| `potato_field.py` | 30 × 30 m potatoes (hilled rows 0.91 m, plants 0.3 m apart, near row closure, 0.55 m canopy), about 7,400 plants | same 3 pivot cameras as corn | 230 |
| `vineyard_field.py` | 30 × 30 m VSP vineyard (12 rows 2.5 m apart, vines 1.5 m apart) | tractor in every other alley, one camera each side, 1.6 m up, 10° down, a photo every 1 m | 396 |

Planted problems, listed in each run's `truth.json` so flags can be scored on simulated data:

- Corn: short plants (P1), pale yellow-green plants (P2), a 3.5 m gap across 3 rows (P3).
- Potato: stunted plants (P1), yellowing plants (P2), a gap of about 3.5 × 2.7 m where no plants came up (P3).
- Vineyard: yellowing leaves on 3 vines (V1), thin canopy on 3 vines (V2), one missing vine (V3).

Output layout matches `docs/capture-format.md`: `photos/<device_id>/<capture_id>.jpg` plus `.json`.

```bash
pip install bpy==5.3.0 numpy        # Python 3.13; or use Blender 5.x: blender -b -P corn_field.py -- --out ...
python corn_field.py --out out/corn --scale 0.2 --samples 16 --only 50          # one quick CPU frame
python corn_field.py --out out/corn --scale 0.5 --samples 32 --gpu              # whole pass on a GPU
python potato_field.py --out out/potato --scale 0.5 --samples 32 --gpu
python vineyard_field.py --out out/vineyard --scale 0.5 --samples 32 --gpu
```

`--scale` is the fraction of the Camera Module 3's 4608 × 2592; the JSON records the resolution actually rendered.
