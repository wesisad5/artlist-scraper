"""Video templates scraper with combinatorial filtering.

TemplatesList supports: categories, softwareNames, softwareVersions, resolutions, aspectRatios, plugins.
We iterate category × software × resolution to break past 3000-item cap.
"""
import logging
import time
from .. import graphql

log = logging.getLogger(__name__)

SORT_OPTIONS = ["STAFF_PICKS", "NEWEST"]
MAX_PAGE_PER_FILTER = 60


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


def _scrape_one_filter(sort_by: str, take: int = 50, max_pages: int = MAX_PAGE_PER_FILTER,
                       categories: list | None = None, software_names: list | None = None,
                       resolutions: list | None = None, aspect_ratios: list | None = None,
                       label: str = "") -> dict[str, dict]:
    items: dict[str, dict] = {}
    log.info(f"  sortBy={sort_by} {label}")
    for page in range(1, max_pages + 1):
        try:
            items_page = graphql.templates_list(
                page=page, take=take, sort_by=sort_by,
                categories=categories, software_names=software_names,
                resolutions=resolutions, aspect_ratios=aspect_ratios,
            )
        except Exception as e:
            err_str = str(e)
            if "PaginationLimitValidator" in err_str or "Argument Validation Error" in err_str \
               or "BAD_USER_INPUT" in err_str or "HTTP 400" in err_str:
                break
            log.error(f"    page {page} failed: {e}")
            time.sleep(2)
            continue
        if not items_page:
            break
        new_count = 0
        for t in items_page:
            tid = str(t.get("id"))
            if tid not in items:
                new_count += 1
            items[tid] = _normalize_template(t)
        if page % 10 == 0 or page == 1:
            log.info(f"    page {page}: {len(items_page)} templates ({new_count} new). Total unique: {len(items)}")
        if len(items_page) < take:
            break
        if new_count == 0 and page > 3:
            break
    return items


def scrape_templates(max_pages_per_sort: int = MAX_PAGE_PER_FILTER,
                     sort_options: list[str] | None = None) -> dict:
    log.info(f"=== Scraping video templates catalog (combinatorial mode) ===")

    cats = graphql.template_root_categories()
    log.info(f"  {len(cats)} template root categories")
    filters = graphql.template_search_filters()
    software_names = filters.get("softwareNames", [])
    resolutions = filters.get("resolutions", [])
    aspect_ratios = filters.get("aspectRatios", [])
    log.info(f"  {len(software_names)} software, {len(resolutions)} resolutions, {len(aspect_ratios)} aspect ratios")

    all_templates: dict[str, dict] = {}

    # Phase 1: per-sort "all" pass
    for sb in (sort_options or SORT_OPTIONS):
        items = _scrape_one_filter(sb, max_pages=max_pages_per_sort, label="(all)")
        log.info(f"  sortBy={sb} (all): collected {len(items)} unique")
        all_templates.update(items)
        log.info(f"  running unique total: {len(all_templates)}")

    # Phase 2: per-category pass
    log.info(f"  Phase 2: per-category pagination ({len(cats)} categories)")
    for i, c in enumerate(cats, 1):
        if i % 5 == 0:
            log.info(f"  [{i}/{len(cats)}] running total: {len(all_templates)}")
        # Category ID is the 'uniqueId' field (e.g. "4_529_530")
        items = _scrape_one_filter("STAFF_PICKS", max_pages=max_pages_per_sort,
                                    categories=[c.get("uniqueId")],
                                    label=f"cat={c.get('name')}")
        all_templates.update(items)

    # Phase 3: per-category × software pass (for categories that hit the cap)
    log.info(f"  Phase 3: per-category × software pagination")
    for c in cats:
        for sw in software_names:
            items = _scrape_one_filter("STAFF_PICKS", max_pages=max_pages_per_sort,
                                        categories=[c.get("uniqueId")],
                                        software_names=[sw.get("id")],
                                        label=f"cat={c.get('name')} sw={sw.get('name')}")
            all_templates.update(items)

    # Phase 4: per-category × resolution pass
    log.info(f"  Phase 4: per-category × resolution pagination")
    for c in cats:
        for res in resolutions:
            items = _scrape_one_filter("STAFF_PICKS", max_pages=max_pages_per_sort,
                                        categories=[c.get("uniqueId")],
                                        resolutions=[res.get("id")],
                                        label=f"cat={c.get('name')} res={res.get('name')}")
            all_templates.update(items)

    log.info(f"=== Templates scrape complete: {len(all_templates)} unique ===")
    return {
        "asset_type": "template",
        "total_unique": len(all_templates),
        "categories": cats,
        "filters": filters,
        "templates": list(all_templates.values()),
    }
