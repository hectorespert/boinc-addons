#!/usr/bin/env bash
# Driver for the run-boinc-addons skill: build, run, verify, and tear down
# the boinc and boinctui Home Assistant add-on images via plain Docker.
#
# Usage:
#   ./smoke.sh boinc      # build boinc image, run CI-style smoke test +
#                          # a persistent run/boinccmd exec check
#   ./smoke.sh boinctui   # build boinctui image, run it, curl the ttyd UI
#   ./smoke.sh all        # both, in sequence
#
# Run from anywhere; paths are resolved relative to this script.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

boinc_smoke() {
  echo "== boinc: build =="
  ( cd "$REPO_ROOT/boinc" && docker build -t boinc-addon-test:local . )

  echo "== boinc: CI-style smoke test (--exit-immediately true) =="
  docker volume rm -f boinc_test_local >/dev/null 2>&1 || true
  docker run --uts=host --pid=host --rm \
    -v boinc_test_local:/data \
    -v "$REPO_ROOT/boinc/operator/options.json:/data/options.json:ro" \
    boinc-addon-test:local \
    --log-level DEBUG \
    --exit-immediately true
  echo "-> exit-immediately smoke test passed (exit code 0, see log above for 'BOINC client initialized')"

  echo "== boinc: persistent run + boinccmd exec check =="
  docker rm -f boinc-driver-test >/dev/null 2>&1 || true
  docker run -d --name boinc-driver-test --uts=host --pid=host \
    -v boinc_test_local:/data \
    -v "$REPO_ROOT/boinc/operator/options.json:/data/options.json:ro" \
    boinc-addon-test:local \
    --log-level DEBUG >/dev/null

  for _ in $(seq 1 20); do
    docker exec --workdir /data/boinc boinc-driver-test boinccmd --get_state >/tmp/boinc-get-state.out 2>&1 \
      && break
    sleep 0.5
  done
  grep -q "Time stats" /tmp/boinc-get-state.out || {
    echo "boinccmd --get_state did not return a valid state:"
    cat /tmp/boinc-get-state.out
    exit 1
  }
  echo "-> boinccmd --get_state responded with client state (Time stats section present)"

  docker rm -f boinc-driver-test >/dev/null
  docker volume rm -f boinc_test_local >/dev/null
  echo "== boinc: cleaned up =="
}

boinctui_smoke() {
  echo "== boinctui: build =="
  ( cd "$REPO_ROOT/boinctui" && docker build -t boinctui-addon-test:local . )

  echo "== boinctui: run + curl ttyd =="
  docker rm -f boinctui-driver-test >/dev/null 2>&1 || true
  docker run -d --name boinctui-driver-test -p 17681:7681 boinctui-addon-test:local >/dev/null

  for _ in $(seq 1 20); do
    code=$(curl -sS -o /tmp/boinctui-index.html -w '%{http_code}' --max-time 5 \
      -H "X-Remote-User-Name: test" http://localhost:17681/ 2>/dev/null || true)
    [ "$code" = "200" ] && break
    sleep 0.5
  done
  if [ "$code" != "200" ]; then
    echo "ttyd did not come up (last HTTP code: $code)"
    docker logs boinctui-driver-test
    exit 1
  fi
  grep -q "ttyd - Terminal" /tmp/boinctui-index.html
  echo "-> ttyd served the terminal UI (HTTP 200, title 'ttyd - Terminal')"

  docker rm -f boinctui-driver-test >/dev/null
  echo "== boinctui: cleaned up =="
}

case "${1:-}" in
  boinc) boinc_smoke ;;
  boinctui) boinctui_smoke ;;
  all) boinc_smoke; boinctui_smoke ;;
  *)
    echo "Usage: $0 {boinc|boinctui|all}" >&2
    exit 1
    ;;
esac
