"""Flows (Flow / Canvas AI tool) scraper.

Scrapes:
- template.list (example flow templates — public)
- flow.list (user's own flows — may be empty)
- For each template/flow: flow.get, flow.outputs, flow.nodeOutputs per node
- catalog.getNodeCatalog (all available node types)
- chatSession.getFreeGenerations
- node.getUiConfig for each node slug
"""
import logging
import json
import time
from .. import trpc
from .. import config
from ..cdn import classify, normalize_cdn_url

log = logging.getLogger(__name__)


def scrape_flow_templates(max_templates: int = 100) -> dict:
    """Scrape all Flow AI templates (example flows)."""
    log.info(f"=== Scraping Flow AI templates ===")
    templates = []
    cursor = 1
    while len(templates) < max_templates:
        try:
            data = trpc.flows_template_list(per_page=100, cursor=cursor)
        except Exception as e:
            log.error(f"  cursor={cursor} failed: {e}")
            break
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            break
        # Enrich each template with full details
        for t in items:
            tid = str(t.get("id"))
            try:
                full = trpc.flows_template_get(tid)
                if full:
                    t["full_config"] = full
            except Exception as e:
                log.warning(f"  template {tid} get failed: {e}")
            # Classify thumbnail URL
            thumb = t.get("thumbnailUrl")
            if thumb:
                t["thumbnail_classification"] = classify(thumb)
                t["thumbnail_normalized"] = normalize_cdn_url(thumb)
        templates.extend(items)
        log.info(f"  cursor={cursor}: {len(items)} templates. Total: {len(templates)}")
        next_cursor = data.get("nextCursor")
        if not next_cursor or next_cursor <= cursor:
            break
        cursor = next_cursor

    return {
        "templates": templates,
        "total": len(templates),
    }


def scrape_user_flows() -> dict:
    """Scrape user's own flows."""
    log.info(f"=== Scraping user flows ===")
    flows = []
    cursor = 1
    while True:
        try:
            data = trpc.flows_flow_list(per_page=100, cursor=cursor)
        except Exception as e:
            log.error(f"  cursor={cursor} failed: {e}")
            break
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            break
        for f in items:
            fid = str(f.get("id"))
            try:
                full = trpc.flows_flow_get(fid)
                if full:
                    f["full_config"] = full
                outputs = trpc.flows_flow_outputs(fid)
                if outputs:
                    f["outputs"] = outputs
                # For each node, get node outputs
                nodes = (full or {}).get("flowConfig", {}).get("nodes", []) if full else []
                for node in nodes:
                    node_id = node.get("id")
                    if node_id:
                        try:
                            no = trpc.flows_flow_node_outputs(fid, node_id, per_page=50)
                            if no:
                                f.setdefault("node_outputs", {})[node_id] = no
                        except Exception as e:
                            log.debug(f"  node outputs {fid}/{node_id}: {e}")
            except Exception as e:
                log.warning(f"  flow {fid} get failed: {e}")
        flows.extend(items)
        log.info(f"  cursor={cursor}: {len(items)} flows. Total: {len(flows)}")
        next_cursor = data.get("nextCursor")
        if not next_cursor or next_cursor <= cursor:
            break
        cursor = next_cursor

    return {
        "flows": flows,
        "total": len(flows),
    }


def scrape_flows_catalog() -> dict:
    """Scrape the Flow AI node catalog (available node types)."""
    log.info(f"=== Scraping Flow node catalog ===")
    try:
        cat = trpc.flows_catalog_get_node_catalog()
        nodes = cat.get("nodes", []) if isinstance(cat, dict) else []
        log.info(f"  {len(nodes)} node types")
        # For each node, fetch UI config
        for n in nodes:
            slug = n.get("slug")
            if slug:
                try:
                    ui = trpc.flows_node_get_ui_config(slug, n.get("defaultModelGroupId"))
                    n["ui_config"] = ui
                except Exception as e:
                    log.debug(f"  ui config {slug}: {e}")
        return {"catalog": cat, "node_count": len(nodes)}
    except Exception as e:
        log.error(f"  failed: {e}")
        return {"catalog": {}, "node_count": 0}


def scrape_flows_billing() -> dict:
    """Scrape Flow AI billing/subscription info."""
    log.info(f"=== Scraping Flow billing ===")
    out = {}
    try:
        out["billing"] = trpc.flows_journeys_billing()
    except Exception as e:
        log.warning(f"  billing failed: {e}")
    try:
        out["last_subscription"] = trpc.flows_journeys_last_subscription()
    except Exception as e:
        log.warning(f"  last_subscription failed: {e}")
    try:
        out["free_generations"] = trpc.flows_chat_session_free_generations()
    except Exception as e:
        log.warning(f"  free_generations failed: {e}")
    return out


def scrape_flows_all() -> dict:
    """Full Flows scrape: templates + user flows + catalog + billing."""
    out = {}
    out.update(scrape_flow_templates())
    out["user_flows"] = scrape_user_flows()
    out.update(scrape_flows_catalog())
    out["billing_info"] = scrape_flows_billing()
    return out
