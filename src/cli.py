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
    """Serve the UI + data files + CDN proxy."""
    import http.server
    import socketserver
    import os
    import urllib.parse
    import urllib.request
    from pathlib import Path

    ui_dir = Path(__file__).parent.parent / "ui"
    project_root = Path(__file__).parent.parent

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            # Map /data/* to project data dir
            if path.startswith("/data/"):
                return str(project_root / path.lstrip("/"))
            return str(ui_dir / path.lstrip("/")) or str(ui_dir / "index.html")

        def log_message(self, fmt, *args):
            # Log to stderr for debugging
            import sys
            sys.stderr.write(f"[UI] {self.address_string()} - {fmt % args}\n")

        def do_GET(self):
            # Parse path explicitly
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            path_only = parsed.path
            qs = parse_qs(parsed.query)

            # CDN proxy: /api/cdn-proxy?url=<encoded_url>
            if path_only == "/api/cdn-proxy":
                self._handle_cdn_proxy(qs)
                return

            # JSON API endpoints
            if path_only == "/api/catalog":
                self._handle_catalog_summary()
                return
            if path_only == "/api/latest":
                self._handle_latest()
                return

            # Default: serve static files (UI or data)
            if self.path == "/" or self.path == "":
                self.path = "/index.html"
            super().do_GET()

        def _handle_cdn_proxy(self, qs):
            import urllib.request, urllib.error
            url = qs.get("url", [None])[0]
            if not url:
                self.send_error(400, "Missing url parameter")
                return
            # Security: only allow artlist CDN hosts
            from urllib.parse import urlparse as up
            host = up(url).netloc
            allowed_hosts = (
                "cms-public-artifacts.artlist.io",
                "cms-toolkit-artifacts.artlist.io",
                "cms-artifacts.artlist.io",
                "artlist-studio-proxy.imgix.net",
            )
            if not (host in allowed_hosts or host.endswith(".imgix.net")):
                self.send_error(403, f"Host {host} not allowed")
                return
            # Determine origin based on URL host
            origin = "https://artlist.io"
            if "flows.artlist.io" in host:
                origin = "https://flows.artlist.io"
            elif "studio.artlist.io" in host:
                origin = "https://studio.artlist.io"
            # Forward request with proper headers
            try:
                req = urllib.request.Request(url, method="GET", headers={
                    "User-Agent": config.USER_AGENT,
                    "Origin": origin,
                    "Referer": origin + "/",
                    "Accept": "*/*",
                })
                opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
                resp = opener.open(req, timeout=30)
                try:
                    self.send_response(resp.status)
                    for h in ("Content-Type", "Content-Length", "Cache-Control", "ETag", "Last-Modified"):
                        v = resp.headers.get(h)
                        if v:
                            self.send_header(h, v)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    total = 0
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                            total += len(chunk)
                        except BrokenPipeError:
                            break
                finally:
                    resp.close()
            except urllib.error.HTTPError as e:
                self.send_error(e.code, f"Upstream error: {e}")
            except Exception as e:
                self.send_error(502, f"Proxy error: {e}")

        def _handle_catalog_summary(self):
            import json
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
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(summary).encode())

        def _handle_latest(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            f = config.META_DIR / "latest.json"
            if f.exists():
                self.wfile.write(f.read_bytes())
            else:
                self.wfile.write(b"{}")

    port = args.port
    print(f"Serving UI from {ui_dir} on http://localhost:{port}")
    print(f"Data dir: {config.DATA_DIR}")
    print(f"CDN proxy: /api/cdn-proxy?url=<encoded_url>")
    # Enable SO_REUSEADDR to avoid "Address already in use" after restart
    socketserver.TCPServer.allow_reuse_address = True
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
