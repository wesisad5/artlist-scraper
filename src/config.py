"""Configuration and environment variables."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (the artlist-scraper/ dir, one level up from src/)
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# === Auth ===
ARTLIST_JWT = os.getenv("ARTLIST_JWT", "")
# Flows (flows.artlist.io) cookies
ARTLIST_FLOWS_SESSION_TOKEN = os.getenv("ARTLIST_FLOWS_SESSION_TOKEN") or os.getenv("ARTLIST_SESSION_TOKEN", "")
ARTLIST_FLOWS_CF_CLEARANCE = os.getenv("ARTLIST_FLOWS_CF_CLEARANCE") or os.getenv("ARTLIST_CF_CLEARANCE", "")
ARTLIST_FLOWS_CF_BM = os.getenv("ARTLIST_FLOWS_CF_BM") or os.getenv("ARTLIST_CF_BM", "")
# Studio (studio.artlist.io) cookies — different session token + csrf token
ARTLIST_STUDIO_SESSION_TOKEN = os.getenv("ARTLIST_STUDIO_SESSION_TOKEN") or os.getenv("ARTLIST_SESSION_TOKEN", "")
ARTLIST_STUDIO_CF_CLEARANCE = os.getenv("ARTLIST_STUDIO_CF_CLEARANCE") or os.getenv("ARTLIST_CF_CLEARANCE", "")
ARTLIST_STUDIO_CF_BM = os.getenv("ARTLIST_STUDIO_CF_BM") or os.getenv("ARTLIST_CF_BM", "")
ARTLIST_STUDIO_CSRF_TOKEN = os.getenv("ARTLIST_STUDIO_CSRF_TOKEN") or os.getenv("ARTLIST_CSRF_TOKEN", "")
# Common
ARTLIST_USER_SESSION = os.getenv("ARTLIST_USER_SESSION", "51a766f0-b846-4993-9fa7-dd5781cfac8d")
ARTLIST_VISITOR_ID = os.getenv("ARTLIST_VISITOR_ID", "91dad878-352d-4e02-9ced-90aff9c4e3d9")
ARTLIST_USER_ID = os.getenv("ARTLIST_USER_ID", "49619108")

# === HTTP ===
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
)
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "60"))
HTTP_RATE_LIMIT_RPS = float(os.getenv("HTTP_RATE_LIMIT_RPS", "2.0"))  # be polite
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "5"))

# === Hosts ===
HOST_ARTLIST = "https://artlist.io"
HOST_API = "https://api.artlist.io"
HOST_SEARCH_API_V1 = "https://search-api.artlist.io/v1/graphql"
HOST_SEARCH_API_V2 = "https://search-api.artlist.io/v2/graphql"
HOST_FLOWS = "https://flows.artlist.io"
HOST_STUDIO = "https://studio.artlist.io"
HOST_CMS_PUBLIC = "https://cms-public-artifacts.artlist.io"

# === Storage ===
NETLIFY_SITE_ID = os.getenv("NETLIFY_SITE_ID", "")
NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN", "")
NETLIFY_BLOB_NAMESPACE = os.getenv("NETLIFY_BLOB_NAMESPACE", "artlist-scraper")

# === Paths ===
DATA_DIR = PROJECT_ROOT / "data"
CATALOG_DIR = DATA_DIR / "catalog"
AI_DIR = DATA_DIR / "ai"
META_DIR = DATA_DIR / "_meta"
BLOB_MIRROR_DIR = DATA_DIR / "blob_mirror"
for d in (CATALOG_DIR, AI_DIR, META_DIR, BLOB_MIRROR_DIR):
    d.mkdir(parents=True, exist_ok=True)

# === Run ===
RUN_TIMESTAMP = os.getenv("RUN_TIMESTAMP", "")

# Asset type IDs (from HAR analysis)
# assetTypeId: 1=music, 2=sfx, 14=footage, 16=lut, 18=template, 22=stem
ASSET_TYPE_MUSIC = 1
ASSET_TYPE_SFX = 2
ASSET_TYPE_FOOTAGE = 14
ASSET_TYPE_LUT = 16
ASSET_TYPE_TEMPLATE = 18
ASSET_TYPE_STEM = 22

# Search page sizes
MUSIC_PAGE_SIZE = 50      # default 20 in HAR; bump for speed
SFX_PAGE_SIZE = 50
FOOTAGE_PAGE_SIZE = 50    # HAR uses 50
LUT_PAGE_SIZE = 50
TEMPLATE_PAGE_SIZE = 50

# Sort options (from HAR analysis)
SORT_STAFF_PICKS = "STAFF_PICKS"
SORT_RECENT = "RECENT"
SORT_BEST_MATCH = "BEST_MATCH"
SORT_MOST_POPULAR = "MOST_POPULAR"
