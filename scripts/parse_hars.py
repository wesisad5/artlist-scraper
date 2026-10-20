#!/usr/bin/env python3
"""Parse all HAR files and extract unique API endpoints, auth tokens, and request patterns."""
import json
import os
import re
from collections import defaultdict
from urllib.parse import urlparse

HAR_DIR = "/home/z/artlist-work/hars"
OUT_DIR = "/home/z/artlist-work/parsed"
os.makedirs(OUT_DIR, exist_ok=True)

# Aggregate data
all_entries = []
endpoints_by_host = defaultdict(set)
api_calls = []  # only api/graphql/fetch endpoints, not static assets
auth_tokens_seen = set()
cookies_seen = {}
request_samples = {}  # endpoint -> first request detail

# patterns for "interesting" endpoints
API_HOSTS = set()
INTERESTING_PATH_PATTERNS = [
    re.compile(r"/api/", re.I),
    re.compile(r"/graphql", re.I),
    re.compile(r"\.graphql$", re.I),
    re.compile(r"/v\d+/", re.I),
    re.compile(r"/search", re.I),
    re.compile(r"/catalog", re.I),
    re.compile(r"/assets?", re.I),
    re.compile(r"/items?", re.I),
    re.compile(r"/list", re.I),
    re.compile(r"/preview", re.I),
    re.compile(r"/download", re.I),
    re.compile(r"/studio", re.I),
    re.compile(r"/flow", re.I),
    re.compile(r"/project", re.I),
    re.compile(r"/template", re.I),
    re.compile(r"/music|/sfx|/footage|/lut|/video", re.I),
]

STATIC_EXT = {".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
              ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webm", ".webp",
              ".map", ".html", ".htm"}


def is_interesting(url, method, content_type):
    p = urlparse(url)
    path = p.path.lower()
    if any(path.endswith(ext) for ext in STATIC_EXT):
        return False
    if method == "OPTIONS":
        return False
    # always interesting if matches pattern
    for pat in INTERESTING_PATH_PATTERNS:
        if pat.search(path):
            return True
    # anything with query string AND not static-looking
    if p.query and "." not in path.split("/")[-1]:
        return True
    if "json" in (content_type or "").lower():
        return True
    return False


for har_file in sorted(os.listdir(HAR_DIR)):
    if not har_file.endswith(".har"):
        continue
    har_path = os.path.join(HAR_DIR, har_file)
    with open(har_path) as f:
        try:
            har = json.load(f)
        except json.JSONDecodeError as e:
            print(f"FAILED to parse {har_file}: {e}")
            continue
    entries = har.get("log", {}).get("entries", [])
    print(f"\n=== {har_file} ({len(entries)} entries) ===")
    interesting_count = 0
    for entry in entries:
        req = entry.get("request", {})
        res = entry.get("response", {})
        url = req.get("url", "")
        method = req.get("method", "")
        status = res.get("status", 0)
        req_headers = {h["name"].lower(): h["value"] for h in req.get("headers", [])}
        res_headers = {h["name"].lower(): h["value"] for h in res.get("headers", [])}
        content_type = res_headers.get("content-type", "")
        req_content_type = req_headers.get("content-type", "")

        p = urlparse(url)
        host = p.netloc
        path = p.path

        endpoints_by_host[host].add(path)

        # capture auth tokens
        auth_header = req_headers.get("authorization", "")
        if auth_header and "bearer" in auth_header.lower():
            token = auth_header.split(" ", 1)[-1].strip()
            if token:
                auth_tokens_seen.add(token)
        # cookie-based
        cookie = req_headers.get("cookie", "")
        if cookie:
            for kv in cookie.split(";"):
                if "=" in kv:
                    k, v = kv.strip().split("=", 1)
                    cookies_seen[k.strip()] = v.strip()

        if not is_interesting(url, method, content_type):
            continue

        # Get request body
        post_data = req.get("postData", {})
        body_text = post_data.get("text", "") if post_data else ""
        # Get response body (truncated)
        res_content = res.get("content", {})
        res_text = res_content.get("text", "")
        res_size = res_content.get("size", 0)
        if res_text and len(res_text) > 4000:
            res_text = res_text[:4000] + "...[TRUNCATED]"

        api_calls.append({
            "har_file": har_file,
            "method": method,
            "url": url,
            "host": host,
            "path": path,
            "query": p.query,
            "status": status,
            "req_content_type": req_content_type,
            "res_content_type": content_type,
            "req_authorization": "yes" if auth_header else "no",
            "req_body": body_text[:2000] if body_text else "",
            "res_body_preview": res_text[:1500] if res_text else "",
            "res_size": res_size,
        })
        interesting_count += 1

        # Store sample per endpoint
        endpoint_key = f"{method} {host}{path}"
        if endpoint_key not in request_samples:
            request_samples[endpoint_key] = {
                "method": method,
                "host": host,
                "path": path,
                "query": p.query,
                "req_headers_subset": {k: v for k, v in req_headers.items()
                                        if k in ("authorization", "cookie", "x-csrf-token",
                                                 "x-artlist-token", "x-api-key", "x-requested-with",
                                                 "origin", "referer")},
                "req_body": body_text[:3000],
                "res_status": status,
                "res_content_type": content_type,
                "res_body_preview": res_text[:3000],
                "har_file": har_file,
            }
    print(f"  interesting API calls: {interesting_count}")

# Save outputs
with open(f"{OUT_DIR}/all_api_calls.json", "w") as f:
    json.dump(api_calls, f, indent=2)

with open(f"{OUT_DIR}/request_samples.json", "w") as f:
    json.dump(request_samples, f, indent=2)

with open(f"{OUT_DIR}/hosts.json", "w") as f:
    json.dump({h: sorted(list(ps)) for h, ps in endpoints_by_host.items()}, f, indent=2)

# print summary
print("\n\n========== SUMMARY ==========")
print(f"\nTotal interesting API calls: {len(api_calls)}")
print(f"Unique endpoints (method+host+path): {len(request_samples)}")
print(f"Auth tokens seen: {len(auth_tokens_seen)}")
for i, tok in enumerate(auth_tokens_seen):
    print(f"  Token {i+1} (last 20 chars): ...{tok[-20:]} (length {len(tok)})")
print(f"\nCookies seen ({len(cookies_seen)}):")
for k, v in sorted(cookies_seen.items()):
    print(f"  {k} = {v[:50]}{'...' if len(v) > 50 else ''}")
print(f"\nHosts:")
for h in sorted(endpoints_by_host.keys()):
    print(f"  {h} ({len(endpoints_by_host[h])} unique paths)")
