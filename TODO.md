# TODO / Analysis notes

Working memory from a repo-wide review (2026-08-08). Nothing here has been acted on yet —
this is a list of findings and ideas to triage, not a changelog. Update/prune as items are
resolved or discarded.

## Bugs / correctness

- [x] **Fixed in `boinc` 3.8.0** — early `return` after the symlink branch, plus
  `test_should_not_overwrite_a_linked_global_prefs_override` asserting the content of both the
  `/config` file and the data-folder path.
  **`global_prefs_override.py` clobbers a user-supplied override file on every start.**
  `link_global_prefs_override` (`boinc/operator/global_prefs_override.py:9-40`) symlinks
  `/config/global_prefs_override.xml` into the data folder when it exists (lines 15-19), but
  then falls through unconditionally to lines 21-40, which build a `preferences` dict from
  `start_hour`/`end_hour`/`max_ncpus`/`cpu_usage_limit` and `open(gui_rpc_auth, 'w')` — writing
  *through* the symlink it just created. Any custom XML the user placed in `/config` gets
  truncated and replaced with the auto-generated (possibly empty) preferences on the very next
  operator start. The docs (`boinc/README.md:152-154`) present the custom-file path as a
  supported feature, so this silently defeats it.
  `test_should_link_global_prefs_override` (`boinc/operator/test/test_global_prefs_override.py:21-34`)
  only asserts the symlink exists — it never checks file content, so the bug has no test
  coverage catching it. Needs an early `return` after the symlink branch.

- [ ] **`gui_rpc_auth.py` imports `logger` from the stdlib `venv` module.**
  `boinc/operator/gui_rpc_auth.py:3` does `from venv import logger` and calls `logger.debug(...)`
  at line 9, instead of using its own `logging.getLogger(__name__)` like every other module in
  `operator/`. It happens to work because CPython's `venv` package exposes a module-level
  `logger`, but that's an implementation detail of an unrelated stdlib module, not a public API —
  it's not guaranteed stable across Python versions. Looks like an autocomplete/typo accident
  rather than an intentional import.

- [ ] **`--exit-immediately` is parsed with `type=bool`, so any non-empty string is truthy.**
  `boinc/operator/main.py:23`: `parser.add_argument("--exit-immediately", type=bool, ...)`.
  Verified in-session:
  ```
  python3 -c "
  import argparse
  p = argparse.ArgumentParser()
  p.add_argument('--exit-immediately', type=bool, default=False)
  print(p.parse_args(['--exit-immediately', 'false']))
  print(p.parse_args(['--exit-immediately', '0']))
  "
  # Namespace(exit_immediately=True)
  # Namespace(exit_immediately=True)
  ```
  `--exit-immediately false` and `--exit-immediately 0` both evaluate to `True` — only omitting
  the flag entirely gives `False`. Currently only ever invoked with the literal `true`
  (`build-addons.yaml:116`), so no live incident, but it's a landmine for anyone who later scripts
  this flag from a variable that can be `"false"`. Fix is `action=argparse.BooleanOptionalAction`
  or explicit string parsing.

- [ ] **`SIGINT` is caught but neither forwarded nor acted on — Ctrl-C hangs the container.**
  `boinc/operator/main.py:58-68` registers `signal_handler` for `SIGHUP`/`SIGINT`/`SIGQUIT`/`SIGTERM`,
  but the handler body (`main.py:60`) explicitly skips forwarding when
  `number == signal.SIGINT`, and does nothing else (no exit, no re-raise). Because
  `signal.signal(signal.SIGINT, ...)` replaces Python's default handler (which would otherwise
  raise `KeyboardInterrupt` and terminate the script), pressing Ctrl-C on an interactive run
  (`boinc/DEVELOPMENT.md:9-13` uses `docker run -it --rm`) is fully swallowed: the BOINC client
  is never signaled and the operator's `sleep(0.5)` loop just continues. The container only stops
  via `docker kill`/`SIGTERM` from another terminal. If the intent was "don't forward SIGINT to
  BOINC," the operator itself still needs to exit in that branch instead of silently continuing.

- [x] **Fixed in `boinc` 3.8.0** — `sys.exit(1)` when `configure_boinc_projects` fails, and the
  BOINC client's own exit code is propagated when it is positive (a negative code means the client
  was signaled, which is how both a Supervisor stop and `--exit-immediately` end it — still 0).
  This unblocks the `watchdog:` item below.
  **The operator always exits with code 0, even when startup fails.**
  `boinc/operator/main.py` never calls `sys.exit(...)` (no `import sys` at all). When
  `configure_boinc_projects` fails (e.g. wrong account-manager credentials) it stops the BOINC
  process (`main.py:80-82`) and the script then falls through the rest of main.py and ends
  normally — process exit code 0. Home Assistant Supervisor (and anyone scripting
  `docker run`/CI around this image) reads the exit code to distinguish "stopped cleanly" from
  "crashed"; a bad account-manager password currently looks identical, from the outside, to a
  deliberate stop. Only an *unhandled* Python exception produces a non-zero exit today.

