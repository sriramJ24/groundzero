import requests, json, certifi
lat,lon=38.5430,-121.8720
def search(dt,lim=100):
    r=requests.post("https://earth-search.aws.element84.com/v1/search",json={"collections":["sentinel-2-l2a"],"intersects":{"type":"Point","coordinates":[lon,lat]},"datetime":dt,"query":{"eo:cloud_cover":{"lt":10}},"limit":lim,"sortby":[{"field":"properties.datetime","direction":"desc"}]},timeout=60)
    r.raise_for_status(); return r.json()["features"]
if __name__=="__main__":
    f=search("2026-04-15T00:00:00Z/2026-11-14T23:59:59Z")
    json.dump(f,open("cache/items.json","w"))
    for i in f: print(i["id"],i["properties"]["datetime"][:10],round(i["properties"]["eo:cloud_cover"],1),i["properties"].get("proj:code") or i["properties"].get("proj:epsg"))
    print(list(f[0]["assets"].keys()))
