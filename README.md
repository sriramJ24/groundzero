# GroundZero — Farm Intelligence / Digital Twin

Hackathon prototype (DNAForge, Agricultural Resilience track). A low-cost camera on existing farm machinery photographs crops as the machine works. GroundZero turns those photos, the irrigation and application logs, and the weather forecast into one view of the field: a rotatable 3D model that doubles as a heatmap, where hovering any zone shows everything known about it and what to check next.

> **Read this first.** This is a prototype. The field, its zones, the irrigation and pesticide logs and the machine path are **simulated** and labelled as such in the UI. Weather, soil-moisture history, satellite NDVI and the model evaluations are **real public data**, each labelled with its source. Scores are transparent rules, not a trained model, and every recommendation is for a person to review. Nothing controls machinery and no product or dosage is ever recommended.

## Run it

Requirements: Python 3.10+ and Node 20+.

```bash
./run.sh
```

Then open http://localhost:8000. The script creates a Python environment, builds the dashboard and serves both the dashboard and the API on port 8000. It prints the address the ESP32 should post to.

No backend? The dashboard also runs on its own from bundled demo data: `cd frontend && npm install && npm run dev`, then open http://localhost:5173. The header shows "Backend: not running" and uploads stay in the browser.

Check the backend:

```bash
backend/.venv/bin/python backend/tests/smoke_test.py
```

## What to try (2 minutes)

1. **Digital Twin.** Drag to rotate, scroll to zoom. Hover a zone to open its panel; click to pin it. Switch layers along the top: crop health, drought/heat risk, water applied, pesticide coverage, forecast impact, satellite NDVI. With "Height = value" on, problem zones rise out of the field.
2. **Weather switch.** "This week" uses the live Open-Meteo forecast for the field coordinates. "Aug 2026 heatwave" replays the real hottest week of last summer at the same location, to show how the risk layers respond.
3. **Replay.** Play or scrub the machine pass; the trail and image pins follow.
4. **Simulate capture** (top right). Pick a sample photo, a zone and a label and send it. It goes through the same `POST /api/captures` endpoint the camera uses; the pin, gallery, zone score and Action Center update live.
5. **Action Center.** Ranked suggestions, each with the evidence that produced it.
6. **Model Evidence.** What has actually been measured, including the results that did not go our way.

## Camera → dashboard

The ESP32-CAM sends a raw JPEG with metadata in `X-*` headers. Full contract: [shared/capture-contract.md](shared/capture-contract.md).

```bash
curl -X POST http://<LAPTOP_LAN_IP>:8000/api/captures -H "Content-Type: image/jpeg" -H "X-Device-ID: fieldos-esp32-01" -H "X-Field-ID: field-A" -H "X-Zone-ID: demo-zone-1" -H "X-Edge-Label: discoloration" -H "X-Edge-Confidence: 0.72" -H "X-Capture-Uptime-Ms: 31415" --data-binary @frontend/public/demo/images/discoloration_01.jpg
```

Use the laptop's LAN IP, not `localhost`, from the board. There is no GPS on the board, so the zone is assigned manually (`demo-zone-1` maps to zone F6). Sensor fields the device does not measure are stored as `null` and shown as "not measured".

Other endpoints: `GET /api/captures`, `GET /api/captures/{id}/image`, `POST /api/captures/{id}/review`, `GET /api/zones`, `GET /api/field`, `GET /api/health`, `GET /api/events` (live stream).

## What is real and what is simulated

| Data | Status | Source |
|---|---|---|
| Field layout, zone soil/exposure, baseline health | Simulated | `shared/gen_demo.mjs` |
| Irrigation log, application log, machine path | Simulated | `shared/gen_demo.mjs` |
| Seeded gallery photos | Real photos, simulated zone assignment | PlantVillage maize leaves (CC BY-SA 3.0); Wikimedia Commons drought-stressed maize (PD / CC BY / CC BY-SA). Attribution files in `frontend/public/demo/images/` |
| Camera captures | Real when the ESP32 posts; otherwise marked simulated | `POST /api/captures` |
| Weather forecast | Real | Open-Meteo forecast API for 38.543, −121.872 |
| Heatwave scenario | Real historical week (1–7 Aug 2026) | Open-Meteo archive (ERA5) |
| Soil moisture history | Real, but modelled reanalysis, not a probe in a field | Open-Meteo archive (ERA5-Land), NASA POWER |
| Satellite NDVI | Real | Sentinel-2 L2A via Element84 Earth Search; a real 360 m square near Davis, CA, used as the reference location. It is not linked to the simulated zone values |
| Health, drought, heat, forecast-impact scores | Rule-based, indicative | `frontend/src/data/scoring.ts`, `backend/scoring.py` |

