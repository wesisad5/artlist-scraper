#!/bin/bash
# Run the full scrape by repeatedly launching the daemon for each step.
# Each step runs in its own daemon process. We wait for each to complete before starting the next.
set -e

LOG_FILE=/tmp/scrape_chain.log
echo "=== Full scrape chain started $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" > $LOG_FILE

while true; do
    echo "--- Launching next step $(date -u +%H:%M:%S) ---" >> $LOG_FILE
    # Start the daemon
    python3 /home/z/my-project/scripts/daemon_scrape_step.py --log /tmp/scrape_step.log
    sleep 5  # wait for daemon to start
    
    # Wait for the daemon to complete (heartbeat says done=true or error)
    while true; do
        sleep 30
        HB=$(cat /home/sync/scrape_step.heartbeat 2>/dev/null || echo '{}')
        DONE=$(echo "$HB" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('done', False))" 2>/dev/null || echo "False")
        ERR=$(echo "$HB" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('error', ''))" 2>/dev/null || echo "")
        if [ "$DONE" = "True" ]; then
            echo "Step completed at $(date -u +%H:%M:%S)" >> $LOG_FILE
            break
        fi
        if [ -n "$ERR" ]; then
            echo "Step ERROR at $(date -u +%H:%M:%S): $ERR" >> $LOG_FILE
            break
        fi
    done
    
    # Check overall progress
    PROGRESS=$(cat /home/z/my-project/artlist-scraper/data/_meta/progress.json 2>/dev/null || echo '{}')
    ALL_DONE=$(echo "$PROGRESS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('done', False))" 2>/dev/null || echo "False")
    if [ "$ALL_DONE" = "True" ]; then
        echo "=== All steps complete! $(date -u +%H:%M:%S) ===" >> $LOG_FILE
        break
    fi
    # Continue to next step
    echo "Continuing to next step..." >> $LOG_FILE
done

echo "=== Chain complete $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> $LOG_FILE
