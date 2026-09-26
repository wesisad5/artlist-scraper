"""Studio AI scraper.

Scrapes:
- project.getSpotlightProjects (public example projects)
- project.getProjects (user's own projects — may be empty)
- For each spotlight/example project: shot.getShot, shot.getShotFrames, shot.getShotHistory
- location.getPredefinedLocations, prop.getPredefinedProps (public assets)
- models.getModelGroups (available AI models)
- growth.getFreeGenerations, growth.getWalletBalance, growth.getLastActiveSubscription
"""
import logging
from .. import trpc
from ..cdn import classify, normalize_cdn_url, extract_proxy_target

log = logging.getLogger(__name__)


def _classify_image_urls(obj):
    """Recursively classify all image/preview URLs in an object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and any(s in k.lower() for s in ("url", "image", "preview", "thumb", "file")):
                if v.startswith("http"):
                    obj[f"_{k}_classification"] = classify(v)
                    obj[f"_{k}_normalized"] = normalize_cdn_url(v)
                    tgt = extract_proxy_target(v)
                    if tgt:
                        obj[f"_{k}_target"] = tgt
            else:
                _classify_image_urls(v)
    elif isinstance(obj, list):
        for item in obj:
            _classify_image_urls(item)


def scrape_spotlight_projects(max_pages: int = 20, page_size: int = 100) -> dict:
    """Scrape Studio AI spotlight (example) projects."""
    log.info(f"=== Scraping Studio AI spotlight projects ===")
    projects = []
    for page in range(1, max_pages + 1):
        try:
            data = trpc.studio_spotlight_projects(page=page, page_size=page_size)
        except Exception as e:
            log.error(f"  page {page} failed: {e}")
            break
        items = data.get("data", []) if isinstance(data, dict) else []
        if not items:
            break
        # Enrich each project with shot details
        for p in items:
            shot_id = p.get("shotId")
            if shot_id:
                try:
                    shot = trpc.studio_shot_get(shot_id)
                    if shot:
                        p["shot"] = shot
                except Exception as e:
                    log.debug(f"  shot {shot_id}: {e}")
                try:
                    frames = trpc.studio_shot_get_frames(shot_id, page_size=100)
                    if frames:
                        p["shot_frames"] = frames
                except Exception as e:
                    log.debug(f"  frames {shot_id}: {e}")
                try:
                    history = trpc.studio_shot_history(shot_id, page_size=100)
                    if history:
                        p["shot_history"] = history
                except Exception as e:
                    log.debug(f"  history {shot_id}: {e}")
            _classify_image_urls(p)
        projects.extend(items)
        pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
        total = pagination.get("total", 0)
        log.info(f"  page {page}: {len(items)} projects. Total: {len(projects)}/{total}")
        if len(items) < page_size:
            break

    return {"spotlight_projects": projects, "total": len(projects)}


def scrape_user_projects() -> dict:
    """Scrape user's own Studio projects."""
    log.info(f"=== Scraping user Studio projects ===")
    projects = []
    for page in range(1, 20):
        try:
            data = trpc.studio_projects(page=page, page_size=100)
        except Exception as e:
            log.error(f"  page {page} failed: {e}")
            break
        items = data.get("data", []) if isinstance(data, dict) else []
        if not items:
            break
        for p in items:
            shot_id = p.get("shotId")
            if shot_id:
                try:
                    shot = trpc.studio_shot_get(shot_id)
                    if shot:
                        p["shot"] = shot
                except Exception:
                    pass
            _classify_image_urls(p)
        projects.extend(items)
        pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
        total = pagination.get("total", 0)
        log.info(f"  page {page}: {len(items)} projects. Total: {len(projects)}/{total}")
        if len(items) < 100:
            break
    return {"user_projects": projects, "total": len(projects)}


def scrape_predefined_assets() -> dict:
    """Scrape predefined locations and props (public assets for Studio AI)."""
    log.info(f"=== Scraping Studio predefined assets ===")
    out = {}
    try:
        locs = trpc.studio_get_predefined_locations(page=1, page_size=500, seed=0.5)
        _classify_image_urls(locs)
        out["predefined_locations"] = locs
        n = len(locs.get("data", [])) if isinstance(locs, dict) else 0
        log.info(f"  {n} predefined locations")
    except Exception as e:
        log.warning(f"  predefined_locations failed: {e}")
    try:
        props = trpc.studio_get_predefined_props(page=1, page_size=500, seed=0.5)
        _classify_image_urls(props)
        out["predefined_props"] = props
        n = len(props.get("data", [])) if isinstance(props, dict) else 0
        log.info(f"  {n} predefined props")
    except Exception as e:
        log.warning(f"  predefined_props failed: {e}")
    return out


def scrape_models() -> dict:
    """Scrape available AI models in Studio."""
    log.info(f"=== Scraping Studio models ===")
    try:
        models = trpc.studio_get_model_groups()
        return {"models": models}
    except Exception as e:
        log.warning(f"  models failed: {e}")
        return {"models": {}}


def scrape_studio_billing() -> dict:
    log.info(f"=== Scraping Studio billing ===")
    out = {}
    try: out["wallet_balance"] = trpc.studio_growth_wallet_balance()
    except Exception as e: log.warning(f"  wallet: {e}")
    try: out["last_subscription"] = trpc.studio_growth_last_subscription()
    except Exception as e: log.warning(f"  sub: {e}")
    try: out["free_generations"] = trpc.studio_growth_free_generations()
    except Exception as e: log.warning(f"  free gens: {e}")
    return out


def scrape_studio_all() -> dict:
    out = {}
    out.update(scrape_spotlight_projects())
    out["user_projects"] = scrape_user_projects().get("user_projects", [])
    out["predefined"] = scrape_predefined_assets()
    out["models"] = scrape_models()
    out["billing"] = scrape_studio_billing()
    return out
