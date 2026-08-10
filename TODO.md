# TODO / Analysis notes

Standing backlog for this repo: known gaps, platform conformance items, and feature ideas found by
review. Consult it before starting work — what you are about to investigate may already be written
up here with file:line references — and update it as items are resolved or discarded.

Last reviewed 2026-08-10. Everything in **Resolved** below has shipped or been deliberately
discarded; it is kept in condensed form so the same ground is not re-covered, not as work to do.

---

# Open

## Bugs / correctness

None known. The bugs found in the 2026-08-08 review all shipped in `boinc` 3.8.0–3.9.0 — see
Resolved.

## Security / permissions

- [ ] **`video` and `docker_api` are granted but never explained.** `boinc/config.yaml` sets
  `video: true`, `host_pid: true`, `host_uts: true` and `docker_api: true`. `host_pid`/`host_uts`
  are explained (CPU monitoring, the Protection Mode warning in `boinc/README.md` and
  `main.py:31-32`), but `video` and `docker_api` are not mentioned in any user-facing doc.
  `boinc/Dockerfile` confirms the intent: `docker-cli` for BOINC's `docker_wrapper` jobs that spawn
  sibling containers, `libgl1` for GPU-compute projects. So the grants are deliberate, not
  boilerplate — but `docker_api` in particular is Docker socket access, a real privilege that users
  accepting the install deserve to see explained in one line next to the Protection Mode warning.

- [ ] **`apparmor: false` on both add-ons, against an explicit documented recommendation.** These
  add-ons disable AppArmor *and* request `host_pid`, `host_uts`, `docker_api` and `video`, so they
  sit at the low end of the platform's 1–6 rating by construction. Ties to the dead
  `boinc/apparmor.txt.disable` under Housekeeping: writing a real profile matching the actual
  process tree fixes both at once. Realistically a large task, not a quick win — but it should be a
  recorded decision rather than an unexamined default.

## Conformance with the official HA apps docs

Reviewed against <https://developers.home-assistant.io/docs/apps/> (fetched 2026-08-08), plus
findings measured directly against the Supervisor in `.devcontainer`.

- [ ] **`icon.png` violates the documented 1x1 aspect ratio in both add-ons.** `boinc/icon.png` and
  `boinctui/icon.png` are byte-identical and **256 x 245**, so they are letterboxed or distorted in
  the store. `logo.png` at 600x305 is fine — the docs explicitly allow other logo ratios. Padding to
  256 x 256 with transparency (not rescaling) is the fix.
  `docs/icon.png` is a symlink to `boinc/icon.png` and follows automatically.

- [ ] **`map:` uses the legacy plain-string form.** `boinc/config.yaml` has `map: [addon_config]`,
  and Supervisor warns on every store scan: `App 'BOINC' uses legacy map type 'addon_config'; use
  'app_config' instead.` The validation regex accepts both spellings plus a permission suffix —
  `^(…|app_config|addon_config)(?::(rw|ro))?$` (`supervisor/apps/validate.py:137`) — with an
  explicit `ADDON_CONFIG → APP_CONFIG` migration and warning (`validate.py:263-270`). So the plain
  string `app_config` is enough; the structured `type:`/`read_only:` form is not required.

  **Blocked on the linter, tried and reverted 2026-08-10.** `frenck/action-addon-linter` accepts
  only the old spelling and fails the add-on with `['app_config'] is not valid under any of the
  given schemas`; v2.21.0 (Nov 2025) is the latest release and still does. Supervisor wants the new
  name, CI rejects it, and the two cannot be satisfied at once — so the warning stays until the
  linter catches up. Recheck when a newer linter release appears.

  The other half of the item is settled: the effective mount is already read-only (`docker inspect`
  on the running add-on reports `/config rw=false`), so the switch would not change access when it
  eventually happens.

- [ ] **`account_manager_url` is typed `str?` when the schema language has a `url` type.**
  `boinc/config.yaml:21`. The `url` type exists (`supervisor/apps/options.py:25`) and gives
  validation in the Supervisor UI instead of a runtime error from `boinccmd --acct_mgr attach`.
  Same category: `remote_hosts` entries are `- "str?"`, and `?` marks optional *fields*, not
  optional element types, so on a list element it likely means nothing — verify against Supervisor
  before changing it to `- "str"`.

- [ ] **`build.yaml` itself is deprecated.** Supervisor, on every store scan: `App local_boinc uses
  build.yaml which is deprecated. Move build parameters into the Dockerfile directly.` Both
  add-ons still ship one. This does **not** compose with simply deleting the file: Supervisor passes
  `--build-arg BUILD_FROM=<its default>` regardless, overriding the `ARG BUILD_FROM` default in the
  Dockerfile. Work out the supported replacement before removing anything — the `build_from` regex
  bug fixed in `boinc` 3.8.0 / `boinctui` 2.4.1 was found exactly here.

