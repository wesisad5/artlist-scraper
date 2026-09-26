"""Categories scraper: RootCategories for all asset types."""
import logging
from .. import graphql
from .. import config

log = logging.getLogger(__name__)

ASSET_TYPES = ["music", "sfx", "footage", "template"]  # only valid RootCategories asset types


def scrape_all_categories() -> dict:
    """Fetch RootCategories for all known asset types."""
    out = {}
    for at in ASSET_TYPES:
        try:
            cats = graphql.root_categories(at)
            out[at] = cats
            n_top = len(cats)
            # subCategory may be None (template) or a list
            n_sub = sum(len(c.get("subCategory") or []) for c in cats)
            log.info(f"  {at}: {n_top} top categories, {n_sub} sub-categories")
        except Exception as e:
            log.error(f"  {at}: FAILED {e}")
            out[at] = []
    return out


def scrape_search_terms() -> dict:
    """Fetch trending search terms per asset type.

    SearchTermsAutosuggestionsSupportedAssetType enum: only MUSIC and FOOTAGE observed working
    in the HAR. SFX, LUT, TEMPLATE values are not in the enum."""
    out = {}
    for at in ["MUSIC", "FOOTAGE"]:  # only these are valid in the enum
        try:
            terms = graphql.search_terms_autosuggestions(at)
            out[at] = terms
            log.info(f"  {at}: {len(terms)} trending terms")
        except Exception as e:
            log.warning(f"  {at}: search terms failed {e}")
            out[at] = []
    return out


def flatten_categories(cats: list[dict], parent: str = "") -> list[dict]:
    """Flatten the nested category tree into a list. Handles None subCategory (template type)."""
    out = []
    for c in cats:
        out.append({
            "id": c["id"],
            "name": c["name"],
            "nameForUrl": c.get("nameForUrl"),
            "parent": parent,
        })
        for sc in (c.get("subCategory") or []):
            out.append({
                "id": sc["id"],
                "name": sc["name"],
                "nameForUrl": sc.get("nameForUrl"),
                "parent": c["name"],
            })
            for ssc in (sc.get("subCategory") or []):
                out.append({
                    "id": ssc["id"],
                    "name": ssc["name"],
                    "nameForUrl": ssc.get("nameForUrl"),
                    "parent": sc["name"],
                })
    return out
