"""SFX scraper: SfxList with pagination.

KEY CONSTRAINT: Server caps pagination at page × take ≤ 3000 (same as music).
Strategy:
1. Iterate sort options (STAFF_PICKS, RECENT, MOST_POPULAR) — dedupes by songId.
2. Iterate sub-categories with categoryIds filter — each yields up to 3000 items.

Note: SfxList's categoryIds is a STRING (comma-separated), unlike SongList's [Int].
"""
import logging
import time
from .. import graphql
from .categories import flatten_categories

log = logging.getLogger(__name__)

SORT_OPTIONS = ["STAFF_PICKS", "RECENT", "MOST_POPULAR"]
MAX_PAGE_PER_FILTER = 60  # 60 × 50 = 3000 (server cap)


def _normalize_sfx(s: dict) -> dict:
    return {
        "songId": str(s.get("songId")),
        "songName": s.get("songName"),
        "nameForURL": s.get("nameForURL"),
        "artistId": str(s.get("artistId")) if s.get("artistId") else None,
        "artistName": s.get("artistName"),
        "albumId": str(s.get("albumId")) if s.get("albumId") else None,
        "albumName": s.get("albumName"),
        "albumNameForURL": s.get("albumNameForURL"),
        "albumImageFilePath": s.get("albumImageFilePath"),
        "durationTime": s.get("durationTime"),
        "assetTypeId": s.get("assetTypeId"),
        "sitePlayableFilePath": s.get("sitePlayableFilePath"),
        "waveSurferFilePath": s.get("waveSurferFilePath"),
        "isNew": s.get("isNew"),
        "grandChildCategories": s.get("grandChildCategories") or [],
    }


def scrape_one_filter(sort_by: str, take: int = 50, max_pages: int = MAX_PAGE_PER_FILTER,
                      category_ids: str = "", label: str = "") -> dict[str, dict]:
    """Scrape SFX for one sort + category filter. Respects 3000-item cap."""
    items: dict[str, dict] = {}
    log.info(f"  sortBy={sort_by} cat={label or category_ids or '(all)'}")
    for page in range(1, max_pages + 1):
        try:
            data = graphql.sfx_list(page=page, sort_by=sort_by, category_ids=category_ids)
        except Exception as e:
            if "PaginationLimitValidator" in str(e) or "Argument Validation Error" in str(e):
                log.info(f"    page {page}: pagination cap hit, stopping")
                break
            log.error(f"    page {page} failed: {e}")
            time.sleep(2)
            continue
        sl = data.get("sfxList", {}) if isinstance(data, dict) else {}
        page_songs = sl.get("songs", []) if isinstance(sl, dict) else []
        if not page_songs:
            log.info(f"    page {page}: empty, stopping")
            break
        new_count = 0
        for s in page_songs:
            sid = str(s.get("songId"))
            if sid not in items:
                new_count += 1
            items[sid] = _normalize_sfx(s)
        if page % 10 == 0 or page == 1:
            log.info(f"    page {page}: {len(page_songs)} items ({new_count} new). Total unique: {len(items)}")
        if new_count == 0 and page > 3:
            log.info(f"    page {page}: no new items, stopping")
            break
    return items


def scrape_sfx(max_pages_per_sort: int = MAX_PAGE_PER_FILTER,
               sort_options: list[str] | None = None,
               categories: list[dict] | None = None) -> dict:
    """Full SFX catalog scrape."""
    log.info(f"=== Scraping SFX catalog ===")

    # Fetch categories
    if categories is None:
        try:
            cats = graphql.root_categories("sfx")
        except Exception as e:
            log.error(f"  categories fetch failed: {e}")
            cats = []
    else:
        cats = categories

    flat = flatten_categories(cats)
    sub_cats = [c for c in flat if c["parent"] != ""]
    log.info(f"  {len(sub_cats)} sub-categories to iterate")

    all_items: dict[str, dict] = {}

    # Phase 1: per-sort "all" pass
    for sb in (sort_options or SORT_OPTIONS):
        items = scrape_one_filter(sb, take=50, max_pages=max_pages_per_sort)
        log.info(f"  sortBy={sb} (all): collected {len(items)} unique")
        all_items.update(items)
        log.info(f"  running unique total: {len(all_items)}")

    # Phase 2: per-sub-category pass
    log.info(f"  Phase 2: per-sub-category pagination")
    for i, c in enumerate(sub_cats, 1):
        if i % 5 == 0:
            log.info(f"  [{i}/{len(sub_cats)}] running total: {len(all_items)}")
        # SFX categoryIds is a string
        items = scrape_one_filter("STAFF_PICKS", take=50, max_pages=max_pages_per_sort,
                                   category_ids=str(c["id"]),
                                   label=f"{c['parent']}/{c['name']}")
        all_items.update(items)

    log.info(f"=== SFX scrape complete: {len(all_items)} unique items ===")
    return {
        "asset_type": "sfx",
        "total_unique": len(all_items),
        "sort_options_used": sort_options or SORT_OPTIONS,
        "category_count": len(sub_cats),
        "items": list(all_items.values()),
    }