- [ ] **`init: false` is not justified by the documented reason, and `main.py` silently depends on
  it.** The docs say to disable `init` only when the image has its own init system (s6-overlay);
  neither image does. Two consequences before changing it:
  1. The Protection Mode detection at `boinc/operator/main.py:31` (`if current_pid == 1`) is an
     *undocumented implicit dependency on `init: false`* — it works only because nothing else
     occupies PID 1. Setting `init: true` would put Docker's init there and silently disable the
     warning the whole README leads with. This coupling deserves a comment in the code at minimum.
  2. With no init process, orphaned grandchildren are never reaped. For `boinc` this is masked by
     `host_pid: true`; for `boinctui`, `ttyd` is PID 1 and spawns `bash` → `boinctui` per session,
     so zombie accumulation across many ingress sessions is plausible. Check `ps` inside a
     long-lived `boinctui` container before deciding.

- [ ] **Only `build-addons.yaml` still hardcodes an add-on name**, in the post-build test step
  (`if: inputs.addon == 'boinc'`). Everything else discovers add-ons by globbing for `config.yaml`.
  Worth generalising if a second add-on ever wants a post-build check. Its `manifest` job also maps
  architectures by name (`amd64`, `aarch64`), so a new arch needs that `case` extended.

### Confirmed correct — checked, no action needed

- `boinctui/run.sh:17` uses `--auth-header X-Remote-User-Name`, matching the ingress identity
  headers the security docs specify. Correct use of the platform auth mechanism.
- `boinc/config.yaml` maps `31416/tcp: null` — null means "not published by default, user may opt
  in", the secure-by-default form.
- Neither add-on requests `hassio_api`, `homeassistant_api`, `auth_api`, `full_access` or
  `privileged`, matching "request only essential API permissions".
- CI signs published images with Cosign, matching the docs' recommendation; the old Codenotary path
  was already removed.
- `network:` **is** a supported top-level translations key (verified against a running Supervisor
  2026-08-09: it validates the key and rejects only bad values). Our `31416/tcp` value is a plain
  string, so no `ports_description:` is needed.
- `boinctui` has no `translations/` dir, but it declares no `schema:` either, so there is nothing
  to translate. Not a gap.
- **`boinctui`'s `panel_icon` is not dead config, and `ingress_panel` cannot be declared.** An
  earlier note here proposed adding `ingress_panel: true` because the installed add-on reports it as
  false. That is impossible: `ATTR_INGRESS_PANEL` lives in `SCHEMA_APP_USER`
  (`supervisor/apps/validate.py:623`) next to `watchdog` and `protected`, it is absent from the
  config schema, and that schema uses `extra=vol.REMOVE_EXTRA` — so the key is silently dropped.
  Verified end to end (2026-08-10): installing with the key present left Supervisor's persisted
  `system.ingress_panel: None` while `system.panel_icon: 'mdi:console'` was read correctly, and
  `POST /addons/local_boinctui/options` with `ingress_panel: true` flipped `user.ingress_panel`.
  It is the user's "show in sidebar" toggle, and `panel_icon` is the icon that toggle uses.

## Test coverage

- [ ] **Nothing exercises the Home Assistant surface in CI**, only the container. Everything under
  Conformance above is invisible to `docker build`/`docker run`: `config.yaml`/`build.yaml`
  validation, the option schema, translations, ingress, protection mode, watchdog. There is a local
  path — `.claude/skills/run-boinc-addons/supervisor.sh` boots the repo's `.devcontainer` with a
  real Supervisor and installs from the working tree — and it has repeatedly paid for itself: the
  `build_from` bug, the `app_config` correction, the `network:` verification, the `ingress_panel`
  finding, and the watchdog finding below. Putting it in CI is a different question: Supervisor in
  docker-in-docker needs `--privileged`, a TTY, a health-check override and a ~2GB pull, so it is
  slow and fragile. Realistic middle ground: keep it a documented manual step before releasing a
  change to `config.yaml`/`build.yaml`/`translations/`, and revisit a nightly (not per-PR) job.

- [ ] **`supervisor.sh install <addon>` fails with `App … is already installed`** instead of
  reinstalling, so every iteration needs a manual uninstall first. Small quality-of-life fix in the
  driver, noticed while verifying the changes above.

## Config schema — breaking redesign, for a future major

