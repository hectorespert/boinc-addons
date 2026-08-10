#!/usr/bin/env bash
# Driver for the run-boinc-addons skill: build, run, verify, and tear down
# the boinc, boinctui and boincui Home Assistant add-on images via plain Docker.
#
# Usage:
#   ./smoke.sh boinc      # build boinc image, run CI-style smoke test +
#                          # a persistent run/boinccmd exec check
#   ./smoke.sh boinctui   # build boinctui image, run it, curl the ttyd UI
#   ./smoke.sh boincui    # build boincui image, run it, check it logs hello world
#   ./smoke.sh all        # all three, in sequence
#
# Run from anywhere; paths are resolved relative to this script.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

boinc_smoke() {
  echo "== boinc: build =="
  ( cd "$REPO_ROOT/boinc" && docker build -t boinc-addon-test:local . )

  echo "== boinc: CI-style smoke test (--exit-immediately) =="
  docker volume rm -f boinc_test_local >/dev/null 2>&1 || true
  docker run --uts=host --pid=host --rm \
    -v boinc_test_local:/data \
    -v "$REPO_ROOT/boinc/operator/options.json:/data/options.json:ro" \
    boinc-addon-test:local \
    --log-level DEBUG \
    --exit-immediately
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

boincui_smoke() {
  echo "== boincui: build =="
  ( cd "$REPO_ROOT/boincui" && docker build -t boincui-addon-test:local . )

  echo "== boincui: one-shot run (--exit-immediately) =="
  docker run --rm boincui-addon-test:local --log-level DEBUG --exit-immediately \
    >/tmp/boincui-run.log 2>&1
  grep -q "hello world" /tmp/boincui-run.log || {
    echo "boincui did not log the expected line:"
    cat /tmp/boincui-run.log
    exit 1
  }
  echo "-> exit-immediately run exited 0 and logged 'hello world'"

  echo "== boincui: persistent run + clean stop =="
  # The add-on has no interface to probe yet, so what matters is the lifecycle: it must stay up
  # until asked to stop, or Supervisor reports it as stopped seconds after the user starts it.
  docker rm -f boincui-driver-test >/dev/null 2>&1 || true
  docker run -d --name boincui-driver-test boincui-addon-test:local --log-level DEBUG >/dev/null

  for _ in $(seq 1 20); do
    docker logs boincui-driver-test 2>&1 | grep -q "BOINC UI started" && break
    sleep 0.5
  done
  [ "$(docker inspect -f '{{.State.Running}}' boincui-driver-test)" = "true" ] || {
    echo "boincui exited on its own instead of waiting to be stopped:"
    docker logs boincui-driver-test
    docker rm -f boincui-driver-test >/dev/null
    exit 1
  }
  echo "-> still running after startup"

  docker stop -t 10 boincui-driver-test >/dev/null
  code=$(docker inspect -f '{{.State.ExitCode}}' boincui-driver-test)
  if [ "$code" != "0" ]; then
    echo "boincui did not stop cleanly on SIGTERM (exit code $code)"
    docker logs boincui-driver-test
    docker rm -f boincui-driver-test >/dev/null
    exit 1
  fi
  docker logs boincui-driver-test 2>&1 | grep -q "BOINC UI stopped"
  echo "-> stopped cleanly on SIGTERM (exit code 0)"

  docker rm -f boincui-driver-test >/dev/null
  echo "== boincui: cleaned up =="
}

case "${1:-}" in
  boinc) boinc_smoke ;;
  boinctui) boinctui_smoke ;;
  boincui) boincui_smoke ;;
  all) boinc_smoke; boinctui_smoke; boincui_smoke ;;
  *)
    echo "Usage: $0 {boinc|boinctui|boincui|all}" >&2
    exit 1
    ;;
esac
