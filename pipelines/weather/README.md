# Weather + soil moisture pipeline (field near Davis, CA)
1. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. `.venv/bin/python fetch.py` downloads Open-Meteo forecast/archive and NASA POWER into `cache/`.
3. `.venv/bin/python build.py` trains the models and writes the JSON files.
4. Outputs go to `frontend/public/data/`: weather, soil_history, forecast_eval, soil_forecast (.json).
5. Soil moisture is ERA5-Land modelled reanalysis, not a probe; rerun both scripts to refresh.