- [ ] **Collapse `start_hour` + `end_hour` into a single `computing_window` option.** Breaking
  change to the option schema, so it belongs in `4.0.0`.

  **Why.** There are three tiers of configuration validation, and only the first is visible to a
  user who does not read logs: (1) the schema, enforced by Supervisor *before* the container starts,
  with the error shown in the UI; (2) a runtime hard failure (`sys.exit(1)`), which with the
  Watchdog toggle off — the default — just reports `state: stopped`, indistinguishable from a stop
  the user asked for; (3) degrade and warn, a log line and nothing more.

  The schedule bugs fixed in 3.8.3 can only be caught at tier 3 today, because HA's schema validates
  field by field and cannot express "these two go together". A single string makes the illegal state
  unrepresentable:

  ```yaml
  computing_window: "match(^(?:[01]\\d|2[0-3]):[0-5]\\d-(?:[01]\\d|2[0-3]):[0-5]\\d$)?"
  ```

  **What it does not fix:** `22:00-22:00` still matches, and BOINC reads an equal pair as no
  restriction at all, so the runtime check from 3.8.3 has to stay.

  **Migration is the hard part, and the obvious assumption is wrong.** Supervisor does *not* reject
  an option missing from the schema — it drops it and logs a warning nobody reads (verified by
  POSTing an unknown option: `Option 'computing_window' does not exist in the schema for BOINC`, and
  the add-on then started with `options.json` = `{}`). A straight rename would make every existing
  user's schedule silently vanish and BOINC would quietly compute 24/7 — the exact failure 3.8.3 was
  written to prevent. The transition needs: all three keys in the schema for a full minor release,
  `computing_window` preferred when set, a deprecation warning when the old pair is used, and the
  old keys dropped only in the major after that.

## Config schema — feature gaps vs. upstream BOINC preferences

`boinc/config.yaml` covers the account manager, remote RPC, a computing window and four CPU knobs.
Common BOINC global preferences not exposed, each roughly one key away in
`global_prefs_override.py`:

- [ ] `work_buf_min_days` / `work_buf_additional_days` — how much work to keep queued; probably the
  most-requested BOINC knob after CPU limits. **Also the real lever on backup size** — see the
  closed `backup_exclude` item in Resolved, which found that the exclusion list is not.
- [ ] GPU usage toggle (`no_gpus` / `exclude_gpu`) — relevant given `video: true` is already granted.
- [ ] `disk_max_used_gb` / `disk_max_used_pct` — useful on small HA hosts.
- [ ] `run_on_batteries` — mostly N/A for typical HA hardware, but trivial to add.
- [ ] A `suspend`/`no_new_work` boolean, to pause computation from the add-on config without
  detaching.
- [ ] Check open GitHub issues before investing: are any of these actually being asked for?

## Feature ideas (not scoped, just candidates)

- [ ] **Link the existing third-party HA integration instead of rebuilding it** (searched
  2026-08-08). Cheapest high-value item in this section.
  <https://github.com/SpuelMett/Boinc-Home-Assistant-Integration> — custom component, MIT, config
  flow, ~12 stars, v0.0.7, **not in HACS**. Talks GUI RPC directly to remote BOINC hosts, so it
  needs `remote_hosts.cfg`, `gui_rpc_auth.cfg` and port 31416 — exactly the mechanism this add-on
  configures. Sensors: total tasks, running tasks, average progress rate. Services: start, hard
  stop, soft stop (waits for the next checkpoint), GPU start/stop. Multiple hosts.
  **The fit is mutual and explicit**: its README states it cannot run BOINC on the Home Assistant
  host itself and that a separate add-on is needed for that — which is this repo. This repo has no
  HA entity surface at all. Complements, not competitors.
  **Action (small):** document the pairing in `boinc/DOCS.md` — enable `allow_remote_gui_rpc`, add
  the HA host to `remote_hosts`, share `gui_rpc_password` — plus a link.
  **Consequence:** the "query" half largely has an answer already; anything built here should target
  the *configure* half (project attach/detach, account manager, preferences), which nothing covers.
  **Maturity caveat:** single maintainer, v0.0.7, not in HACS. Linking is free; depending on it is a
  risk decision. No core/official HA BOINC integration found, though that rests on web search rather
  than a direct check of the (client-side rendered) integrations listing.

- [ ] **HA-native sensors for BOINC stats** — tasks running/queued, credits, project status. Today
  the only way to see BOINC state from Home Assistant is opening the `boinctui` ingress panel.
  ⚠ Partly solved by the integration above; read that item first.