## State ownership — the operator vs. changes made outside it

Root cause shared by the items below: the operator writes BOINC state at startup as if it were the
only writer, but this repo ships a second writer (`boinctui`) and `boinc/config.yaml:11` exposes
GUI RPC on `31416/tcp` for a third (desktop BOINC Manager, gated by `remote_hosts`). A fourth,
the account manager, pushes changes by design. External modification is not hypothetical here —
it's the advertised use case of the sibling add-on.

The Kubernetes-operator answer to this is *not* "run a reconcile loop" — BOINC already re-syncs
with its account manager on its own schedule, so a loop would mostly duplicate that. The useful
half of the pattern is **field ownership**: an option the user never set is a field the operator
does not own and must not touch. Both bugs below are that rule being missing.

- [x] **Fixed in `boinc` 3.8.0** — unset options now mean "not a field the operator owns": it logs
  the externally-attached account manager and leaves it alone. New `test/test_boinccmd.py` covers
  this and the four other branches. Follow-up left open: **there is now no way to express "detach
  it" through the options**; `boinc/DOCS.md` documents `boinccmd --acct_mgr detach` as the manual
  route, but an explicit gate (empty string, or `manage_account_manager: bool`) would be better.
  **An account manager attached from `boinctui` is silently detached on the next restart.**
  `configure_boinc_projects` (`boinc/operator/boinccmd.py:84-88`) treats "all three
  `account_manager_*` options unset" as the desired state *no account manager*, and calls
  `detach_account_manager`. But all three are optional (`boinc/config.yaml:21-23`, `str?`/
  `password?`), so unset is also the default for a user who never intended the operator to manage
  this at all and attached their account manager interactively through the TUI. Their attachment
  survives until the next add-on restart/update, then disappears with only a `logging.debug` line.
  Fix is the ownership rule: unset options → skip reconciliation entirely, don't detach. A real
  "detach it" intent needs to be expressible separately (explicit empty string, or a
  `manage_account_manager: bool` gate).

- [ ] **Only the account-manager *host* is compared, so same-host URL changes are missed.**
  `boinc/operator/boinccmd.py:70` compares `urlparse(...).netloc` of current vs. desired. Two
  account managers on the same host but different paths compare equal, so the operator logs
  "already attached, synchronizing" and syncs against the old one. Probably deliberate leniency
  for `http`/`https` and trailing-slash differences — but netloc-only is a wider net than that
  needs. Normalising scheme + path (strip trailing `/`) would keep the leniency without the
  false match.

- [ ] **Generated `global_prefs_override.xml` is a full overwrite, wiping TUI-set preferences.**
  Distinct from the symlink bug above, and present even when no `/config` file exists.
  `global_prefs_override.py:39-40` writes a freshly built dict containing *only* the four keys the
  operator manages (`start_hour`, `end_hour`, `niu_max_ncpus_pct`, `niu_cpu_usage_limit`). BOINC
  GUI clients write their "computing preferences" into this same file, so anything a user set from
  `boinctui` outside those four keys (disk limits, memory, network) is dropped on the next
  operator start. Reading the existing XML and merging only the managed keys would preserve them —
  and would compose correctly with the early-`return` fix for the symlink bug.

## Security / permissions — needs documentation or review

- [x] **Fixed in `boinc` 3.8.0** — new `operator/redact.py` replaces `gui_rpc_password` and
  `account_manager_password` with `***` before the dump, covered by `test/test_redact.py`.
  **Secrets are logged in plaintext at `DEBUG` level.**
  `boinc/operator/main.py:37`: `logging.debug(f'Current configuration\n{json.dumps(options, indent=2)}')`
  dumps the entire parsed `options.json`, including `gui_rpc_password` and
  `account_manager_password` (both `password?` in the schema, `boinc/config.yaml:17,23`), verbatim
  into the log stream whenever `--log-level DEBUG` is used. This isn't hypothetical — CI already
  runs the image this way (`build-addons.yaml:115`: `--log-level DEBUG --exit-immediately true`),
  so every build's public GitHub Actions log contains the (dummy, thankfully) password from
  `boinc/operator/options.json:2`. A real user who sets DEBUG logging to troubleshoot something
  else and then pastes container logs into a GitHub issue would leak their actual BOINC/account-
  manager password. Should redact/omit the password fields before logging.

