"""Collections scraper (artlist.io/api/v1/directory).

The /v1/directory endpoint returns collections (folders) of curated assets.
"""
import logging
from .. import auth
from ..http_client import get_json

log = logging.getLogger(__name__)


def scrape_collections(max_pages: int = 50, take: int = 50) -> dict:
    log.info(f"=== Scraping collections ===")
    collections = []
    for skip in range(0, max_pages * take, take):
        try:
            data = get_json(
                f"https://api.artlist.io/v1/directory",
                headers=auth.api_headers(),
                params={
                    "directoryType": "FOLDER",
                    "take": take,
                    "skip": skip,
                    "orderByKey": "lastUpdated",
                    "orderByDirection": "DESC",
                },
            )
        except Exception as e:
            log.error(f"  skip={skip} failed: {e}")
            break
        items = data.get("data", []) if isinstance(data, dict) else []
        if not items:
            break
        collections.extend(items)
        log.info(f"  skip={skip}: {len(items)} collections. Total: {len(collections)}")
        if len(items) < take:
            break
    return {
        "asset_type": "collection",
        "total": len(collections),
        "collections": collections,
    }