- [ ] **Python GUI RPC libraries already exist — pick one rather than writing one.**
  <https://pypi.org/project/boinc-client/> (v1.12.1, May 2024, synchronous) and
  <https://github.com/nielstron/pyboinc> (MIT, asyncio, the one SpuelMett's integration uses, whose
  README admits it is "very basic"). Both small and lightly maintained, so vendoring vs. depending
  is a real call — but either removes "write a GUI RPC client from scratch" from the critical path
  of everything below.

- [ ] **Prometheus metrics endpoint** — same data source, different consumer.

- [ ] **Graphical web UI** — biggest item in this file by an order of magnitude. What follows is the
  design work, independent of where the code ends up living.

  **Honest baseline: `boinctui` already does this.** It is a full BOINC Manager through ingress,
  working today, built from ~20 lines of `run.sh` plus an apt package. A graphical UI adds usability
  (mobile/touch, people who will not use a TUI), not capability. Valid reason, but the cost ratio is
  10-50x.

  - **"Query" and "configure" are two different products.** Querying in HA is done with *entities* —
    dashboards, automations, notifications, history, statistics — none of which an ingress page
    gives. Configuring is where a UI genuinely wins. Both need the same backend, and **that backend,
    not the UI, is the real first deliverable**; it is shared with the sensors item above.
  - **Ingress compatibility is the gate that decides wrap-vs-build.** Served under
    `/api/hassio_ingress/<token>/` with a changing token, so the app must emit relative URLs or take
    a base path **at runtime, not build time** — which rules out most third-party SPAs that bake
    absolute `/assets/...` paths. It must also have no login of its own and trust `X-Remote-User-*`.
    WebSockets do work through ingress (`boinctui` proves it). Usual breakage: absolute `Location:`
    redirects and `Path=/` cookies. **Evaluating an existing web UI against this costs about an
    afternoon** and can save months — run that experiment first. Candidates: BoincTasks Js and any
    other browser-based BOINC manager (list unverified — search before assuming none exist).
  - **Cross-add-on connectivity is the worst part of the current UX and would be inherited.** Today
    `boinctui` → `boinc` needs three manual steps across two add-ons, including **a second copy of
    the GUI RPC password in another `options.json`**. Consider instead running the UI *inside* the
    `boinc` add-on: localhost RPC, reads `gui_rpc_auth.cfg` straight from the data folder, no
    `remote_hosts` entry, no duplicated password. The price is **not** loss of multi-host (a process
    there can still dial other hosts on 31416); it is loss of lifecycle independence — if the local
    client crash-loops, the UI you were using to watch the *other* machines goes with it.
  - **`boinccmd` is not a viable backend.** The operator shells out and regex-parses human-readable
    text (`boinccmd.py`, `re.search(r'URL: (\S+)')`) — fine for one field at startup, unusable for a
    UI polling every few seconds: one process spawn per call against output that is not a stable
    API. And from a *separate* add-on it would need `--passwd <pw>` in argv, which with
    `host_pid: true` is more visible than usual. Speak GUI RPC over TCP 31416 instead (XML,
    nonce+MD5 auth — verify the exact protocol against upstream, not from memory).
  - **A configuration UI is a third external writer** — read the state-ownership reasoning in
    Resolved as a prerequisite, not parallel debt.
  - **Multi-host is a stated requirement**, and retrofitting it is expensive while designing it in
    is nearly free:
    - Multi-host alone is not a differentiator (`boinctui` and SpuelMett's integration both do it).
      What neither offers is **cross-host aggregation** — one table of all tasks across all machines,
      sortable by deadline, with bulk actions. That is the actual reason to build, and it should
      drive the design. It also raises the value of the ingress experiment: BoincTasks Js is
      multi-machine by design.
    - **Host + credential storage is a design fork.** N × (host, port, password) either in add-on
      options (declarative, visible, backed up, but static and multiplying the secrets problem by N)
      or managed from the UI under `/data` (dynamic, but invisible to HA's config layer and needing
      its own secret handling). Doing both recreates the two-writers problem inside the UI itself.
    - **Likely network gotcha — verify empirically.** Add-on ↔ add-on traffic stays on HA's Docker
      network and the target sees the container hostname. Traffic to a LAN machine is masqueraded,
      so the remote host most likely sees **the Home Assistant host's IP** — i.e. a remote PC's
      `remote_hosts.cfg` needs a *different* entry than a sibling add-on does. This is inference
      about Docker NAT, **not verified**; confirm with `tcpdump` or a remote BOINC's rejection log.
      If true it is the first support question this will get, and both recipes belong in the docs.
    - **Security blast radius multiplies.** BOINC's GUI RPC has one password per client and no users
      or roles. A multi-host UI concentrates total control of every BOINC machine behind one ingress
      panel. **Verify whether HA can restrict an ingress panel to admin users**; if it cannot, any HA
      account controls the whole fleet.
    - **Partial failure is the normal case** (one powered-off host must not stall the aggregate
      view), and **version skew** is real (different client versions expose different RPC fields).
  - **MVP scope, if it happens:** read-only tasks/projects/transfers plus a few actions (global
    suspend/resume, per-project suspend/resume/update, abort task), leaving the rest to `boinctui`.
  - **Suggested order:** (1) link the existing integration from `boinc/DOCS.md` — hours of work,
    closes the loop for users today; (2) run the ingress wrap experiment; (3) pick an existing GUI
    RPC library rather than writing one; (4) only then decide on the UI, with real demand data on
    whether users need to *configure* from a phone or `boinctui` suffices.

- [ ] **Declare projects to attach in the add-on options** (a `projects:` list). Attractive, but a
  much bigger step than the existing scalar options, because it turns reconciliation into *set*
  reconciliation with a destructive removal branch:
  - **Detach is destructive**, unlike the account-manager detach the operator already does:
    `boinccmd --project <url> detach` aborts in-progress tasks and deletes downloaded files. So
    `actual − desired` must *not* map to detach. The BOINC-native soft equivalent is `nomorework`:
    stop fetching, let current tasks drain. Default to draining; hard detach only on explicit opt-in.
  - **Ownership needs persisted state**, because BOINC has no labels/annotations on a project.
    Without a marker, a project the user attached from `boinctui` is indistinguishable from one the
    operator attached and the user then removed from the options. Same `kubectl apply` trick already
    used for preferences: keep a `managed_projects` file under `/data` and compute removals as
    `previously-managed − desired`, never `actual − desired`.
  - **Mutually exclusive with the account manager**, which owns the project list and re-asserts it
    on every sync. Reject that combination at startup rather than letting it oscillate.
  - **Project URLs need canonicalising before diffing** — reuse `boinc/operator/url.py`, which
    exists for exactly this.
  - **Credentials**: attach takes an account key, so `--lookup_account <url> <email> <password>`
    first — a network call per project that can fail or rate-limit.
  - **This is the first place a real retry loop earns its keep.** Projects go offline for days; a
    one-shot attach at startup means "project was down at boot → silently never attached". Retry the
    *additive* half with backoff, never police the removal half on a timer.
  - **Partial failure becomes normal**: per-project error isolation plus an aggregated result, and
    the outcome has to reach the exit code.

## Housekeeping

- [ ] `boinc/apparmor.txt.disable` is unmodified add-on template boilerplate (references
  `/etc/services.d`, `/etc/cont-init.d`, bashio, s6-overlay `/init`) — none of which this add-on
  uses; its entrypoint is a plain `python3 /opt/operator/main.py`. Inert today (`apparmor: false`),
  but it would need a full rewrite, not just re-enabling. Either rewrite it to match the real
  process tree or delete it so it does not mislead a future contributor.
- [ ] The Dockerfile labels disagree between add-ons without reason: `image.vendor` is
  "Hector Espert" in one and "Home Assistant Boinc Add-ons" in the other; `image.licenses` is
  "Apache 2.0", "Apache2" and "Apache License 2.0" depending on where you look, counting the
  `build.yaml` files; and `image.url` points at the repo in one and the docs site in the other.
  Pick one set — SPDX `Apache-2.0`, vendor "Hector Espert", the docs site — and apply it to both.

---

# Resolved — kept so it is not re-litigated

## Discarded after investigation

- [x] **`backup_exclude` — no exclusion is free; nothing is excluded (decided 2026-08-10).**
  The idea was to keep `slots/` and `projects/` out of every Home Assistant backup. Reading the
  BOINC 8.x client source shows the cost is not "tasks restart" but "tasks fail":
  - **`slots/` absent → every in-progress task errors, and is reported as such.** `setup_slot_dir()`
    relinks the app-version files and `make_soft_link()` fails with `ENOENT`
    (`client/file_names.cpp:47-54`), surfacing as `"Can't link app version file"`
    (`client/app_start.cpp:571-575`) and ending in `report_result_error()` → `RESULT_COMPUTE_ERROR`
    (`client/client_state.cpp:2051-2064`), plus a project RPC backoff. Credit lost.
  - **This add-on lands exactly there.** `prepare_data_folders` (`boinc/operator/folders.py:9-16`)
    recreates `slots/` but not `slots/<N>`, and the client never recreates a slot for a restored
    task: `make_slot_dir()` is called only from `get_free_slot()` (`client/app.cpp:748`), itself
    called only when creating a new `ACTIVE_TASK` (`client/cpu_sched.cpp:1665-1680`).
  - **And the saving would be small**, because on Linux BOINC *links* rather than copies into slots.
    The volume is in `projects/`.
  - **`projects/` absent** recreates the dirs and re-queues downloadable files
    (`client/cs_files.cpp:385-391`), but nothing moves a result back from `RESULT_FILES_DOWNLOADED`
    to downloading, so the scheduler tries to start it first and `task_files_present()` errors it
    anyway (`client/app_start.cpp:538-548`). For anonymous-platform projects the loss of
    `app_info.xml` is **silent and unrecoverable**: tasks are discarded without ever being reported
    (`client/cs_statefile.cpp:385-393`). `app_config.xml` is silently lost too.
  - **`locale/` is safe to exclude** — the client never reads it; `_()` is a marker macro
    (`client/client_msgs.h:77`) and the Manager does the translating — but it is irrelevant by size.
  - **The real lever on backup size is the work buffer**, not the exclusion list — see
    `work_buf_min_days` under feature gaps.
  - **`backup: cold` stays**, and now for a concrete reason: the state file is rotated
    `client_state_next.xml` → `client_state.xml` → `client_state_prev.xml`, and a half-written
    `client_state_next.xml` **wins** over the good one at startup. A hot backup could capture that.
  - Mechanics, if this is ever revisited: patterns are matched against the **absolute** path
    (`supervisor/apps/app.py:1477`, a documented legacy quirk) using `PurePath.match`, which matches
    **from the right** and in which **`**` is not recursive** — `boinc/slots/**` matches
    `…/slots/0` but not `…/slots/0/ckpt`. The filter is applied to directories too and prunes the
    whole subtree (`securetar/__init__.py:1876`), so matching the directory is sufficient. Note the
    add-on's `/data` contains `options.json` *and* a `boinc/` subdirectory, so patterns need that
    prefix.

- [x] **`watchdog:` — cannot work for `boinc`; not added (decided 2026-08-10).** Supervisor's
  application watchdog is a bare TCP connect to the **container's** IP
  (`check_port`, 0.5s timeout, no read or write). Measured in the devcontainer: the BOINC client
  listens on **`127.0.0.1:31416` only** unless the user enables `allow_remote_gui_rpc` or populates
  `remote_hosts`, so a connect from `hassio_supervisor` to `172.30.33.0:31416` is refused. Declaring
  `watchdog: "tcp://[HOST]:[PORT:31416]"` would therefore fail permanently and, with the Watchdog
  toggle on, restart the add-on repeatedly. `config.yaml` is static and cannot depend on an option,
  so there is no way to declare it conditionally.
  Also worth separating, because the original write-up conflated them: **the container watchdog
  already covers a dead client** — `watchdog_container` (`supervisor/apps/app.py:1844-1858`) reacts
  to `FAILED`/`STOPPED`/`UNHEALTHY` with no `watchdog:` key at all, and since 3.8.0 a client that
  dies produces a non-zero exit. What the key would have added is detection of a client that is
  *hung but alive*, and a plain TCP connect would not catch that anyway: a listening socket whose
  owner is stopped still completes handshakes from the kernel backlog.
  `boinctui` **is** reachable (`172.30.33.1:7681` accepts), so a watchdog there would work — but it
  was dropped with the rest: `ttyd` hanging is rare, and shipping half the item was not worth a
  release. If `boinc` ever needs a real one, the shape is a small health listener in the operator,
  bound to all interfaces, answering only when `boinccmd --get_state` succeeds — which checks that
  BOINC actually responds rather than that a socket is open.
  Restart behaviour, for whoever picks this up: `_restart_after_problem` is rate-limited to
  10 calls per 30 minutes (`supervisor/apps/const.py:41-44`), the probe is skipped while the add-on
  is starting (`supervisor/misc/tasks.py:344`), and the Watchdog toggle is off by default.

## Shipped in `boinc` 3.8.0

- [x] **A user-supplied `global_prefs_override.xml` was overwritten on every start** — the symlink
  branch fell through to the generation code, writing *through* the symlink it had just created.
  Fixed with an early `return`, plus a test asserting the file's content, not just the symlink.
- [x] **An account manager attached from `boinctui` was silently detached on the next restart.**
  Unset options now mean "not a field the operator owns": it logs and leaves it alone. Follow-up
  still open: **there is no way to express "detach it" through the options** — `boinc/DOCS.md`
  documents `boinccmd --acct_mgr detach` as the manual route, but an explicit gate (empty string, or
  `manage_account_manager: bool`) would be better.
- [x] **The operator always exited 0, even when startup failed.** Now `sys.exit(1)` when
  `configure_boinc_projects` fails, and the client's own exit code is propagated when positive (a
  negative code means it was signaled, which is how both a Supervisor stop and `--exit-immediately`
  end — still 0).