- [ ] `boinc/config.yaml:12-15` grants `video: true`, `host_pid: true`, `host_uts: true`, and
  `docker_api: true`. `host_pid`/`host_uts` are explained (CPU-monitoring, see
  `boinc/README.md:7-13` and the Protection Mode warning in `main.py:31-32`), but `video` and
  `docker_api` are not mentioned anywhere in README/DOCS. `boinc/Dockerfile:19-24` installs
  `docker-cli` and `libgl1`, which confirms the intent: `docker-cli` → BOINC's `docker_wrapper`
  jobs that spawn sibling containers, `libgl1` → GPU-compute projects (OpenCL/CUDA via `/dev/dri`).
  So the grants are almost certainly deliberate, not leftover boilerplate — but that reasoning
  exists only in this analysis, not in any user-facing doc. `docker_api: true` in particular is a
  meaningful privilege grant (Docker socket access); users accepting it deserve a one-line
  explanation in `boinc/README.md` next to the existing Protection Mode warning, same as the
  bugs above — document or drop, don't leave silent.

## Conformance with the official HA apps docs

Reviewed against <https://developers.home-assistant.io/docs/apps/> (configuration, security,
presentation pages, fetched 2026-08-08). Ordered roughly by impact.

### Broken / non-functional

- [x] **Fixed in `boinc` 3.8.0** — the four structural keys are back in English, all Spanish
  strings kept. The `network:` caveat below is unchanged and still unverified.
  **`boinc/translations/es.yaml` is entirely non-functional — the structural keys are
  translated too.** The file uses `configuración:` / `nombre:` / `descripción:` / `red:` where
  the format requires the literal English keys `configuration:` / `name:` / `description:`
  (`network:`). Per the configuration docs the shape is fixed:
  ```yaml
  configuration:
    ssl:
      name: Enable SSL
      description: Enable usage of SSL on the webserver inside the app
  ```
  — "The key under configuration (ssl) in this case, needs to match a key in your schema
  configuration." Only the *values* are translatable. `boinc/translations/en.yaml` is correct;
  `es.yaml` is a faithful Spanish translation of the wrong thing, so Supervisor finds no
  `configuration:` block and silently falls back to English for every option label. Fix is
  mechanical: revert the four structural key names, keep all the Spanish strings.
  (Side note: `network:` as a top-level translations key is used by `en.yaml` for the
  `31416/tcp` port description — it did not appear in the docs pages fetched, so **verify it's a
  supported key** rather than assuming; if it isn't, port descriptions need `ports_description:`
  in `config.yaml` instead.)

- [ ] **`icon.png` violates the documented aspect-ratio requirement in both apps.**
  Docs: "The aspect ratio of the icon must be 1x1 (square)", recommended 128x128px. Actual
  (`file boinc/icon.png boinctui/icon.png`): both are **256 x 245** — close to square but not
  square, so it will be letterboxed/distorted in the store. `logo.png` is 600x305 against a
  recommended 250x100, which is fine — the docs explicitly allow other logo ratios.

### Missing capabilities the platform already offers

- [ ] **Neither app declares a `watchdog`, so a crashed BOINC client is never restarted.**
  Docs: `watchdog: "tcp://[HOST]:[PORT:31416]"` (or `http://…`) lets Supervisor monitor app
  health and restart it. Today, if the BOINC client dies, `main.py`'s `while boinc_process.poll()
  is None` loop (`main.py:89-90`) simply falls through and the operator exits **0** (see the
  exit-code bug above), so Supervisor sees a clean stop and leaves the app down — silently, until
  someone notices they've stopped contributing compute. `boinc` has port 31416 available for a
  TCP watchdog; `boinctui` could use `tcp://[HOST]:[PORT:7681]`. This is probably the single
  highest-value item in this file: it converts a silent-death failure mode into auto-recovery.

- [ ] **No `backup_exclude`, so cold backups snapshot the entire BOINC working set.**
  Docs list `backup_exclude` as "List of files/paths (with glob support) that are excluded from
  backups". `boinc/config.yaml:30` sets `backup: cold` (app stopped for the duration), and
  `folders.py:9-16` creates `slots/`, `locale/`, `projects/` under the data dir. `slots/` is
  purely transient scratch space for running tasks and `projects/` holds re-downloadable project
  binaries — both can be many GB. Every HA full backup therefore stops BOINC (losing compute
  progress) and copies gigabytes of regenerable data. Excluding at minimum `slots/` looks like a
  clear win; whether `projects/` is safe to exclude needs a check against how BOINC recovers on
  restart.

