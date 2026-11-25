"""Pi ingestion, following docs/capture-format.md.

The Pi (or a simulated pass) uploads the JPEG first, then the JSON sidecar as the ready marker:

  PUT /api/pi/{device_id}/{date}/{capture_id}.jpg     body = JPEG bytes
  PUT /api/pi/{device_id}/{date}/{capture_id}.json    body = sidecar JSON

Both are idempotent: the same bytes again -> 200, different bytes under the same key -> 409 conflict.
A JSON whose JPEG is missing is refused (409, jpeg_missing) so the Pi retries later.

  GET /api/pi/captures?field_id=...&limit=...         ingested captures, oldest sequence first
  GET /api/pi/{device_id}/{date}/{capture_id}.jpg     the original photo
"""
import hashlib
import io
import json
import re
import sqlite3
import threading
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

import config
import db

router = APIRouter()
_lock = threading.RLock()

ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CAPTURE_RE = re.compile(r"^(\d{8}T\d{9}Z)_(\d{6,})$")
MAX_JPEG = 30_000_000
MAX_JSON = 64_000
TIME_SOURCES = {"gps", "ntp", "rtc", "unsynced"}
TILT_SOURCES = {"installed", "imu", "none"}


def root() -> Path:
    return config.UPLOADS_DIR / "pi"


def conn():
    c = db.conn()
    c.execute("""CREATE TABLE IF NOT EXISTS pi_captures(
        device_id TEXT, capture_id TEXT, seq INTEGER, field_id TEXT, date TEXT, utc TEXT,
        synthetic INTEGER, meta TEXT, jpeg_sha256 TEXT, received_at TEXT,
        PRIMARY KEY(device_id, capture_id))""")
    return c


def err(status, body):
    return JSONResponse(body, status_code=status)


def check_key(device_id, date, capture_id):
    if not ID_RE.match(device_id):
        return "bad_device_id"
    if not DATE_RE.match(date):
        return "bad_date"
    m = CAPTURE_RE.match(capture_id)
    if not m:
        return "bad_capture_id"
    ts = m.group(1)
    if f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}" != date:
        return "date_mismatch"
    return None


async def read_body(request, limit):
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            return None
    return bytes(body)


def store(path: Path, data: bytes):
    """Write once. Returns 'created', 'same' or 'conflict'."""
    if path.exists():
        return "same" if path.read_bytes() == data else "conflict"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return "created"


def validate(meta, device_id, capture_id, jpeg_size):
    if not isinstance(meta, dict):
        return "not_object"
    for k in ("format_version", "capture_id", "device_id", "field_id", "time", "camera", "gps"):
        if k not in meta:
            return f"missing:{k}"
    if meta["capture_id"] != capture_id or meta["device_id"] != device_id:
        return "id_mismatch"
    if not isinstance(meta["field_id"], str) or not meta["field_id"]:
        return "bad_field_id"
    t = meta["time"]
    if not isinstance(t, dict) or t.get("source") not in TIME_SOURCES or not isinstance(t.get("utc"), str):
        return "bad_time"
    if not isinstance(t.get("monotonic_ms"), int) or t["monotonic_ms"] < 0 or not t.get("boot_id"):
        return "bad_time"
    cam = meta["camera"]
    if not isinstance(cam, dict) or cam.get("tilt_source") not in TILT_SOURCES:
        return "bad_camera"
    if (cam.get("tilt_deg") is None) != (cam.get("tilt_source") == "none"):
        return "bad_camera_tilt"
    res = cam.get("resolution")
    if not (isinstance(res, list) and len(res) == 2 and list(res) == list(jpeg_size)):
        return "resolution_mismatch"
    if meta["gps"] is not None and not ({"lat", "lon", "fix", "source"} <= set(meta["gps"])):
        return "bad_gps"
    return None


