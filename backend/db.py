import json
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import config

_lock = threading.RLock()
_conn = None
_conn_path = None


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def conn():
    global _conn, _conn_path
    path = str(config.DB_PATH)
    if _conn is None or _conn_path != path:
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn_path = path
        _conn.executescript("""
        CREATE TABLE IF NOT EXISTS captures(
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          id TEXT UNIQUE, data TEXT NOT NULL, zone_id TEXT, received_at TEXT);
        CREATE INDEX IF NOT EXISTS ix_zone ON captures(zone_id);
        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
        """)
        _conn.commit()
    return _conn


def load_demo():
    try:
        with open(config.DEMO_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _demo_image_info(image_file):
    try:
        from PIL import Image
        p = config.DEMO_IMAGES / image_file
        with Image.open(p) as im:
            return {"width": im.width, "height": im.height, "bytes": p.stat().st_size}
    except Exception:
        return {"width": None, "height": None, "bytes": None}


def seed_if_needed():
    """Seed from demo JSON once (empty DB, not yet seeded)."""
    with _lock:
        c = conn()
        if c.execute("SELECT v FROM meta WHERE k='seeded'").fetchone():
            return False
        if c.execute("SELECT COUNT(*) FROM captures").fetchone()[0] > 0:
            return False
        demo = load_demo()
        if not demo or not demo.get("captures"):
            return False
        caps = sorted(demo["captures"], key=lambda x: (x.get("captured_at") or x.get("received_at") or "", str(x.get("id"))))
        for s in caps:
            ep = s.get("edge_prediction") or {}
            rec = {
                "id": str(s.get("id")),
                "device_id": s.get("device_id"),
                "field_id": s.get("field_id"),
                "zone_id": s.get("zone_id"),
                "reported_zone_id": s.get("reported_zone_id", s.get("zone_id")),
                "captured_at": s.get("captured_at"),
                "received_at": s.get("received_at") or s.get("captured_at") or now_iso(),
                "capture_uptime_ms": s.get("capture_uptime_ms"),
                "position": s.get("position"),
                "image_url": f"/api/captures/{s.get('id')}/image",
                "image": _demo_image_info(s["image_file"]) if s.get("image_file") else {"width": None, "height": None, "bytes": None},
                "edge_prediction": {
                    "label": ep.get("label"), "confidence": ep.get("confidence"),
                    "model_version": ep.get("model_version"),
                    "label_known": ep.get("label") in config.ALLOWED_LABELS},
                "inference_ms": s.get("inference_ms"),
                "ingest_ms": s.get("ingest_ms"),
                "sensors": s.get("sensors") or {"soil_moisture_pct": None, "air_temp_c": None, "humidity_pct": None, "light_lux": None},
                "review": {"status": (s.get("review") or {}).get("status", "unreviewed"),
                           "note": (s.get("review") or {}).get("note"),
                           "reviewed_at": (s.get("review") or {}).get("reviewed_at")},
                "provenance": s.get("provenance", "simulated"),
                "t": s.get("t"),
                "_image_file": s.get("image_file"),
            }
            c.execute("INSERT OR IGNORE INTO captures(id,data,zone_id,received_at) VALUES(?,?,?,?)",
                      (rec["id"], json.dumps(rec), rec["zone_id"], rec["received_at"]))
        c.execute("INSERT OR REPLACE INTO meta VALUES('seeded','1')")
        c.commit()
        return True


def public(rec):
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def insert_capture(rec):
    with _lock:
        c = conn()
        c.execute("INSERT INTO captures(id,data,zone_id,received_at) VALUES(?,?,?,?)",
                  (rec["id"], json.dumps(rec), rec["zone_id"], rec["received_at"]))
        c.commit()


def get_capture(cid):
    with _lock:
        r = conn().execute("SELECT data FROM captures WHERE id=?", (cid,)).fetchone()
    return json.loads(r["data"]) if r else None


def update_capture(rec):
    with _lock:
        c = conn()
        c.execute("UPDATE captures SET data=? WHERE id=?", (json.dumps(rec), rec["id"]))
        c.commit()


def list_captures(zone_id=None, limit=None, internal=False):
    q = "SELECT data FROM captures"
    args = []
    if zone_id:
        q += " WHERE zone_id=?"
        args.append(zone_id)
    q += " ORDER BY seq DESC"
    if limit:
        q += " LIMIT ?"
        args.append(int(limit))
    with _lock:
        rows = conn().execute(q, args).fetchall()
    out = [json.loads(r["data"]) for r in rows]
    return out if internal else [public(x) for x in out]


def count():
    with _lock:
        return conn().execute("SELECT COUNT(*) FROM captures").fetchone()[0]
