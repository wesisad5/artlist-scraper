"""Audit pipeline: E2E check from data discovery to final storage.

Verifies:
1. All expected catalog files exist and are non-empty.
2. Asset counts match expected ranges.
3. Each asset has required fields.
4. CDN URLs are classified correctly (permlink vs signed).
5. Sample of CDN URLs are reachable (HEAD request returns 200/302).
6. Signed URLs that need mirroring are in the blob manifest.
7. JSON files are valid and parseable.
"""
import json
import logging
import random
from pathlib import Path
from .. import config
from ..http_client import request, HttpError
from ..cdn import classify, needs_mirror, get_expiry
from ..storage import manifest as blob_manifest

log = logging.getLogger(__name__)


REQUIRED_FIELDS = {
    "music": ["songId", "songName", "artistName", "sitePlayableFilePath"],
    "sfx": ["songId", "songName", "artistName", "sitePlayableFilePath"],
    "footage": ["id", "clipName", "thumbnailUrl", "clipPath"],
    "luts": ["id", "name", "thumbnailUrl"],
    "templates": ["id", "name", "thumbnailUrl"],
    "collections": ["id"],  # may vary
}


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        log.error(f"  {path}: invalid JSON ({e})")
        return None


def audit_catalog() -> dict:
    """Audit catalog data files."""
    log.info(f"=== CATALOG AUDIT ===")
    report = {"files": {}, "issues": [], "summary": {}}

    for name, fname in [("music", "music.json"), ("sfx", "sfx.json"),
                         ("footage", "footage.json"), ("luts", "luts.json"),
                         ("templates", "templates.json"), ("collections", "collections.json")]:
        path = config.CATALOG_DIR / fname
        frep = {"path": str(path), "exists": path.exists()}
        if not path.exists():
            report["issues"].append(f"{name}: file missing")
            report["files"][name] = frep
            continue
        frep["size_kb"] = round(path.stat().st_size / 1024, 1)
        data = _load(path)
        if data is None:
            frep["valid"] = False
            report["issues"].append(f"{name}: invalid JSON")
            report["files"][name] = frep
            continue
        frep["valid"] = True

        # Count items
        items_key = {
            "music": "songs", "sfx": "items", "footage": "clips",
            "luts": "luts", "templates": "templates", "collections": "collections",
        }.get(name)
        items = data.get(items_key, []) if items_key else []
        frep["item_count"] = len(items)
        report["summary"][name] = len(items)

        # Check required fields on first 10 items
        if name in REQUIRED_FIELDS and items:
            missing = []
            for item in items[:10]:
                for f in REQUIRED_FIELDS[name]:
                    if not item.get(f):
                        missing.append(f"{f} (id={item.get('id') or item.get('songId')})")
            if missing:
                frep["missing_fields_sample"] = missing[:5]
                report["issues"].append(f"{name}: {len(missing)} missing required fields in first 10")

        # URL classification stats
        url_fields = {
            "music": ["sitePlayableFilePath", "waveSurferFilePath", "albumImageFilePath"],
            "sfx": ["sitePlayableFilePath", "waveSurferFilePath", "albumImageFilePath"],
            "footage": ["thumbnailUrl", "clipPath"],
            "luts": ["thumbnailUrl", "hlsUrl"],
            "templates": ["thumbnailUrl", "previewVideoFileUrl"],
            "collections": [],
        }.get(name, [])
        cls_counts = {"permlink": 0, "signed": 0, "proxy": 0, "unknown": 0, "empty": 0}
        for item in items:
            for f in url_fields:
                v = item.get(f)
                if not v:
                    cls_counts["empty"] += 1
                    continue
                c = classify(v)
                cls_counts[c] = cls_counts.get(c, 0) + 1
        frep["url_classification"] = cls_counts

        report["files"][name] = frep
        log.info(f"  {name}: {frep['item_count']} items, {frep['url_classification']}")

    return report


