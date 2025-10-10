#!/usr/bin/env bash
set -e

echo "[INFO] Starting boinctui addon..."
echo "[INFO] Hello World from boinctui!"

# Main loop - keep addon running
while true; do
    echo "[INFO] boinctui is running: $(date)"
    sleep 60
done
