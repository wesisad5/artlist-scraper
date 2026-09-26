"""CLI entry point.

Usage:
  python -m src.cli catalog [--skip music,footage]
  python -m src.cli ai [--skip flows]
  python -m src.cli all
  python -m src.cli audit
  python -m src.cli serve [--port 8000]
  python -m src.cli test-auth
"""
import argparse
import json
import logging
import sys
from . import config
from .pipelines import catalog as cat_pipeline
from .pipelines import audit as audit_pipeline


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_test_auth(args):
    """Quick auth check for all endpoints."""
    from . import graphql, trpc
    print("== Testing auth ==")
    # GraphQL
    try:
        cats = graphql.root_categories("music")
        print(f"  GraphQL (search-api.artlist.io): OK - {len(cats)} music categories")
    except Exception as e:
        print(f"  GraphQL: FAILED - {e}")
    # Flows trpc
    try:
        data = trpc.flows_template_list(per_page=1)
        items = data.get("items", []) if isinstance(data, dict) else []
        print(f"  tRPC flows.artlist.io: OK - {len(items)} templates in 1 page")
    except Exception as e:
        print(f"  tRPC flows: FAILED - {e}")
    # Studio trpc
    try:
        data = trpc.studio_spotlight_projects(page=1, page_size=1)
        items = data.get("data", []) if isinstance(data, dict) else []
        print(f"  tRPC studio.artlist.io: OK - {len(items)} spotlight projects in 1 page")
    except Exception as e:
        print(f"  tRPC studio: FAILED - {e}")


def cmd_catalog(args):
    skip = args.skip.split(",") if args.skip else []
    meta = cat_pipeline.run_catalog(skip=skip)
    print(json.dumps(meta, indent=2))


def cmd_ai(args):
    skip = args.skip.split(",") if args.skip else []
    meta = cat_pipeline.run_ai(skip=skip)
    print(json.dumps(meta, indent=2))


def cmd_all(args):
    skip = args.skip.split(",") if args.skip else []
    meta = cat_pipeline.run_all(skip=skip)
    print(json.dumps(meta, indent=2))


def cmd_audit(args):
    report = audit_pipeline.audit_all()
    print(json.dumps(report, indent=2, default=str))


def cmd_serve(args):
    """Serve the UI + data files."""
    import http.server
    import socketserver
    import os
    from pathlib import Path

    ui_dir = Path(__file__).parent.parent / "ui"
    project_root = Path(__file__).parent.parent

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            # Map /data/* to project data dir
            if path.startswith("/data/"):
                return str(project_root / path.lstrip("/"))
            if path.startswith("/api/"):
                return self._api(path)
            return str(ui_dir / path.lstrip("/")) or str(ui_dir / "index.html")

        def _api(self, path):
            return str(ui_dir / "index.html")  # fallback

        def do_GET(self):
            # Special routes
            if self.path == "/" or self.path == "":
                self.path = "/index.html"
            if self.path.startswith("/api/"):
                self._handle_api(self.path)
                return
            super().do_GET()

        def _handle_api(self, path):
            from urllib.parse import urlparse, parse_qs
            import json
            p = urlparse(path)
            qs = parse_qs(p.query)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if p.path == "/api/catalog":
                # Return catalog summary
                summary = {}
                for name in ["music", "sfx", "footage", "luts", "templates", "collections"]:
                    f = config.CATALOG_DIR / f"{name}.json"
                    if f.exists():
                        try:
                            data = json.loads(f.read_text())
                            items_key = {"music": "songs", "sfx": "items", "footage": "clips",
                                         "luts": "luts", "templates": "templates",
                                         "collections": "collections"}.get(name, "")
                            summary[name] = {
                                "count": len(data.get(items_key, [])),
                                "size_kb": round(f.stat().st_size / 1024, 1),
                            }
                        except Exception:
                            summary[name] = {"error": "parse_failed"}
                    else:
                        summary[name] = {"missing": True}
                self.wfile.write(json.dumps(summary).encode())
                return
            if p.path == "/api/latest":
                f = config.META_DIR / "latest.json"
                if f.exists():
                    self.wfile.write(f.read_bytes())
                else:
                    self.wfile.write(b"{}")
                return
            # Default: serve catalog files
            self.wfile.write(b"{}")

    port = args.port
    print(f"Serving UI from {ui_dir} on http://localhost:{port}")
    print(f"Data dir: {config.DATA_DIR}")
    with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
        httpd.serve_forever()


def main():
    p = argparse.ArgumentParser(prog="artlist-scraper")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("test-auth", help="Quick auth check").set_defaults(func=cmd_test_auth)

    p_cat = sub.add_parser("catalog", help="Run catalog scrape")
    p_cat.add_argument("--skip", help="Comma-separated list to skip (music,sfx,footage,luts,templates,collections,categories)")
    p_cat.set_defaults(func=cmd_catalog)

    p_ai = sub.add_parser("ai", help="Run AI tools scrape")
    p_ai.add_argument("--skip", help="Comma-separated list to skip (flows,studio)")
    p_ai.set_defaults(func=cmd_ai)

    p_all = sub.add_parser("all", help="Run everything")
    p_all.add_argument("--skip", help="Comma-separated list to skip")
    p_all.set_defaults(func=cmd_all)

    sub.add_parser("audit", help="Run E2E audit").set_defaults(func=cmd_audit)

    p_serve = sub.add_parser("serve", help="Serve UI")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    args = p.parse_args()
    setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
