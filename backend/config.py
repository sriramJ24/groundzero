import os
from pathlib import Path

PRODUCT_NAME = "GroundZero"
DEMO_ZONE_MAP = {"demo-zone-1": "F6"}
MAX_UPLOAD_BYTES = 2_000_000
PORT = 8000

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DB_PATH = Path(os.environ.get("GROUNDZERO_DB", BASE_DIR / "groundzero.db"))
UPLOADS_DIR = Path(os.environ.get("GROUNDZERO_UPLOADS", BASE_DIR / "uploads"))
DEMO_JSON = ROOT_DIR / "frontend" / "src" / "data" / "demo" / "field.json"
DEMO_IMAGES = ROOT_DIR / "frontend" / "public" / "demo" / "images"
DIST_DIR = ROOT_DIR / "frontend" / "dist"
PUBLIC_DATA = ROOT_DIR / "frontend" / "public" / "data"
PUBLIC_DEMO = ROOT_DIR / "frontend" / "public" / "demo"
DEFAULT_ZONE = "F6"
ALLOWED_LABELS = ("healthy", "discoloration", "wilting")
REVIEW_STATUSES = ("unreviewed", "approved", "rejected", "needs-review")