- [x] **Secrets were logged in plaintext at DEBUG.** New `operator/redact.py` replaces
  `gui_rpc_password` and `account_manager_password` with `***` before the dump. CI runs the image at
  DEBUG, so every build's public log used to contain the sample password.
- [x] **`boinc/translations/es.yaml` was entirely non-functional** — the *structural* keys were
  translated too (`configuración:`/`nombre:`/`descripción:`/`red:`), so Supervisor found no
  `configuration:` block and silently fell back to English. Only values are translatable.
- [x] **`build.yaml`'s `build_from` was rejected by Supervisor**, which fell back to its Alpine base
  and broke building from source. The bare `debian:13.x-slim` form fails Supervisor's `owner/name`
  regex; all add-ons now pin `docker.io/library/debian:...`.

## Shipped in `boinc` 3.8.1

- [x] **Generated `global_prefs_override.xml` was a full overwrite, wiping preferences set from
  `boinctui`.** Replaced with a three-way merge against the operator's own last-applied state
  (`.managed_global_prefs.json`, the `kubectl apply` pattern). Per managed key: option set → write;
  option unset **and the operator wrote it last run** → remove; option unset and never written by
  the operator → leave alone.
  **Provenance cannot live in the XML**, verified in BOINC's source: `GLOBAL_PREFS::write_subset`
  (`lib/prefs.cpp`) serializes only masked known fields with no "unparsed" buffer, and
  `handle_set_global_prefs_override` (`client/gui_rpc_server_ops.cpp`) writes the GUI's blob
  verbatim, deleting the file when the blob is empty. Any marker the operator embedded would be
  destroyed by the first edit from `boinctui`. The module also moved from `dict2xml` to
  `xml.etree.ElementTree` so element order and unknown structure survive editing (`cc_config.py`
  still uses `dict2xml`, so the dependency stays).
