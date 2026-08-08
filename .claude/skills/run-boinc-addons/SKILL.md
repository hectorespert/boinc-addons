---
name: run-boinc-addons
description: Build, run, and smoke-test the boinc and boinctui Home Assistant add-ons via plain Docker (no Supervisor needed). Use when asked to run boinc-addons, build/start the boinc or boinctui add-on, start the BOINC client in a container, talk to it via boinccmd, test the boinctui ttyd terminal UI, or run the operator's Python unit tests.
---

This repo ships two independent Home Assistant add-ons (`boinc/`, `boinctui/`), each
just a Dockerfile — no Supervisor is needed to build/run/drive them locally, plain
`docker build`/`docker run` is enough. Drive both via
`.claude/skills/run-boinc-addons/smoke.sh`, which builds each image, launches it,
and verifies it's actually working (`boinccmd` RPC for `boinc`, an HTTP request to
`ttyd` for `boinctui`), then tears everything down. All paths below are relative to
the repo root.

## Prerequisites

- A working Docker daemon (`docker info` succeeds). No other system packages are
  needed — the driver only shells out to `docker`, `curl`, and `grep`.
- Optional, only for the operator's Python unit tests: Python 3 and the `dict2xml`
  package (see Test section — a venv is recommended, not a system-wide install).

## Run (agent path)

```bash
./.claude/skills/run-boinc-addons/smoke.sh boinc      # build + smoke-test boinc
./.claude/skills/run-boinc-addons/smoke.sh boinctui    # build + smoke-test boinctui
./.claude/skills/run-boinc-addons/smoke.sh all         # both, in sequence
```

Exit code 0 means the image built and the running container was verified end to
end; any failure aborts the script (`set -euo pipefail`) with the relevant Docker
build/run/curl output on stdout. Each subcommand cleans up its own
containers/volumes on success.

What each subcommand actually does (all verified in this session):

| target | build | run | verify |
|---|---|---|---|
| `boinc` | `docker build -t boinc-addon-test:local boinc/` | CI-style one-shot run with `--exit-immediately true`, then a second persistent run | `--exit-immediately` run exits 0; then `docker exec --workdir /data/boinc <container> boinccmd --get_state` returns a real state dump (`Time stats` section) |
| `boinctui` | `docker build -t boinctui-addon-test:local boinctui/` | `docker run -d -p 17681:7681 boinctui-addon-test:local` | `curl -H "X-Remote-User-Name: test" http://localhost:17681/` returns HTTP 200 with the ttyd terminal HTML page |

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
