"""Upload a rendered pass to the backend the way the Pi will: each JPEG first, then its JSON sidecar.

  python upload_pass.py --pass-dir out/corn --api http://localhost:8000

Uses only the standard library. Safe to re-run: the backend accepts identical re-uploads.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--pass-dir", type=Path, required=True)
ap.add_argument("--api", default="http://localhost:8000")
a = ap.parse_args()


def put(url, data, ctype):
    req = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


done = skipped = 0
for meta_path in sorted((a.pass_dir / "photos").glob("*/*.json")):
    jpg = meta_path.with_suffix(".jpg")
    if not jpg.is_file():
        skipped += 1          # not rendered (quick runs render a subset)
        continue
    meta = json.loads(meta_path.read_text())
    cid, dev = meta["capture_id"], meta["device_id"]
    date = f"{cid[0:4]}-{cid[4:6]}-{cid[6:8]}"
    base = f"{a.api.rstrip('/')}/api/pi/{dev}/{date}/{cid}"
    for url, path, ctype in ((base + ".jpg", jpg, "image/jpeg"), (base + ".json", meta_path, "application/json")):
        status, body = put(url, path.read_bytes(), ctype)
        if status not in (200, 201):
            print("FAILED", status, url, body[:200], file=sys.stderr)
            sys.exit(1)
    done += 1
print(f"uploaded {done} photos ({skipped} not rendered, skipped)")
