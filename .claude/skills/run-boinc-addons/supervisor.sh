#!/usr/bin/env bash
# Run the add-ons under a real Home Assistant Supervisor, not plain Docker.
#
# Wraps the repo's .devcontainer (ghcr.io/home-assistant/devcontainer:2-addons) from the
# command line, applying the workarounds documented in SKILL.md. Everything happens inside
# one privileged container named $CONTAINER; the repo itself is never modified.
set -euo pipefail

CONTAINER="ha-addons-dev"
IMAGE="ghcr.io/home-assistant/devcontainer:2-addons"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HA_URL="http://localhost:7123"

# Supervisor reads the local store from /data/apps/local (the addons -> apps rename);
# devcontainer_bootstrap still mounts into the legacy addons/local, so we place add-ons here.
APPS_LOCAL="/mnt/supervisor/apps/local"

indocker() { docker exec "$CONTAINER" bash -lc "$1"; }
ha() { indocker "docker exec hassio_cli ha $1 --no-progress"; }

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [addon]

  up                 start the devcontainer and boot Supervisor (idempotent)
  install <addon>    stage boinc|boinctui|boincui into the local store, build it, install and start it
  logs <addon>       tail that add-on's log as Supervisor sees it
  status             list installed apps and the Supervisor container states
  down               remove the devcontainer and its volumes (frees ~5GB)

Home Assistant UI: $HA_URL
EOF
}

require_addon() {
    case "${1:-}" in
        boinc | boinctui | boincui) ;;
        *)
            echo "error: expected 'boinc', 'boinctui' or 'boincui', got '${1:-}'" >&2
            exit 1
            ;;
    esac
}

supervisor_running() {
    indocker 'docker inspect -f "{{.State.Status}}" hassio_supervisor 2>/dev/null' 2>/dev/null | grep -q running
}

container_running() {
    [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ]
}

# supervisor_run starts the devcontainer's own dockerd, but on a container that was stopped
# uncleanly it finds a stale /var/run/docker.pid, concludes the daemon is already up, fails to
# connect to it and gives up -- leaving the whole hassio stack down with nothing but
# `Cannot connect to the Docker daemon` in /tmp/supervisor.log. Clearing the pidfile and starting
# dockerd ourselves first is what makes a restart behave like a first boot.
ensure_docker() {
    indocker 'docker info' >/dev/null 2>&1 && return

    echo "==> starting the devcontainer's Docker daemon"
    docker exec -d "$CONTAINER" bash -lc 'rm -f /var/run/docker.pid && dockerd > /tmp/dockerd.log 2>&1'

    local waited=0
    until indocker 'docker info' >/dev/null 2>&1; do
        sleep 2
        waited=$((waited + 2))
        if [ "$waited" -ge 60 ]; then
            echo "error: dockerd did not start inside $CONTAINER; see /tmp/dockerd.log there" >&2
            exit 1
        fi
    done
}

cmd_up() {
    if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
        echo "==> starting devcontainer $CONTAINER"
        docker run -d --name "$CONTAINER" --privileged \
            -e WORKSPACE_DIRECTORY=/workspaces/boinc-addons \
            -v "$REPO_ROOT:/workspaces/boinc-addons" \
            -v ha-dev-docker:/var/lib/docker \
            -v ha-dev-supervisor:/mnt/supervisor \
            -p 7123:8123 -p 7357:4357 -p 21416:31416 \
            "$IMAGE" sleep infinity >/dev/null
        indocker 'bash /usr/bin/supervisor_bootstrap'
    elif ! container_running; then
        # `docker inspect` succeeds for a stopped container too, so testing existence alone left
        # every command below failing with `container ... is not running`.
        echo "==> restarting existing devcontainer $CONTAINER"
        docker start "$CONTAINER" >/dev/null
    fi

    ensure_docker

    if supervisor_running; then
        echo "==> Supervisor already running"
    else
        echo "==> booting Supervisor (first run pulls ~2GB of HA images, several minutes)"
        # Home Assistant Core bind-mounts /run/supervisor; it is created on the very first boot
        # and lost if Supervisor is restarted by hand, which then fails Core with
        # `bind source path does not exist`.
        indocker 'mkdir -p /run/supervisor'
        # -t is required: supervisor_run calls `stty sane`, which fails without a TTY and,
        # under `set -e`, kills the script right after dockerd starts.
        docker exec -dt "$CONTAINER" bash -lc 'supervisor_run > /tmp/supervisor.log 2>&1'
    fi

    # Readiness is the Supervisor API, not the Home Assistant UI: add-ons install and run
    # through Supervisor alone, and Core takes several more minutes to come up.
    echo "==> waiting for the Supervisor API"
    until ha 'supervisor info' >/dev/null 2>&1; do sleep 5; done

    # In docker-in-docker the gateway health check fails, and an unhealthy system refuses
    # every install with `blocked from execution, system is not healthy`.
    ha 'jobs options --ignore-conditions healthy' >/dev/null
    echo "==> ready: $HA_URL"
}

cmd_install() {
    local addon="$1"
    require_addon "$addon"
    supervisor_running || {
        echo "error: Supervisor is not running, run '$(basename "$0") up' first" >&2
        exit 1
    }

    # Supervisor refuses to install over an existing app with `App ... is already installed`, so
    # every iteration used to need a manual uninstall first. Reinstalling is also the only way to
    # re-read config.yaml and translations, which Supervisor snapshots into apps.json at install
    # time -- editing them and restarting keeps serving the old values.
    # Note this discards the app's /data, which is the point when testing a schema and a nuisance
    # when testing an upgrade: for that, edit the version and use `ha apps update` by hand instead.
    if ha "apps info local_$addon" >/dev/null 2>&1; then
        echo "==> uninstalling the previously installed local_$addon"
        ha "apps uninstall local_$addon" >/dev/null
    fi

    echo "==> staging $addon into the local store"
    # A copy, not a bind mount: Supervisor keeps submounts from its own start in its mount
    # namespace, so a mount added later is invisible to it until it is restarted.
    indocker "rm -rf $APPS_LOCAL/$addon && cp -r /workspaces/boinc-addons/$addon $APPS_LOCAL/$addon"
    # With `image:` set, Supervisor pulls the published image instead of building the local
    # source -- and a version that is not released yet fails with a 404 manifest.
    indocker "sed -i 's|^image: |# image: |' $APPS_LOCAL/$addon/config.yaml"

    ha 'store reload' >/dev/null
    sleep 5

    echo "==> building and installing local_$addon (first build takes several minutes)"
    ha "store apps install local_$addon"
    ha "apps start local_$addon"
    ha "apps info local_$addon --raw-json" 2>/dev/null |
        docker exec -i "$CONTAINER" jq -r '.data | {slug, version, state, protected}'
}

cmd_logs() {
    require_addon "${1:-}"
    ha "apps logs local_$1"
}

cmd_status() {
    indocker 'docker ps --format "{{.Names}}\t{{.Status}}"'
    echo
    ha 'apps' | grep -E 'slug:|name:|version:|state:' || echo '(no apps installed)'
}

cmd_down() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    docker volume rm ha-dev-docker ha-dev-supervisor >/dev/null 2>&1 || true
    echo "==> removed $CONTAINER and its volumes"
}

case "${1:-}" in
    up) cmd_up ;;
    install) cmd_install "${2:-}" ;;
    logs) cmd_logs "${2:-}" ;;
    status) cmd_status ;;
    down) cmd_down ;;
    *)
        usage
        exit 1
        ;;
esac
