"""Music scraper with combinatorial filtering to break 3000-item pagination cap.

Strategy:
1. For each (sort_type, category, vocalType) combination: paginate normally (3000 items max).
2. If total > 3000: subdivide by bpm range.
3. Merge by songId across all combinations.

Verified vocalTypes: VOCAL, INSTRUMENTAL, VOCAL_AND_INSTRUMENTS
Verified bpm ranges: 0-60, 60-90, 90-120, 120-150, 150-200
"""
import logging
import time
from .. import graphql
from .. import config
from .categories import flatten_categories

log = logging.getLogger(__name__)

SORT_TYPES = ["STAFF_PICKS", "NEWEST"]
VOCAL_TYPES = ["VOCAL_AND_INSTRUMENTS", "VOCAL", "INSTRUMENTAL"]
BPM_RANGES = [(0, 60), (60, 90), (90, 120), (120, 150), (150, 200)]
MAX_PAGE_PER_FILTER = 60  # 60 × 50 = 3000 (server cap)


def _normalize_song(s: dict) -> dict:
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


def _paginate_filter(sort_type: str, take: int, category_ids: list[int] | None,
                     vocal_type: str, bpm_min: int | None, bpm_max: int | None,
                     max_pages: int, label: str) -> tuple[dict[str, dict], int]:
    """Paginate one filter combo. Returns (songs_by_id, total_reported)."""
    songs: dict[str, dict] = {}
    total_reported = 0
    for page in range(1, max_pages + 1):
        try:
            data = graphql.song_list(
                page=page, take=take, sort_type=sort_type,
                vocal_type=vocal_type, category_ids=category_ids,
                bpm_min=bpm_min, bpm_max=bpm_max,
            )
        except Exception as e:
            err_str = str(e)
            if any(s in err_str for s in ["PaginationLimitValidator", "Argument Validation Error",
                                           "BAD_USER_INPUT", "HTTP 400"]):
                break
            log.error(f"    page {page} failed: {e}")
            time.sleep(2)
            continue
        sl = data.get("songList", data) if isinstance(data, dict) else {}
        page_songs = sl.get("songs", []) if isinstance(sl, dict) else []
        total_reported = sl.get("totalResults", total_reported)
        if not page_songs:
            break
        for s in page_songs:
            sid = str(s.get("songId"))
            songs[sid] = _normalize_song(s)
        if len(page_songs) < take:
            break
    log.info(f"    {label}: {len(songs)}/{total_reported}")
    return songs, total_reported


def scrape_one_filter_full(sort_type: str, take: int = 50,
                            category_ids: list[int] | None = None,
                            label: str = "") -> dict[str, dict]:
    """Scrape ALL songs for one sort+category, subdividing by vocalType and bpm if needed."""
    songs: dict[str, dict] = {}

    # Try each vocalType
    for vt in VOCAL_TYPES:
        vt_songs, total = _paginate_filter(
            sort_type, take, category_ids, vt, None, None,
            MAX_PAGE_PER_FILTER, f"{label} vt={vt}"
        )
        songs.update(vt_songs)

        # If this vocalType had > 2900 items (close to cap), subdivide by bpm
        if total > 2900:
            log.info(f"    {label} vt={vt} total={total} > 2900, subdividing by bpm")
            for bpm_min, bpm_max in BPM_RANGES:
                bpm_songs, _ = _paginate_filter(
                    sort_type, take, category_ids, vt, bpm_min, bpm_max,
                    MAX_PAGE_PER_FILTER, f"{label} vt={vt} bpm={bpm_min}-{bpm_max}"
                )
                songs.update(bpm_songs)

    return songs


def scrape_music(max_pages_per_filter: int = MAX_PAGE_PER_FILTER,
                 sort_types: list[str] | None = None,
                 categories: list[dict] | None = None) -> dict:
    """Full music catalog scrape with combinatorial filtering."""
    log.info(f"=== Scraping music catalog (combinatorial mode) ===")

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
    log.info(f"  {len(sub_cats)} sub-categories")

    all_songs: dict[str, dict] = {}

    # Phase 1: per-sort "all" pass (3 vocalTypes)
    for sort_type in (sort_types or SORT_TYPES):
        songs = scrape_one_filter_full(sort_type, take=config.MUSIC_PAGE_SIZE, label=f"sort={sort_type} all")
        log.info(f"  sort={sort_type} (all): collected {len(songs)} unique")
        all_songs.update(songs)
        log.info(f"  running unique total: {len(all_songs)}")

    # Phase 2: per-sub-category pass
    log.info(f"  Phase 2: per-sub-category ({len(sub_cats)} categories)")
    for i, c in enumerate(sub_cats, 1):
        if i % 10 == 0:
            log.info(f"  [{i}/{len(sub_cats)}] running total: {len(all_songs)}")
        songs = scrape_one_filter_full("STAFF_PICKS", take=config.MUSIC_PAGE_SIZE,
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
