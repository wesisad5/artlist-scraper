#!/usr/bin/env python3
"""Double-forked daemon for the full catalog scrape with pagination breakthrough."""
import os, sys, time, json, logging, signal

def daemonize():
    if os.fork(): os._exit(0)
    os.setsid()
    if os.fork(): os._exit(0)
    sys.stdout.flush(); sys.stderr.flush()
    devnull = os.open('/dev/null', os.O_RDWR)
    os.dup2(devnull, 0); os.dup2(devnull, 1); os.dup2(devnull, 2)

daemonize()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler("/tmp/catalog_scrape.log")],
)
log = logging.getLogger("daemon")

sys.path.insert(0, '/home/z/my-project/artlist-scraper')
os.chdir('/home/z/my-project/artlist-scraper')

heartbeat_path = "/home/sync/catalog_scrape.heartbeat"
os.makedirs("/home/sync", exist_ok=True)
stop_hb = [False]

def heartbeat():
    while not stop_hb[0]:
        try:
            with open(heartbeat_path, "w") as f:
                json.dump({"ts": time.time(), "pid": os.getpid()}, f)
        except: pass
        time.sleep(30)

import threading
threading.Thread(target=heartbeat, daemon=True).start()

log.info(f"Daemon PID {os.getpid()} starting full catalog scrape (breakthrough mode)")
try:
    from src.pipelines import catalog as cat_pipeline
    meta = cat_pipeline.run_catalog()
    log.info(f"Catalog scrape done: {json.dumps(meta.get('totals', {}))}")
    # Save progress
    progress = {
        "done_steps": list(meta.get("steps", {}).keys()),
        "done": all(s.get("status") == "ok" for s in meta.get("steps", {}).values()),
        "totals": meta.get("totals", {}),
        "run_id": meta.get("run_id"),
    }
    from src import config
    (config.META_DIR / "progress.json").write_text(json.dumps(progress, indent=2))
    with open(heartbeat_path, "w") as f:
        json.dump({"ts": time.time(), "pid": os.getpid(), "done": True, "totals": meta.get("totals", {})}, f)
except Exception as e:
    log.exception(f"Daemon crashed: {e}")
    with open(heartbeat_path, "w") as f:
        json.dump({"ts": time.time(), "pid": os.getpid(), "error": str(e)}, f)
finally:
    stop_hb[0] = True