@router.put("/api/pi/{device_id}/{date}/{name}")
async def put_file(device_id: str, date: str, name: str, request: Request):
    stem, _, ext = name.rpartition(".")
    bad = check_key(device_id, date, stem)
    if bad or ext not in ("jpg", "json"):
        return err(400, {"error": bad or "bad_extension"})
    folder = root() / device_id / date
    if ext == "jpg":
        body = await read_body(request, MAX_JPEG)
        if body is None:
            return err(413, {"error": "payload_too_large", "max_bytes": MAX_JPEG})
        try:
            with Image.open(io.BytesIO(body)) as im:
                im.load()
                if im.format != "JPEG":
                    raise ValueError
        except Exception:
            return err(415, {"error": "not_jpeg"})
        with _lock:
            r = store(folder / f"{stem}.jpg", body)
        if r == "conflict":
            return err(409, {"error": "conflict", "detail": "a different JPEG is already stored under this key"})
        return JSONResponse({"stored": True, "status": r}, status_code=201 if r == "created" else 200)

    body = await read_body(request, MAX_JSON)
    if body is None:
        return err(413, {"error": "payload_too_large", "max_bytes": MAX_JSON})
    jpg = folder / f"{stem}.jpg"
    if not jpg.is_file():
        return err(409, {"error": "jpeg_missing", "detail": "upload the JPEG first"})
    try:
        meta = json.loads(body)
    except Exception:
        return err(400, {"error": "bad_json"})
    with Image.open(jpg) as im:
        size = (im.width, im.height)
    bad = validate(meta, device_id, stem, size)
    if bad:
        return err(422, {"error": "invalid_metadata", "detail": bad})
    with _lock:
        r = store(folder / f"{stem}.json", body)
        if r == "conflict":
            return err(409, {"error": "conflict", "detail": "different metadata is already stored under this key"})
        c = conn()
        try:
            c.execute("INSERT INTO pi_captures VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (device_id, stem, int(CAPTURE_RE.match(stem).group(2)), meta["field_id"], date, meta["time"]["utc"],
                       1 if meta.get("synthetic") else 0, json.dumps(meta), hashlib.sha256(jpg.read_bytes()).hexdigest(),
                       db.now_iso()))
            c.commit()
        except sqlite3.IntegrityError:
            pass
    rec = public(device_id, date, stem, meta)
    if r == "created":
        try:
            from app import publish
            publish("pi_capture", rec)
        except Exception:
            pass
    return JSONResponse(rec, status_code=201 if r == "created" else 200)


def public(device_id, date, capture_id, meta):
    return {"device_id": device_id, "capture_id": capture_id, "field_id": meta["field_id"], "utc": meta["time"]["utc"],
            "synthetic": bool(meta.get("synthetic")), "image_url": f"/api/pi/{device_id}/{date}/{capture_id}.jpg",
            "meta_url": f"/api/pi/{device_id}/{date}/{capture_id}.json"}


@router.get("/api/pi/captures")
def list_pi(field_id: str = "", limit: int = 5000):
    limit = max(1, min(limit, 20000))
    c = conn()
    q = "SELECT device_id, date, capture_id, meta FROM pi_captures"
    args = []
    if field_id:
        q += " WHERE field_id = ?"
        args.append(field_id)
    q += " ORDER BY device_id, seq LIMIT ?"
    args.append(limit)
    return [public(r[0], r[1], r[2], json.loads(r[3])) for r in c.execute(q, args).fetchall()]


@router.get("/api/pi/{device_id}/{date}/{name}")
def get_file(device_id: str, date: str, name: str):
    stem, _, ext = name.rpartition(".")
    if check_key(device_id, date, stem) or ext not in ("jpg", "json"):
        return err(400, {"error": "bad_key"})
    p = root() / device_id / date / name
    if not p.is_file():
        return err(404, {"error": "not_found"})
    return FileResponse(p, media_type="image/jpeg" if ext == "jpg" else "application/json")
