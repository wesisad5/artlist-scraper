"""SFX scraper: SfxList with pagination.

Note: SfxList response doesn't return totalResults — only 'page' and 'songs'.
We paginate until empty.
"""
import logging
import time
from .. import graphql

log = logging.getLogger(__name__)

SORT_OPTIONS = ["STAFF_PICKS", "RECENT", "MOST_POPULAR"]


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


def scrape_one_sort(sort_by: str, take: int = 50, max_pages: int = 2000,
                    category_ids: str = "") -> tuple[dict[str, dict], int]:
    items: dict[str, dict] = {}
    log.info(f"  sortBy={sort_by} cat={category_ids or '(all)'}")
    for page in range(1, max_pages + 1):
        try:
            data = graphql.sfx_list(page=page, sort_by=sort_by, category_ids=category_ids)
        except Exception as e:
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
        if page % 20 == 0 or page == 1:
            log.info(f"    page {page}: {len(page_songs)} items ({new_count} new). Total unique: {len(items)}")
        # Safety: if 3 pages in a row have no new items, stop
        if new_count == 0 and page > 3:
            log.info(f"    page {page}: no new items, stopping")
            break
    return items, 0


def scrape_sfx(max_pages_per_sort: int = 2000, sort_options: list[str] | None = None) -> dict:
    """Full SFX catalog scrape."""
    log.info(f"=== Scraping SFX catalog ===")
    all_items: dict[str, dict] = {}

    for sb in (sort_options or SORT_OPTIONS):
        items, _ = scrape_one_sort(sb, take=50, max_pages=max_pages_per_sort)
        log.info(f"  sortBy={sb}: collected {len(items)} unique")
        all_items.update(items)
        log.info(f"  running unique total: {len(all_items)}")

    return {
        "asset_type": "sfx",
        "total_unique": len(all_items),
        "sort_options_used": sort_options or SORT_OPTIONS,
        "items": list(all_items.values()),
    }
