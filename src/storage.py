"""Netlify Blob storage interface.

Blobs are stored under namespace 'artlist-scraper' (configurable).
Each blob is keyed by SHA1(url) to dedupe.

Usage:
    from src.storage import blob
    url = blob.put('https://example.com/file.mp4', 'music/previews/abc.mp4')
    url = blob.get('https://example.com/file.mp4')  # returns blob URL or None

Uses Netlify Blobs API (https://docs.netlify.com/api/blobs/).
Free tier: no documented meter for at-rest or read/write.
"""
import hashlib
import logging
import os
import json
import urllib.request
import urllib.error
from . import config
from .http_client import request, HttpError

log = logging.getLogger(__name__)


def _key_for_url(url: str) -> str:
    """SHA1(url) as the blob key (dedup)."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _site_token_auth_headers() -> dict:
    """Headers for Netlify API auth."""
    return {
        "Authorization": f"Bearer {config.NETLIFY_TOKEN}",
        "Content-Type": "application/json",
    }


def list_namespaces() -> dict:
    """List all blob namespaces for the site."""
    url = f"https://api.netlify.com/api/v1/sites/{config.NETLIFY_SITE_ID}/blobs"
    status, _, body = request("GET", url, headers=_site_token_auth_headers())
    if status >= 400:
        log.error(f"list_namespaces failed: {status} {body[:200]}")
        return {}
    return json.loads(body)


def list_keys(namespace: str | None = None) -> list[str]:
    """List all keys in a namespace."""
    ns = namespace or config.NETLIFY_BLOB_NAMESPACE
    url = f"https://api.netlify.com/api/v1/sites/{config.NETLIFY_SITE_ID}/blobs/{ns}"
    status, _, body = request("GET", url, headers=_site_token_auth_headers())
    if status >= 400:
        log.error(f"list_keys failed: {status} {body[:200]}")
        return []
    data = json.loads(body)
    # Response: {"blobs": [{"key": "...", ...}]}
    return [b.get("key") for b in data.get("blobs", [])]


def get_metadata(key: str, namespace: str | None = None) -> dict | None:
    """Get metadata for a blob."""
    ns = namespace or config.NETLIFY_BLOB_NAMESPACE
    url = f"https://api.netlify.com/api/v1/sites/{config.NETLIFY_SITE_ID}/blobs/{ns}/{key}"
    status, hdrs, body = request("HEAD", url, headers=_site_token_auth_headers(), allow_redirects=False)
    if status >= 400:
        return None
    # metadata is in headers
    return {k.lower().replace("x-nf-blob-metadata-", ""): v for k, v in hdrs.items() if k.lower().startswith("x-nf-blob-metadata-")}


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream",
              metadata: dict | None = None, namespace: str | None = None) -> bool:
    """Upload bytes to a blob key."""
    ns = namespace or config.NETLIFY_BLOB_NAMESPACE
    url = f"https://api.netlify.com/api/v1/sites/{config.NETLIFY_SITE_ID}/blobs/{ns}/{key}"
    h = _site_token_auth_headers()
    h["Content-Type"] = content_type
    if metadata:
        for k, v in metadata.items():
            h[f"X-NF-Blob-Metadata-{k}"] = str(v)
    # Use direct request to send raw bytes
    body_bytes = data
    req = urllib.request.Request(url, data=body_bytes, method="PUT", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as resp:
            return resp.status < 400
    except urllib.error.HTTPError as e:
        log.error(f"put_bytes failed: {e.code} {e.read()[:200]}")
        return False
    except Exception as e:
        log.error(f"put_bytes error: {e}")
        return False


def get_bytes(key: str, namespace: str | None = None) -> bytes | None:
    """Get blob bytes."""
    ns = namespace or config.NETLIFY_BLOB_NAMESPACE
    url = f"https://api.netlify.com/api/v1/sites/{config.NETLIFY_SITE_ID}/blobs/{ns}/{key}"
    status, _, body = request("GET", url, headers=_site_token_auth_headers())
    if status >= 400:
        return None
    return body


def delete(key: str, namespace: str | None = None) -> bool:
    """Delete a blob."""
    ns = namespace or config.NETLIFY_BLOB_NAMESPACE
    url = f"https://api.netlify.com/api/v1/sites/{config.NETLIFY_SITE_ID}/blobs/{ns}/{key}"
    status, _, _ = request("DELETE", url, headers=_site_token_auth_headers())
    return status < 400


# === Manifest ===

class BlobManifest:
    """Persistent index of mirrored URLs → blob keys.

    Stored as a JSON file at data/_meta/blob_manifest.json
    Map: original_url -> {key, namespace, content_type, size, mirrored_at, source_url}
    """

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
    """Mirror a URL to Netlify blob. Returns manifest entry.

    If already mirrored, returns existing entry.
    """
    m = manifest()
    if m.has(url):
        return m.get(url)

    # Download to memory
    from . import auth
    from .cdn import classify
    cls = classify(url)
    headers = auth.cdn_headers()
    if cls == "signed":
        # signed URLs are on artlist's CDN, need Origin/Referer too
        pass

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
        "mirrored_at": str(int(__import__("time").time())),
        **(extra_metadata or {}),
    }
    ok = put_bytes(key, body, content_type=content_type, metadata=metadata)
    if not ok:
        return {}
    info = {
        "key": key,
        "namespace": config.NETLIFY_BLOB_NAMESPACE,
        "content_type": content_type,
        "size": len(body),
        "mirrored_at": metadata["mirrored_at"],
        "source_url": url,
    }
    m.add(url, info)
    return info


def get_blob_url(key: str, namespace: str | None = None) -> str:
    """Returns the public read URL for a blob key.

    Note: Netlify Blobs are not publicly readable by default; we need to expose them
    via a Netlify Function or use the API URL with auth.
    For UI use, we'll serve them via a small function.
    """
    ns = namespace or config.NETLIFY_BLOB_NAMESPACE
    # The UI will hit /api/blob/<key> which proxies to Netlify
    return f"/api/blob/{ns}/{key}"
