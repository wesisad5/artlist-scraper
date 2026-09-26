"""Music scraper: SongList with pagination.

Strategy:
- Use sort_type STAFF_PICKS first (returns totalResults).
- Paginate through all pages (take=50, page=1..N).
- totalResults is reported but may be approximate; we keep paging until empty or duplicate.
- Also iterate sort types (STAFF_PICKS, RECENT, BEST_MATCH, MOST_POPULAR) and merge by songId to maximize coverage.
- Also iterate category IDs (genre, mood, etc.) to ensure we hit everything if pagination caps out.
"""
import logging
import time
from .. import graphql
from .. import config

log = logging.getLogger(__name__)

SORT_TYPES = ["STAFF_PICKS", "RECENT", "MOST_POPULAR", "BEST_MATCH"]


def scrape_one_sort(sort_type: str, take: int = 50, max_pages: int = 1000,
                    category_ids: list[int] | None = None,
                    vocal_type: str = "VOCAL_AND_INSTRUMENTS") -> tuple[dict[str, dict], int]:
    """Scrape all songs for one sort type (and optional category filter).
    Returns (songs_by_id, total_results_reported).
    """
    songs: dict[str, dict] = {}
    total_reported = 0
    cat_label = f"cat={category_ids[:3]}" if category_ids else "all"
    log.info(f"  sort={sort_type} {cat_label} take={take}")
    for page in range(1, max_pages + 1):
        try:
            data = graphql.song_list(
                page=page, take=take, sort_type=sort_type,
                vocal_type=vocal_type, category_ids=category_ids,
            )
        except Exception as e:
            log.error(f"    page {page} failed: {e}")
            time.sleep(2)
            continue
        sl = data.get("songList", data) if isinstance(data, dict) else {}
        page_songs = sl.get("songs", []) if isinstance(sl, dict) else []
        if not page_songs:
            log.info(f"    page {page}: empty, stopping")
            break
        total_reported = sl.get("totalResults", total_reported)
        new_count = 0
        for s in page_songs:
            sid = str(s.get("songId"))
            if sid not in songs:
                new_count += 1
            songs[sid] = _normalize_song(s)
        if page % 20 == 0 or page == 1:
            log.info(f"    page {page}: {len(page_songs)} songs ({new_count} new). Total unique: {len(songs)}/{total_reported}")
        # If we got fewer than take, we're at the end
        if len(page_songs) < take:
            break
        # If we've collected everything reported and no new songs in last page, stop
        if total_reported and len(songs) >= total_reported and new_count == 0:
            log.info(f"    page {page}: reached total {total_reported}, stopping")
            break
    return songs, total_reported


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


def scrape_music(max_pages_per_sort: int = 1000, sort_types: list[str] | None = None) -> dict:
    """Full music catalog scrape. Returns {meta, songs: [...]}."""
    log.info(f"=== Scraping music catalog ===")
    all_songs: dict[str, dict] = {}

    for sort_type in (sort_types or SORT_TYPES):
        songs, total = scrape_one_sort(sort_type, take=config.MUSIC_PAGE_SIZE, max_pages=max_pages_per_sort)
        log.info(f"  sort={sort_type}: collected {len(songs)} unique (reported total: {total})")
        all_songs.update(songs)
        log.info(f"  running unique total: {len(all_songs)}")

    return {
        "asset_type": "music",
        "total_unique": len(all_songs),
        "sort_types_used": sort_types or SORT_TYPES,
        "songs": list(all_songs.values()),
    }
