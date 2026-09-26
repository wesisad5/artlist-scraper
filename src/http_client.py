"""HTTP client with retry, rate limiting, and JSON helpers."""
import json
import time
import logging
import threading
from typing import Any
import urllib.request
import urllib.error
import urllib.parse

from . import config

log = logging.getLogger(__name__)

# Simple token-bucket rate limiter per host
_rate_lock = threading.Lock()
_last_call: dict[str, float] = {}
_min_interval = 1.0 / config.HTTP_RATE_LIMIT_RPS if config.HTTP_RATE_LIMIT_RPS > 0 else 0


def _wait_rate_limit(host: str) -> None:
    if _min_interval <= 0:
        return
    with _rate_lock:
        now = time.monotonic()
        last = _last_call.get(host, 0)
        wait = _min_interval - (now - last)
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


class HttpError(Exception):
    def __init__(self, status: int, body: str, url: str = ""):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"HTTP {status} {url}: {body[:200]}")


def request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    json_body: Any | None = None,
    cookies: dict | None = None,
    timeout: int | None = None,
    allow_redirects: bool = True,
) -> tuple[int, dict, bytes]:
    """Make an HTTP request. Returns (status, headers, body_bytes).

    Retries on 429, 5xx, and network errors with exponential backoff.
    """
    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params, doseq=True)

    # Build cookie header
    final_headers = dict(headers or {})
    if cookies:
        # filter empty values
        cstr = "; ".join(f"{k}={v}" for k, v in cookies.items() if v)
        if cstr:
            final_headers["Cookie"] = cstr

    body_bytes: bytes | None = None
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")
        final_headers.setdefault("Content-Type", "application/json")

    last_exc: Exception | None = None
    for attempt in range(config.HTTP_MAX_RETRIES):
        _wait_rate_limit(urllib.parse.urlparse(url).netloc)
        try:
            req = urllib.request.Request(url, data=body_bytes, method=method, headers=final_headers)
            try:
                # urllib follows redirects by default for GET/POST; we control via handlers
                opener = urllib.request.build_opener(
                    _NoRedirectHandler() if not allow_redirects else urllib.request.HTTPRedirectHandler()
                )
                with opener.open(req, timeout=timeout or config.HTTP_TIMEOUT) as resp:
                    return resp.status, dict(resp.headers), resp.read()
            except urllib.error.HTTPError as e:
                status = e.code
                resp_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                if status in (429, 500, 502, 503, 504) and attempt < config.HTTP_MAX_RETRIES - 1:
                    wait = min(2 ** attempt * 1.0 + (0.5 * attempt), 30.0)
                    log.warning(f"HTTP {status} on {url} (attempt {attempt+1}/{config.HTTP_MAX_RETRIES}), retry in {wait:.1f}s")
                    time.sleep(wait)
                    continue
                # For 3xx with no-follow, return the redirect
                if 300 <= status < 400 and not allow_redirects:
                    return status, dict(e.headers), resp_body.encode()
                raise HttpError(status, resp_body, url)
        except urllib.error.URLError as e:
            last_exc = e
            if attempt < config.HTTP_MAX_RETRIES - 1:
                wait = min(2 ** attempt * 1.0, 30.0)
                log.warning(f"URLError on {url}: {e}; retry in {wait:.1f}s")
                time.sleep(wait)
                continue
            raise HttpError(0, str(e), url) from e
    raise HttpError(0, str(last_exc), url)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # don't follow


def get_json(url: str, **kw) -> Any:
    status, hdrs, body = request("GET", url, **kw)
    if status >= 400:
        raise HttpError(status, body.decode("utf-8", errors="replace"), url)
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body.decode("utf-8", errors="replace")


def post_json(url: str, payload: Any, **kw) -> Any:
    status, hdrs, body = request("POST", url, json_body=payload, **kw)
    if status >= 400:
        raise HttpError(status, body.decode("utf-8", errors="replace"), url)
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body.decode("utf-8", errors="replace")


def head(url: str, **kw) -> tuple[int, dict]:
    """HEAD request, returns (status, headers)."""
    status, hdrs, _ = request("HEAD", url, allow_redirects=False, **kw)
    return status, hdrs


def download(url: str, dest: str, *, headers: dict | None = None, cookies: dict | None = None,
             max_size_mb: int = 200) -> bool:
    """Download URL to file. Returns True on success."""
    import os
    h = headers or {}
    h.setdefault("Accept", "*/*")
    status, hdrs, body = request("GET", url, headers=h, cookies=cookies, allow_redirects=True)
    if status >= 400:
        log.warning(f"Download failed {url}: HTTP {status}")
        return False
    if len(body) > max_size_mb * 1024 * 1024:
        log.warning(f"Skipping {url}: too large ({len(body)/1024/1024:.1f}MB > {max_size_mb}MB)")
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(body)
    return True
