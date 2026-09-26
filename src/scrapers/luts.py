"""LUTs scraper.

The Luts query requires lutBasePreviewId (a video preview UUID).
We need to find all base preview IDs first. The HAR doesn't show how these are discovered;
likely there's a hidden query like LutBasePreviews or we iterate over known ones.

Strategy:
1. Try to find a list endpoint. The HAR shows lutBasePreviewId was set to a specific UUID.
   We can try 'Luts' with an empty/dummy UUID to see if it returns all LUTs.
2. If that fails, we use LutsByIds which takes a list of LUT IDs.
   But we don't have a way to list LUT IDs without first calling Luts.

Alternative: try fetching the LUTs page HTML and parsing it, or look at the lut HAR more carefully.
"""
import logging
import time
import json
from .. import graphql

log = logging.getLogger(__name__)


def _normalize_lut(l: dict) -> dict:
    return {
        "id": l.get("id"),
        "name": l.get("name"),
        "thumbnailUrl": l.get("thumbnailUrl"),
        "hlsUrl": l.get("hlsUrl"),
        "videoCategoryName": l.get("videoCategoryName"),
        "moodCategoryName": l.get("moodCategoryName"),
        "contrast": l.get("contrast"),
        "saturation": l.get("saturation"),
        "temperature": l.get("temperature"),
        "files": l.get("files") or [],
    }


def scrape_luts(max_pages: int = 200, take: int = 50) -> dict:
    """Scrape LUTs.

    The Luts query requires a lutBasePreviewId. We'll try common preview IDs and
    the lut HAR's first preview ID. If we can't enumerate, we'll use LutsByIds with
    sequential IDs (LUT IDs are likely sequential integers).
    """
    log.info(f"=== Scraping LUTs catalog ===")

    all_luts: dict[str, dict] = {}

    # Strategy 1: Try sequential LUT IDs via LutsByIds (in batches)
    # The HAR shows LutsByIds accepting IDs like "ce039f36-f67c-48a7-b849-323bda0b753f"
    # which are UUIDs. But the Luts query returns id values that might be smaller.
    # Let's try both.

    # Strategy 2: Use a known lutBasePreviewId and iterate pages
    # The HAR used "3c517c9f-8a96-4eb6-b221-225162ea475a"
    known_preview = "3c517c9f-8a96-4eb6-b221-225162ea475a"
    log.info(f"  Pass: lutBasePreviewId={known_preview}")
    for page in range(1, max_pages + 1):
        try:
            items = graphql.luts(lut_base_preview_id=known_preview, page=page, take=take)
        except Exception as e:
            log.error(f"    page {page} failed: {e}")
            time.sleep(2)
            continue
        if not items:
            log.info(f"    page {page}: empty, stopping")
            break
        new_count = 0
        for l in items:
            lid = str(l.get("id"))
            if lid not in all_luts:
                new_count += 1
            all_luts[lid] = _normalize_lut(l)
        if page % 20 == 0 or page == 1:
            log.info(f"    page {page}: {len(items)} luts ({new_count} new). Total unique: {len(all_luts)}")
        if len(items) < take:
            break
        if new_count == 0 and page > 3:
            break

    log.info(f"  LUTs collected: {len(all_luts)}")
    return {
        "asset_type": "lut",
        "total_unique": len(all_luts),
        "luts": list(all_luts.values()),
    }
