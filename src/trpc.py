"""tRPC client for flows.artlist.io and studio.artlist.io.

tRPC v11 with batch + cursor pagination.
Input is encoded as JSON in the ?input= query param.
Batch queries use ?batch=1&input={"0":{...},"1":{...}}.
"""
import json
import urllib.parse
from typing import Any
from . import config
from . import auth
from .http_client import get_json, post_json, HttpError
import logging

log = logging.getLogger(__name__)


def _build_input(params: dict, batch: bool = False) -> str:
    """Build the ?input= value for tRPC GET requests.

    Non-batch: {"json":{...}}  (no meta field — verified from HAR)
    Batch:     {"0":{"json":{...},"meta":{"values":["undefined"]}},"1":{...}}
    """
    if batch:
        out = {}
        for i, p in enumerate(params):
            out[str(i)] = {"json": p, "meta": {"values": ["undefined"]}}
        return json.dumps(out, separators=(",", ":"))
    else:
        return json.dumps({"json": params}, separators=(",", ":"))


def _encode_query(params: dict, batch: bool = False, extra: dict | None = None) -> str:
    inp = _build_input(params, batch)
    q = {"input": inp}
    if batch:
        q["batch"] = "1"
    if extra:
        q.update(extra)
    return urllib.parse.urlencode(q)


def trpc_get(host: str, op: str, params: dict, cookies: dict, headers: dict,
             batch: bool = False, extra_query: dict | None = None) -> Any:
    """Single-or-batch tRPC GET. Returns parsed JSON (dict for single, list for batch)."""
    base = f"{host}/api/trpc/{op}"
    qs = _encode_query(params, batch=batch, extra=extra_query)
    url = f"{base}?{qs}"
    return get_json(url, headers=headers, cookies=cookies)


def trpc_post(host: str, op: str, payload: dict, cookies: dict, headers: dict,
              batch: bool = False) -> Any:
    """tRPC POST (used for flow.create etc.)."""
    url = f"{host}/api/trpc/{op}"
    if batch:
        body = {"0": {"json": payload}}
    else:
        body = {"json": payload}
    return post_json(url, body, headers=headers, cookies=cookies)


# === Flows ===

def flows_get(op: str, params: dict, batch: bool = False) -> Any:
    return trpc_get(config.HOST_FLOWS, op, params, auth.flows_cookies(), auth.trpc_flows_headers(), batch=batch)


def flows_post(op: str, payload: dict) -> Any:
    return trpc_post(config.HOST_FLOWS, op, payload, auth.flows_cookies(), auth.trpc_flows_headers())


# === Studio ===

def studio_get(op: str, params: dict, batch: bool = False) -> Any:
    return trpc_get(config.HOST_STUDIO, op, params, auth.studio_cookies(), auth.trpc_studio_headers(), batch=batch)


def studio_post(op: str, payload: dict) -> Any:
    return trpc_post(config.HOST_STUDIO, op, payload, auth.studio_cookies(), auth.trpc_studio_headers())


# === High-level Flows ===

def flows_template_list(per_page: int = 100, cursor: int = 1, direction: str = "forward") -> dict:
    """List Flow AI templates (example flows). Returns {items, nextCursor}."""
    resp = flows_get("template.list", {"perPage": per_page, "cursor": cursor, "direction": direction})
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_template_get(template_id: str) -> dict:
    resp = flows_get("template.get", {"id": template_id})
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_flow_list(per_page: int = 100, cursor: int = 1, direction: str = "forward") -> dict:
    """List user's own flows. Returns {items, nextCursor}."""
    resp = flows_get("flow.list", {"perPage": per_page, "cursor": cursor, "direction": direction})
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_flow_get(flow_id: str) -> dict:
    resp = flows_get("flow.get", {"id": flow_id})
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_flow_outputs(flow_id: str) -> dict:
    resp = flows_get("flow.outputs", {"id": flow_id})
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_flow_node_outputs(flow_id: str, node_id: str, per_page: int = 100,
                             cursor: int = 1, direction: str = "forward") -> dict:
    resp = flows_get("flow.nodeOutputs", {
        "id": flow_id, "nodeId": node_id,
        "perPage": per_page, "cursor": cursor, "direction": direction,
    })
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_assets_resolve_url(file_key: str) -> str | None:
    """Resolve a Flows file key to a signed CDN URL."""
    resp = flows_get("assets.resolveUrl", {"fileKey": file_key})
    return resp.get("result", {}).get("data", {}).get("json", {}).get("url")


