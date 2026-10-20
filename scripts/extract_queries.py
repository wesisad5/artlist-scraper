#!/usr/bin/env python3
"""Extract GraphQL queries and trpc queries from HARs in detail."""
import json
import os
import re
from urllib.parse import urlparse, unquote

HAR_DIR = "/home/z/artlist-work/hars"
OUT_DIR = "/home/z/artlist-work/parsed"
os.makedirs(OUT_DIR, exist_ok=True)

graphql_ops = []   # collected GraphQL operations
trpc_ops = []      # collected tRPC operations

for har_file in sorted(os.listdir(HAR_DIR)):
    if not har_file.endswith(".har"):
        continue
    har_path = os.path.join(HAR_DIR, har_file)
    har = json.load(open(har_path))
    entries = har.get("log", {}).get("entries", [])
    for entry in entries:
        req = entry.get("request", {})
        res = entry.get("response", {})
        url = req.get("url", "")
        method = req.get("method", "")
        p = urlparse(url)
        host = p.netloc
        path = p.path
        if "/graphql" in path and method == "POST":
            post = req.get("postData", {}) or {}
            try:
                body = json.loads(post.get("text", "") or "{}")
            except Exception:
                body = {"_raw": post.get("text", "")}
            res_content = res.get("content", {})
            res_text = res_content.get("text", "")
            try:
                res_body = json.loads(res_text) if res_text else None
            except Exception:
                res_body = {"_raw_preview": res_text[:500]} if res_text else None
            graphql_ops.append({
                "har_file": har_file,
                "host": host,
                "path": path,
                "query_string": p.query,
                "operationName": body.get("operationName"),
                "variables": body.get("variables"),
                "query_text": body.get("query", "")[:5000],
                "res_status": res.get("status"),
                "res_body_preview": json.dumps(res_body, indent=2)[:6000] if res_body else "",
            })
        elif "/api/trpc/" in path:
            trpc_text_query = unquote(p.query)
            # parse input field
            m = re.search(r'"input"=([^&]+)', trpc_text_query + '="')
            # simpler: split on & input=
            input_val = None
            if "input=" in trpc_text_query:
                _, rest = trpc_text_query.split("input=", 1)
                # take until &batch= or end
                # but input itself may contain & ... actually it's url-encoded
                input_val = rest.split("&batch=")[0] if "&batch=" in rest else rest
            # the batch field indicates batched queries
            is_batch = "batch=" in trpc_text_query
            # operation names are in path after /api/trpc/
            ops_in_path = path.split("/api/trpc/", 1)[1]
            post = req.get("postData", {}) or {}
            post_body = post.get("text", "")
            res_content = res.get("content", {})
            res_text = res_content.get("text", "")
            try:
                res_body = json.loads(res_text) if res_text else None
            except Exception:
                res_body = {"_raw_preview": res_text[:500]} if res_text else None
            trpc_ops.append({
                "har_file": har_file,
                "host": host,
                "path": path,
                "ops": ops_in_path,
                "is_batch": is_batch,
                "input": input_val,
                "post_body": post_body[:3000],
                "res_status": res.get("status"),
                "res_body_preview": json.dumps(res_body, indent=2)[:6000] if res_body else "",
            })

with open(f"{OUT_DIR}/graphql_ops.json", "w") as f:
    json.dump(graphql_ops, f, indent=2)
with open(f"{OUT_DIR}/trpc_ops.json", "w") as f:
    json.dump(trpc_ops, f, indent=2)

# Print summary
print(f"GraphQL operations: {len(graphql_ops)}")
print(f"tRPC operations: {len(trpc_ops)}")

# Unique GraphQL operation names + the queries
gql_unique = {}
for op in graphql_ops:
    key = (op["host"], op["path"], op.get("operationName") or "?")
    if key not in gql_unique:
        gql_unique[key] = op
print(f"\nUnique GraphQL ops: {len(gql_unique)}")
for (host, path, op_name), op in gql_unique.items():
    print(f"\n--- {host}{path}  op={op_name}  ({op['har_file']}) ---")
    print(f"QUERY:\n{op['query_text'][:1500]}")
    print(f"VARIABLES: {json.dumps(op.get('variables'), indent=2)[:1500] if op.get('variables') else '(none)'}")
    print(f"RESP preview: {op['res_body_preview'][:1000]}")

# Unique tRPC ops (by host + ops)
trpc_unique = {}
for op in trpc_ops:
    key = (op["host"], op["ops"])
    if key not in trpc_unique:
        trpc_unique[key] = op
print(f"\n\nUnique tRPC ops: {len(trpc_unique)}")
for (host, ops), op in sorted(trpc_unique.items()):
    print(f"\n--- {host}  ops={ops[:80]} ({op['har_file']}) ---")
    print(f"  input: {op['input'][:300] if op['input'] else '(none)'}")
    print(f"  res preview: {op['res_body_preview'][:400]}")
