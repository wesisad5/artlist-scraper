"""Pipeline orchestration: full catalog scrape with metadata + audit.

Supports resume via progress.json — each step can be run independently.
The workflow can run one step at a time and self-chain to the next.
"""
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

# Ordered list of catalog steps (for chunked execution)
CATALOG_STEPS = ["categories", "music", "sfx", "footage", "luts", "templates", "collections"]
AI_STEPS = ["flows", "studio"]

PROGRESS_FILE = config.META_DIR / "progress.json"


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    log.info(f"  saved {path} ({path.stat().st_size / 1024:.1f} KB)")


def _step(name: str, fn, save_path: Path | None = None, *args, **kwargs):
    """Run a step with timing + error capture. Saves result if save_path given."""
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


def load_progress() -> dict:
    """Load progress.json (or return empty if not present)."""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
    return {"done_steps": [], "current_step": None, "done": False, "totals": {}, "run_id": None}


def save_progress(progress: dict):
    """Save progress.json."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))
    log.info(f"  progress saved: {progress}")


def next_pending_step(progress: dict, steps: list[str] = CATALOG_STEPS) -> str | None:
    """Return the next step that hasn't been completed successfully."""
    done = set(progress.get("done_steps", []))
    for step in steps:
        if step not in done:
            return step
    return None


def run_single_step(step: str, out_dir: Path | None = None) -> dict:
    """Run a single catalog step. Used for chunked execution."""
    out_dir = out_dir or config.CATALOG_DIR

    # Load categories for steps that need them
    cats_data = None
    if step in ("music", "sfx", "footage"):
        cats_path = out_dir / "categories.json"
        if cats_path.exists():
            try:
                cats_data = json.loads(cats_path.read_text())
            except Exception:
                pass

    if step == "categories":
        data, s = _step("categories", cat_scraper.scrape_all_categories, out_dir / "categories.json")
        try:
            terms = cat_scraper.scrape_search_terms()
            _save(out_dir / "search_terms.json", {"terms": terms})
        except Exception as e:
            log.warning(f"search_terms failed: {e}")
        return {"step": "categories", "status": s, "total": sum(len(v) for v in (data or {}).values())}

    elif step == "music":
        music_cats = (cats_data or {}).get("music", []) if cats_data else None
        data, s = _step("music", music_scraper.scrape_music, out_dir / "music.json", categories=music_cats)
        return {"step": "music", "status": s, "total": data.get("total_unique", 0) if data else 0}

    elif step == "sfx":
        sfx_cats = (cats_data or {}).get("sfx", []) if cats_data else None
        data, s = _step("sfx", sfx_scraper.scrape_sfx, out_dir / "sfx.json", categories=sfx_cats)
        return {"step": "sfx", "status": s, "total": data.get("total_unique", 0) if data else 0}

    elif step == "footage":
        footage_cats = (cats_data or {}).get("footage", []) if cats_data else None
        data, s = _step("footage", footage_scraper.scrape_footage, out_dir / "footage.json",
                         categories=footage_cats, max_pages_per_filter=60)
        return {"step": "footage", "status": s,
                "total": data.get("total_unique_clips", 0) if data else 0,
                "stories": data.get("total_stories", 0) if data else 0}

    elif step == "luts":
        data, s = _step("luts", luts_scraper.scrape_luts, out_dir / "luts.json")
        return {"step": "luts", "status": s, "total": data.get("total_unique", 0) if data else 0}

    elif step == "templates":
        data, s = _step("templates", tmpl_scraper.scrape_templates, out_dir / "templates.json")
        return {"step": "templates", "status": s, "total": data.get("total_unique", 0) if data else 0}

    elif step == "collections":
        data, s = _step("collections", coll_scraper.scrape_collections, out_dir / "collections.json")
        return {"step": "collections", "status": s, "total": data.get("total", 0) if data else 0}

    elif step == "flows":
        data, s = _step("flows", flows_scraper.scrape_flows_all, config.AI_DIR / "flows.json")
        return {"step": "flows", "status": s, "total": data.get("total", 0) if data else 0}

    elif step == "studio":
        data, s = _step("studio", studio_scraper.scrape_studio_all, config.AI_DIR / "studio.json")
        return {"step": "studio", "status": s, "total": data.get("total", 0) if data else 0}

    else:
        return {"step": step, "status": {"status": "skipped", "error": "unknown step"}, "total": 0}


