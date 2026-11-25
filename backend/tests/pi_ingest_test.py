"""Pi ingestion against docs/capture-format.md: JPEG first, JSON as ready marker, idempotent, conflicts refused."""
import copy
import io
import json
import os
import sys
import tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["GROUNDZERO_DB"] = os.path.join(tmp, "t.db")
os.environ["GROUNDZERO_UPLOADS"] = os.path.join(tmp, "uploads")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import app as appmod  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[2] / "docs" / "samples"
META = json.loads((SAMPLE / "20261121T154210123Z_000412.json").read_text())
JPG = (SAMPLE / "20261121T154210123Z_000412.jpg").read_bytes()
KEY = "/api/pi/sample-cam-01/2026-11-21/20261121T154210123Z_000412"


def check(name, cond):
    if not cond:
        print("FAIL", name)
        sys.exit(1)
    print("PASS", name)


with TestClient(appmod.app) as c:
    check("json before jpeg refused", c.put(KEY + ".json", content=json.dumps(META)).status_code == 409)
    check("jpeg stored", c.put(KEY + ".jpg", content=JPG).status_code == 201)
    check("jpeg retry same bytes ok", c.put(KEY + ".jpg", content=JPG).status_code == 200)
    buf = io.BytesIO(); Image.new("RGB", (64, 64)).save(buf, "JPEG")
    check("jpeg different bytes conflict", c.put(KEY + ".jpg", content=buf.getvalue()).status_code == 409)
    check("not a jpeg 415", c.put("/api/pi/sample-cam-01/2026-11-21/20261121T154210123Z_000413.jpg", content=b"nope").status_code == 415)
    check("date mismatch 400", c.put("/api/pi/sample-cam-01/2026-11-22/20261121T154210123Z_000412.jpg", content=JPG).status_code == 400)
    bad = copy.deepcopy(META); bad["device_id"] = "other"
    check("id mismatch 422", c.put(KEY + ".json", content=json.dumps(bad)).status_code == 422)
    bad = copy.deepcopy(META); bad["camera"]["resolution"] = [100, 100]
    check("resolution mismatch 422", c.put(KEY + ".json", content=json.dumps(bad)).status_code == 422)
    bad = copy.deepcopy(META); del bad["gps"]
    check("missing gps key 422", c.put(KEY + ".json", content=json.dumps(bad)).status_code == 422)
    r = c.put(KEY + ".json", content=json.dumps(META))
    check("json stored", r.status_code == 201 and r.json()["synthetic"] is False)
    check("json retry ok", c.put(KEY + ".json", content=json.dumps(META)).status_code == 200)
    m2 = copy.deepcopy(META); m2["field_id"] = "changed"
    check("json conflict 409", c.put(KEY + ".json", content=json.dumps(m2)).status_code == 409)
    lst = c.get("/api/pi/captures", params={"field_id": "sample-field"}).json()
    check("listed once", len(lst) == 1 and lst[0]["capture_id"] == "20261121T154210123Z_000412")
    img = c.get(lst[0]["image_url"])
    check("image served", img.status_code == 200 and img.content == JPG)
    check("old ESP32 health still works", c.get("/api/health").status_code == 200)
