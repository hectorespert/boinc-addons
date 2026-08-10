---
name: run-boinc-addons
description: Build, run, and smoke-test the boinc, boinctui and boincui Home Assistant add-ons, either via plain Docker or under a real Home Assistant Supervisor. Use when asked to run boinc-addons, build/start the boinc, boinctui or boincui add-on, start the BOINC client in a container, talk to it via boinccmd, test the boinctui ttyd terminal UI, test an add-on in Home Assistant/Supervisor/the devcontainer, or run the Python unit tests.
---

This repo ships three independent Home Assistant add-ons (`boinc/`, `boinctui/`,
`boincui/`), each just a Dockerfile — no Supervisor is needed to build/run/drive them
locally, plain `docker build`/`docker run` is enough. Drive all three via
`.claude/skills/run-boinc-addons/smoke.sh`, which builds each image, launches it,
and verifies it's actually working (`boinccmd` RPC for `boinc`, an HTTP request to
`ttyd` for `boinctui`, a log line for `boincui`), then tears everything down. All
paths below are relative to the repo root.

Plain Docker cannot see anything Supervisor does *around* the container: option
schema validation, `config.yaml`/`build.yaml` conformance, translations, ingress,
protection mode, watchdog. For those, use `supervisor.sh` (see "Run under a real
Supervisor" below) — it is slower and heavier, so reach for `smoke.sh` first and
escalate only when the question is about the add-on's Home Assistant surface.

## Prerequisites

- A working Docker daemon (`docker info` succeeds). No other system packages are
  needed — the driver only shells out to `docker`, `curl`, and `grep`.
- Optional, only for the operator's Python unit tests: Python 3 and the `dict2xml`
  package (see Test section — a venv is recommended, not a system-wide install).

## Run (agent path)

```bash
./.claude/skills/run-boinc-addons/smoke.sh boinc      # build + smoke-test boinc
./.claude/skills/run-boinc-addons/smoke.sh boinctui    # build + smoke-test boinctui
./.claude/skills/run-boinc-addons/smoke.sh boincui     # build + smoke-test boincui
./.claude/skills/run-boinc-addons/smoke.sh all         # all three, in sequence
```

Exit code 0 means the image built and the running container was verified end to
end; any failure aborts the script (`set -euo pipefail`) with the relevant Docker
build/run/curl output on stdout. Each subcommand cleans up its own
containers/volumes on success.

What each subcommand actually does (all verified in this session):

| target | build | run | verify |
|---|---|---|---|
| `boinc` | `docker build -t boinc-addon-test:local boinc/` | CI-style one-shot run with `--exit-immediately`, then a second persistent run | `--exit-immediately` run exits 0; then `docker exec --workdir /data/boinc <container> boinccmd --get_state` returns a real state dump (`Time stats` section) |
| `boinctui` | `docker build -t boinctui-addon-test:local boinctui/` | `docker run -d -p 17681:7681 boinctui-addon-test:local` | `curl -H "X-Remote-User-Name: test" http://localhost:17681/` returns HTTP 200 with the ttyd terminal HTML page |
| `boincui` | `docker build -t boincui-addon-test:local boincui/` | a one-shot `docker run --rm boincui-addon-test:local --log-level DEBUG --exit-immediately`, then a detached run without the flag | the one-shot run exits 0 having logged `hello world`; the detached one is still running after startup and exits 0 on `docker stop`. The add-on has no interface yet, so its lifecycle is all there is to probe — and **without `--exit-immediately` it blocks until signalled**, so a foreground `docker run` will appear to hang |

## Run (human path)

Manual equivalent for `boinc` (from `boinc/`, see `boinc/DEVELOPMENT.md`):

```bash
docker build -t boinc-addon-test:local .
docker run -it --uts=host --pid=host --rm \
  -v boinc:/data \
  -v $(pwd)/operator/options.json:/data/options.json:ro \
  boinc-addon-test:local
```

Manual equivalent for `boinctui` (from `boinctui/`):

```bash
docker build -t boinctui-addon-test:local .
docker run -it -p 7681:7681 boinctui-addon-test:local
```

Then open `http://localhost:7681/` in a browser — but see Gotchas: a bare browser
request (no ingress header) gets a `407 Proxy Auth Required` from `ttyd`. This is
only reachable through Home Assistant's Ingress in production, which injects the
required header automatically.

## Run under a real Supervisor

Use this when the question is about the add-on's Home Assistant surface rather than
its process: whether `config.yaml`/`build.yaml` are accepted, whether the option
schema and `translations/*.yaml` render, whether ingress is wired, whether
protection mode/watchdog behave. It boots the repo's `.devcontainer`
(`ghcr.io/home-assistant/devcontainer:2-addons`) with a full Supervisor stack
(`hassio_supervisor`, `cli`, `dns`, `audio`, `observer`, `multicast`,
`homeassistant`) and installs the add-on from the local store, building it from
your working tree.

```bash
./.claude/skills/run-boinc-addons/supervisor.sh up               # boot Supervisor (idempotent)
./.claude/skills/run-boinc-addons/supervisor.sh install boinc    # stage + build + install + start
./.claude/skills/run-boinc-addons/supervisor.sh install boinctui
./.claude/skills/run-boinc-addons/supervisor.sh install boincui
./.claude/skills/run-boinc-addons/supervisor.sh logs boinc       # the log as Supervisor sees it
./.claude/skills/run-boinc-addons/supervisor.sh status
./.claude/skills/run-boinc-addons/supervisor.sh down             # remove container + volumes (~5GB)
```

`install` prints the installed state, e.g.:

```
{"slug": "local_boinctui", "version": "2.4.1", "state": "started", "protected": true}
```

Cost: ~2GB of HA images on the first `up` (several minutes), plus a full add-on
build per `install`. Everything lives inside the `ha-addons-dev` container and two
named volumes; the repo is only ever read.

Home Assistant's own UI is at `http://localhost:7123` once Core finishes starting,
but you do not need it — add-ons install and run through Supervisor alone, which is
why `up` waits on the Supervisor API rather than the UI.

Useful probes once an add-on is installed (all through the CLI in `hassio_cli`):

```bash
docker exec ha-addons-dev bash -lc \
  'docker exec hassio_cli ha apps info local_boinctui --raw-json' | jq -c '.data.ingress_url'
# -> "/api/hassio_ingress/t8TZXaXBaLxQ9i9GCxhdl4e7yzqk0wrkOwIr3a3hsks/"

docker exec ha-addons-dev bash -lc \
  'docker exec hassio_cli ha apps info local_boinc --raw-json' | jq '.data.translations.es.configuration | length'
# -> 10

docker exec ha-addons-dev bash -lc 'docker logs hassio_supervisor 2>&1 | grep -i "apps.validate\|apps.build"'
# config.yaml / build.yaml conformance warnings for your add-on land here
```

## Test

Operator unit tests (from `boinc/operator/`) need the `dict2xml` package, which
isn't in the stdlib — install it in a venv rather than system-wide:

```bash
cd boinc/operator
python3 -m venv .venv
.venv/bin/pip install --quiet dict2xml
.venv/bin/python -m unittest discover -s test -t test
# -> Ran 15 tests in 0.005s / OK
```

Running `python -m unittest discover -s test -t test` without `dict2xml` installed
still runs but reports 2 module-import errors (12 tests instead of 15) — see
Gotchas.

## Gotchas

- **`docker exec <container> boinccmd ...` fails with `Authorization failure: -155`
  unless you also pass `--workdir /data/boinc`.** `boinccmd` looks for
  `gui_rpc_auth.cfg` in its current working directory, not via a `--dir` flag —
  which is exactly why `boinc/operator/boinccmd.py` always calls
  `subprocess.run([...], cwd=data_folder)` internally. Any external `docker exec`
  driving `boinccmd` needs the same `--workdir`.
- **`curl`ing `boinctui`'s ttyd without a header returns `407 Proxy Auth
  Required`, not a connection error.** `boinctui/run.sh` launches `ttyd` with
  `--auth-header X-Remote-User-Name`, which is how it trusts Home Assistant
  Ingress's identity header instead of doing its own login. Any direct HTTP check
  needs `-H "X-Remote-User-Name: <anything>"`.
- **The `boinc` client itself logs `Docker found but 'hello-world' test failed`
  on every startup inside the container** — it's BOINC probing whether it can run
  nested Docker-based science apps (needs the host's Docker socket mounted in,
  which the smoke test doesn't do). Harmless for build/run verification purposes.
- **`ttyd` can refuse the first connection right after the container starts**
  (`curl: (56) Recv failure: Connection reset by peer`) before it's actually
  listening — the driver retries with a short poll loop, so this only matters if
  you're curling it manually; retry once or two after a `sleep 0.5`.
- **Supervisor mode, five traps, all handled by `supervisor.sh` — but you will hit
  them the moment you drive it by hand:**
  1. `supervisor_run` calls `stty sane` and runs under `set -e`, so without a TTY it
     dies silently right after `Waiting for Docker to initialize...`. Use
     `docker exec -dt`, never `-d` alone.
  2. In docker-in-docker the `docker_gateway_unprotected` health check fails and
     Supervisor refuses every install with `blocked from execution, system is not
     healthy`. Clear it with `ha jobs options --ignore-conditions healthy`.
  3. `devcontainer_bootstrap` bind-mounts the workspace into
     `/mnt/supervisor/addons/local/`, but the current Supervisor reads its local
     store from `/mnt/supervisor/apps/local/` (the add-on -> app rename). Stage
     add-ons in `apps/local` or Supervisor silently uses the stale copy.
  4. With `image:` present in `config.yaml`, Supervisor pulls the published image
     instead of building your working tree — and 404s if that version isn't
     released. Comment it out in the staged copy (the driver does).
  5. Restarting `hassio_supervisor` by hand loses `/run/supervisor`, after which
     Home Assistant Core fails to start with `bind source path does not exist`.
     `mkdir -p /run/supervisor` before rebooting Supervisor fixes it.
- **An installed add-on's metadata is a snapshot.** Supervisor stores the parsed
  `config.yaml`/`translations` in `/mnt/supervisor/apps.json` at install time, so
  `ha apps info` keeps serving the old values after you edit those files — even
  across a Supervisor restart. Re-run `install` to re-read them.
- **`ha apps logs local_boinctui` is legitimately empty** until something connects
  through ingress: `ttyd` writes nothing on startup. `local_boinc` logs immediately.
- **Operator unit tests silently under-report** if `dict2xml` isn't installed:
  `python -m unittest discover` still exits with a failure summary, but only 2 of
  the 5 test modules actually failed to import — read the `ModuleNotFoundError`,
  don't assume real test regressions.

## Troubleshooting

- **`docker pull`/`docker build` hangs indefinitely with zero output** (not even
  past `Using default tag: latest`): check `docker info` for
  `HTTP Proxy: http.docker.internal:3128` — if Docker Desktop's internal VM proxy
  is wedged, pulls hang forever instead of failing fast. Fix: restart Docker
  Desktop, then retry (`docker pull hello-world` should complete in a few
  seconds).
- **`boinccmd --get_state` → `Authorization failure: -155`**: missing
  `--workdir /data/boinc` on the `docker exec` call — see Gotchas.
- **`curl` on boinctui's port → `407 Proxy Auth Required`**: missing the
  `X-Remote-User-Name` header — see Gotchas.
- **Supervisor install fails with `Can't install ghcr.io/...:<version>: [404]
  manifest unknown`**: it is pulling instead of building. Either `image:` is still
  uncommented in the staged copy, or Supervisor is reading a stale copy from
  `apps/local` — see Gotchas 3 and 4.
- **Supervisor build fails with `/bin/bash: line 1: apt-get: command not found`**:
  `build.yaml` was rejected and Supervisor fell back to its Alpine base. Check for
  `Error parsing ... build config ... using defaults` in the Supervisor log; the
  cause is a `build_from` value that doesn't match Supervisor's `owner/name` regex,
  which is why both add-ons pin `docker.io/library/debian:...` rather than the bare
  `debian:...`.