## Measured results

Everything below was computed by the scripts in `pipelines/` and is shown in the Model Evidence view exactly as computed.

**Soil moisture forecast** (0–7 cm, ERA5-Land at the field location; gradient-boosted trees; trained 2021–2024, tested on 2026, n = 2,536):

| Variant | +24 h MAE | +48 h MAE | +72 h MAE | vs persistence |
|---|---|---|---|---|
| With observed future weather as a stand-in for a forecast | 0.0088 | 0.0123 | 0.0155 | 40–47% better |
| Without any future weather | 0.0255 | 0.0306 | 0.0370 | 27–73% **worse** |
| Persistence baseline | 0.0147 | 0.0230 | 0.0292 | — |

Units are m³/m³. Without future weather the model does not beat simply assuming nothing changes. With perfect knowledge of future weather it does. A real forecast would land somewhere between, and that has not been measured. The target is reanalysis, not a sensor in a field.

**Camera drought detection on the Zenodo maize dataset: not validated.** We downloaded one trial (2,405 images) but the frames did not match the documented four-plants-side-by-side layout, so plants could not be labelled reliably. No accuracy is claimed.

**Crop outcome prediction** (IPK maize drought + heat phenotyping, 765 plants, 125 genotypes, whole genotypes held out in 5 folds; predicting from measurements up to the first days of stress):

| Target | Model R² (MAE % of mean) | Treatment-group mean | Last value carried forward |
|---|---|---|---|
| Biovolume at end of stress (day 21) | 0.83 (23.1%) | 0.39 (45.0%) | −0.63 (87.9%) |
| Biovolume after recovery (day 35) | 0.78 (26.2%) | 0.47 (39.6%) | −1.50 (98.2%) |
| Relative loss vs control, day 21 | −0.37 (15.2%) | −0.01 (13.1%) | −3.38 (30.6%) |
| Relative loss vs control, day 35 | −0.26 (19.4%) | −0.01 (16.4%) | −1.99 (30.0%) |

The model predicts how big a plant will be well ahead of time, mostly from its early size and its treatment. It does **not** predict how much a given genotype loses to stress: there it is worse than guessing the average. Control and stress were separate experiments and the stress plants were already 59% smaller before stress began, so the raw 76.6% reduction at day 21 overstates the effect (about 43% after adjusting for that gap). These are greenhouse pots, not a field, and not this farm.

**Not measured at all:** accuracy of the on-device model (not trained yet), pesticide efficacy, forecast skill against in-field probes, anything on a real farm.

## Layout

```
frontend/   React + TypeScript + Vite, React Three Fiber for the 3D field
backend/    FastAPI + SQLite: capture ingestion, images, review, live events
pipelines/  Scripts that fetched and evaluated the public datasets
shared/     Capture contract and the demo-data generator
run.sh      One-command local run
```

The product was called FIELDOS earlier in the hackathon. Lower-case `fieldos` identifiers (device ids such as `fieldos-esp32-01`, the `FIELDOS_DB` test variable, the database file name) are part of the camera contract or internal and were left unchanged so the firmware keeps working.

To rename the product, change `PRODUCT_NAME` in `frontend/src/config.ts` and `backend/config.py`.

## Data credits

Open-Meteo (CC BY 4.0) · ERA5 / ERA5-Land, Copernicus Climate Change Service · NASA POWER · Copernicus Sentinel-2 via Element84 Earth Search · PlantVillage (Hughes & Salathé 2015; Mohanty et al. 2016) · Wikimedia Commons contributors (see attribution file) · Banerjee, *Maize-Drought-Stress-Dataset-Raw*, Zenodo 10.5281/zenodo.10991581 · Shi, *High-throughput shoot phenotyping of maize under combined drought and heat stress*, IPK e!DAL 10.5447/ipk/2025/8.

## Team

Dashboard, backend and data: sriramJ24. Camera hardware and firmware: TMRmehta.
