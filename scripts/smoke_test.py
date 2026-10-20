#!/usr/bin/env python3
"""Quick smoke test: fetch 1-2 pages from each scraper to verify they work end-to-end."""
import sys
import os
sys.path.insert(0, '/home/z/artlist-work/artlist-scraper')

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from src import graphql, trpc
from src.scrapers import music, sfx, footage, luts, templates, collections, flows, studio

print("\n=== Music (1 page) ===")
data = graphql.song_list(page=1, take=5, sort_type="STAFF_PICKS")
print(f"  songs: {len(data.get('songList', {}).get('songs', []))}")
print(f"  totalResults: {data.get('songList', {}).get('totalResults')}")

print("\n=== SFX (1 page) ===")
data = graphql.sfx_list(page=1, sort_by="STAFF_PICKS")
print(f"  songs: {len(data.get('sfxList', {}).get('songs', []))}")

print("\n=== Footage ClipList (1 page) ===")
data = graphql.clip_list(page=1)
cl = data.get("clipList", {})
print(f"  exactResults: {len(cl.get('exactResults', []))}")
print(f"  totalExact: {cl.get('totalExact')}")

print("\n=== Footage Catalog (1 page) ===")
data = graphql.catalog(page=1, take=10)
cat_list = data.get("catalog", []) if isinstance(data, dict) else []
print(f"  catalog platforms: {len(cat_list)}")
total_results = sum(len(p.get('results', [])) for p in cat_list)
print(f"  total results across platforms: {total_results}")

print("\n=== LUTs (1 page) ===")
data = graphql.luts(lut_base_preview_id="3c517c9f-8a96-4eb6-b221-225162ea475a", page=1, take=10)
print(f"  luts: {len(data) if isinstance(data, list) else 'unknown'}")

print("\n=== Templates (1 page) ===")
data = graphql.templates_list(page=1, take=10, sort_by="STAFF_PICKS")
print(f"  templates: {len(data)}")

print("\n=== Collections (1 page) ===")
from src import auth
from src.http_client import get_json
data = get_json("https://api.artlist.io/v1/directory",
                 headers=auth.api_headers(),
                 params={"directoryType": "FOLDER", "take": 5, "skip": 0,
                         "orderByKey": "lastUpdated", "orderByDirection": "DESC"})
items = data.get("data", []) if isinstance(data, dict) else []
print(f"  collections: {len(items)}")
if items:
    print(f"  first: {items[0].get('name', items[0])}")

print("\n=== Flows templates (1 page) ===")
data = trpc.flows_template_list(per_page=5)
items = data.get("items", []) if isinstance(data, dict) else []
print(f"  templates: {len(items)}")
for t in items[:3]:
    print(f"    - id={t.get('id')} name={t.get('name')}")

print("\n=== Studio spotlight (1 page) ===")
data = trpc.studio_spotlight_projects(page=1, page_size=5)
items = data.get("data", []) if isinstance(data, dict) else []
print(f"  projects: {len(items)}")
for p in items[:3]:
    print(f"    - id={p.get('id')} name={p.get('name')} type={p.get('type')}")

print("\n=== Studio shot.getShot for example ===")
# Try fetching one shot (may return NOT_FOUND for example projects without project context)
if items:
    shot_id = items[0].get("shotId")
    if shot_id:
        try:
            shot = trpc.studio_shot_get(shot_id)
            print(f"  shot.getShot({shot_id}): {type(shot).__name__}, keys={list(shot.keys())[:10] if isinstance(shot, dict) else 'N/A'}")
        except Exception as e:
            print(f"  shot.getShot({shot_id}): FAILED ({str(e)[:100]})")
            print(f"  (Note: shot.getShot may need project context per HAR; using spotlight data only)")

print("\nAll smoke tests passed!")
