import asyncio
import io
import json
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

import config
import db
import pi_ingest
from scoring import zone_health

app = FastAPI(title=config.PRODUCT_NAME)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(pi_ingest.router)

ZONE_RE = re.compile(r"^[A-L](?:1[0-2]|[1-9])$")
SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")
REQUIRED = ["X-Device-ID", "X-Field-ID", "X-Zone-ID", "X-Edge-Label", "X-Edge-Confidence", "X-Capture-Uptime-Ms"]
EMPTY_SENSORS = {"soil_moisture_pct": None, "air_temp_c": None, "humidity_pct": None, "light_lux": None}

subscribers = set()


def publish(event, data):
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    for q in list(subscribers):
        q.put_nowait(msg)


def clean(v):
    return SAFE_RE.sub("", (v or "").strip())[:64]


def err(status, body):
    return JSONResponse(body, status_code=status)


@app.on_event("startup")
def _startup():
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    db.seed_if_needed()


def demo():
    db.seed_if_needed()
    return db.load_demo() or {}


# ---------------------------------------------------------------- captures
@app.post("/api/captures")
async def post_capture(request: Request):
    t0 = time.perf_counter()
    h = request.headers
    for name in REQUIRED:
        if not (h.get(name) or "").strip():
            return err(400, {"error": "missing_header", "header": name})
    try:
        conf = float((h["X-Edge-Confidence"]).strip())
        if conf != conf:
            raise ValueError
    except ValueError:
        return err(400, {"error": "bad_confidence", "header": "X-Edge-Confidence"})
    conf = max(0.0, min(1.0, conf))
    try:
        uptime = int(float(h["X-Capture-Uptime-Ms"].strip()))
    except ValueError:
        return err(400, {"error": "bad_header", "header": "X-Capture-Uptime-Ms"})

    cl = h.get("content-length")
    if cl and cl.isdigit() and int(cl) > config.MAX_UPLOAD_BYTES:
        return err(413, {"error": "payload_too_large", "max_bytes": config.MAX_UPLOAD_BYTES})
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > config.MAX_UPLOAD_BYTES:
            return err(413, {"error": "payload_too_large", "max_bytes": config.MAX_UPLOAD_BYTES})
    body = bytes(body)
    if body[:3] != b"\xff\xd8\xff":
        return err(415, {"error": "not_jpeg"})
    try:
        with Image.open(io.BytesIO(body)) as im:
            im.load()
            width, height = im.width, im.height
            if im.format != "JPEG":
                raise ValueError
    except Exception:
        return err(415, {"error": "not_jpeg"})

    label = clean(h["X-Edge-Label"]).lower()
    raw_zone = clean(h["X-Zone-ID"])
    zone_mapped = False
    if raw_zone in config.DEMO_ZONE_MAP:
        zone = config.DEMO_ZONE_MAP[raw_zone]
    elif ZONE_RE.match(raw_zone.upper()):
        zone = raw_zone.upper()
    else:
        zone = config.DEFAULT_ZONE
        zone_mapped = True

    captured_at = None
    ts = (h.get("X-Timestamp-Unix") or "").strip()
    if ts:
        try:
            captured_at = datetime.fromtimestamp(float(ts), timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        except (ValueError, OverflowError, OSError):
            captured_at = None
    inf = None
    try:
        if (h.get("X-Inference-Ms") or "").strip():
            inf = float(h["X-Inference-Ms"])
    except ValueError:
        inf = None
    provenance = "simulated" if (h.get("X-Provenance") or "").strip().lower() == "simulated" else "real-device"

    cid = "cap-" + uuid.uuid4().hex[:12]
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (config.UPLOADS_DIR / f"{cid}.jpg").write_bytes(body)
    now = db.now_iso()
    rec = {
        "id": cid,
        "device_id": clean(h["X-Device-ID"]),
        "field_id": clean(h["X-Field-ID"]),
        "zone_id": zone,
        "reported_zone_id": raw_zone,
        "zone_mapped": zone_mapped,
        "captured_at": captured_at,
        "received_at": now,
        "capture_uptime_ms": uptime,
        "position": None,
        "image_url": f"/api/captures/{cid}/image",
        "image": {"width": width, "height": height, "bytes": len(body)},
        "edge_prediction": {"label": label, "confidence": conf,
                            "model_version": clean(h.get("X-Model-Version")) or None,
                            "label_known": label in config.ALLOWED_LABELS},
        "inference_ms": inf,
        "ingest_ms": None,
        "sensors": dict(EMPTY_SENSORS),
        "review": {"status": "unreviewed", "note": None, "reviewed_at": None},
        "provenance": provenance,
        "t": int(time.time() * 1000),
    }
    rec["ingest_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    db.insert_capture(rec)
    publish("capture", db.public(rec))
    return JSONResponse({"capture_id": cid, "stored": True, "zone_id": zone, "image_url": rec["image_url"]}, status_code=201)


@app.get("/api/captures")
def list_captures(zone_id: str = "", limit: int = 100):
    limit = max(1, min(limit, 1000))
    return db.list_captures(zone_id or None, limit)


@app.get("/api/captures/{cid}/image")
def capture_image(cid: str):
    rec = db.get_capture(cid)
    if not rec:
        return err(404, {"error": "not_found"})
    p = config.UPLOADS_DIR / f"{re.sub(r'[^A-Za-z0-9._-]', '', cid)}.jpg"
    if not p.is_file() and rec.get("_image_file"):
        p = config.DEMO_IMAGES / re.sub(r"[^A-Za-z0-9._-]", "", rec["_image_file"])
    if not p.is_file():
        return err(404, {"error": "image_missing"})
    return FileResponse(p, media_type="image/jpeg")


@app.post("/api/captures/{cid}/review")
async def review(cid: str, request: Request):
    try:
        body = await request.json()
        assert isinstance(body, dict)
    except Exception:
        return err(400, {"error": "bad_json"})
    status = body.get("status")
    if status not in config.REVIEW_STATUSES:
        return err(400, {"error": "bad_status", "allowed": list(config.REVIEW_STATUSES)})
    rec = db.get_capture(cid)
    if not rec:
        return err(404, {"error": "not_found"})
    note = body.get("note")
    rec["review"] = {"status": status, "note": str(note)[:500] if note is not None else None, "reviewed_at": db.now_iso()}
    db.update_capture(rec)
    pub = db.public(rec)
    publish("review", pub)
    return pub


# ---------------------------------------------------------------- field data
def computed_zones(d=None):
    d = d if d is not None else demo()
    by_zone = {}
    for c in db.list_captures(internal=False):
        by_zone.setdefault(c["zone_id"], []).append(c)
    out = []
    for z in d.get("zones", []):
        z = dict(z)
        z["health"] = zone_health(by_zone.get(z.get("id"), []), z.get("health"))
        out.append(z)
    return out


@app.get("/api/field")
def get_field():
    f = dict(demo().get("field") or {"id": "field-1", "rows": 12, "cols": 12})
    f["product_name"] = config.PRODUCT_NAME
    f["demo_zone_map"] = config.DEMO_ZONE_MAP
    return f


@app.get("/api/zones")
def get_zones():
    return computed_zones()


@app.get("/api/machine")
def get_machine():
    return demo().get("machine")


@app.get("/api/actions")
def get_actions():
    return demo().get("actions", [])


@app.get("/api/demo")
def get_demo():
    d = dict(demo())
    d["field"] = get_field()
    d["zones"] = computed_zones(d)
    d["captures"] = db.list_captures()
    return d


# ---------------------------------------------------------------- events / health
@app.get("/api/events")
async def events(request: Request):
    q = asyncio.Queue()
    subscribers.add(q)

    async def gen():
        try:
            yield ": connected\n\n"
            while True:
                try:
                    yield await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                if await request.is_disconnected():
                    break
        finally:
            subscribers.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/health")
def health():
    caps = db.list_captures()
    devs = {}
    for c in reversed(caps):  # oldest -> newest
        d = devs.setdefault(c["device_id"], {"device_id": c["device_id"], "captures": 0, "_inf": [], "_ing": []})
        d["captures"] += 1
        d["last_seen"] = c["received_at"]
        d["last_uptime_ms"] = c["capture_uptime_ms"]
        d["provenance"] = c["provenance"]
        if c.get("inference_ms") is not None:
            d["_inf"].append(c["inference_ms"])
        if c.get("ingest_ms") is not None:
            d["_ing"].append(c["ingest_ms"])
    out = []
    for d in devs.values():
        inf, ing = d.pop("_inf"), d.pop("_ing")
        d["avg_inference_ms"] = round(sum(inf) / len(inf), 2) if inf else None
        d["avg_ingest_ms"] = round(sum(ing) / len(ing), 2) if ing else None
        out.append(d)
    return {"ok": True, "captures": len(caps), "last_capture_at": caps[0]["received_at"] if caps else None, "devices": out}


# ---------------------------------------------------------------- static
if config.DIST_DIR.is_dir():
    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            return err(404, {"error": "not_found"})
        f = (config.DIST_DIR / path).resolve()
        if path and f.is_file() and config.DIST_DIR.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(config.DIST_DIR / "index.html")
else:
    if config.PUBLIC_DATA.is_dir():
        app.mount("/data", StaticFiles(directory=config.PUBLIC_DATA), name="data")
    if config.PUBLIC_DEMO.is_dir():
        app.mount("/demo", StaticFiles(directory=config.PUBLIC_DEMO), name="demo")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