- [ ] **`account_manager_url` is typed `str?` when the schema language has a `url` type.**
  `boinc/config.yaml:21`. The documented schema types include `url` (and `email`, `port`,
  `password`). Switching to `url?` gets free validation in the Supervisor UI instead of letting a
  typo through to `boinccmd --acct_mgr attach`, where it surfaces only as a runtime log error.
  Same category: `remote_hosts` entries are `str?` — worth checking whether the trailing `?`
  even means anything on a *list element* (docs describe `?` as marking an optional field, not an
  optional element type); it may be silently ignored, in which case `- "str"` is the honest form.

### Deprecated / template-copied config worth modernizing

- [ ] **`map:` uses the legacy plain-string form.** `boinc/config.yaml:31-32` is
  `map: [addon_config]`; the documented format is now structured:
  ```yaml
  map:
    - type: addon_config
      read_only: false
  ```
  with "Defaults to read-only, which you can change by adding the property read_only: false".
  This used to interact with the `global_prefs_override.py` clobber bug at the top of this file —
  a read-only mount turned the write-through-the-symlink into an uncaught `OSError` and a startup
  crash loop rather than silent truncation. **The early-`return` fix in 3.8.0 removed both failure
  modes**, so this item is now purely about modernizing the `map:` syntax and making the
  `read_only` intent explicit rather than inherited from a default.

- [ ] **`init: false` isn't justified by the documented reason, and `main.py` silently depends on
  it.** Docs: `init` defaults `true`; disable it "if the image has a custom init system (e.g.
  s6-overlay)". Neither image has one — `boinc/Dockerfile:42` is a plain `python3 main.py`
  entrypoint and `boinctui/run.sh:13` `exec`s ttyd. So the setting looks template-copied.
  Two consequences worth thinking about before changing it:
  1. The protection-mode detection at `boinc/operator/main.py:31` (`if current_pid == 1`) is an
     *undocumented implicit dependency on `init: false`* — the heuristic works only because
     nothing else occupies PID 1. Flipping `init` to `true` would put Docker's init at PID 1,
     giving the operator a non-1 PID and silently disabling the Protection Mode warning that the
     whole README leads with. This coupling deserves a comment in the code at minimum.
  2. With no init process, orphaned grandchildren are never reaped. For `boinc` this is masked by
     `host_pid: true` (host PID namespace); for `boinctui`, ttyd is PID 1 and spawns
     `bash` → `boinctui` per session, so zombie accumulation across many ingress sessions is
     plausible. Worth actually checking `ps` inside a long-lived boinctui container before
     deciding.

- [ ] **`apparmor: false` on both apps runs against an explicit documented recommendation.**
  The security page's best-practice list includes "Establish an AppArmor profile", and states
  apps are rated 1–6 "based on the wanted rights". These two apps disable AppArmor *and* request
  `host_pid`, `host_uts`, `docker_api`, and `video` — so they sit at the low end of that scale by
  construction. (The docs do not publish a per-option point table, so no specific number is
  claimed here.) This ties directly to the dead `boinc/apparmor.txt.disable` boilerplate noted
  under Housekeeping: writing a real profile matching the actual process tree is the fix for both
  items at once. Realistically this is a large task, not a quick win — but it should be a
  conscious decision, recorded somewhere, rather than an unexamined default.

### Confirmed-correct (checked, no action needed — recorded so it isn't re-litigated)

- `boinctui/run.sh:17` uses `--auth-header X-Remote-User-Name`, which matches the ingress identity
  headers the security docs specify (`X-Remote-User-Id`, `X-Remote-User-Name`,
  `X-Remote-User-Display-Name`). Correct use of the platform auth mechanism.
- `boinc/config.yaml:10-11` maps `31416/tcp: null` — null means "not published by default, user
  may opt in", which is the secure-by-default form.
- Neither app requests `hassio_api`, `homeassistant_api`, `auth_api`, `full_access`, or
  `privileged`, matching the docs' "request only essential API permissions".
- CI signs published images with Cosign (`build-addons.yaml:98`), matching the docs' "Sign
  published images using the official workflow with Cosign"; the old Codenotary path was already
  removed (`boinctui/CHANGELOG.md:43-45`).
- `boinctui` has no `translations/` dir, but its `config.yaml` declares no `schema:` at all, so
  there is nothing to translate. Not a gap.

## Config schema — feature gaps vs. upstream BOINC preferences

`boinc/config.yaml:16-27` covers account manager, remote RPC, a computing time window, and two
CPU-usage knobs. Common BOINC global-preference options that aren't exposed and might be worth
adding (each is a `dict2xml` key away, same pattern as `global_prefs_override.py`):

