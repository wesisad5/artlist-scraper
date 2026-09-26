"""Auth header/cookie builders for Artlist endpoints.

Two auth mechanisms:
1. Bearer JWT (PS256-signed, ~14 day expiry) — for artlist.io / api.artlist.io / search-api.artlist.io
2. Session cookie (__Secure-session.artlist-prod.session-token, A256GCM-encrypted JWT)
   — for flows.artlist.io / studio.artlist.io (tRPC)
   Also requires cf_clearance + __cf_bm (Cloudflare bot bypass) + userSession + artlist_visitor_id
"""
from . import config


def jwt_headers(extra: dict | None = None) -> dict:
    """Headers for search-api.artlist.io GraphQL calls (Bearer JWT auth)."""
    h = {
        "Authorization": f"Bearer {config.ARTLIST_JWT}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": config.HOST_ARTLIST,
        "Referer": config.HOST_ARTLIST + "/",
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }
    if extra:
        h.update(extra)
    return h


def api_headers(extra: dict | None = None) -> dict:
    """Headers for api.artlist.io (Bearer JWT auth)."""
    return jwt_headers(extra)


def trpc_flows_headers(extra: dict | None = None) -> dict:
    """Headers for flows.artlist.io tRPC (cookie auth)."""
    h = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": config.HOST_FLOWS,
        "Referer": config.HOST_FLOWS + "/",
        "User-Agent": config.USER_AGENT,
        "x-trpc-source": "nextjs-react",
        "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
    if extra:
        h.update(extra)
    return h


def trpc_studio_headers(extra: dict | None = None) -> dict:
    """Headers for studio.artlist.io tRPC (cookie auth)."""
    h = trpc_flows_headers(extra)
    h["Origin"] = config.HOST_STUDIO
    h["Referer"] = config.HOST_STUDIO + "/"
    return h


def flows_cookies() -> dict:
    """Cookie dict for flows.artlist.io tRPC."""
    return {
        "__Secure-session.artlist-prod.session-token": config.ARTLIST_FLOWS_SESSION_TOKEN,
        "cf_clearance": config.ARTLIST_FLOWS_CF_CLEARANCE,
        "__cf_bm": config.ARTLIST_FLOWS_CF_BM,
        "userSession": config.ARTLIST_USER_SESSION,
        "artlist_visitor_id": config.ARTLIST_VISITOR_ID,
        "ajs_user_id": config.ARTLIST_USER_ID,
    }


def studio_cookies() -> dict:
    """Cookie dict for studio.artlist.io tRPC. Different session-token + csrf-token per host."""
    c = {
        "__Secure-session.artlist-prod.session-token": config.ARTLIST_STUDIO_SESSION_TOKEN,
        "cf_clearance": config.ARTLIST_STUDIO_CF_CLEARANCE,
        "__cf_bm": config.ARTLIST_STUDIO_CF_BM,
        "userSession": config.ARTLIST_USER_SESSION,
        "artlist_visitor_id": config.ARTLIST_VISITOR_ID,
        "ajs_user_id": config.ARTLIST_USER_ID,
    }
    if config.ARTLIST_STUDIO_CSRF_TOKEN:
        c["__Host-session.artlist-prod.csrf-token"] = config.ARTLIST_STUDIO_CSRF_TOKEN
    return c


def cdn_headers(origin: str | None = None) -> dict:
    """Headers for fetching CDN permlinks (cms-public-artifacts.artlist.io).

    The CDN requires Origin + Referer matching artlist.io or it 403s.
    """
    base = origin or config.HOST_ARTLIST
    return {
        "User-Agent": config.USER_AGENT,
        "Origin": base,
        "Referer": base + "/",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
    }
