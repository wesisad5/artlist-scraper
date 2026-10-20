#!/usr/bin/env python3
"""Double-forked daemon that runs ONE catalog step at a time, then exits.
Re-launch this script to run the next step. Repeat until progress.done=true."""
import os, sys, time, json, logging, argparse

def daemonize():
    if os.fork(): os._exit(0)
    os.setsid()
    if os.fork(): os._exit(0)
    sys.stdout.flush(); sys.stderr.flush()
    devnull = os.open('/dev/null', os.O_RDWR)
    os.dup2(devnull, 0); os.dup2(devnull, 1); os.dup2(devnull, 2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="/tmp/scrape_step.log")
    args = parser.parse_args()

    daemonize()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(args.log)],
    )
    log = logging.getLogger("scrape_step")

    sys.path.insert(0, '/home/z/my-project/artlist-scraper')
    os.chdir('/home/z/my-project/artlist-scraper')

    # Heartbeat
    import threading
    hb_path = "/home/sync/scrape_step.heartbeat"
    os.makedirs("/home/sync", exist_ok=True)
    stop_hb = threading.Event()
    def heartbeat():
        while not stop_hb.wait(30):
            try:
                with open(hb_path, "w") as f:
                    json.dump({"ts": time.time(), "pid": os.getpid()}, f)
            except: pass
    threading.Thread(target=heartbeat, daemon=True).start()

    log.info(f"Daemon PID {os.getpid()} starting: catalog --resume")
    try:
        from src.cli import main as cli_main
        sys.argv = ['src.cli', 'catalog', '--resume']
        cli_main()
        log.info("Step complete.")
        with open(hb_path, "w") as f:
            json.dump({"ts": time.time(), "pid": os.getpid(), "done": True}, f)
    except Exception as e:
        log.exception(f"Daemon crashed: {e}")
        with open(hb_path, "w") as f:
            json.dump({"ts": time.time(), "pid": os.getpid(), "error": str(e)}, f)
    finally:
        stop_hb.set()
