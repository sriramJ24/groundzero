import io
import os
import sys
import tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["FIELDOS_DB"] = os.path.join(tmp, "t.db")
os.environ["FIELDOS_UPLOADS"] = os.path.join(tmp, "uploads")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import app as appmod  # noqa: E402
import config  # noqa: E402

buf = io.BytesIO()
Image.new("RGB", (320, 240), (40, 160, 60)).save(buf, "JPEG")
JPG = buf.getvalue()


def hdr(**kw):
    h = {"X-Device-ID": "esp32-1", "X-Field-ID": "field-1", "X-Zone-ID": "C3", "X-Edge-Label": "healthy",
         "X-Edge-Confidence": "0.9", "X-Capture-Uptime-Ms": "1234", "Content-Type": "image/jpeg"}
    h.update(kw)
    return {k: v for k, v in h.items() if v is not None}


def check(name, cond):
    if not cond:
        print("FAIL", name)
        sys.exit(1)
    print("PASS", name)


with TestClient(appmod.app) as c:
    r = c.post("/api/captures", content=JPG, headers=hdr())
    check("upload 201", r.status_code == 201)
    j = r.json()
    check("response keys", {"capture_id", "stored", "zone_id", "image_url"} <= set(j) and j["stored"] is True)
    cid = j["capture_id"]
    lst = c.get("/api/captures", params={"zone_id": "C3"}).json()
    check("in list", lst and lst[0]["id"] == cid and lst[0]["image"]["width"] == 320 and lst[0]["sensors"]["light_lux"] is None)
    ir = c.get(j["image_url"])
    check("image jpeg", ir.status_code == 200 and ir.content[:3] == b"\xff\xd8\xff" and ir.headers["content-type"] == "image/jpeg")
    rv = c.post(f"/api/captures/{cid}/review", json={"status": "approved", "note": "ok"})
    check("review", rv.status_code == 200 and rv.json()["review"]["status"] == "approved")
    check("review bad status 400", c.post(f"/api/captures/{cid}/review", json={"status": "x"}).status_code == 400)
    m = c.post("/api/captures", content=JPG, headers=hdr(**{"X-Zone-ID": "demo-zone-1"})).json()
    check("demo-zone-1 -> F6", m["zone_id"] == "F6" and c.get("/api/captures", params={"zone_id": "F6"}).json()[0]["reported_zone_id"] == "demo-zone-1")
    bad = c.post("/api/captures", content=JPG, headers=hdr(**{"X-Zone-ID": "ZZ99"})).json()
    check("invalid zone -> F6", bad["zone_id"] == "F6")
    r = c.post("/api/captures", content=JPG, headers=hdr(**{"X-Zone-ID": None}))
    check("missing header 400", r.status_code == 400 and r.json() == {"error": "missing_header", "header": "X-Zone-ID"})
    check("non-JPEG 415", c.post("/api/captures", content=b"hello not a jpeg", headers=hdr()).status_code == 415)
    check("fake magic 415", c.post("/api/captures", content=b"\xff\xd8\xff" + b"x" * 50, headers=hdr()).status_code == 415)
    check("oversized 413", c.post("/api/captures", content=b"\xff\xd8\xff" + b"0" * (config.MAX_UPLOAD_BYTES + 10), headers=hdr()).status_code == 413)
    check("bad confidence 400", c.post("/api/captures", content=JPG, headers=hdr(**{"X-Edge-Confidence": "abc"})).status_code == 400)
    check("health", c.get("/api/health").json()["captures"] >= 3)

    def score(z):
        zs = {x["id"]: x for x in c.get("/api/zones").json()}
        return zs[z]["health"]["score"] if z in zs else None
    zs = c.get("/api/zones").json()
    if zs:
        before = score("E5")
        c.post("/api/captures", content=JPG, headers=hdr(**{"X-Zone-ID": "E5", "X-Edge-Label": "wilting", "X-Edge-Confidence": "1.0"}))
        after = score("E5")
        check(f"zone health changed ({before} -> {after})", before != after)
    else:
        print("NOTE demo field.json absent; verifying via scoring directly")
        from scoring import zone_health
        h1 = zone_health([], {"score": 90})
        h2 = zone_health([{"id": "a", "received_at": "1", "edge_prediction": {"label": "wilting", "confidence": 1.0}, "review": {"status": "unreviewed"}}], {"score": 90})
        check("zone health changes after wilting", h1["score"] != h2["score"] and h2["score"] == 40)
print("ALL PASS")
