"""Music scraper: SongList with pagination.

KEY CONSTRAINT: Server caps pagination at page × take ≤ 3000 ("PaginationLimitValidator").
With take=50, max page = 60. To cover the full 35,512 songs:
1. Iterate sort types (STAFF_PICKS, RECENT, MOST_POPULAR, BEST_MATCH) — dedupes by songId.
2. Iterate sub-categories with filterCategories=[cat_id] — each yields up to 3000 songs.
"""
import logging
import time
from .. import graphql
from .. import config
from .categories import flatten_categories

log = logging.getLogger(__name__)

SORT_TYPES = ["STAFF_PICKS", "NEWEST"]  # only valid enum values

# Server cap: page × take ≤ 3000. With take=50, max page = 60.
MAX_PAGE_PER_FILTER = 60


def scrape_one_filter(sort_type: str, take: int = 50, max_pages: int = MAX_PAGE_PER_FILTER,
                      category_ids: list[int] | None = None,
                      vocal_type: str = "VOCAL_AND_INSTRUMENTS",
                      excluded_song_ids: list[str] | None = None,
                      label: str = "") -> dict[str, dict]:
    """Scrape songs for one sort + category filter combo. Respects 3000-item cap."""
    songs: dict[str, dict] = {}
    cat_label = f"cat={category_ids[:3]}" if category_ids else "all"
    log.info(f"  sort={sort_type} {cat_label} label={label} take={take}")
    for page in range(1, max_pages + 1):
        try:
            data = graphql.song_list(
                page=page, take=take, sort_type=sort_type,
                vocal_type=vocal_type, category_ids=category_ids,
                excluded_song_ids=excluded_song_ids,
            )
        except Exception as e:
            err_str = str(e)
            # Stop on pagination cap or any 400 validation error (don't retry)
            if "PaginationLimitValidator" in err_str or "Argument Validation Error" in err_str \
               or "BAD_USER_INPUT" in err_str or "HTTP 400" in err_str:
                log.info(f"    page {page}: stopping this filter ({err_str[:120]})")
                break
            log.error(f"    page {page} failed: {e}")
            time.sleep(2)
            continue
        sl = data.get("songList", data) if isinstance(data, dict) else {}
        page_songs = sl.get("songs", []) if isinstance(sl, dict) else []
        if not page_songs:
            log.info(f"    page {page}: empty, stopping")
            break
        new_count = 0
        for s in page_songs:
            sid = str(s.get("songId"))
            if sid not in songs:
                new_count += 1
            songs[sid] = _normalize_song(s)
        if page % 10 == 0 or page == 1:
            log.info(f"    page {page}: {len(page_songs)} songs ({new_count} new). Total unique: {len(songs)}")
        if len(page_songs) < take:
            break
        # If we've collected this filter's worth and no new items, stop
        if new_count == 0 and page > 3:
            log.info(f"    page {page}: no new items, stopping")
            break
    return songs


def _normalize_song(s: dict) -> dict:
    """Normalize a song dict for storage."""
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
        "albumThumbFilePath": s.get("albumThumbFilePath"),
        "duration": s.get("duration"),
        "durationTime": s.get("durationTime"),
        "explicit": s.get("explicit"),
        "isOriginal": s.get("isOriginal"),
        "isNew": s.get("isNew"),
        "isPreRelease": s.get("isPreRelease"),
        "officialReleaseDate": s.get("officialReleaseDate"),
        "numberOfStems": s.get("numberOfStems"),
        "assetTypeId": s.get("assetTypeId"),
        "sitePlayableFilePath": s.get("sitePlayableFilePath"),
        "waveSurferFilePath": s.get("waveSurferFilePath"),
        "genreCategories": s.get("genreCategories") or [],
        "hook30Start": s.get("hook30Start"),
        "hook30End": s.get("hook30End"),
        "featuredArtists": s.get("featuredArtists"),
        "primaryArtists": s.get("primaryArtists"),
        "lyrics": s.get("lyrics"),
        "originalVersionID": s.get("originalVersionID"),
    }


def scrape_music(max_pages_per_filter: int = MAX_PAGE_PER_FILTER,
                 sort_types: list[str] | None = None,
                 categories: list[dict] | None = None) -> dict:
    """Full music catalog scrape.

    Strategy:
    1. Fetch music categories (if not provided).
    2. For each sort type: paginate "all" (up to 3000 items).
    3. For each sub-category: paginate with filter (up to 3000 items each).
    4. Merge by songId.
    """
    log.info(f"=== Scraping music catalog ===")

    # Fetch categories if not provided
    if categories is None:
        try:
            cats = graphql.root_categories("music")
        except Exception as e:
            log.error(f"  categories fetch failed: {e}")
            cats = []
    else:
        cats = categories

    flat = flatten_categories(cats)
    sub_cats = [c for c in flat if c["parent"] != ""]
    log.info(f"  {len(sub_cats)} sub-categories to iterate")

    all_songs: dict[str, dict] = {}

    # Phase 1: per-sort "all" pass
    for sort_type in (sort_types or SORT_TYPES):
        songs = scrape_one_filter(sort_type, take=config.MUSIC_PAGE_SIZE, max_pages=max_pages_per_filter)
        log.info(f"  sort={sort_type} (all): collected {len(songs)} unique")
        all_songs.update(songs)
        log.info(f"  running unique total: {len(all_songs)}")

    # Phase 2: per-sub-category pass (using STAFF_PICKS sort, which seems most diverse)
    log.info(f"  Phase 2: per-sub-category pagination")
    for i, c in enumerate(sub_cats, 1):
        if i % 10 == 0:
            log.info(f"  [{i}/{len(sub_cats)}] running total: {len(all_songs)}")
        songs = scrape_one_filter("STAFF_PICKS", take=config.MUSIC_PAGE_SIZE,
                                   max_pages=max_pages_per_filter,
                                   category_ids=[c["id"]],
                                   label=f"{c['parent']}/{c['name']}")
        all_songs.update(songs)

    log.info(f"=== Music scrape complete: {len(all_songs)} unique songs ===")
    return {
        "asset_type": "music",
        "total_unique": len(all_songs),
        "sort_types_used": sort_types or SORT_TYPES,
        "category_count": len(sub_cats),
        "songs": list(all_songs.values()),
    }
