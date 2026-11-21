# GroundZero

A farm dashboard built at the DNAForge AI x Biology hackathon (Agricultural Resilience track).

The idea: put a cheap camera on machinery a farmer already owns. As the sprayer or tractor works the field, it photographs the crop. GroundZero puts those photos, the irrigation and spray logs, and the weather forecast into one view: a 3D model of the field that doubles as a heatmap. Hover a zone and you see everything known about it and what to check next.

**This is a prototype.** The field, its zones, the logs and the machine path are simulated, and the UI says so wherever they appear. The weather, soil-moisture history, satellite and aerial imagery, and the model results are real public data. Scores are simple, visible rules, not a trained model. Nothing controls machinery and nothing recommends a product or dose.

## Run it

You need Python 3.10+ and Node 20+.

```bash
./run.sh
```

Open http://localhost:8000. The script sets everything up and prints the address the camera should post to.

To check the backend:

```bash
backend/.venv/bin/python backend/tests/smoke_test.py
```

## What to try

1. **Landing page.** You start above a real aerial photo of farmland with a slowly orbiting camera. Use the arrows to switch between three demo fields, click inside the outline to pick a zone, then open it.
2. **3D field.** Drag to rotate, scroll to zoom. Hover a zone to open its panel, click to pin it. Switch layers along the top: crop health, drought and heat risk, water applied, pesticide coverage, forecast impact, satellite NDVI. Problem zones rise out of the field.
3. **Weather switch.** "This week" is the live forecast. "Aug 2026 heatwave" replays the real hottest week of last summer at the same spot, so you can see the risk layers react.
4. **Simulate capture** (top right). Send a photo to a zone. It goes through the same endpoint the camera uses, and the map, gallery, zone score and action list update live.
5. **Action Center.** Ranked suggestions, each with the evidence behind it.
6. **Model Evidence.** What we actually measured, including what didn't work.

## Real row scan

From the landing page, **Real row scan** opens a coarse 3D view of an actual corn row built only from photographs (47 frames of public CropDriveSD side-camera footage). The row is split into five sections; click one to see its original photos, times and how much of it was placed in 3D, and to flag it for an in-person check. Crop condition is shown as "not assessed" because no condition method has been built or tested. Scale is not measured. How it is made: [pipelines/crop_view/README.md](pipelines/crop_view/README.md).

## 3D field section

`viewer/field3d/` is a standalone three.js page showing a real corn field rebuilt from public drone photos (UAV3DCrop, CC BY 4.0): a detailed 23 × 25 m section around six hand-measured plots on 12 survey dates (bare soil to full height), the whole surveyed field (about 57 × 67 m) on day 40, a crop-height layer measured from the photos with an accuracy check against hand measurements, a modeled center pivot with PivotCam and a simulated pass, and a guided tour. Serve the folder with any static server (for example `python3 -m http.server` inside it). How it is built: [pipelines/field_model/README.md](pipelines/field_model/README.md).

## Camera to dashboard

The camera sends a raw JPEG with its metadata in `X-*` headers. Full details are in [shared/capture-contract.md](shared/capture-contract.md).

```bash
curl -X POST http://<LAPTOP_LAN_IP>:8000/api/captures -H "Content-Type: image/jpeg" -H "X-Device-ID: groundzero-esp32-01" -H "X-Field-ID: field-A" -H "X-Zone-ID: demo-zone-1" -H "X-Edge-Label: discoloration" -H "X-Edge-Confidence: 0.72" -H "X-Capture-Uptime-Ms: 31415" --data-binary @frontend/public/demo/images/discoloration_01.jpg
```

There is no GPS on the board, so the zone is set by hand. Anything the device doesn't measure is stored as empty and shown as "not measured".

The current firmware in [hardware/](hardware/) saves to an SD card and does not post to this endpoint yet, so in the demo photos come in through the simulator.

## What's real and what's simulated

| Data | Status | Source |
|---|---|---|
| Field layout, zone soil, baseline health | Simulated | `shared/gen_demo.mjs` |
| Irrigation log, spray log, machine path | Simulated | `shared/gen_demo.mjs` |
| Fields B and C | Simulated, separate from Field A | Browser only; the backend serves Field A |
| Gallery photos | Real photos, assigned to zones by us | PlantVillage (CC BY-SA 3.0), Wikimedia Commons |
| Landing page imagery | Real, public domain | USDA NAIP via USGS, Yolo County, CA |
| Weather forecast and heatwave replay | Real | Open-Meteo |
| Soil moisture history | Real, but modelled, not a probe in a field | ERA5-Land, NASA POWER |
| Satellite NDVI | Real | Sentinel-2 |
| Health and risk scores | Simple rules | `frontend/src/data/scoring.ts` |
| Login | Not built | The "Log in" button says so |
| Row scan photos and 3D shape | Real photos; shape derived from them, approximate, no measured scale | CropDriveSD (CC BY 4.0), `pipelines/crop_view/` |

## What we measured

**Soil moisture forecast** (24 to 72 hours ahead, trained on 2021 to 2024, tested on 2026). Given the real future weather, the model beats "assume nothing changes" by 40 to 47%. Without future weather, it is 27 to 73% worse. A real forecast would land somewhere in between, and we haven't measured that.

**Crop outcome under drought and heat** (IPK maize dataset, 765 plants, whole genotypes held out). The model predicts how big a plant will be two to four weeks later (R² 0.83 and 0.78, against 0.39 and 0.47 for guessing the group average). It cannot predict how much a given genotype loses to stress; there it does worse than guessing the average. These are greenhouse pots, not a field.

**Camera drought detection** (Zenodo maize images). Not validated. The images didn't match the dataset's described layout, so we claim nothing.

**Not measured:** the on-device model, pesticide effectiveness, or anything on a real farm.

## Biobase challenge

`biobase/` is a separate entry for Biobase's "Find the Right Patients" challenge, using only their data. Results on their held-out answer key:

| Task | Ours | Their baseline |
|---|---|---|
| Criteria search | F1 1.000 | 0.27 |
| Slide organ labels | 79.1% | about 70% |
| Similar slides (precision at 1 / 5 / 10) | 0.836 / 0.779 / 0.765 | about 0.8 / 0.7 / 0.6 |

More in [biobase/README.md](biobase/README.md).

## Layout

Working on this repo with an agent? Start with [CLAUDE.md](CLAUDE.md) (same text as [AGENTS.md](AGENTS.md)).

```
frontend/   React + TypeScript, React Three Fiber for the 3D views
backend/    FastAPI + SQLite: photo uploads, review, live updates
hardware/   ESP32-CAM firmware and model trainers
pipelines/  Scripts that pulled and evaluated the public data
biobase/    Biobase challenge entry
shared/     Camera contract and demo data generator
docs/       Decisions, Pi capture format (draft), Cotal setup, GPU job template
```

## Credits

Open-Meteo, ERA5 and ERA5-Land (Copernicus), NASA POWER, Sentinel-2 via Element84 Earth Search, USDA NAIP via USGS, PlantVillage (Hughes & Salathé 2015), Wikimedia Commons contributors, Banerjee's Maize Drought Stress dataset (Zenodo 10.5281/zenodo.10991581), and Shi's maize phenotyping dataset (IPK 10.5447/ipk/2025/8).

## Team

Dashboard, backend and data: sriramJ24. Camera hardware and firmware: TMRmehta.
