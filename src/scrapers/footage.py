"""Footage scraper with combinatorial filtering to break 3000-item pagination cap.

Footage has 857,760 clips — way more than 3000. We subdivide via:
  category × orientation × frameRate × duration_bucket

Each combination yields <3000 clips, so we can fully paginate.
"""
import logging
import time
from .. import graphql
from .. import config
from .categories import flatten_categories

log = logging.getLogger(__name__)

ORIENTATIONS = ["HORIZONTAL", "VERTICAL"]
FRAME_RATES = ["FPS_24", "FPS_25", "FPS_30"]
# Duration buckets in milliseconds (1000 = 1s)
DURATION_BUCKETS = [
    (0, 5000),        # 0-5s
    (5000, 10000),    # 5-10s
    (10000, 20000),   # 10-20s
    (20000, 30000),   # 20-30s
    (30000, 60000),   # 30-60s
    (60000, 120000),  # 1-2min
    (120000, 300000), # 2-5min
    (300000, 999999999),  # 5min+
]


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
                             max_pages: int = 60, take: int = 50,
                             orientation: str | None = None,
                             frame_rate: str | None = None,
                             duration_min: int | None = None,
                             duration_max: int | None = None) -> dict[int, dict]:
    """Paginate ClipList for a given filter. Respects 3000-item cap."""
    clips: dict[int, dict] = {}
    log.info(f"  filter={label} orient={orientation} fps={frame_rate} dur={duration_min}-{duration_max}")
    last_total = 0
    for page in range(1, max_pages + 1):
        try:
            data = graphql.clip_list(
                page=page, filter_categories=filter_categories,
                orientation=orientation, frame_rate=frame_rate,
                duration_min=duration_min, duration_max=duration_max,
            )
        except Exception as e:
            err_str = str(e)
            if "PaginationLimitValidator" in err_str or "Argument Validation Error" in err_str \
               or "BAD_USER_INPUT" in err_str or "HTTP 400" in err_str:
                log.info(f"    page {page}: stopping ({err_str[:80]})")
                break
            log.error(f"    page {page} failed: {e}")
            time.sleep(2)
            continue
        cl = data.get("clipList", {})
        page_clips = cl.get("exactResults", [])
        total = cl.get("totalExact", 0)
        if not page_clips:
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
            break
    log.info(f"  filter={label} o={orientation} fps={frame_rate} dur={duration_min}-{duration_max}: {len(clips)} unique / {last_total} reported")
    return clips, last_total


def scrape_footage(categories: list[dict] | None = None, max_pages_per_filter: int = 60) -> dict:
    """Full footage scrape with combinatorial filtering.

    Strategy:
    1. "All" pass (no filter) — catches top 3000 clips.
    2. Per-sub-category pass — each yields up to 3000 clips.
    3. For sub-categories where total > 3000: subdivide by orientation × fps × duration.
    4. Merge by clip id.
    """
    log.info(f"=== Scraping footage catalog (combinatorial mode) ===")

    if categories is None:
        categories = graphql.root_categories("footage")

    flat = flatten_categories(categories)
    sub_cats = [c for c in flat if c["parent"] != ""]
    log.info(f"  {len(sub_cats)} sub-categories")

    all_clips: dict[int, dict] = {}

    # Pass 1: "all" (no filter)
    log.info(f"  Pass 1: no filter")
    clips, total_all = scrape_clips_for_filter([], label="ALL", max_pages=max_pages_per_filter)
    all_clips.update(clips)
    log.info(f"  Pass 1 done: {len(all_clips)} unique (total reported: {total_all})")

    # Pass 2: per-sub-category
    log.info(f"  Pass 2: per-sub-category")
    for i, c in enumerate(sub_cats, 1):
        if i % 10 == 0:
            log.info(f"  [{i}/{len(sub_cats)}] running total: {len(all_clips)}")
        clips, total = scrape_clips_for_filter([c["id"]], label=f"{c['parent']}/{c['name']}",
                                                max_pages=max_pages_per_filter)
        all_clips.update(clips)

        # If this category had > 3000 items, subdivide by orientation × fps × duration
        if total > 2900:  # close to cap, likely more
            log.info(f"    subdividing {c['name']} (total={total} > 2900)")
            for orient in ORIENTATIONS:
                for fps in FRAME_RATES:
                    for dmin, dmax in DURATION_BUCKETS:
                        clips, _ = scrape_clips_for_filter(
                            [c["id"]],
                            label=f"{c['parent']}/{c['name']}",
                            max_pages=max_pages_per_filter,
                            orientation=orient, frame_rate=fps,
                            duration_min=dmin, duration_max=dmax,
                        )
                        all_clips.update(clips)

    # Catalog endpoint (trending stories)
    log.info(f"  Fetching footage catalog (trending stories)")
    stories = []
    for page in range(1, 50):
        try:
            data = graphql.catalog(page=page, take=100)
        except Exception as e:
            log.error(f"  catalog page {page} failed: {e}")
            break
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

    log.info(f"=== Footage scrape complete: {len(all_clips)} unique clips, {len(stories)} stories ===")
    return {
        "asset_type": "footage",
        "total_unique_clips": len(all_clips),
        "total_stories": len(stories),
        "categories": flat,
        "clips": list(all_clips.values()),
        "stories": stories,
    }
