#!/usr/bin/env bash
set -e

# Ensure /data/boinctui exists and has correct permissions
mkdir -p /data/boinctui
chown -R boinctui:boinctui /data/boinctui

# Get boinctui user UID and GID
BOINCTUI_UID=$(id -u boinctui)
BOINCTUI_GID=$(id -g boinctui)

# Execute ttyd with boinctui using -u and -g parameters
exec ttyd \
    -p 7681 \
    -d 1 \
    -W \
    --auth-header X-Remote-User-Name \
    -u "$BOINCTUI_UID" \
    -g "$BOINCTUI_GID" \
    -w /data/boinctui \
    /bin/bash -c "HOME=/data/boinctui exec boinctui"
