from ndvi import *
import datetime
lat,lon=38.5430,-121.8720
ids=["S2B_10SEH_20260518_0_L2A","S2C_10SEH_20260612_0_L2A","S2A_10SEH_20260714_0_L2A","S2C_10SEH_20260811_0_L2A","S2B_10SEH_20260915_0_L2A","S2B_10SEH_20261015_0_L2A","S2A_10SEH_20261111_0_L2A"]
series=[]; so=None
for sid in ids:
    z,so,vf=zones(ITEMS[sid],lat,lon); v=[x for x in z.values() if x is not None]
    it=ITEMS[sid]
    series.append(dict(scene_id=sid,date=it["properties"]["datetime"][:10],cloud_cover=round(it["properties"]["eo:cloud_cover"],1),mean=round(sum(v)/len(v),3),zones=z,_min=min(v),_max=max(v),_valid=round(vf,3)))
    print(sid,series[-1]["mean"],min(v),max(v),vf)
L=series[-1]
latest=dict(scene_id=L["scene_id"],date=L["date"],cloud_cover=L["cloud_cover"],zones=L["zones"],min=L["_min"],max=L["_max"],mean=L["mean"])
for s in series:
    for k in ("_min","_max","_valid","cloud_cover"): s.pop(k)
out=dict(source="Sentinel-2 L2A via Element84 Earth Search (AWS open data)",
 license_note="Contains modified Copernicus Sentinel data 2026. Sentinel data is free and open under the Copernicus Sentinel Data Terms (full, free and open access, attribution required).",
 field=dict(center={"lat":lat,"lon":lon},size_m=360,crs="EPSG:32610 (UTM zone 10N); 12x12 grid of 30 m zones, north-up, ids A1 (NW) to L12 (SE)",center_note="Requested centre used unchanged: July 2026 mean NDVI is about 0.32, well above the 0.15 non-cropland threshold, so no shift was applied. The footprint is a mixed block (low-NDVI strip along the east edge, columns K-L, looks like road/bare ground)."),
 pixel_size_m=10,
 method="STAC search (collection sentinel-2-l2a, point intersects, eo:cloud_cover<10). B04 (red) and B08 (nir) COGs read with rasterio windowed reads over the 360 m x 360 m footprint (36x36 10 m pixels) in the scene UTM CRS. Reflectance = DN*scale+offset using the asset raster:bands metadata (scale=%s, offset=%s, i.e. the processing-baseline 04.00 BOA_ADD_OFFSET of -1000 DN) clipped to [0,1] (very dark pixels can go slightly negative after the offset, which otherwise pushes NDVI above 1), then NDVI=(nir-red)/(nir+red). SCL (20 m, nearest-resampled to 10 m) used to drop nodata, saturated, cloud shadow, cloud medium/high, thin cirrus and snow pixels. Each 30 m zone is the mean of its 3x3 valid pixels (null if none). Series dates were picked from the clear scenes (cloud<10%%) at roughly monthly spacing May-Nov 2026; latest = most recent clear scene."%(so[0],so[1]),
 latest=latest,series=series,
 caveat="Real imagery of a real location used as the demo field; the dashboard's other zone data is simulated and is not derived from this field.",
 generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
json.dump(out,open("/Users/sriramjoshi/Code/Hackathons/GroundZero/groundzero/frontend/public/data/ndvi_zones.json","w"),indent=1)
