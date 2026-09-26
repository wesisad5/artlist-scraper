"""CDN URL classification and handling.

Permlink hosts (no expiry, no signature):
- cms-public-artifacts.artlist.io/{base64}  → 302 → /content/...  (works with Origin/Referer)
- cms-public-artifacts.artlist.io/content/...  (direct path)
- artlist-albums.imgix.net/...
- artlist-content-images.imgix.net/...
- artlist-templates.imgix.net/...
- artlist-artistpage.imgix.net/...
- artlist-dev.imgix.net/...

Signed URL hosts (long-lived ~10yr expiry but signed):
- cms-toolkit-artifacts.artlist.io/...?Expires=...&Key-Pair-Id=...&Signature=...
- cms-artifacts.artlist.io/...?Expires=...&Key-Pair-Id=...&Signature=...
- artlist-studio-proxy.imgix.net/{encoded_signed_url}  (proxy wrapping signed URL)

For permlink URLs we just store the URL.
For signed URLs we mirror to Netlify blob.
"""
import re
import urllib.parse
from . import config

PERMLINK_HOSTS = {
    "cms-public-artifacts.artlist.io",
    "artlist-albums.imgix.net",
    "artlist-content-images.imgix.net",
    "artlist-templates.imgix.net",
    "artlist-artistpage.imgix.net",
    "artlist-dev.imgix.net",
}

SIGNED_HOSTS = {
    "cms-toolkit-artifacts.artlist.io",
    "cms-artifacts.artlist.io",
}

# Proxy host wraps another URL (which may itself be signed)
PROXY_HOSTS = {
    "artlist-studio-proxy.imgix.net",
}


def classify(url: str) -> str:
    """Classify a URL as 'permlink', 'signed', or 'proxy'.

    - permlink: stable URL, no expiry
    - signed: signed URL with Expires/Signature
    - proxy: imgix proxy wrapping another URL
    """
    if not url:
        return "permlink"
    p = urllib.parse.urlparse(url)
    host = p.netloc
    if host in PERMLINK_HOSTS:
        # cms-public-artifacts may have base64 paths but no signature — still permlink
        return "permlink"
    if host in PROXY_HOSTS:
        return "proxy"
    if host in SIGNED_HOSTS:
        return "signed"
    # Heuristic: any URL with Expires=...&Signature=... is signed
    if "Expires=" in (p.query or "") and "Signature=" in (p.query or ""):
        return "signed"
    # Default: treat as permlink if no signature params
    return "permlink"


def get_expiry(url: str) -> int | None:
    """Extract Expires value from a signed URL (unix timestamp)."""
    if classify(url) != "signed":
        return None
    p = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(p.query)
    exp_str = qs.get("Expires", [None])[0]
    if exp_str:
        try:
            return int(exp_str)
        except ValueError:
            return None
    return None


def needs_mirror(url: str, *, max_expiry_days: int = 365) -> bool:
    """Decide if a URL needs to be mirrored to Netlify blob.

    Permlinks: never mirror (just store URL).
    Signed URLs: mirror if expiry is within max_expiry_days.
    Proxy URLs: extract wrapped URL and recurse.
    """
    cls = classify(url)
    if cls == "permlink":
        return False
    if cls == "signed":
        exp = get_expiry(url)
        if exp is None:
            return True  # unknown expiry, mirror to be safe
        import time
        days_until_expiry = (exp - int(time.time())) / 86400
        return days_until_expiry < max_expiry_days
    if cls == "proxy":
        # Extract wrapped URL from path
        p = urllib.parse.urlparse(url)
        wrapped = urllib.parse.unquote(p.path.lstrip("/"))
        if wrapped.startswith("http"):
            return needs_mirror(wrapped, max_expiry_days=max_expiry_days)
        return True
    return False


def extract_proxy_target(url: str) -> str | None:
    """For an artlist-studio-proxy.imgix.net URL, return the wrapped target URL."""
    p = urllib.parse.urlparse(url)
    if p.netloc not in PROXY_HOSTS:
        return None
    wrapped = urllib.parse.unquote(p.path.lstrip("/"))
    if wrapped.startswith("http"):
        return wrapped
    return None


def normalize_cdn_url(url: str) -> str:
    """Normalize a CDN URL.

    For cms-public-artifacts.artlist.io/{base64} URLs, decode the base64 path
    to get the canonical /content/... form (which is what the 302 redirects to).
    This makes the URL more transparent / debuggable.
    """
    if not url:
        return url
    p = urllib.parse.urlparse(url)
    if p.netloc == "cms-public-artifacts.artlist.io":
        # If path doesn't start with /content/, try base64 decode
        if not p.path.startswith("/content/"):
            try:
                import base64
                # path may have leading /
                encoded = p.path.lstrip("/")
                # base64url decode
                decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
                if decoded.startswith("content/"):
                    return url.replace(p.path, "/" + decoded, 1)
            except Exception:
                pass
    return url