- [ ] `work_buf_min_days` / `work_buf_additional_days` — how much work to keep queued; probably
  the single most-requested BOINC tuning knob after CPU limits.
- [ ] GPU usage toggle (`no_gpus` / `exclude_gpu`) — relevant given `video: true` is already
  granted (see above).
- [ ] `disk_max_used_gb` / `disk_max_used_pct` — disk usage cap, useful on small HA hosts.
- [ ] `run_on_batteries` — mostly N/A for typical HA hardware (NUCs, RPis on mains) but trivial
  to add if anyone runs HA on a laptop.
- [ ] A `suspend`/`no_new_work` boolean would let users pause computation from the add-on config
  without detaching, complementing the existing start/end-hour schedule.

## Test coverage

- [ ] `test_global_prefs_override.py` needs a case that supplies a config-dir override file
  *and* schedule/CPU options together, asserting the override file's original bytes survive —
  this is exactly the scenario the bug above breaks silently.
- [ ] No test currently asserts on `gui_rpc_auth.py` logging behavior specifically (low
  priority — cosmetic — but flagging alongside the `venv.logger` import finding).
- [ ] No test covers `main.py`'s exit-code/signal behavior (the `--exit-immediately` parsing bug,
  the SIGINT swallow, and the always-exits-0 issue above) — reasonable since `main.py` is a script
  with no functions to import, but worth a lightweight subprocess-based test if any of those get
  fixed, so they don't regress silently.

## Future add-on / feature ideas (not scoped, just candidates)

- [ ] **HA-native sensors for BOINC stats** (tasks running/queued, credits, project status,
  disk/CPU usage) — today the only way to see BOINC state from Home Assistant itself is opening
  the `boinctui` ingress panel. A small exporter (MQTT discovery or a REST endpoint HA's
  `sensor: platform: rest` can poll) built on top of `boinccmd --get_tasks`/`--get_state` would
  enable dashboards and automations (e.g., notify on task completion/error, pause BOINC via
  automation instead of only the static schedule). Could live in the existing `boinc` add-on
  (a sidecar thread in the operator) or as a new third add-on.
  **⚠ Partly solved by a third party already — see the prior-art item below before scoping this.**

- [ ] **Prior art: link the existing third-party HA integration instead of rebuilding it**
  (searched 2026-08-08). Cheapest high-value item in this section.

  - **<https://github.com/SpuelMett/Boinc-Home-Assistant-Integration>** — custom component, MIT,
    config flow (no YAML), ~12 stars, v0.0.7, compatible with HA 2025.6.0. **Not in HACS** (listed
    as a roadmap item); installed by copying into `config/custom_components`. Talks **GUI RPC
    directly** to remote BOINC hosts — needs `remote_hosts.cfg`, `gui_rpc_auth.cfg` and port 31416,
    exactly the mechanism analysed here. Sensors: total tasks, running tasks, average progress rate.
    Services: start, hard stop, **soft stop** (waits for the next checkpoint, configurable threshold,
    default 120 s), GPU start/stop. Supports multiple BOINC hosts. Advertised use cases: run BOINC
    on surplus solar, reuse compute heat for heating.
  - **The fit is mutual and explicit**: that README states it *cannot* run BOINC on the Home
    Assistant host itself and that a separate add-on is needed for that — which is precisely this
    repo. This repo, in turn, has no HA entity surface at all. They are complements, not competitors.
  - **Action (small):** document the pairing in `boinc/DOCS.md` — the exact three-step recipe
    (`allow_remote_gui_rpc: true`, add the HA host to `remote_hosts`, share `gui_rpc_password`) plus
    a link to the integration. Closes the loop for users (this add-on *runs* BOINC, that integration
    *monitors and controls* it) and directly attacks the cross-add-on setup friction noted below,
    which that integration demonstrably suffers too.
  - **Consequence for the sensors item above:** rebuilding it from scratch would duplicate existing
    work. Realistic options are contributing to SpuelMett's integration (e.g. helping it into HACS,
    adding sensors) or simply linking it.
  - **The "configure" half is still genuinely unfilled.** That integration does run-mode control and
    basic task sensors — no project attach/detach, no account manager, no preferences. If anything
    gets built here, that's the gap.
  - **No core/official HA BOINC integration found.** Caveat: the home-assistant.io integrations
    listing renders client-side and returned nothing useful when fetched, so this rests on web
    search, not on a direct check of the listing. Re-verify before relying on it.
  - Also found, same author, superseded: <https://github.com/SpuelMett/Boinc-Home-Assistant-Control>
    — a Flask sidecar exposing `/start`, `/stop`, `/soft_stop` on top of PyBoinc (3 stars).
  - **Maturity caveat before depending on any of it:** 12 and 8 stars, single maintainer, v0.0.7,
    not in HACS. Linking to it is free; taking a dependency on it is a risk decision.

