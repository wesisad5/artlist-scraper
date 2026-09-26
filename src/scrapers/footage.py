"""Footage scraper: ClipList with pagination.

Footage has ~857,760 clips — too many to page through sequentially with take=50.
That'd be ~17,000 pages. We need to segment by category to fit in pagination limits.

Strategy:
1. Fetch root categories for footage.
2. For each sub-category, paginate ClipList with filterCategories=[cat_id].
3. Also paginate without filter for the "all" view (may not complete; we save what we get).
4. Merge by clip id.

Also fetch Catalog (collection of stories) — separate endpoint.
"""
import logging
import time
from .. import graphql
from .. import config
from .categories import flatten_categories

log = logging.getLogger(__name__)


def _normalize_clip(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "clipName": c.get("clipName"),
        "clipNameForUrl": c.get("clipNameForUrl"),
        "thumbnailUrl": c.get("thumbnailUrl"),
        "clipPath": c.get("clipPath"),
        "isInFavorites": c.get("isInFavorites"),
        "isInDownloadHistory": c.get("isInDownloadHistory"),
        "isNew": c.get("isNew"),
        "isVfx": c.get("isVfx"),
        "isInFolder": c.get("isInFolder"),
        "filmMakerDisplayName": c.get("filmMakerDisplayName"),
        "filmMakerId": c.get("filmMakerId"),
        "filmMakerNameForUrl": c.get("filmMakerNameForUrl"),
        "storyId": c.get("storyId"),
        "storyName": c.get("storyName"),
        "storyNameForURL": c.get("storyNameForURL"),
        "isLicensed": c.get("isLicensed"),
        "isOriginal": c.get("isOriginal"),
        "duration": c.get("duration"),
        "width": c.get("width"),
        "height": c.get("height"),
        "orientation": c.get("orientation"),
        "isMadeWithAi": c.get("isMadeWithAi"),
        "geoLocationGridDisplay": c.get("geoLocationGridDisplay"),
        "aiFrames": c.get("aiFrames") or [],
        "availableFormats": c.get("availableFormats") or [],
    }


def scrape_clips_for_filter(filter_categories: list[int], label: str = "",
                             max_pages: int = 60, take: int = 50) -> dict[int, dict]:
    """Paginate ClipList for a given filter. Respects 3000-item cap.

    With take=50, max page = 60 (3000 items). Use category filtering for full coverage.
    """
    clips: dict[int, dict] = {}
    log.info(f"  filter={label or filter_categories} take={take}")
    last_total = 0
    for page in range(1, max_pages + 1):
        try:
            data = graphql.clip_list(page=page, filter_categories=filter_categories, take=take)
        except Exception as e:
            if "PaginationLimitValidator" in str(e) or "Argument Validation Error" in str(e):
                log.info(f"    page {page}: pagination cap hit, stopping")
                break
            log.error(f"    page {page} failed: {e}")
            time.sleep(2)
            continue
        cl = data.get("clipList", {})
        page_clips = cl.get("exactResults", [])
        total = cl.get("totalExact", 0)
        if not page_clips:
            log.info(f"    page {page}: empty, stopping (total was {total})")
            break
        new_count = 0
        for c in page_clips:
            cid = c.get("id")
            if cid not in clips:
                new_count += 1
            clips[cid] = _normalize_clip(c)
        if page % 10 == 0 or page == 1:
            log.info(f"    page {page}: {len(page_clips)} clips ({new_count} new). Total unique: {len(clips)}/{total}")
        last_total = total
        if len(page_clips) < take:
            break
        if new_count == 0 and page > 3:
            log.info(f"    page {page}: no new items, stopping")
            break
    log.info(f"  filter={label or filter_categories}: {len(clips)} unique / {last_total} reported total")
    return clips


def scrape_footage(categories: list[dict] | None = None, max_pages_per_filter: int = 60) -> dict:
    """Full footage scrape. Respects 3000-item pagination cap.

    Strategy:
    1. Fetch footage categories.
    2. "All" pass (no filter) — catches top 3000 clips.
    3. Per-sub-category pass — each yields up to 3000 clips.
    4. Merge by clip id.
    """
    log.info(f"=== Scraping footage catalog ===")

    if categories is None:
        categories = graphql.root_categories("footage")

    flat = flatten_categories(categories)
    log.info(f"  {len(flat)} categories")

    all_clips: dict[int, dict] = {}

    # First pass: "all" without filter (best match sort=1)
    log.info(f"  Pass 1: no filter (sort=BestMatch)")
    clips = scrape_clips_for_filter([], label="ALL", max_pages=max_pages_per_filter)
    all_clips.update(clips)

    # Second pass: per sub-category
    sub_cats = [c for c in flat if c["parent"] != ""]
    log.info(f"  Pass 2: {len(sub_cats)} sub-categories")
    for i, c in enumerate(sub_cats, 1):
        if i % 20 == 0:
            log.info(f"  [{i}/{len(sub_cats)}] running total: {len(all_clips)}")
        clips = scrape_clips_for_filter([c["id"]], label=f"{c['parent']}/{c['name']}", max_pages=max_pages_per_filter)
        all_clips.update(clips)

    # Catalog endpoint (returns list of platforms, each with results)
    log.info(f"  Fetching footage catalog (top charts / trending stories)")
    stories = []
    for page in range(1, 50):
        try:
            data = graphql.catalog(page=page, take=100)
        except Exception as e:
            log.error(f"  catalog page {page} failed: {e}")
            break
        # Response shape: {"catalog": [{"platformCode": "spotify", "results": [...]}, ...]}
        cat_list = data.get("catalog", []) if isinstance(data, dict) else []
        if not cat_list:
            break
        page_added = 0
        for platform in cat_list:
            for r in platform.get("results", []) or []:
                r["_platform"] = platform.get("platformCode")
                stories.append(r)
                page_added += 1
        if page_added == 0:
            break
        if page % 5 == 0:
            log.info(f"    catalog page {page}: {page_added} items, total {len(stories)}")
        if page_added < 100:
            break

    return {
        "asset_type": "footage",
        "total_unique_clips": len(all_clips),
        "total_stories": len(stories),
        "categories": flat,
        "clips": list(all_clips.values()),
        "stories": stories,
    }
