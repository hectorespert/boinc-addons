# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

For what this repo is, how to install it, and per-app end-user docs, see:
[README.md](README.md), [boinc/README.md](boinc/README.md) + [boinc/DOCS.md](boinc/DOCS.md) +
[boinc/DEVELOPMENT.md](boinc/DEVELOPMENT.md), [boinctui/README.md](boinctui/README.md) +
[boinctui/DOCS.md](boinctui/DOCS.md), and [boinc/operator/README.md](boinc/operator/README.md).
This file only covers what those don't: internal architecture and contributor workflow.

## Repository structure

Two independent Home Assistant add-ons, each self-contained with its own `config.yaml`,
`build.yaml`, `Dockerfile`, `CHANGELOG.md`, and `DOCS.md`:

- **`boinc/`** — runs the actual BOINC client. Has a Python "operator" (`boinc/operator/`) that
  translates Home Assistant add-on options into BOINC config files and supervises the `boinc`
  process.
- **`boinctui/`** — a terminal UI (via `ttyd` + `boinctui`) for monitoring/controlling the BOINC
  client, exposed through Home Assistant ingress.

Add-ons are versioned and released independently: each has its own semver in `config.yaml`, and CI
only builds/releases an add-on when files inside its directory change (see CI section below).

## The `boinc` operator (`boinc/operator/`)

`main.py` is the container entrypoint (invoked as
`python3 main.py --options /data/options.json --data /data/boinc --config /config`). On startup it:

1. `folders.py` — creates the BOINC data directory tree (`slots`, `locale`, `projects`).
2. `gui_rpc_auth.py` — writes `gui_rpc_auth.cfg` from the `gui_rpc_password` option.
3. `remote_hosts.py` — writes `remote_hosts.cfg` from the `remote_hosts` option.
4. `global_prefs_override.py` — either symlinks a user-supplied `global_prefs_override.xml` from
   `/config`, or generates one from `start_hour`/`end_hour`/`max_ncpus`/`cpu_usage_limit` options
   (note: BOINC's own time format is `hours + minutes/100`, not decimal — see
   `convert_time_to_boinc_format`).
5. `cc_config.py` — writes a static `cc_config.xml` enabling task/file-transfer/scheduler logging.
6. `boinc.py` — builds the `boinc` client command line (`build_boinc_command`).
7. Launches the `boinc` client as a subprocess, forwards `SIGHUP`/`SIGINT`/`SIGQUIT`/`SIGTERM` to
   it, and waits for the BOINC RPC state to become available (`boinccmd.py:get_state`) before
   proceeding.
8. `boinccmd.py:configure_boinc_projects` — reconciles the desired account manager
   (`account_manager_url/username/password`) against the currently attached one via `boinccmd`,
   attaching/detaching/syncing as needed.
9. If `--exit-immediately` is passed (used by CI smoke tests), the operator stops the BOINC client
   and exits right after startup instead of running forever.

When `current_pid == 1`, the operator logs a warning: BOINC needs host-wide CPU visibility, so
Home Assistant Protection Mode must be disabled for this add-on — see
[boinc/README.md](boinc/README.md) for the user-facing explanation.

Add-on options are declared in `boinc/config.yaml` under `schema:` — keep that schema, the
operator's `options.get(...)` calls, and `boinc/DOCS.md` in sync when adding/changing options.

## Commands

### Run the operator's unit tests

```bash
cd boinc/operator
python -m unittest discover -s test -t test
```

Run a single test file/case, e.g.:

```bash
cd boinc/operator
python -m unittest test.test_boinc.TestBoincCommand.test_builds_command_with_remote_gui_rpc
```

Dependency: `dict2xml` (`pip install dict2xml`).

### Build/run an add-on image locally

See [boinc/DEVELOPMENT.md](boinc/DEVELOPMENT.md) for the `docker build`/`docker run` commands.
`boinc/operator/options.json` is the sample options file those commands (and CI's smoke test)
mount in.

### Docs site

```bash
pip install -r requirements.txt
mkdocs build --strict   # or: mkdocs serve
```

`mkdocs.yml` nav pulls each add-on's `README.md`, `DOCS.md`, and `CHANGELOG.md` directly, plus
`boinc/DEVELOPMENT.md`.

### Linting (mirrors CI, see `.github/workflows/lint.yaml`)

- YAML: `yamllint .` (config in `.yamllint`; `.github` is ignored, line-length is warning-only at 180).
- Add-on metadata: `frenck/action-addon-linter` per add-on directory (no direct local CLI equivalent).
- Dockerfiles: `hadolint boinc/Dockerfile` / `hadolint boinctui/Dockerfile`.
- Shell scripts: `shellcheck -s bash` over each add-on directory (covers `boinctui/run.sh`).

## CI/CD architecture (`.github/workflows/`)

Workflows are composed via `workflow_call` — `pr.yaml` and `release.yaml` are the entry points that
chain the reusable workflows in this order:

`lint.yaml` → `operator.yaml` (Python tests) → `find-changed-addons.yaml` (diffs
`build.yaml`/`config.yaml`/`Dockerfile`/`operator` per add-on directory) → `check-version.yaml`
(on PRs: informational; on release/main: strict — new version must exceed the latest
`<addon>-vX.Y.Z` git tag) → `build-addons.yaml` (matrix build per changed add-on/arch; on PRs
builds only, on release also publishes to `ghcr.io/hectorespert/addon-<name>` and verifies the
multi-arch manifest).

`release.yaml` (push to `main`) additionally tags each changed add-on as `<addon>-vX.Y.Z`, cuts a
GitHub Release with the matching section extracted from that add-on's `CHANGELOG.md`, and posts an
announcement to Bluesky.

Because builds/releases are gated on **which files changed**, bumping an add-on's version in
`config.yaml` (and updating its `CHANGELOG.md`) is what triggers a release for that add-on —
editing files outside a changed add-on's directory does not trigger its pipeline.

## Conventions

- Each add-on is versioned independently in its own `config.yaml`; keep `CHANGELOG.md` entries
  (`## X.Y.Z` headers) in sync since release notes are extracted from them automatically.
- Add-on Dockerfiles build from `debian:13.5-slim`, install packages needed for the BOINC/ttyd
  binaries, and set the standard Home Assistant add-on `io.hass.*`/`org.opencontainers.image.*`
  labels using the `BUILD_*` args injected by the builder — follow the existing pattern rather than
  hand-rolling new labels.
- User-facing terminology has migrated from "add-on" to "app" in docs (README, operator README);
  `config.yaml`/directory names/internal code still say "addon"/"add-on".
- When Claude Code creates a commit in this repo, use an `Assisted-by:` trailer instead of the
  default `Co-Authored-By:` trailer.