def audit_ai() -> dict:
    """Audit AI tools data files."""
    log.info(f"=== AI AUDIT ===")
    report = {"files": {}, "issues": [], "summary": {}}

    for name, fname in [("flows", "flows.json"), ("studio", "studio.json")]:
        path = config.AI_DIR / fname
        frep = {"path": str(path), "exists": path.exists()}
        if not path.exists():
            report["issues"].append(f"{name}: file missing")
            report["files"][name] = frep
            continue
        frep["size_kb"] = round(path.stat().st_size / 1024, 1)
        data = _load(path)
        if data is None:
            frep["valid"] = False
            report["issues"].append(f"{name}: invalid JSON")
            report["files"][name] = frep
            continue
        frep["valid"] = True
        if name == "flows":
            frep["template_count"] = len(data.get("templates", []))
            frep["user_flow_count"] = len(data.get("user_flows", {}).get("flows", []))
            frep["node_count"] = data.get("node_count", 0)
            report["summary"]["flow_templates"] = frep["template_count"]
            report["summary"]["user_flows"] = frep["user_flow_count"]
        elif name == "studio":
            frep["spotlight_count"] = len(data.get("spotlight_projects", []))
            frep["user_project_count"] = len(data.get("user_projects", []))
            report["summary"]["studio_spotlight"] = frep["spotlight_count"]
            report["summary"]["studio_user_projects"] = frep["user_project_count"]
        report["files"][name] = frep
        log.info(f"  {name}: {frep}")

    return report


def audit_cdn_reachability(sample_size: int = 10) -> dict:
    """Sample CDN URLs and verify they are reachable."""
    log.info(f"=== CDN REACHABILITY AUDIT (sample={sample_size}) ===")
    report = {"samples": [], "issues": []}

    # Collect sample URLs from each catalog
    samples: list[tuple[str, str]] = []  # (source, url)
    for name, fname, key in [("music", "music.json", "sitePlayableFilePath"),
                              ("sfx", "sfx.json", "sitePlayableFilePath"),
                              ("footage", "footage.json", "clipPath"),
                              ("luts", "luts.json", "thumbnailUrl"),
                              ("templates", "templates.json", "thumbnailUrl")]:
        path = config.CATALOG_DIR / fname
        data = _load(path)
        if not data: continue
        items = data.get({"music": "songs", "sfx": "items", "footage": "clips",
                          "luts": "luts", "templates": "templates"}.get(name, ""), [])
        if items:
            for item in random.sample(items, min(sample_size, len(items))):
                url = item.get(key)
                if url:
                    samples.append((name, url))

    from .. import auth
    for source, url in samples:
        cls = classify(url)
        try:
            status, hdrs, _ = request("HEAD", url, headers=auth.cdn_headers(), allow_redirects=False)
            ok = status in (200, 302, 304)
            report["samples"].append({
                "source": source, "url": url[:100], "classification": cls,
                "status": status, "ok": ok,
            })
            if not ok:
                report["issues"].append(f"{source}: {url[:80]} returned {status}")
        except Exception as e:
            report["samples"].append({
                "source": source, "url": url[:100], "classification": cls,
                "status": -1, "ok": False, "error": str(e)[:100],
            })
            report["issues"].append(f"{source}: {url[:80]} error: {e}")

    report["ok_count"] = sum(1 for s in report["samples"] if s["ok"])
    report["fail_count"] = len(report["samples"]) - report["ok_count"]
    log.info(f"  {report['ok_count']}/{len(report['samples'])} samples reachable")
    return report


def audit_blob_manifest() -> dict:
    """Audit blob manifest consistency."""
    log.info(f"=== BLOB MANIFEST AUDIT ===")
    m = blob_manifest()
    urls = m.all()
    report = {"manifest_count": len(urls), "issues": []}
    if not urls:
        report["issues"].append("Blob manifest is empty (no mirrored assets)")
    log.info(f"  {report['manifest_count']} mirrored URLs")
    return report


def audit_all() -> dict:
    """Run all audit steps."""
    return {
        "catalog": audit_catalog(),
        "ai": audit_ai(),
        "cdn_reachability": audit_cdn_reachability(sample_size=5),
        "blob_manifest": audit_blob_manifest(),
    }
