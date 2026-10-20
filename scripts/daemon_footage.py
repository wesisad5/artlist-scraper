#!/usr/bin/env python3
"""Double-forked daemon for the footage scrape (separate from main catalog)."""
import os, sys, time, json, logging

def daemonize():
    if os.fork(): os._exit(0)
    os.setsid()
    if os.fork(): os._exit(0)
    sys.stdout.flush(); sys.stderr.flush()
    devnull = os.open('/dev/null', os.O_RDWR)
    os.dup2(devnull, 0); os.dup2(devnull, 1); os.dup2(devnull, 2)

daemonize()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("/tmp/footage_scrape.log"),
    ],
)
log = logging.getLogger("footage_daemon")

sys.path.insert(0, '/home/z/my-project/artlist-scraper')
os.chdir('/home/z/my-project/artlist-scraper')

# Heartbeat
import threading
heartbeat_path = "/home/sync/footage_scrape.heartbeat"
os.makedirs("/home/sync", exist_ok=True)
stop_hb = threading.Event()
def heartbeat():
    while not stop_hb.wait(60):
        try:
            with open(heartbeat_path, "w") as f:
                json.dump({"ts": time.time(), "pid": os.getpid()}, f)
        except Exception: pass
threading.Thread(target=heartbeat, daemon=True).start()

log.info(f"Footage daemon PID {os.getpid()} starting")
try:
    from src.scrapers import footage
    from src import graphql
    # Fetch footage categories
    cats = graphql.root_categories("footage")
    log.info(f"Got {len(cats)} footage root categories")
    data = footage.scrape_footage(categories=cats, max_pages_per_filter=60)
    # Save
    import json
    with open('/home/z/my-project/artlist-scraper/data/catalog/footage.json', 'w') as f:
        json.dump(data, f, indent=2)
    log.info(f"Footage scrape done: {data.get('total_unique_clips', 0)} clips, {data.get('total_stories', 0)} stories")
    with open(heartbeat_path, "w") as f:
        json.dump({"ts": time.time(), "pid": os.getpid(), "done": True, "clips": data.get('total_unique_clips', 0)}, f)
except Exception as e:
    log.exception(f"Footage daemon crashed: {e}")
    with open(heartbeat_path, "w") as f:
        json.dump({"ts": time.time(), "pid": os.getpid(), "error": str(e)}, f)
finally:
    stop_hb.set()
