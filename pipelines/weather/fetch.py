import requests, json, datetime as dt, os
LAT, LON, TZ = 38.5430, -121.8720, "America/Los_Angeles"
C = os.path.join(os.path.dirname(__file__), "cache")
def get(url, params, name):
    r = requests.get(url, params=params, timeout=120); r.raise_for_status()
    open(f"{C}/{name}.json", "w").write(r.text); return r.json()
today = dt.date(2026, 11, 14) if os.environ.get("FIXED_TODAY") else dt.date.today()
end = today - dt.timedelta(days=2)
get("https://archive-api.open-meteo.com/v1/archive", dict(latitude=LAT, longitude=LON, timezone=TZ,
    start_date="2021-01-01", end_date=str(today),
    hourly="soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,temperature_2m,relative_humidity_2m,precipitation,et0_fao_evapotranspiration,shortwave_radiation"), "archive")
H = "temperature_2m,relative_humidity_2m,precipitation,shortwave_radiation,et0_fao_evapotranspiration,wind_speed_10m,soil_moisture_0_to_1cm,soil_moisture_3_to_9cm"
get("https://api.open-meteo.com/v1/forecast", dict(latitude=LAT, longitude=LON, timezone=TZ, forecast_days=8, past_days=2, hourly=H,
    daily="temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration,shortwave_radiation_sum,wind_speed_10m_max"), "forecast")
s = (today - dt.timedelta(days=120)).strftime("%Y%m%d")
get("https://power.larc.nasa.gov/api/temporal/daily/point", dict(parameters="ALLSKY_SFC_SW_DWN,GWETROOT,GWETTOP,T2M_MAX,T2M_MIN,PRECTOTCORR",
    community="AG", longitude=LON, latitude=LAT, start=s, end=today.strftime("%Y%m%d"), format="JSON"), "power")
print("ok")