def run_catalog_resume(out_dir: Path | None = None) -> dict:
    """Run the next pending catalog step (for chunked execution).
    Returns progress dict with 'done' flag and 'next_step' (None if done)."""
    progress = load_progress()
    next_step = next_pending_step(progress)

    if next_step is None:
        log.info("=== All catalog steps complete ===")
        progress["done"] = True
        save_progress(progress)
        return progress

    log.info(f"=== Running step: {next_step} ===")
    result = run_single_step(next_step, out_dir)

    # Update progress
    if result["status"]["status"] == "ok":
        progress.setdefault("done_steps", []).append(next_step)
        progress["totals"][next_step] = result.get("total", 0)
    else:
        progress.setdefault("failed_steps", []).append(next_step)

    # Check if there's a next step
    next_after = next_pending_step(progress)
    progress["current_step"] = next_after
    progress["done"] = (next_after is None)
    if not progress.get("run_id"):
        progress["run_id"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    save_progress(progress)

    # Also update latest.json
    latest = {
        "run_id": progress.get("run_id"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "steps_completed": progress.get("done_steps", []),
        "totals": progress.get("totals", {}),
        "done": progress.get("done", False),
        "next_step": next_after,
    }
    _save(config.META_DIR / "latest.json", latest)

    return progress


def run_catalog(out_dir: Path | None = None, *, skip: list[str] | None = None) -> dict:
    """Run full catalog scrape (all steps in one call). For non-chunked execution."""
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

    cats_data = None
    if "categories" not in skip:
        cats_data, s = _step("categories", cat_scraper.scrape_all_categories, out_dir / "categories.json")
        run_meta["steps"]["categories"] = s
        if cats_data:
            run_meta["totals"]["categories_top"] = sum(len(v) for v in cats_data.values())
        try:
            terms = cat_scraper.scrape_search_terms()
            _save(out_dir / "search_terms.json", {"terms": terms})
        except Exception as e:
            log.warning(f"search_terms failed: {e}")

    if "music" not in skip:
        music_cats = (cats_data or {}).get("music", []) if cats_data else None
        data, s = _step("music", music_scraper.scrape_music, out_dir / "music.json", categories=music_cats)
        run_meta["steps"]["music"] = s
        if data: run_meta["totals"]["music"] = data.get("total_unique", 0)

    if "sfx" not in skip:
        sfx_cats = (cats_data or {}).get("sfx", []) if cats_data else None
        data, s = _step("sfx", sfx_scraper.scrape_sfx, out_dir / "sfx.json", categories=sfx_cats)
        run_meta["steps"]["sfx"] = s
        if data: run_meta["totals"]["sfx"] = data.get("total_unique", 0)

    if "footage" not in skip:
        footage_cats = (cats_data or {}).get("footage", []) if cats_data else None
        data, s = _step("footage", footage_scraper.scrape_footage, out_dir / "footage.json",
                         categories=footage_cats, max_pages_per_filter=60)
        run_meta["steps"]["footage"] = s
        if data:
            run_meta["totals"]["footage_clips"] = data.get("total_unique_clips", 0)
            run_meta["totals"]["footage_stories"] = data.get("total_stories", 0)

    if "luts" not in skip:
        data, s = _step("luts", luts_scraper.scrape_luts, out_dir / "luts.json")
        run_meta["steps"]["luts"] = s
        if data: run_meta["totals"]["luts"] = data.get("total_unique", 0)

    if "templates" not in skip:
        data, s = _step("templates", tmpl_scraper.scrape_templates, out_dir / "templates.json")
        run_meta["steps"]["templates"] = s
        if data: run_meta["totals"]["templates"] = data.get("total_unique", 0)

    if "collections" not in skip:
        data, s = _step("collections", coll_scraper.scrape_collections, out_dir / "collections.json")
        run_meta["steps"]["collections"] = s
        if data: run_meta["totals"]["collections"] = data.get("total", 0)

    run_meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    _save(config.META_DIR / f"run_{run_id}.json", run_meta)
    _save(config.META_DIR / "latest.json", run_meta)
    # Also save progress.json for compatibility
    save_progress({
        "done_steps": [k for k, v in run_meta["steps"].items() if v["status"] == "ok"],
        "current_step": None,
        "done": True,
        "totals": run_meta["totals"],
        "run_id": run_id,
    })
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
