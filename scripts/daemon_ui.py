#!/usr/bin/env python3
"""Double-forked daemon for the UI server.

Survives bash toolcall ends. Serves UI + data + CDN proxy on port 9000.
"""
import os, sys

def daemonize():
    if os.fork(): os._exit(0)
    os.setsid()
    if os.fork(): os._exit(0)
    sys.stdout.flush(); sys.stderr.flush()
    devnull = os.open('/dev/null', os.O_RDWR)
    os.dup2(devnull, 0); os.dup2(devnull, 1); os.dup2(devnull, 2)

daemonize()
sys.path.insert(0, '/home/z/my-project/artlist-scraper')
os.chdir('/home/z/my-project/artlist-scraper')
from src.cli import cmd_serve
import argparse
args = argparse.Namespace(port=9000, verbose=False)
cmd_serve(args)