- [ ] **Python GUI RPC libraries already exist — pick one rather than writing one.**
  - <https://pypi.org/project/boinc-client/> (Lewis England) — v1.12.1, May 2024, synchronous,
    advertises "consistent response types", Python >=3.9.
  - <https://github.com/nielstron/pyboinc> — MIT, asyncio, 8 stars; the one SpuelMett's integration
    uses. Its own README admits it is "very basic" and does not cover the whole protocol.
  - Both are small and lightly maintained, so vendoring vs. depending is a real call. Either way
    this removes "write a GUI RPC client from scratch" from the critical path of every item below.
- [ ] **Prometheus metrics endpoint** — same data source as above, different consumer, for users
  who already run Prometheus/Grafana off their HA host.

- [ ] **Graphical web UI to query and configure BOINC (a BOINC Manager equivalent) as an ingress
  add-on.** Biggest item in this file by an order of magnitude; recorded with the constraints found
  while thinking it through so the design isn't re-derived.

  **Start from the honest baseline: `boinctui` already does this.** It is a full BOINC Manager,
  through ingress, working today, built from ~20 lines of `run.sh` plus an apt package. A graphical
  UI adds usability (mobile/touch, HA-companion-app users, people who won't use a TUI), not
  capability. Valid reason, but the cost ratio is 10-50x — decide with that in view.

  - **"Query" and "configure" are two different products.** Querying in HA is done with *entities*,
    not an embedded page: sensors give dashboards, automations, mobile notifications, history and
    long-term statistics for free, and an ingress UI gives none of that (it's an island inside HA).
    Configuring is where a UI genuinely wins, since HA has no good declarative surface for "attach
    this project" / "abort this task". Both halves need the same backend — a decent GUI RPC client.
    **That backend, not the UI, is the real first deliverable**, and it's shared with the
    HA-native-sensors item above.
  - **Ingress compatibility is the hard gate that decides wrap-vs-build.** The app is served under
    `/api/hassio_ingress/<token>/` with a token that changes, so it must emit relative URLs or accept
    a base path **at runtime, not build time** — which rules out most third-party SPAs that bake
    absolute `/assets/...` paths. It must also have no login of its own and trust the
    `X-Remote-User-*` headers (the pattern `boinctui/run.sh:17` already uses via
    `--auth-header X-Remote-User-Name`). WebSockets do work through ingress (`boinctui` proves it
    here), so live task updates are viable. Usual breakage: absolute `Location:` redirects and
    `Path=/` cookies. **Evaluating an existing web UI against this costs about an afternoon** (stand
    it up, see if it survives the base path) and can save months — run that experiment before
    committing to writing one. Candidates to test: BoincTasks Js and any other browser-based BOINC
    manager (list unverified — search before assuming none exist).
  - **Cross-add-on connectivity is the worst part of the current UX and would be inherited.** Today
    `boinctui` → `boinc` needs three manual steps across two add-ons (`boinctui/DOCS.md:7-9`):
    enable `allow_remote_gui_rpc` (`boinc/config.yaml:20` → `boinc.py:build_boinc_command`), add the
    other add-on's hostname to `remote_hosts` (`boinc/config.yaml:18-20` → `remote_hosts.py`), and
    copy the `gui_rpc_password` — i.e. **a second copy of the secret in another `options.json`**.
    Worth explicitly considering the alternative: **run the UI inside the `boinc` add-on** as a
    second process — localhost RPC, reads `gui_rpc_auth.cfg` straight from the data folder, no
    `remote_hosts` entry, no duplicated password, zero setup friction *for the local host*. Price is
    **not** loss of multi-host (a process in that container can still dial out to other hosts on
    31416); it is loss of lifecycle independence — if the local BOINC client stops or crash-loops,
    the UI you were using to watch the *other* machines goes with it. Real fork in the road, not a
    detail.
  - **`boinccmd` is not a viable backend for a UI.** The operator shells out and regex-parses
    human-readable text (`boinccmd.py:58`, `re.search(r'URL: (\S+)')`) — fine for one field at
    startup, unusable for a UI polling tasks every few seconds: one process spawn per call, against
    output that is not a stable API. Security angle specific to a *separate* add-on: `boinccmd`
    finds `gui_rpc_auth.cfg` only because it runs with `cwd=data_folder`; another add-on has no such
    folder and would have to pass `--passwd <pw>` on the command line, putting the password in argv
    — and `boinc` runs with `host_pid: true` (`config.yaml:13`), so that argv is more visible than
    usual. Speak GUI RPC directly over TCP 31416 instead (XML, nonce+MD5 auth — **verify the exact
    protocol against upstream BOINC docs**, not from memory).
  - **A configuration UI is by definition a third external writer** — read the "State ownership"
    section above as a prerequisite, not as parallel debt. The AM-silently-detached bug
    (`boinccmd.py:84-88`) and the `global_prefs_override.xml` full-overwrite
    (`global_prefs_override.py:39-40`) already bite `boinctui` users today; shipping a first-party
    UI promotes them from edge case to broken main flow. And if the declarative `projects:` option
    below also lands, declarative config and imperative UI end up fighting over the same state —
    two controllers, one resource.
  - **Multi-host is a stated requirement** (controlling other BOINC instances, not just the one in
    the `boinc` add-on). Consequences, decided now because retrofitting multi-host is expensive
    while designing it in from the start is nearly free:

    - **Multi-host on its own is not a differentiator.** `boinctui` already connects to other BOINC
      clients (`boinctui/DOCS.md:11-15`) and SpuelMett's integration already supports several hosts.
      What neither offers is **cross-host aggregation** — one table of all tasks across all machines,
      sortable by deadline, with bulk actions. That is the actual reason to build (it's what
      BoincTasks is known for), so it should drive the design rather than being a later feature.
      It also raises the value of the ingress wrap experiment: BoincTasks Js is multi-machine by
      design, so if it survives the base path, multi-host comes for free.
    - **Host + credential storage is a design fork, not a detail.** N × (host, port, password).
      Either *in add-on options* (HA schema supports list-of-dict) — declarative, visible in the
      Supervisor UI, covered by backups, but static (adding a machine means restarting the add-on)
      and multiplying the plaintext-secret problem (`main.py:37`) by N; or *managed from the UI and
      persisted under `/data`* — dynamic, but invisible to HA's config layer and needing its own
      secret handling. Doing **both** recreates the two-writers problem from the "State ownership"
      section, this time inside the UI itself.
    - **Likely network gotcha — verify empirically.** Add-on ↔ add-on traffic stays on HA's Docker
      network and the target sees the container hostname (hence `boinctui/DOCS.md:7`, "use the
      hostname on the app info page"). Traffic to a LAN machine is masqueraded on the way out, so
      the remote host most likely sees **the Home Assistant host's IP**, not the container's — i.e.
      a remote PC's `remote_hosts.cfg` needs a *different* entry than a sibling add-on does. This is
      inference about Docker NAT, **not verified**; confirm with `tcpdump` or a remote BOINC's
      rejection log. If true it is the first support question this add-on will get, and both
      recipes belong in the docs.
    - **Security blast radius multiplies.** BOINC's GUI RPC has one password per client and no
      users or roles — whoever connects has full control. A multi-host UI concentrates total control
      of every BOINC machine on the network behind one ingress panel. **Verify whether HA can
      restrict an ingress panel to admin users**; if it cannot, any HA account controls the whole
      fleet.
    - **Partial failure is the normal case.** One powered-off host must not stall the aggregate
      view: per-host connection state, timeouts, partial render. Same requirement as the `projects:`
      item below.
    - **Version skew.** Different BOINC client versions expose different RPC fields; the aggregate
      view has to tolerate a host missing data another one provides.
  - **Scope, if it happens.** BOINC Manager's real surface is large (Projects, Tasks, Transfers,
    Statistics, Disk, Notices, Event Log, Computing Preferences, add/remove project, account
    manager). An MVP should be read-only tasks/projects/transfers plus a handful of actions
    (global suspend/resume, per-project suspend/resume/update, abort task) and leave the rest to
    `boinctui`.
  - **Checked (2026-08-08): a third-party HA integration already covers part of the "query" half** —
    see the prior-art item above. No core integration found. This materially narrows what a UI here
    would add: the query half has an answer that exists, so anything built here should target the
    *configure* half (project attach/detach, account manager, preferences), which nothing covers.
  - **Suggested order:** (1) fix the ownership bugs; (2) link the existing integration from
    `boinc/DOCS.md` — hours of work, closes the loop for users today; (3) pick an existing GUI RPC
    library rather than writing one; (4) only then decide on the UI, with the ingress experiment
    done and real demand data on whether users need to *configure* from a phone or `boinctui`
    suffices.
  - Packaging note: a new add-on directory slots into CI automatically (`find-changed-addons`
    diffs per directory), and it should ship a **square** `icon.png` from day one — see the
    aspect-ratio bug above, which both existing add-ons have.
- [ ] Consider whether the missing config options above (work buffer, GPU toggle) are common
  enough support requests to justify scoping as a real change — check open GitHub issues before
  investing time.

- [ ] **Declare projects to attach in the add-on options** (e.g. a `projects:` list, HA schema
  supports list-of-dict). Attractive, but it is a much bigger design step than the existing
  scalar options, because it turns reconciliation into set reconciliation with a destructive
  removal branch. Design constraints found while thinking it through — read alongside the
  "State ownership" section above:

  - **Detach is destructive, unlike the account-manager detach the operator already does.**
    `boinccmd --project <url> detach` aborts in-progress tasks and deletes downloaded project
    files (potentially GBs, and lost partial credit). So `actual − desired` must *not* map to
    detach. The BOINC-native soft equivalent is `--project <url> nomorework`: stop fetching new
    work, let current tasks drain. Default to draining; hard detach only on explicit opt-in.
  - **Ownership needs persisted state, because BOINC has nowhere to record it.** There are no
    labels/annotations on a BOINC project. Without a marker, a project the user attached from
    `boinctui` is indistinguishable from one the operator attached and the user then removed from
    the options — and the removal branch would eat the former. Fix is the `kubectl apply`
    last-applied-configuration trick: the operator keeps its own `managed_projects` file under
    `/data`, and computes removals as `previously-managed − desired`, never `actual − desired`.
    Anything the operator never attached is never touched.
  - **Mutually exclusive with the account manager.** When an AM is attached it owns the project
    list and re-asserts it on every sync (Science United especially), so a hand-declared
    `projects:` list plus `account_manager_*` means two controllers fighting over the same state.
    The operator should reject that combination at startup rather than let it oscillate.
  - **Project URLs need canonicalising before diffing** — `http`/`https`, trailing slash, `www.`.
    A false mismatch here means attaching a duplicate or draining the live one. Same bug class as
    the `netloc`-only comparison at `boinc/operator/boinccmd.py:70`, but with worse consequences.
  - **Credentials.** Attach takes an account key, not a password: `--lookup_account <url> <email>
    <password>` first, then `--project_attach <url> <key>`. That is a *network call per project*
    that can fail or rate-limit. It also multiplies the plaintext-secrets-at-DEBUG problem
    (`main.py:37`) by the number of projects.
  - **This is the first place a real retry loop earns its keep.** BOINC projects go offline for
    days at a time; a one-shot attach at startup means "project was down at boot → silently never
    attached until someone restarts the add-on". Additions want converge-with-backoff. Note the
    asymmetry: retry the *additive* half, never police the removal half on a timer.
  - **Partial failure becomes the normal case.** `configure_boinc_projects` returns a single bool
    today; with N projects, per-project error isolation plus an aggregated result is needed — one
    unreachable project must not block the other four, and the outcome has to reach the exit code
    (see the always-exits-0 bug above).

## Housekeeping

- [ ] `boinc/config.yaml` doesn't document `video`/`docker_api` (see Security section) —
  smallest fix here is just adding a short paragraph to `boinc/README.md` alongside the
  existing Protection Mode warning.
- [ ] Confirm CHANGELOG minor-bump convention (base-image bumps → minor) is written down
  somewhere other than tribal knowledge / `CLAUDE.md` — it already is, in `CLAUDE.md`'s
  Conventions section, so this is just a note that it's the reference to follow when the next
  bump PR comes up.
- [ ] `boinc/apparmor.txt.disable` is the unmodified Home Assistant add-on template boilerplate
  (references `/etc/services.d`, `/etc/cont-init.d`, bashio, s6-overlay `/init`) — none of which
  this add-on uses; its actual entrypoint is a plain `python3 /opt/operator/main.py`
  (`boinc/Dockerfile:42`). It's inert today (`apparmor: false` in `boinc/config.yaml:29`), so no
  functional impact, but it would need a full rewrite — not just re-enabling — before it could
  ever be turned on. Either rewrite it to match the real process tree or delete it so it doesn't
  mislead a future contributor into thinking AppArmor support is closer than it is.
- [ ] `configure_boinc_projects` (`boinc/operator/boinccmd.py:45-90`) logs a warning and returns
  `True` (success) when account-manager options are partially set (e.g. URL without
  username/password) — `boinccmd.py:63-64`. That's arguably the right runtime behavior (don't
  tear down a running client over a config typo), but it means an invalid partial config is
  silently accepted forever, re-warned on every restart, with no schema-level validation ever
  surfacing it as an error in the Supervisor UI. Low priority; noting since it compounds the
  "always exits 0" issue above — there's currently no path from *misconfigured account manager*
  to *visible failure state*.
