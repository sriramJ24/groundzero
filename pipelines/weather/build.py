import json, os, numpy as np, pandas as pd, datetime as dt
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
HERE = os.path.dirname(os.path.abspath(__file__)); C = HERE + "/cache"
OUT = os.path.abspath(HERE + "/../../frontend/public/data"); os.makedirs(OUT, exist_ok=True)
LOC = {"lat": 38.5430, "lon": -121.8720, "timezone": "America/Los_Angeles", "description": "maize demo field near Davis, California"}
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def dump(name, obj):
    p = f"{OUT}/{name}"; json.dump(obj, open(p, "w"), separators=(",", ":"), allow_nan=False)
    print(name, os.path.getsize(p) // 1024, "KB")
def rnd(x, n=3): return None if x is None or pd.isna(x) else round(float(x), n)

# ---------- load
A = pd.DataFrame(json.load(open(C + "/archive.json"))["hourly"]); A["time"] = pd.to_datetime(A["time"]); A = A.set_index("time").sort_index()
F = pd.DataFrame(json.load(open(C + "/forecast.json"))["hourly"]); F["time"] = pd.to_datetime(F["time"]); F = F.set_index("time")
FD = pd.DataFrame(json.load(open(C + "/forecast.json"))["daily"]); FD["time"] = pd.to_datetime(FD["time"])
P = json.load(open(C + "/power.json"))["properties"]["parameter"]
last_ts = A.index[-1]; today = pd.Timestamp("2026-11-14") if False else pd.Timestamp(dt.date.today())

# ---------- weather.json
hum_d = F["relative_humidity_2m"].groupby(F.index.normalize()).mean()
daily = []
for _, r in FD[FD.time >= today].head(7).iterrows():
    d = r.time
    daily.append(dict(date=d.strftime("%Y-%m-%d"), tmax_c=rnd(r.temperature_2m_max, 1), tmin_c=rnd(r.temperature_2m_min, 1),
        precip_mm=rnd(r.precipitation_sum, 1), et0_mm=rnd(r.et0_fao_evapotranspiration, 2), radiation_mj_m2=rnd(r.shortwave_radiation_sum, 1),
        rh_mean_pct=rnd(hum_d.get(d), 0), wind_max_kmh=rnd(r.wind_speed_10m_max, 1)))
nxt = F[F.index > last_ts if False else F.index >= pd.Timestamp.now().floor("h")].head(72)
hourly = [dict(time=t.strftime("%Y-%m-%dT%H:%M"), temp_c=rnd(r.temperature_2m, 1), rh_pct=rnd(r.relative_humidity_2m, 0), precip_mm=rnd(r.precipitation, 2), radiation_w_m2=rnd(r.shortwave_radiation, 0)) for t, r in nxt.iterrows()]
dump("weather.json", dict(source="Open-Meteo forecast API (api.open-meteo.com/v1/forecast), model forecast for the field coordinates", fetched_at=now, location=LOC, daily=daily, hourly_next_72h=hourly))

# ---------- soil_history.json
d = A.resample("D").agg({"soil_moisture_0_to_7cm": "mean", "soil_moisture_7_to_28cm": "mean", "et0_fao_evapotranspiration": "sum", "precipitation": "sum", "temperature_2m": "max"})
d = d[d.index >= d.index[-1] - pd.Timedelta(days=89)]
def pw(k, date):
    v = P.get(k, {}).get(date.strftime("%Y%m%d")); return None if v is None or v <= -990 else v
days = [dict(date=i.strftime("%Y-%m-%d"), soil_moisture_0_7cm_m3m3=rnd(r.soil_moisture_0_to_7cm, 4), soil_moisture_7_28cm_m3m3=rnd(r.soil_moisture_7_to_28cm, 4),
    et0_mm=rnd(r.et0_fao_evapotranspiration, 2), precip_mm=rnd(r.precipitation, 2), tmax_c=rnd(r.temperature_2m, 1),
    power_radiation_mj_m2=pw("ALLSKY_SFC_SW_DWN", i), power_gwetroot=pw("GWETROOT", i), power_gwettop=pw("GWETTOP", i)) for i, r in d.iterrows()]
dump("soil_history.json", dict(source_notes="MODELLED REANALYSIS for the field coordinates, not an in-ground probe. Soil moisture, ET0, precipitation and tmax: Open-Meteo archive (ERA5/ERA5-Land, ~9-11 km grid), daily mean/sum/max of hourly values; the most recent days may be filled from a forecast-model analysis rather than final reanalysis. power_*: NASA POWER daily (AG community); GWETROOT/GWETTOP are 0-1 wetness fractions, radiation in MJ/m2/day; null = missing (POWER lags several days).", location=LOC, days=days))

# ---------- features
def build_features(A):
    X = pd.DataFrame(index=A.index); s0, s1 = A.soil_moisture_0_to_7cm, A.soil_moisture_7_to_28cm
    X["sm0"] = s0; X["sm1"] = s1
    for l in (24, 72, 168): X[f"sm0_lag{l}"] = s0.shift(l); X[f"sm1_lag{l}"] = s1.shift(l)
    X["sm0_d24"] = s0 - s0.shift(24)
    for w in (24, 72, 168):
        for c, k, f in (("precipitation", "precip", "sum"), ("et0_fao_evapotranspiration", "et0", "sum"), ("temperature_2m", "temp", "mean"), ("shortwave_radiation", "rad", "mean"), ("relative_humidity_2m", "rh", "mean")):
            X[f"{k}_{f}{w}"] = getattr(A[c].rolling(w), f)()
    hr = A.index.hour; doy = A.index.dayofyear
    X["hod_sin"] = np.sin(2 * np.pi * hr / 24); X["hod_cos"] = np.cos(2 * np.pi * hr / 24)
    X["doy_sin"] = np.sin(2 * np.pi * doy / 365.25); X["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return X
def future_feats(W, idx):
    """W: hourly weather with precipitation/et0/temp; features for windows (t,t+24],(t+24,t+48],(t+48,t+72]; t is excluded of window start."""
    out = pd.DataFrame(index=idx)
    for c, k, f in (("precipitation", "precip", "sum"), ("et0_fao_evapotranspiration", "et0", "sum"), ("temperature_2m", "temp", "mean")):
        r = getattr(W[c].rolling(24), f)()  # window ending at index
        for j, h in enumerate((24, 48, 72)):
            out[f"fut_{k}_{f}_{h}"] = r.shift(-h).reindex(idx)  # window (t+h-24, t+h]
    return out
Xb = build_features(A); Xf = future_feats(A, A.index)
BASE = list(Xb.columns)
HORS = (24, 48, 72)
sub = (A.index.hour % 3 == 0)
tr_end, va_end = pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-12-31 23:00")
doy_all = A.index.dayofyear
def clim_pred(train_mask, target_doy):
    s = A.soil_moisture_0_to_7cm[train_mask]; g = s.groupby(s.index.dayofyear).mean()
    g = g.reindex(range(1, 367)).interpolate(limit_direction="both"); ext = pd.concat([g.iloc[-7:], g, g.iloc[:7]]); ext.index = range(-6, 374)
    sm = ext.rolling(7, center=True).mean().iloc[7:-7]; sm.index = range(1, 367)
    return sm.reindex(target_doy).values
variants = []; best = {}
for vname, use_fut in (("with_future_weather_proxy", True), ("no_future_weather", False)):
    hs = []; importance = None
    for h in HORS:
        fcols = [c for c in Xf.columns if any(c.endswith(f"_{x}") for x in (24, 48, 72) if x <= h)] if use_fut else []
        X = pd.concat([Xb, Xf[fcols]], axis=1); y = A.soil_moisture_0_to_7cm.shift(-h)
        ok = X.notna().all(axis=1) & y.notna() & sub
        tr = ok & (A.index <= tr_end); va = ok & (A.index > tr_end) & (A.index <= va_end); te = ok & (A.index > va_end)
        m = HGB(max_iter=300, learning_rate=0.05, max_depth=6, min_samples_leaf=40, l2_regularization=1.0, random_state=0).fit(X[tr], (y - X['sm0'])[tr])
        pr = m.predict(X[te]) + X.loc[te, 'sm0'].values; yt = y[te].values; pers = X.loc[te, "sm0"].values
        tdoy = (A.index[te] + pd.Timedelta(hours=h)).dayofyear
        clim = clim_pred(A.index <= tr_end, tdoy)
        mae = mean_absolute_error(yt, pr); pm = mean_absolute_error(yt, pers)
        hs.append(dict(hours=h, mae=rnd(mae, 5), rmse=rnd(mean_squared_error(yt, pr) ** .5, 5), r2=rnd(r2_score(yt, pr), 4),
            persistence_mae=rnd(pm, 5), persistence_rmse=rnd(mean_squared_error(yt, pers) ** .5, 5), climatology_mae=rnd(mean_absolute_error(yt, clim), 5),
            skill_vs_persistence_pct=rnd(100 * (1 - mae / pm), 2), val_mae=rnd(mean_absolute_error(y[va], m.predict(X[va]) + X.loc[va, 'sm0'].values), 5)))
        if h == 24:
            pi = permutation_importance(m, X[va], (y - X["sm0"])[va], n_repeats=3, random_state=0, n_jobs=-1, scoring="neg_mean_absolute_error")  # importance of delta-model (target minus current sm0)
            importance = [dict(feature=c, importance_mae_increase=rnd(v, 6)) for c, v in sorted(zip(X.columns, pi.importances_mean), key=lambda z: -z[1])[:10]]
            ntr, nte = int(tr.sum()), int(te.sum())
        best[(vname, h)] = dict(mae=mae, pers=pm, fcols=fcols)
    variants.append(dict(name=vname, uses_future_weather=use_fut, horizons=hs, n_train_24h=ntr, n_test_24h=nte, top_features_24h_permutation_on_validation=importance))
lim = ["Soil moisture here is ERA5/ERA5-Land modelled reanalysis for a ~9-11 km grid cell, not an in-ground probe, so skill measures how well we reproduce the reanalysis model, not a real field's soil water.",
 "The with_future_weather_proxy variant uses OBSERVED (reanalysis) precipitation, ET0 and temperature for the next 24/48/72h as a stand-in for a forecast, so its test scores are optimistic; real forecast errors, especially for rain timing, will degrade it.",
 "The test period (2026-01-01 to the latest data) is under one year, covers only part of the seasonal cycle, and its last days may be model-filled rather than final reanalysis; metrics are uncertain with so little data and autocorrelated samples."]
for v in variants:
    for h in v["horizons"]:
        if h["skill_vs_persistence_pct"] <= 0: lim.append(f"Variant {v['name']} does NOT beat persistence at +{h['hours']}h on the test set (MAE {h['mae']} vs persistence {h['persistence_mae']}).")
for v in variants:
    for h in v["horizons"]:
        if h["climatology_mae"] < h["mae"]: lim.append(f"Variant {v['name']} is worse than day-of-year climatology at +{h['hours']}h (MAE {h['mae']} vs {h['climatology_mae']}).")
dump("forecast_eval.json", dict(target="soil_moisture_0_to_7cm at t+24h, t+48h, t+72h", units="m3/m3 (volumetric)", location=LOC,
    data_source="Open-Meteo archive API (ERA5 / ERA5-Land reanalysis), hourly, subsampled to every 3rd hour",
    uses_observed_future_weather_as_forecast_proxy=True, note_on_flag="True only for the variant named with_future_weather_proxy; the no_future_weather variant uses none.",
    train_period="2021-01-01 to 2024-12-31", val_period="2025-01-01 to 2025-12-31", test_period=f"2026-01-01 to {last_ts.date()}",
    n_train=variants[0]["n_train_24h"], n_test=variants[0]["n_test_24h"], variants=variants,
    top_features=variants[0]["top_features_24h_permutation_on_validation"], model="sklearn HistGradientBoostingRegressor, one per horizon, predicting the change from current soil moisture (target minus value at t, added back); time-based split, no shuffling",
    limitations=lim, generated_at=now))

# ---------- soil_forecast.json (real forecast, no leak)
# future weather = Open-Meteo forecast hours after last archive timestamp; trailing features from archive only.
Ff = F[F.index > last_ts][["precipitation", "et0_fao_evapotranspiration", "temperature_2m"]]
choice = "with_forecast_weather"
preds = []
if len(Ff) >= 72:
    row = Xb.iloc[[-1]]
    for h in HORS:
        fcols = best[("with_future_weather_proxy", h)]["fcols"]
        X = pd.concat([Xb, Xf[fcols]], axis=1); y = A.soil_moisture_0_to_7cm.shift(-h)
        ok = X.notna().all(axis=1) & y.notna() & sub & (A.index <= va_end)  # train+val only; test untouched
        m = HGB(max_iter=300, learning_rate=0.05, max_depth=6, min_samples_leaf=40, l2_regularization=1.0, random_state=0).fit(X[ok], (y - X['sm0'])[ok])
        x = row.copy()
        for c in fcols:
            _, k, f, hh = c.split("_"); col = {"precip": "precipitation", "et0": "et0_fao_evapotranspiration", "temp": "temperature_2m"}[k]; hh = int(hh)
            w = Ff[col].iloc[hh - 24:hh]; x[c] = w.sum() if f == "sum" else w.mean()
        preds.append(dict(hours=h, time=(last_ts + pd.Timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M"), value=rnd(m.predict(x[X.columns])[0] + x['sm0'].iloc[0], 4), test_mae=rnd(best[("with_future_weather_proxy", h)]["mae"], 5)))
else:
    choice = "no_future_weather"
hist = A.soil_moisture_0_to_7cm[A.index > last_ts - pd.Timedelta(days=14)]; hist = hist[hist.index.hour % 3 == 0]
dump("soil_forecast.json", dict(issued_from=last_ts.strftime("%Y-%m-%dT%H:%M"), units="m3/m3", target="soil_moisture_0_to_7cm (ERA5-Land modelled, not a probe)",
    history=[dict(time=t.strftime("%Y-%m-%dT%H:%M"), value=rnd(v, 4)) for t, v in hist.items()], predictions=preds,
    model_variant=("with_future_weather_proxy architecture, fed the REAL Open-Meteo forecast for +24/48/72h weather (trained on observed-weather proxy; test_mae comes from that proxy evaluation so is optimistic)" if preds else choice),
    note="Trailing features from the archive only; future-weather features from api.open-meteo.com forecast hours after issued_from. Model trained on 2021-2025, test period unused for fitting."))
print(json.dumps([{ "v": v["name"], "h": [(x["hours"], x["mae"], x["persistence_mae"], x["skill_vs_persistence_pct"], x["r2"], x["climatology_mae"]) for x in v["horizons"]]} for v in variants], indent=0))
print(preds, last_ts)