def flows_assets_resolve_urls(file_keys: list[str]) -> dict[str, str]:
    resp = flows_get("assets.resolveUrls", {"fileKeys": file_keys})
    return resp.get("result", {}).get("data", {}).get("json", {}).get("urls", {})


def flows_catalog_get_node_catalog() -> dict:
    resp = flows_get("catalog.getNodeCatalog", {})
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_chat_session_free_generations() -> dict:
    resp = flows_get("chatSession.getFreeGenerations", {})
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_node_get_ui_config(slug: str, model_group_id: int | None = None) -> dict:
    params = {"slug": slug}
    if model_group_id is not None:
        params["modelGroupId"] = model_group_id
    resp = flows_get("node.getUiConfig", params)
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_journeys_billing() -> dict:
    resp = flows_get("journeys.getBillingInformation", {})
    return resp.get("result", {}).get("data", {}).get("json", {})


def flows_journeys_last_subscription() -> dict:
    resp = flows_get("journeys.getLastActiveSubscription", {})
    return resp.get("result", {}).get("data", {}).get("json", {})


# === High-level Studio ===

def studio_projects(page: int = 1, page_size: int = 100) -> dict:
    resp = studio_get("project.getProjects", {"page": page, "pageSize": page_size})
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_spotlight_projects(page: int = 1, page_size: int = 100) -> dict:
    """Public example projects."""
    resp = studio_get("project.getSpotlightProjects", {"page": page, "pageSize": page_size})
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_shot_get(shot_id: str) -> dict:
    resp = studio_get("shot.getShot", {"id": shot_id})
    if "error" in resp:
        log.warning(f"shot.getShot({shot_id}) failed: {resp['error']}")
        return {}
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_shot_get_frames(shot_id: str, page: int = 1, page_size: int = 100) -> dict:
    resp = studio_get("shot.getShotFrames", {
        "id": shot_id, "page": page, "pageSize": page_size,
        "imgixParams": {"w": 256, "h": 256, "fit": "crop"},
    })
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_shot_history(shot_id: str, page: int = 1, page_size: int = 100) -> dict:
    resp = studio_get("shot.getShotHistory", {
        "id": shot_id, "page": page, "pageSize": page_size,
        "imgixParams": {"w": 256, "h": 256, "fit": "crop"},
    })
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_get_locations(page: int = 1, page_size: int = 100) -> dict:
    resp = studio_get("location.getLocations", {"page": page, "pageSize": page_size})
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_get_predefined_locations(page: int = 1, page_size: int = 100, seed: float = 0.5) -> dict:
    resp = studio_get("location.getPredefinedLocations", {
        "page": page, "pageSize": page_size, "randomizeSeed": seed,
    })
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_get_props(page: int = 1, page_size: int = 100) -> dict:
    resp = studio_get("prop.getProps", {"page": page, "pageSize": page_size})
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_get_predefined_props(page: int = 1, page_size: int = 100, seed: float = 0.5) -> dict:
    resp = studio_get("prop.getPredefinedProps", {
        "page": page, "pageSize": page_size, "randomizeSeed": seed,
    })
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_get_characters() -> dict:
    """List user's characters (likely empty for new accounts)."""
    # We don't have a direct 'character.list' op captured; try character.getCharacter with batch of known IDs
    # Instead use character.list guess:
    resp = studio_get("character.getCharacters", {"page": 1, "pageSize": 100})
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_get_model_groups() -> dict:
    resp = studio_get("models.getModelGroups", {})
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_growth_wallet_balance() -> dict:
    resp = studio_get("growth.getWalletBalance", {})
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_growth_last_subscription() -> dict:
    resp = studio_get("growth.getLastActiveSubscription", {})
    return resp.get("result", {}).get("data", {}).get("json", {})


def studio_growth_free_generations() -> dict:
    resp = studio_get("growth.getFreeGenerations", {})
    return resp.get("result", {}).get("data", {}).get("json", {})
