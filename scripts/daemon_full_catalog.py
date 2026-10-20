#!/usr/bin/env python3
"""Double-forked daemon that runs the FULL catalog scrape (all steps in one process).
Survives bash toolcall ends. Logs to /tmp/full_catalog.log.
Writes heartbeat to /home/sync/full_catalog.heartbeat every 60s."""
import os, sys, time, json, logging, threading

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
    handlers=[logging.FileHandler("/tmp/full_catalog.log")],
)
log = logging.getLogger("full_catalog")

sys.path.insert(0, '/home/z/my-project/artlist-scraper')
os.chdir('/home/z/my-project/artlist-scraper')

# Heartbeat
hb_path = "/home/sync/full_catalog.heartbeat"
os.makedirs("/home/sync", exist_ok=True)
stop_hb = threading.Event()
def heartbeat():
    while not stop_hb.wait(60):
        try:
            with open(hb_path, "w") as f:
                json.dump({"ts": time.time(), "pid": os.getpid()}, f)
        except: pass
threading.Thread(target=heartbeat, daemon=True).start()

log.info(f"Daemon PID {os.getpid()} starting full catalog scrape")
try:
    from src.cli import main as cli_main
    sys.argv = ['src.cli', 'catalog']
    cli_main()
    log.info("Full catalog scrape complete.")
    with open(hb_path, "w") as f:
        json.dump({"ts": time.time(), "pid": os.getpid(), "done": True}, f)
except Exception as e:
    log.exception(f"Daemon crashed: {e}")
    with open(hb_path, "w") as f:
        json.dump({"ts": time.time(), "pid": os.getpid(), "error": str(e)}, f)
finally:
    stop_hb.set()
