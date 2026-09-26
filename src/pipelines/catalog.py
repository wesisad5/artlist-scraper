"""Pipeline orchestration: full catalog scrape with metadata + audit."""
import json
import logging
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from .. import config
from ..scrapers import categories as cat_scraper
from ..scrapers import music as music_scraper
from ..scrapers import sfx as sfx_scraper
from ..scrapers import footage as footage_scraper
from ..scrapers import luts as luts_scraper
from ..scrapers import templates as tmpl_scraper
from ..scrapers import collections as coll_scraper
from ..scrapers import flows as flows_scraper
from ..scrapers import studio as studio_scraper

log = logging.getLogger(__name__)


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    log.info(f"  saved {path} ({path.stat().st_size / 1024:.1f} KB)")


def _step(name: str, fn, save_path: Path | None = None, *args, **kwargs):
    """Run a step with timing + error capture. Saves result if save_path given.
    Returns (result_dict, status_dict).
    """
    start = time.time()
    log.info(f"\n>>> STEP: {name}")
    try:
        result = fn(*args, **kwargs)
        dur = time.time() - start
        if save_path and result is not None:
            _save(save_path, result)
        log.info(f"<<< {name} OK ({dur:.1f}s)")
        return result, {"status": "ok", "duration_sec": round(dur, 1), "error": None}
    except Exception as e:
        dur = time.time() - start
        log.exception(f"!!! {name} FAILED ({dur:.1f}s): {e}")
        return None, {"status": "failed", "duration_sec": round(dur, 1), "error": str(e)}


def run_catalog(out_dir: Path | None = None, *, skip: list[str] | None = None) -> dict:
    """Run full catalog scrape. Returns run metadata."""
    out_dir = out_dir or config.CATALOG_DIR
    skip = set(skip or [])
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log.info(f"=== CATALOG SCRAPE RUN {run_id} ===")

    run_meta = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": {},
        "totals": {},
    }

    # 1. Categories
    cats_data = None
    if "categories" not in skip:
        cats_data, s = _step("categories", cat_scraper.scrape_all_categories,
                              out_dir / "categories.json")
        run_meta["steps"]["categories"] = s
        if cats_data:
            run_meta["totals"]["categories_top"] = sum(len(v) for v in cats_data.values())
        # search terms
        try:
            terms = cat_scraper.scrape_search_terms()
            _save(out_dir / "search_terms.json", {"terms": terms})
        except Exception as e:
            log.warning(f"search_terms failed: {e}")

    # 2. Music
    if "music" not in skip:
        data, s = _step("music", music_scraper.scrape_music, out_dir / "music.json")
        run_meta["steps"]["music"] = s
        if data: run_meta["totals"]["music"] = data.get("total_unique", 0)

    # 3. SFX
    if "sfx" not in skip:
        data, s = _step("sfx", sfx_scraper.scrape_sfx, out_dir / "sfx.json")
        run_meta["steps"]["sfx"] = s
        if data: run_meta["totals"]["sfx"] = data.get("total_unique", 0)

    # 4. Footage
    if "footage" not in skip:
        footage_cats = (cats_data or {}).get("footage", []) if cats_data else None
        data, s = _step("footage", footage_scraper.scrape_footage,
                         out_dir / "footage.json",
                         categories=footage_cats, max_pages_per_filter=200)
        run_meta["steps"]["footage"] = s
        if data:
            run_meta["totals"]["footage_clips"] = data.get("total_unique_clips", 0)
            run_meta["totals"]["footage_stories"] = data.get("total_stories", 0)

    # 5. LUTs
    if "luts" not in skip:
        data, s = _step("luts", luts_scraper.scrape_luts, out_dir / "luts.json")
        run_meta["steps"]["luts"] = s
        if data: run_meta["totals"]["luts"] = data.get("total_unique", 0)

    # 6. Templates
    if "templates" not in skip:
        data, s = _step("templates", tmpl_scraper.scrape_templates, out_dir / "templates.json")
        run_meta["steps"]["templates"] = s
        if data: run_meta["totals"]["templates"] = data.get("total_unique", 0)

    # 7. Collections
    if "collections" not in skip:
        data, s = _step("collections", coll_scraper.scrape_collections, out_dir / "collections.json")
        run_meta["steps"]["collections"] = s
        if data: run_meta["totals"]["collections"] = data.get("total", 0)

    run_meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    _save(config.META_DIR / f"run_{run_id}.json", run_meta)
    _save(config.META_DIR / "latest.json", run_meta)
    return run_meta


def run_ai(out_dir: Path | None = None, *, skip: list[str] | None = None) -> dict:
    """Run AI tools (Flows + Studio) scrape."""
    out_dir = out_dir or config.AI_DIR
    skip = set(skip or [])
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log.info(f"=== AI TOOLS SCRAPE RUN {run_id} ===")

    run_meta = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": {},
        "totals": {},
    }

    if "flows" not in skip:
        data, s = _step("flows", flows_scraper.scrape_flows_all, out_dir / "flows.json")
        run_meta["steps"]["flows"] = s
        if data:
            run_meta["totals"]["flow_templates"] = data.get("total", 0)
            run_meta["totals"]["user_flows"] = data.get("user_flows", {}).get("total", 0)
            run_meta["totals"]["flow_nodes"] = data.get("node_count", 0)

    if "studio" not in skip:
        data, s = _step("studio", studio_scraper.scrape_studio_all, out_dir / "studio.json")
        run_meta["steps"]["studio"] = s
        if data:
            run_meta["totals"]["studio_spotlight"] = data.get("total", 0)
            run_meta["totals"]["studio_user_projects"] = len(data.get("user_projects", []))

    run_meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    _save(config.META_DIR / f"ai_run_{run_id}.json", run_meta)
    _save(config.META_DIR / "ai_latest.json", run_meta)
    return run_meta


def run_all(skip: list[str] | None = None) -> dict:
    """Run both catalog + AI scrapes."""
    catalog_meta = run_catalog(skip=skip)
    ai_meta = run_ai(skip=skip)
    return {"catalog": catalog_meta, "ai": ai_meta}