- [x] **A stale symlink made the operator recreate the file it was meant to read.** `os.path.exists`
  follows symlinks, so a broken one read as missing: the operator then wrote *through* it,
  recreating the user's deleted `/config` file and freezing their preferences forever. Fixed with
  `os.path.lexists` plus an explicit branch dropping a symlink whose target is gone.

## Shipped in `boinc` 3.8.2

- [x] **An unset `gui_rpc_password` wrote an *empty* `gui_rpc_auth.cfg`, disabling BOINC's own
  secure default.** An empty file is not "no authentication", it is *the empty password*. Verified
  end to end against the real image with `allow_remote_gui_rpc: true` from a second container: with
  an empty file, `boinccmd --host <ip> --passwd "" --set_run_mode never` succeeded and the target
  reported `current mode: never`. Run with no operator against an empty data dir, BOINC creates the
  file itself, 0600, with a random 32-character password — so the operator was **removing** a
  protection by creating the file first.
  Now three states: unset → do not create the file, and delete an empty one left by an older version
  (while keeping a password BOINC generated itself, so it does not rotate); explicitly empty → an
  empty file, opting in on purpose; set → written, 0600. Verified against a real Supervisor that the
  states are distinguishable: an unset option arrives as `{}` while `gui_rpc_password: ""` reaches
  `options.json` as an empty string.
  **Two false positives to avoid when re-checking this:** `--get_cc_status` is answered without
  authentication by design, so it "succeeds" against a protected client and proves nothing; and
  `boinccmd` exits 0 on an auth failure, whose message is `Operation failed: authentication error`,
  not the `Authorization failure: -155` that a *wrong* password produces.
  Scope, for context: with the defaults only localhost can connect. The dangerous combination is no
  password *plus* remote RPC — which is exactly the path `boinctui/DOCS.md` walks users through.
