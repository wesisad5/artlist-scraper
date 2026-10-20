#!/usr/bin/env python3
"""Double-forked daemon for mirroring signed URLs to Netlify blob."""
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
    handlers=[logging.FileHandler("/tmp/mirror.log")],
)
log = logging.getLogger("mirror")

sys.path.insert(0, '/home/z/my-project/artlist-scraper')
os.chdir('/home/z/my-project/artlist-scraper')

hb_path = "/home/sync/mirror.heartbeat"
os.makedirs("/home/sync", exist_ok=True)
stop_hb = threading.Event()
def heartbeat():
    while not stop_hb.wait(30):
        try:
            with open(hb_path, "w") as f:
                json.dump({"ts": time.time(), "pid": os.getpid()}, f)
        except: pass
threading.Thread(target=heartbeat, daemon=True).start()

log.info(f"Mirror daemon PID {os.getpid()} starting")
try:
    from src.cli import main as cli_main
    sys.argv = ['src.cli', 'mirror-signed']
    cli_main()
    log.info("Mirror complete.")
    with open(hb_path, "w") as f:
        json.dump({"ts": time.time(), "pid": os.getpid(), "done": True}, f)
except Exception as e:
    log.exception(f"Mirror crashed: {e}")
    with open(hb_path, "w") as f:
        json.dump({"ts": time.time(), "pid": os.getpid(), "error": str(e)}, f)
finally:
    stop_hb.set()
