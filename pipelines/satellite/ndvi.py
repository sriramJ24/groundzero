import os, json, sys, datetime
os.environ["AWS_NO_SIGN_REQUEST"]="YES"
import numpy as np, rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
ITEMS={i["id"]:i for i in json.load(open("cache/items.json"))}
HALF=180.0
def zones(item,lat,lon):
    crs=item["properties"].get("proj:code") or "EPSG:%s"%item["properties"]["proj:epsg"]
    t=Transformer.from_crs("EPSG:4326",crs,always_xy=True)
    cx,cy=t.transform(lon,lat)
    # field is a square in UTM metres centred on centre (north-up)
    x0,y0,x1,y1=cx-HALF,cy-HALF,cx+HALF,cy+HALF
    out={}
    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES",GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        arrs={}
        for k in ("red","nir","scl"):
            a=item["assets"][k]
            with rasterio.open(a["href"]) as ds:
                if k=="scl":
                    # SCL is 20 m: read at 10 m grid by nearest resampling
                    w=from_bounds(x0,y0,x1,y1,ds.transform)
                    arr=ds.read(1,window=w,out_shape=(36,36),resampling=rasterio.enums.Resampling.nearest,boundless=True,fill_value=0)
                else:
                    w=from_bounds(x0,y0,x1,y1,ds.transform)
                    arr=ds.read(1,window=w,out_shape=(36,36),resampling=rasterio.enums.Resampling.nearest,boundless=True,fill_value=0)
                    rb=(a.get("raster:bands") or [{}])[0]
                    arrs[k+"_so"]=(rb.get("scale",1.0),rb.get("offset",0.0))
                arrs[k]=arr
    sc_r,of_r=arrs["red_so"]; sc_n,of_n=arrs["nir_so"]
    red=arrs["red"].astype("float64")*sc_r+of_r; nir=arrs["nir"].astype("float64")*sc_n+of_n
    red=np.clip(red,0,1.0); nir=np.clip(nir,0,1.0)  # negative reflectance after offset (very dark pixels) is noise; clip so NDVI stays in [-1,1]
    scl=arrs["scl"]
    valid=(arrs["red"]>0)&(arrs["nir"]>0)&~np.isin(scl,[0,1,3,8,9,10,11])  # nodata,saturated,shadow,cloud med/high,cirrus,snow
    with np.errstate(all="ignore"): nd=(nir-red)/(nir+red)
    nd=np.where(valid,nd,np.nan)
    z={}
    for r in range(12):
        for c in range(12):
            blk=nd[r*3:(r+1)*3,c*3:(c+1)*3]   # 30 m = 3x3 px of 10 m
            z["ABCDEFGHIJKL"[c]+str(r+1)]=None if np.isnan(blk).all() else round(float(np.nanmean(blk)),3)
    return z,(sc_r,of_r,sc_n,of_n),float(valid.mean())
if __name__=="__main__":
    lat,lon=float(sys.argv[1]),float(sys.argv[2]); sid=sys.argv[3]
    z,so,vf=zones(ITEMS[sid],lat,lon); v=[x for x in z.values() if x is not None]
    print(sid,so,round(vf,2),min(v),round(sum(v)/len(v),3),max(v))
