"""Video templates scraper: TemplatesList with pagination.

KEY CONSTRAINT: Server caps pagination at page × take ≤ 3000 (same as music/sfx).
Strategy: iterate sort options + per-category pagination.
"""
import logging
import time
from .. import graphql

log = logging.getLogger(__name__)

SORT_OPTIONS = ["STAFF_PICKS", "RECENT", "MOST_POPULAR", "BEST_MATCH"]
MAX_PAGE_PER_FILTER = 60  # 60 × 50 = 3000 (server cap)


def _normalize_template(t: dict) -> dict:
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "artistId": str(t.get("artistId")) if t.get("artistId") else None,
        "artistName": t.get("artistName"),
        "artistNameForUrl": t.get("artistNameForUrl"),
        "isNew": t.get("isNew"),
        "isOriginal": t.get("isOriginal"),
        "thumbnailUrl": t.get("thumbnailUrl"),
        "previewVideoFileUrl": t.get("previewVideoFileUrl"),
        "nameForUrl": t.get("nameForUrl"),
        "resolutions": t.get("resolutions") or [],
        "files": t.get("files") or [],
        "availableFormats": t.get("availableFormats") or [],
    }


def scrape_templates(max_pages_per_sort: int = MAX_PAGE_PER_FILTER, sort_options: list[str] | None = None) -> dict:
    log.info(f"=== Scraping video templates catalog ===")

    # First fetch categories + filters
    try:
        cats = graphql.template_root_categories()
        log.info(f"  {len(cats)} template root categories")
    except Exception as e:
        log.warning(f"  template root categories failed: {e}")
        cats = []
    try:
        filters = graphql.template_search_filters()
    except Exception as e:
        log.warning(f"  template search filters failed: {e}")
        filters = {}

    all_templates: dict[str, dict] = {}

    # Phase 1: per-sort "all" pass
    for sb in (sort_options or SORT_OPTIONS):
        log.info(f"  sortBy={sb}")
        for page in range(1, max_pages_per_sort + 1):
            try:
                items = graphql.templates_list(page=page, take=50, sort_by=sb)
            except Exception as e:
                if "PaginationLimitValidator" in str(e) or "Argument Validation Error" in str(e):
                    log.info(f"    page {page}: pagination cap hit, stopping")
                    break
                log.error(f"    page {page} failed: {e}")
                time.sleep(2)
                continue
            if not items:
                log.info(f"    page {page}: empty, stopping")
                break
            new_count = 0
            for t in items:
                tid = str(t.get("id"))
                if tid not in all_templates:
                    new_count += 1
                all_templates[tid] = _normalize_template(t)
            if page % 10 == 0 or page == 1:
                log.info(f"    page {page}: {len(items)} templates ({new_count} new). Total unique: {len(all_templates)}")
            if len(items) < 50:
                break
            if new_count == 0 and page > 3:
                break

    # Phase 2: per-category pass
    log.info(f"  Phase 2: per-category pagination ({len(cats)} categories)")
    for i, c in enumerate(cats, 1):
        if i % 5 == 0:
            log.info(f"  [{i}/{len(cats)}] running total: {len(all_templates)}")
        for page in range(1, max_pages_per_sort + 1):
            try:
                items = graphql.templates_list(page=page, take=50, sort_by="STAFF_PICKS",
                                                categories=[c.get("id")])
            except Exception as e:
                if "PaginationLimitValidator" in str(e):
                    break
                log.debug(f"    cat {c.get('name')} page {page}: {e}")
                break
            if not items:
                break
            new_count = 0
            for t in items:
                tid = str(t.get("id"))
                if tid not in all_templates:
                    new_count += 1
                all_templates[tid] = _normalize_template(t)
            if len(items) < 50 or new_count == 0:
                break

    return {
        "asset_type": "template",
        "total_unique": len(all_templates),
        "categories": cats,
        "filters": filters,
        "templates": list(all_templates.values()),
    }
