# GroundZero hardware (ESP32-CAM)

Firmware and model-training scripts by the hardware teammate (TMRmehta) for the AI-Thinker ESP32-CAM.

## What is here

- `GroundZero_Trained/GroundZero_Trained.ino`: the camera sketch. Every 5 seconds it captures a 320×240 JPEG, runs three small INT8 TensorFlow Lite Micro models on a 96×96 copy (plant / no-plant gate, crop identity, visible soil surface), saves the JPEG to the microSD card and appends one CSV row per capture. If no card is present, rows are printed over USB serial instead.
- `train_plant_detector.py`, `train_crop_classifier.py`, `train_soil_classifier.py`: the trainers that produce the `plant_model.h`, `crop_model.h` and `soil_model.h` headers the sketch includes.

Board settings from the sketch: AI Thinker ESP32-CAM, Huge APP partition, Chirale_TensorFlowLite 2.0.0, PSRAM required.

## What to know before relying on it

- **The model headers are not in this folder.** The sketch will not compile until the three trainers have been run on their datasets (Fruits-360 for crop identity, a soil dataset, and a plant / no-plant set). No accuracy figures for these models are recorded here.
- **This sketch does not upload over Wi-Fi.** It records to microSD or USB serial. The dashboard's `POST /api/captures` endpoint (see `shared/capture-contract.md`) is not called by this version, so photos reach the dashboard through the capture simulator or a manual upload.
- **Its labels differ from the dashboard contract.** It reports plant status, crop identity and soil surface. The `healthy` / `discoloration` / `wilting` condition label the dashboard scores on is left empty in its CSV rows.
- The device id, field and zone are fixed in the sketch (`groundzero-esp32-01`, `field-A`, `demo-zone-1`); there is no GPS.
- Renamed from "FieldOS" to "GroundZero" in file names, usage text, the device id and the method version string. No logic was changed.