- [x] **`gui_rpc_auth.py` imported `logger` from the stdlib `venv` module.** Gone with the rewrite.

## Shipped in `boinc` 3.8.3

- [x] **`start_hour`/`end_hour` were documented as a pair but nothing enforced it**, and setting one
  alone silently created a different schedule: BOINC fills the missing one with its default of
  midnight, so `start_hour: 22:00` alone means "compute 22:00 → 00:00". Verified against a live
  client. Now written as a pair or not at all, matching BOINC Manager
  (`clientgui/DlgAdvPreferences.cpp` sets `mask.start_hour = mask.end_hour = true`, so a half window
  is unreachable from its UI).
  **An equal pair is also ignored**, found while asking what BOINC Manager does: BOINC reads
  `start_hour == end_hour` as *no restriction at all* (`TIME_SPAN::suspended` returns false), so
  `22:00`–`22:00` is the opposite of a schedule, and BOINC Manager rejects it outright with an error
  dialog. Deliberately a warning rather than a startup failure: a soft config mistake should not
  crash-loop the app now that exit codes propagate.
  (BOINC's own time format is `hours + minutes/100`, not decimal — see `convert_time_to_boinc_format`.)

## Shipped in `boinc` 3.8.4

- [x] **A partially configured account manager was silently accepted forever.** Now an error and
  `sys.exit(1)`. This is the one place the official hard-fail pattern fits: the closest precedent in
  `home-assistant/addons` is `zwave_js`, which refuses to start when two keys disagree — *"we are
  unsure which one to use"*. Half an account manager is the same shape: no safe reading, and
  continuing leaves the app looking healthy while contributing to nothing. Contrast 3.8.3, which
  degrades because it *does* have a documented safe reading.
  **Caveat, measured on a running Supervisor: a hard failure is not loud.** The container runs with
  Docker restart policy `no`, so with the Watchdog toggle off — the default — the app just reports
  `state: stopped`, indistinguishable from a stop the user asked for; the only trace is the log line.

## Shipped in `boinc` 3.8.5

- [x] **`--exit-immediately` was parsed with `type=bool`, so any non-empty string was truthy** —
  `--exit-immediately false` evaluated to `True`. Now `action='store_true'`, which removes the
  possibility entirely rather than guarding against it. No live incident; this closed a landmine.
- [x] **`SIGINT` was caught but neither forwarded nor acted on.** All four signals are now forwarded
  identically, verified against BOINC's own source (`client/main.cpp:157-175`): the client treats
  `SIGINT` exactly like `SIGTERM`, a clean checkpointed shutdown, so forwarding is correct and
  idempotent even if something else already delivered it to the process group.
  **The originally recorded symptom was backwards**, measured against a container built before the
  fix: interactive Ctrl-C already worked *by accident*, because the terminal delivers `SIGINT` to the
  whole foreground process group. The real failure was any `SIGINT` reaching *only* the operator —
  `docker kill -s INT`, an orchestrator signalling PID 1 with no pty — where the operator logged the
  signal and did nothing, and the container ran forever.
- [x] **Only the account-manager *host* was compared**, so same-host URL changes were missed. Rather
  than inventing a normalisation, the fix mirrors BOINC's own `canonicalize_master_url`
  (`lib/url.cpp`), which the client already applies before storing (`client/acct_mgr.cpp`) — so what
  `boinccmd --acct_mgr info` reports is already in that form. New module `boinc/operator/url.py`
  (not a private helper, because the `projects:` item needs it). Rules: no scheme, or any scheme
  other than `https`, becomes `http`; repeated slashes collapse; a trailing slash is always
  appended; only the host is lower-cased. Deliberate behaviour changes: same host different path now
  detaches and re-attaches, and correcting `http` → `https` now re-attaches instead of silently
  staying on the old one.
- [x] **A stop during initialization produced a misleading exit 1.** `configure_boinc_projects` now
  runs only if the operator is not stopping and the client is still alive.
- [x] **`main.py` had no test coverage.** New `test/test_main.py`, subprocess-based with fake
  `boinc`/`boinccmd` executables on `PATH`, covering `--exit-immediately`, `SIGINT`/`SIGTERM`
  forwarding, the client exiting non-zero on its own, and a `SIGTERM` during initialization.

## Shipped in `boinc` 3.9.0

- [x] **The operator only ever wrote the `niu_` ("not in use") CPU limits**, so no limit applied
  while the computer was in use, though `DOCS.md` documented both as unconditional. Confirmed
  against a running client: with `max_ncpus: 75.0`, BOINC reported *"When computer is in use … Use
  at most 100% of the CPU time"*. On a headless HA host "not in use" is the normal state, which is
  why nobody noticed.
  `max_ncpus`/`cpu_usage_limit` now write the unprefixed keys, and two new options
  `max_ncpus_idle`/`cpu_usage_limit_idle` write the `niu_` ones. BOINC itself falls back to the
  in-use pair when the `niu_` ones are unset (`lib/prefs.cpp:398-406`), so an upgrading user who only
  had the two original options keeps the same effective limit in both states. **Migration needed no
  new code**: the `niu_` keys stayed in `MANAGED_PREFERENCES`, so a stale value the operator wrote
  itself falls into the removal branch that has existed since 3.8.1, while one set by the user from
  `boinctui` is untouched.
