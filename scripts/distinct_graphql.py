#!/usr/bin/env python3
"""Extract DISTINCT GraphQL query texts (ignore op name) to see actual search queries."""
import json
import os
import re
from urllib.parse import urlparse

HAR_DIR = "/home/z/artlist-work/hars"

# Group by hash of query text
queries_by_text = {}  # query_text -> [list of (har_file, variables, response_preview)]

for har_file in sorted(os.listdir(HAR_DIR)):
    if not har_file.endswith(".har"):
        continue
    har_path = os.path.join(HAR_DIR, har_file)
    har = json.load(open(har_path))
    for entry in har.get("log", {}).get("entries", []):
        req = entry.get("request", {})
        res = entry.get("response", {})
        url = req.get("url", "")
        method = req.get("method", "")
        p = urlparse(url)
        if "/graphql" not in p.path or method != "POST":
            continue
        post = req.get("postData", {}) or {}
        try:
            body = json.loads(post.get("text", "") or "{}")
        except Exception:
            continue
        qtext = body.get("query", "").strip()
        if not qtext:
            continue
        # normalize whitespace for grouping
        key = re.sub(r"\s+", " ", qtext)[:300]
        if key not in queries_by_text:
            queries_by_text[key] = {
                "first_har": har_file,
                "query_text": qtext,
                "samples": []
            }
        if len(queries_by_text[key]["samples"]) < 3:
            res_text = (res.get("content", {}) or {}).get("text", "")
            try:
                res_body = json.loads(res_text) if res_text else None
            except Exception:
                res_body = None
            queries_by_text[key]["samples"].append({
                "har_file": har_file,
                "operationName": body.get("operationName"),
                "variables": body.get("variables"),
                "res_status": res.get("status"),
                "res_body_preview": json.dumps(res_body, indent=2)[:2500] if res_body else "",
            })

# Output
out = []
for i, (key, info) in enumerate(queries_by_text.items(), 1):
    out.append(f"\n{'='*70}\nQUERY #{i}  (first seen in {info['first_har']})\n{'='*70}")
    out.append(f"\nQUERY TEXT:\n{info['query_text'][:3000]}")
    for s in info["samples"]:
        out.append(f"\n--- sample ({s['har_file']}, op={s['operationName']}) ---")
        out.append(f"VARIABLES: {json.dumps(s['variables'], indent=2)[:2000] if s['variables'] else '(none)'}")
        out.append(f"RESP preview: {s['res_body_preview'][:2000]}")

with open("/home/z/artlist-work/parsed/distinct_graphql_queries.txt", "w") as f:
    f.write("\n".join(out))

print(f"Distinct GraphQL queries: {len(queries_by_text)}")
print("\n".join(out[:5000]))
