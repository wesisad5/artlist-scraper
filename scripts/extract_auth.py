#!/usr/bin/env python3
"""Extract full session cookies and JWT from HARs (don't truncate)."""
import json
import os
from urllib.parse import urlparse

HAR_DIR = "/home/z/artlist-work/hars"
SECRET_DIR = "/home/z/artlist-work/secrets"
os.makedirs(SECRET_DIR, exist_ok=True)

# Find the most recent / complete cookie set + JWT
best_cookie_set = {}  # host -> {cookie_name: value}
best_jwt = None

for har_file in sorted(os.listdir(HAR_DIR)):
    if not har_file.endswith(".har"):
        continue
    har = json.load(open(os.path.join(HAR_DIR, har_file)))
    for entry in har.get("log", {}).get("entries", []):
        req = entry.get("request", {})
        url = req.get("url", "")
        host = urlparse(url).netloc
        # Cookies can be in 'cookies' array or 'Cookie' header
        cookies = {}
        for c in req.get("cookies", []):
            cookies[c["name"]] = c["value"]
        # also parse from headers (some HARs only have the header)
        for h in req.get("headers", []):
            if h["name"].lower() == "cookie":
                # split on '; ' but values may contain '='
                for kv in h["value"].split("; "):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        if k not in cookies:
                            cookies[k] = v
        if cookies:
            if host not in best_cookie_set or len(cookies) > len(best_cookie_set[host]):
                best_cookie_set[host] = cookies
        # JWT
        for h in req.get("headers", []):
            if h["name"].lower() == "authorization" and "bearer" in h["value"].lower():
                tok = h["value"].split(" ", 1)[-1].strip()
                if not best_jwt or len(tok) > len(best_jwt):
                    best_jwt = tok

# Save
with open(f"{SECRET_DIR}/JWT.txt", "w") as f:
    f.write(best_jwt or "")
print(f"Saved JWT (length {len(best_jwt or '')})")

with open(f"{SECRET_DIR}/COOKIES_BY_HOST.json", "w") as f:
    json.dump(best_cookie_set, f, indent=2)
print(f"Saved cookies for hosts: {list(best_cookie_set.keys())}")

# Print key cookie names per host
for host, cookies in best_cookie_set.items():
    if host in ("api.mixpanel.com", "browser-intake-datadoghq.com", "cdn.segment.com",
                "sdk.split.io", "auth.split.io", "streaming.split.io"):
        continue
    interesting = [k for k in cookies if any(s in k.lower() for s in ["session", "token", "csrf", "auth", "cf_clearance", "__cf_bm"])]
    if interesting:
        print(f"\n{host}:")
        for k in interesting:
            v = cookies[k]
            print(f"  {k}: len={len(v)}  preview={v[:60]}...")
