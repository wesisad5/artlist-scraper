"""Netlify Blob storage interface (two-step presigned URL flow).

Flow:
1. PUT https://api.netlify.com/api/v1/sites/{site_id}/blobs/{store}/{key}
   → Returns presigned S3 URL
2. PUT {presigned_s3_url} with actual data
   → Uploads to S3

Read flow:
1. GET https://api.netlify.com/api/v1/sites/{site_id}/blobs/{store}/{key}
   → Returns presigned S3 URL (30s expiry)
2. GET {presigned_s3_url}
   → Downloads from S3
"""
import hashlib
import json
import logging
import os
import time
import urllib.request
import urllib.error
from . import config

log = logging.getLogger(__name__)

NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN", "")
NETLIFY_SITE_ID = os.getenv("NETLIFY_SITE_ID", "39481ca6-1e9c-4714-b161-dc63b94cbe11")  # aigc-scrape-runner
NETLIFY_BLOB_NAMESPACE = os.getenv("NETLIFY_BLOB_NAMESPACE", "artlist-scraper")
NETLIFY_API = "https://api.netlify.com/api/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NETLIFY_TOKEN}",
        "Content-Type": "application/json",
    }


def _key_for_url(url: str) -> str:
    """SHA1(url) as the blob key (dedup)."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
    """Upload bytes to a blob key via two-step presigned URL flow."""
    # Step 1: Get presigned S3 URL from Netlify API
    url = f"{NETLIFY_API}/sites/{NETLIFY_SITE_ID}/blobs/{NETLIFY_BLOB_NAMESPACE}/{key}"
    req = urllib.request.Request(url, method="PUT", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read())
            s3_url = resp_data.get("url")
            if not s3_url:
                log.error(f"put_bytes: no S3 URL in response")
                return False
    except urllib.error.HTTPError as e:
        log.error(f"put_bytes step1 failed: {e.code} {e.read()[:200]}")
        return False
    except Exception as e:
        log.error(f"put_bytes step1 error: {e}")
        return False

    # Step 2: Upload to S3 via presigned URL
    req2 = urllib.request.Request(s3_url, data=data, method="PUT", headers={
        "Content-Type": content_type,
    })
    try:
        with urllib.request.urlopen(req2, timeout=120) as resp:
            return resp.status < 400
    except Exception as e:
        log.error(f"put_bytes step2 (S3 upload) error: {e}")
        return False


def get_bytes(key: str) -> bytes | None:
    """Get blob bytes via two-step presigned URL flow."""
    # Step 1: Get presigned S3 URL
    url = f"{NETLIFY_API}/sites/{NETLIFY_SITE_ID}/blobs/{NETLIFY_BLOB_NAMESPACE}/{key}"
    req = urllib.request.Request(url, method="GET", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read())
            s3_url = resp_data.get("url")
            if not s3_url:
                return None
    except Exception as e:
        log.error(f"get_bytes step1 error: {e}")
        return None

    # Step 2: Download from S3
    req2 = urllib.request.Request(s3_url, method="GET")
    try:
        with urllib.request.urlopen(req2, timeout=120) as resp:
            return resp.read()
    except Exception as e:
        log.error(f"get_bytes step2 error: {e}")
        return None


def list_keys() -> list[str]:
    """List all keys in the blob store."""
    url = f"{NETLIFY_API}/sites/{NETLIFY_SITE_ID}/blobs/{NETLIFY_BLOB_NAMESPACE}"
    req = urllib.request.Request(url, method="GET", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            # This returns a presigned S3 URL for listing
            resp_data = json.loads(resp.read())
            s3_url = resp_data.get("url")
            if not s3_url:
                return []
    except Exception as e:
        log.error(f"list_keys step1 error: {e}")
        return []

    # Step 2: List from S3
    req2 = urllib.request.Request(s3_url, method="GET")
    try:
        with urllib.request.urlopen(req2, timeout=30) as resp:
            # S3 listing is XML
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.read())
            ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            keys = []
            for contents in root.findall(".//s3:Contents", ns):
                key_elem = contents.find("s3:Key", ns)
                if key_elem is not None:
                    # Key format: {site_id}/production/{store}/{key}
                    k = key_elem.text
                    parts = k.split("/")
                    if len(parts) >= 4:
                        keys.append("/".join(parts[3:]))
            return keys
    except Exception as e:
        log.error(f"list_keys step2 error: {e}")
        return []


def delete(key: str) -> bool:
    """Delete a blob."""
    url = f"{NETLIFY_API}/sites/{NETLIFY_SITE_ID}/blobs/{NETLIFY_BLOB_NAMESPACE}/{key}"
    req = urllib.request.Request(url, method="DELETE", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status < 400
    except Exception as e:
        log.error(f"delete error: {e}")
        return False


# === Manifest ===

class BlobManifest:
    """Persistent index of mirrored URLs → blob keys."""
    MANIFEST_PATH = config.META_DIR / "blob_manifest.json"

    def __init__(self):
        if self.MANIFEST_PATH.exists():
            self._data = json.loads(self.MANIFEST_PATH.read_text())
        else:
            self._data = {"urls": {}}

    def save(self):
        self.MANIFEST_PATH.write_text(json.dumps(self._data, indent=2))

    def has(self, url: str) -> bool:
        return url in self._data["urls"]

    def get(self, url: str) -> dict | None:
        return self._data["urls"].get(url)

    def add(self, url: str, info: dict):
        self._data["urls"][url] = info
        self.save()

    def all(self) -> dict:
        return self._data["urls"]


_manifest: BlobManifest | None = None


def manifest() -> BlobManifest:
    global _manifest
    if _manifest is None:
        _manifest = BlobManifest()
    return _manifest


def mirror_url(url: str, *, content_type: str = "application/octet-stream",
               extra_metadata: dict | None = None, max_size_mb: int = 100) -> dict:
    """Mirror a URL to Netlify blob. Returns manifest entry."""
    m = manifest()
    if m.has(url):
        return m.get(url)

    from . import auth
    from .cdn import classify
    from .http_client import request

    cls = classify(url)
    headers = auth.cdn_headers()

    status, _, body = request("GET", url, headers=headers)
    if status >= 400:
        log.warning(f"mirror_url: failed to fetch {url}: {status}")
        return {}
    if len(body) > max_size_mb * 1024 * 1024:
        log.info(f"mirror_url: skipping {url} ({len(body)/1024/1024:.1f}MB > {max_size_mb}MB)")
        return {}

    key = _key_for_url(url)
    metadata = {
        "source_url": url,
        "mirrored_at": str(int(time.time())),
        **(extra_metadata or {}),
    }
    ok = put_bytes(key, body, content_type=content_type)
    if not ok:
        return {}
    info = {
        "key": key,
        "namespace": NETLIFY_BLOB_NAMESPACE,
        "content_type": content_type,
        "size": len(body),
        "mirrored_at": metadata["mirrored_at"],
        "source_url": url,
    }
    m.add(url, info)
    return info
