# TODO / Analysis notes

Standing backlog for this repo: known gaps, platform conformance items, and feature ideas found by
review. Consult it before starting work — what you are about to investigate may already be written
up here with file:line references — and update it as items are resolved or discarded.

Last reviewed 2026-08-15. Everything in **Resolved** below has shipped or been deliberately
discarded; it is kept in condensed form so the same ground is not re-covered, not as work to do.

---

# Open

## Bugs / correctness

- [ ] **Does "computer is in use" mean anything at all in this container? Four shipped options
  depend on it.** The client logs this once per start, right after `Initialization completed`:

  > `Currently BOINC uses legacy idle detection methods that might not work properly on all systems.
  > Please consider installing a modern idle detection utility that works on Wayland and X11:`
  > <https://github.com/jamescowens/idle_detect>

  **Why it matters here rather than being noise.** `max_ncpus` / `cpu_usage_limit` apply *while the
  computer is in use*, and `max_ncpus_idle` / `cpu_usage_limit_idle` (the `niu_` preferences, added
  in 3.9.0) apply while it is not. `boinc/DOCS.md` promises the user exactly that distinction. But
  idle detection on Linux is built around a desktop session, and a Home Assistant host is headless —
  there is no X11 or Wayland, and the container has no `/dev/input`. If the client therefore reports
  "not in use" permanently, then the in-use pair is dead configuration and the docs describe a
  behaviour nobody can observe; if it reports the opposite, the `niu_` pair is. Either way one half
  of a documented feature does nothing.

  The 3.9.0 entry in Resolved already brushed against this — *"On a headless HA host 'not in use' is
  the normal state, which is why nobody noticed"* — but that was reasoning about which preferences
  got **written**, never a measurement of which state the client is actually **in**.

  **What to check.** Whether the client ever reports the in-use state at all (it logs
  `Suspending computation - computer is in use` when it does); what `users_idle()` falls back to with
  no session and no input devices; and whether `<idle_time_to_run>` changes anything. If one state
  is unreachable, the honest fix is documentation — say which pair actually applies — not more
  options.

  **The suggested remedy is probably wrong advice for this audience**, which is a second, smaller
  item: `idle_detect` is a helper for X11/Wayland desktops, and a Home Assistant OS user cannot
  install anything on the host. The line lands in their **Log** tab telling them to do something
  impossible, so it may deserve a note in `DOCS.md` saying it is harmless and why.

The bugs found in the 2026-08-08 review all shipped in `boinc` 3.8.0–3.9.0 — see Resolved.

## Security / permissions

- [ ] **`apparmor: false` on all three add-ons, against an explicit documented recommendation.**
  These add-ons disable AppArmor *and* request `host_pid`, `host_uts`, `docker_api` and `video`, so
  they sit at the low end of the platform's 1–6 rating by construction. Ties to the dead
  `boinc/apparmor.txt.disable` under Housekeeping: writing a real profile matching the actual
  process tree fixes both at once. Realistically a large task, not a quick win — but it should be a
  recorded decision rather than an unexamined default.

  **What a profile can and cannot buy here, since it is not the usual case.** BOINC's whole purpose
  is to download third-party binaries from projects and execute them out of `slots/`, so a profile
  cannot meaningfully restrict *what runs* — it has to permit executing arbitrary downloaded code,
  or the add-on does nothing. What it can still do is bound the *blast radius* of that code: keep it
  out of `/config`, off the host paths `host_pid` exposes, and away from the Docker socket
  `docker_api` grants. That is worth having, but it is a different claim from the one "AppArmor
  enabled" usually implies, and the item should be judged on it rather than on the rating.

## Conformance with the official HA apps docs

Reviewed against <https://developers.home-assistant.io/docs/apps/> (fetched 2026-08-08), plus
findings measured directly against the Supervisor in `.devcontainer`.

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

- **Option types are right as they stand, and the old item about them was half stale (2026-08-15).**
  `account_manager_url` has been `url?` since 3.9.1, not the `str?` that item claimed. The other
  half is now measured against a running Supervisor rather than guessed: `remote_hosts` keeps
  `- "str?"`, because changing it to `- "str"` would demonstrate nothing. The element type is
  enforced either way (`[1234]` → `expected str`); the `?` does not make elements nullable
  (`[null]` is rejected, confusingly, as `Missing required option 'remote_hosts'` — Supervisor reads
  a null first element as the option being absent); and the option is optional regardless, since
  options posted with no `remote_hosts` key are accepted.
  **A list of *dicts* behaves the opposite way**, which is worth knowing before adding another one:
  options posted without `projects` are rejected with `Missing option 'projects' in root`, hence the
  mandatory `options: projects: []` in `config.yaml`. That does not break existing installs —
  verified by updating a real 3.9.1 install with five options and no `projects` key in place with
  `ha apps update`: it came up `started`, every option preserved, `projects: []` filled in from the
  schema default.
- **The Dockerfile labels already agree; that item was stale too (2026-08-15).** It described
  `image.vendor` disagreeing between add-ons, three spellings of the licence, and `image.url`
  pointing at the repo in one place and the docs site in another. None of it is true now: the three
  `LABEL` blocks are identical apart from the add-on's own name, every `licenses` is the SPDX
  `Apache-2.0` in both the Dockerfiles and the `build.yaml` files, `vendor` is "Hector Espert"
  everywhere and `url` is the docs site everywhere. The only place those old spellings survived was
  the TODO entry describing them.
  One real difference is left and it belongs to the `build.yaml` item above, not here: the
  `build.yaml` labels use their own title and description ("Boinc add-on") and hardcode `source`,
  where the Dockerfile uses `${BUILD_REPOSITORY}`. Worth settling *if* `build.yaml` survives; there
  is no point tidying a file slated for removal.

- **Every permission this repo requests is now explained to the user.** `host_pid`/`host_uts` by the
  Protection Mode warning, and `video`/`docker_api` by the *What else this app asks for* section
  added to `boinc/README.md` in `ad846b7` — graphics access for GPU-capable projects, Docker access
  for projects shipping their work as containers, said plainly to be the broadest permission
  requested and not separately switchable. This was an open item until re-checked 2026-08-11.
- **`icon.png` meets the 1x1 rule — fixed, not a false alarm.** The 256 x 245 recorded here was
  real; the icon was squared in `ad846b7` and shipped as `boinc` 3.9.1 / `boinctui` 2.4.2. Measured
  again 2026-08-11: all three are byte-identical and **256 x 256**. `logo.png` at 600x305 is fine
  either way — the docs explicitly allow other logo ratios. `docs/icon.png` is a symlink to
  `boinc/icon.png` and follows automatically.
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

- [ ] **No project has ever been attached to a *real* BOINC project.** Everything verifying the
  `projects` option in 3.10.0 — unit tests, the end-to-end lifecycle, the Supervisor run — used
  `http://example.invalid/...` with invented account keys. That proves the operator issues the right
  calls and that the client persists them; it proves nothing about a real project **accepting** the
  key and sending work. Two things ride on it:
  1. **Whether an account key in this option actually authenticates.** A rejected key still leaves
     the project attached, so the failure is quiet: the client logs `Invalid or missing account key`
     and the app looks fine. Nothing in the operator notices.
  2. **`detach_when_done` draining real work**, which is the promise `DOCS.md` makes to the user —
     *"finish the work it has already downloaded and then leave"*. Our test projects had zero tasks,
     so that behaviour is asserted from BOINC's semantics, never measured.

  **Procedure, for whoever picks it up.** Work in a gitignored scratch directory; the account key is
  a secret and must not reach the repo or a transcript.
  1. Register on a project with a steady Linux x86_64 work supply — Einstein@Home. World Community
     Grid has had work droughts, which would waste the run.
  2. Copy the *account key* from the project's own account page (look for "account keys"). The
     alternative, `boinccmd --lookup_account`, is a GUI RPC so it needs a running client, and it
     wants the project password as well.
  3. Start the built image with that `options.json` and real network access.
  4. **The check that matters**: `--get_project_status` must show a real `name:` and `user_name:`.
     Those come from the scheduler's reply, so they stay empty when the key was rejected — which is
     exactly the distinction `example.invalid` cannot make.
  5. `--get_task_summary` should show work arriving.
  6. Remove the project from the options and restart: expect `don't request more work: yes`, the
     project **still attached**, and its tasks intact. That is the drain promise, on real work.
  7. Re-add and restart: expect `don't request more work: no`.
  8. Free extra: run at DEBUG and confirm `redact.py` masks a genuine key as `***`.

  A full drain takes hours or days, so step 6 verifies the mechanism, not the completion. Detach
  properly afterwards so the project is not left with an orphan host record.

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

The entity surface — sensors, and a Prometheus endpoint — is **not this repo's job**; see Resolved.
Anything built here should target the *configure* half (project attach/detach, account manager,
preferences), which nothing else covers.

### `boincui` follow-ups

The "build a graphical web UI" item that used to dominate this file was answered by `boincui` 1.0.0 —
see Resolved for what was decided and why. What follows is what it did **not** settle, in rough order
of cost.

- [ ] **Localise `boincui`'s page.** Only `translations/*.yaml` is translated today, and that covers
  configuration fields, not the page itself. If it is ever done, the activity control's wording
  should come from BOINC's own catalogue rather than a third phrasing — `locale/es/BOINC-Manager.po`
  has *Ejecutar siempre* / *Ejecutar según preferencias* / *Suspender* with their descriptions. See
  the UI/UX section of `boincui/DEVELOPMENT.md`.

- [ ] **Show how long a temporary activity mode has left.** `cc_status` already returns
  `task_mode_delay` alongside `task_mode_perm`, in the reply `boincui` fetches anyway, so a machine
  suspended for an hour from BOINC Manager could say so instead of just "paused". Needs a duration
  formatter; `format_due` only handles deadlines.

- [ ] **Publish a maintained fork of `pyboinc` to PyPI.** Deferred deliberately; `boincui` vendors it
  instead (see `boincui/server/pyboinc/VENDOR.md`). What is already established, so it is not
  re-derived:
  - Upstream is dormant: last commit 2022-10-16, **PR #4 — from the author of the HACS integration —
    open since 2023-05-22**, issue #5 unanswered since 2023-09. Two forks already exist.
  - MIT permits it, keeping the copyright and licence. The name `pyboinc` is **free on PyPI** (its
    `setup.py` declares `name='PyBOINC'`), as are `aioboinc`, `boinc-rpc` and `boinc-gui-rpc`.
  - Its `setup.py` **already declares `license='MIT'` and the OSI classifier** — exactly the metadata
    `boinc-client` lacks, which would otherwise fail Home Assistant's licence check and need an entry
    in `script/licenses.py`'s `EXCEPTIONS`.
  - Work: `setup.py` → `pyproject.toml`, a real version (it is `0.0.1`), a meaningful
    `python_requires`, GitHub Actions instead of the dead `.travis.yml`, and PyPI Trusted Publishing
    (OIDC) so there is no long-lived token. Plus folding in the fixes that already exist but are
    stranded upstream: SpuelMett's `str(duration)`, PR #1's Windows buffer fix, PR #2's typo, our
    `close()` and the `"\n"` normalisation.
  - **The write path is broken upstream and in both forks**, which is the strongest reason yet to
    publish a fixed one. All three `set_*_mode()` methods pass the duration where a tag name belongs,
    so they raise `TypeError` before sending anything; `Igor-Misic` left it, and SpuelMett's
    `str(duration)` stops the crash while silently dropping the duration, turning a timed change into
    a permanent one. `boincui` carries the real fix (`ET.SubElement(req, Tag.DURATION)`), verified
    against a running client — it is a three-line PR to upstream whenever the fork happens.
  - **This is what a Home Assistant core integration would require**, since core only accepts
    dependencies pinned as `<package>==<version>` from PyPI (`script/hassfest/requirements.py`).
  - Cost: a public package to maintain. Courtesy first: offer upstream to take over maintenance.

- [ ] **Discover the BOINC add-on's hostname through the Supervisor API**, instead of making the user
  copy it from the Info page into `boincui`'s configuration. It would remove the worst half of the
  cross-add-on setup friction, but requires granting `hassio_api`, i.e. widening this add-on's
  permissions. Needs its own analysis before anyone reaches for it.

- [ ] **Cross-host aggregation — one table of every task across every machine**, sortable by
  deadline, with bulk actions. This is the one thing neither `boinctui` nor SpuelMett's integration
  offers, and `boincui` does not either: it renders a section per machine, deliberately (see the
  UI/UX section of `boincui/DEVELOPMENT.md`, which argues the per-machine view is the right default,
  not that an aggregate view is wrong). Needs a story for **partial failure** — one powered-off host
  must not empty or stall the table — which the current per-machine layout gets for free.

- [ ] **Act on individual tasks and projects.** `boincui` can set a machine's activity mode and
  nothing else. The next rungs, in BOINC's own vocabulary: per-project suspend / resume / update /
  no new work, and abort task. Each is one more `pyboinc` call and one more confirmation question —
  aborting a task destroys days of work, so it is not a bare button like the mode control is.

- [ ] **Can an ingress panel be restricted to admin users?** Unverified, and it decides how much
  power `boincui` may concentrate: BOINC's GUI RPC has one password per client and no roles, so the
  panel already grants total control of every configured machine to whoever opens it. If HA cannot
  restrict it, that is a documentation duty at minimum. Check `SCHEMA_APP_USER` and the ingress
  session API in Supervisor.

- [ ] **Version skew across BOINC clients.** Different client versions expose different RPC fields;
  `boinc.py` reads what it needs and would `KeyError` or silently blank on an older one. Nothing has
  gone wrong yet because every client tested was current. Decide the policy — a declared minimum
  version, or defensive reads — before someone points it at an old machine.

- [ ] **Confirm the Docker NAT behaviour on a real Home Assistant host.** Add-on ↔ add-on traffic
  stays on HA's Docker network and the target sees the container hostname; traffic to a LAN machine
  is masqueraded, so the remote host most likely sees **the Home Assistant host's IP** — meaning a
  remote PC's `remote_hosts.cfg` needs a *different* entry than a sibling add-on does. Strongly
  supported, not confirmed there: 2026-08-11 a BOINC client in a container reached through a
  published port logged `GUI RPC request from non-allowed address 192.168.65.1`, the Docker gateway
  rather than the caller — but that is Docker Desktop's NAT. Already documented in `boincui/DOCS.md`
  as the likely cause when a LAN machine refuses the connection, so the risk is a wrong hint, not a
  broken feature.

- [ ] **The GUI RPC password is still typed twice**, once in `boinc`'s options and again in
  `boincui`'s, because they are separate add-ons. Running the UI *inside* the `boinc` add-on would
  remove it — localhost RPC, `gui_rpc_auth.cfg` read straight from the data folder, no `remote_hosts`
  entry — at the cost of lifecycle independence: a crash-looping local client would take down the UI
  you were using to watch the *other* machines. Not a reversal to make lightly now that `boincui`
  ships; the cheaper half is the hostname discovery item above.

### `boinc` operator

None open. The `projects:` list shipped in 3.10.0 — see Resolved.

## Housekeeping

- [ ] `boinc/apparmor.txt.disable` is unmodified add-on template boilerplate (references
  `/etc/services.d`, `/etc/cont-init.d`, bashio, s6-overlay `/init`) — none of which this add-on
  uses; its entrypoint is a plain `python3 /opt/operator/main.py`. It still carries the template's
  `my_program` placeholders and its commented-out "here is how to build the list" instructions, so
  nobody ever adapted it. **Doubly inert**: `apparmor: false`, *and* Supervisor looks for
  `apparmor.txt`, so the `.disable` suffix means it was never read either way. Only `boinc` has one;
  `boinctui` and `boincui` declare `apparmor: false` with no file at all, so deleting it would make
  the three consistent.
  Either rewrite it to match the real process tree or delete it so it does not mislead a future
  contributor. **If deleting: `CLAUDE.md` cites this exact path** as the example of why
  `monitored_files` is a regex that can over-match (`app` would also match
  `boinc/apparmor.txt.disable`), so that example needs a different filename or the note needs
  rewording.
- The Dockerfile labels item was **stale and is closed** — see *Confirmed correct* under
  Conformance. They already agree across all three add-ons.

---

# Resolved — kept so it is not re-litigated

## Discarded after investigation

- [x] **A Home Assistant entity surface is not this repo's job (decided 2026-08-11).** Three items
  used to sit here — link SpuelMett's integration, build HA-native sensors, expose a Prometheus
  endpoint. Only the first survived, as work rather than backlog: the pairing is now documented in
  `boinc/DOCS.md`, and the maintainer runs that integration against this add-on.
  - **Sensors: dropped.** An add-on cannot create entities — it is not an integration and lives in
    another container. Publishing would mean MQTT discovery (forces a broker on the user), or Core's
    REST API with `homeassistant_api: true` (widens permissions this repo deliberately keeps narrow,
    see the `hassio_api` item), or shipping a custom integration alongside — which is precisely what
    <https://github.com/SpuelMett/Boinc-Home-Assistant-Integration> already is (MIT, config flow,
    multiple hosts; sensors for total/running tasks and average progress; services for start, hard
    stop, soft stop and GPU start/stop). Its README says it cannot run BOINC on the Home Assistant
    host and that a separate add-on is needed for that — which is this repo. Complements, not
    competitors. Maturity caveat, unchanged: single maintainer, v0.0.7, not in HACS. Linking is free;
    depending on it would be a risk decision, and the docs treat it as optional.
  - **Prometheus: dropped, and it was never parallel to sensors.** Home Assistant's own `prometheus`
    integration exports the entities it already has, so once the integration above provides them,
    scraping comes essentially free. A `/metrics` endpoint in an add-on gives no entity in return, so
    it would only serve someone wanting BOINC metrics *without* Home Assistant — not this repo's
    audience.
  - **The `boincui` data layer stays where it is.** `boincui/server/boinc.py` already reads running /
    queued / finished tasks, projects and activity mode from every configured machine each minute.
    That it could feed entities is true and irrelevant: the blocker was never the data.

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

## Shipped in `boinc` 3.10.0

- [x] **`projects:` — declare the projects to attach in the add-on options.** New
  `boinc/operator/projects.py` reconciling three sets on every start: `desired` (the option,
  canonicalized through `url.py`), `actual` (`--get_project_status`), and `managed`
  (`.managed_projects.json`, the `kubectl apply` pattern already used for preferences). The
  ownership file has **two** lists, `attached` and `detaching`. Five of the seven constraints
  written up here survived contact; the design notes below are what measurement changed, so the
  same ground is not re-covered:
  - **Credentials: an `account_key` per project, not email + password.** That removes
    `--lookup_account` entirely, and with it two traps found in BOINC 8.2.15: it takes its exit
    code from the *initial* RPC rather than the poll, so a failed lookup prints
    `poll status: can't resolve hostname` and still **exits 0**; and its poll loop has no sleep and
    no break when the poll RPC itself errors, i.e. an infinite busy loop upstream. Success is only
    detectable as `account key: <auth>` on stdout.
  - **Removal is `detach_when_done`, not `nomorework` and not a bare `detach`.** It drains first and
    detaches after, so no completed work is destroyed. Its flag is **not** among the fields
    `--get_project_status` prints, which is the whole reason the state file needs a second list: a
    pending detach is invisible from outside, so a project removed and then re-added would otherwise
    have a detach fire silently days later. Re-adding sends `dont_detach_when_done` **and**
    `allowmorework`; BOINC's source pairs the two, but that pairing was the one thing not verified
    live, so it is asserted explicitly instead of assumed.
  - **There is no retry at all, which took two goes to see.** `--project_attach` is a *local* RPC
    that returns instantly and persists even against an unresolvable host — the client then retries
    the project's own scheduler by itself, indefinitely. So "the project is down" was never the
    operator's problem, which left only "the client is not answering yet" — and *that* window is
    already closed by the initialization loop, since `configure_projects` runs only after
    `boinccmd --get_state` has succeeded. A bounded backoff was written first and then deleted: it
    guarded a case that cannot arise. A failed attach is now a warning naming the projects, retried
    when the app restarts, which is when an options change takes effect anyway.
  - **No background thread either, and nothing polls after startup.** A thread only earns its place
    if the attach can block on the network, and it cannot. The wait loop is now a bare
    `boinc_process.wait()`: in CPython 3.13, `wait()` with no timeout is a blocking `waitpid()`,
    while `wait(timeout=...)` is an explicit busy loop sleeping up to 50 ms — *worse* than the
    `sleep(0.5)` it replaced, and the trap waiting for anyone who reintroduces a periodic wake-up
    here. Measured: the operator sits at `Threads: 1`, `State: S (sleeping)`. The one remaining
    `sleep` is the initialization loop, which stays — see below.
  - **The initialization loop is now bounded, which was the real defect in it.** It had no deadline:
    a client that starts but never answers RPCs left the operator spawning `boinccmd` twice a second
    *forever* while Home Assistant reported the app as started — more polling than the retry loop
    above ever did. Now it gives up after `--initialization-timeout` (300 s by default, generous
    because taking a while normally means a slow host reading a large `client_state.xml`, and
    stopping an app that was merely slow is the worse mistake), stops the client and exits 1 with a
    message about the client rather than about the configuration. The probe also moved *before* the
    first sleep, so a normal start no longer pays the interval for nothing.
  - **Removing that last `sleep` with inotify was evaluated and rejected on price, not on
    impossibility** — which corrects an earlier claim here that no blocking primitive existed. One
    does: BOINC creates a Unix domain socket (`GUI_RPC_FILE`) and `bind()`s + `listen()`s on it
    *before* setting up the TCP socket (`client/gui_rpc_server.cpp`), so there is a filesystem event
    at the exact moment it starts accepting RPCs. What makes it a bad trade: the watch has to be
    armed *before* `Popen` or the file can appear in the gap and block forever; BOINC `unlink()`s a
    stale socket before binding, so a leftover from the previous start would fool a plain existence
    check; a deadline and a confirming `--get_state` would still be needed; and all of that plus a
    new Dockerfile dependency (`python3-watchdog`, or ~40 lines of `ctypes`) buys about three fewer
    `boinccmd` spawns, once per container start.
  - **Reconciliation runs at startup only.** Home Assistant cannot apply an options change without
    restarting the app, so there is nothing new to read afterwards. A periodic check was rejected
    for a second reason: combined with the re-attach behaviour below it would make BOINC Manager's
    detach button useless for any listed project.
  - **A project detached outside the options comes back on the next start**, deliberately and with
    no special-cased log line — it is simply `desired − actual`. Consistent with the operator
    re-asserting its own preference keys on every start. Documented in `DOCS.md`.
  - **The account manager is refused, not merged**: `projects` plus any `account_manager_url` is a
    startup failure, before the client is even launched. Separately, a project reported as
    `attached via Account Manager: yes` is excluded from the diff entirely, which covers a manager
    attached outside the options.
  - **Verified end to end against a real client**, not only in unit tests: attach with URL
    canonicalization, removal → `detach_when_done`, a project attached by hand left untouched, the
    state file self-healing once the client lets a project go, re-add re-attaching, and the account
    manager conflict exiting 1 without starting BOINC.
  - **And against a real Supervisor** (`supervisor.sh`, 2026-08-15), which is the half CI cannot
    see. Supervisor parses the option as `type: schema`, `multiple: true`, with `url` carrying
    `format: url` and `account_key` `format: password`; both translations render; the
    `options: projects: []` default lets a fresh install validate; and **the schema rejects at
    tier 1**, before the container starts, with the message shown in the UI — `expected a URL` for a
    malformed address and `Missing option 'account_key' in projects` for a half-filled entry. The
    runtime conflict then reports **`state: error`**, not the `stopped` the 3.8.4 note predicted;
    that note describes a failure minutes into a run, while this one exits within a second of start,
    so the two are not necessarily in conflict — but a fast hard failure is visibly an error.

- [x] **`boinccmd.py`'s vestigial `while not current_account_manager_read:` loop — removed.** It
  always ran exactly once, since its body either returned or set the flag; probably a retry loop
  that lost its retry. Found next to the `sleep(10)` below.

- [x] **`sleep(10)` between detaching and attaching an account manager — deleted, not shortened.**
  BOINC's `--acct_mgr detach` is `rpc.acct_mgr_rpc("", "", "")`, a single synchronous RPC
  (`client/boinc_cmd.cpp`); only `attach` and `sync` poll, and they do it inside `boinccmd`. So the
  wait was for something that had already happened. It also mattered because of what it exposed:
  `time.sleep()` is *resumed* after a signal handler runs rather than cut short (PEP 475, measured —
  handler at 0.31 s, `sleep(3)` still returning at 3.01 s), so a stop during that window ended in an
  attach against a dead client and a **misleading `exit 1`**. `main.py` now re-checks for a stop
  *after* `configure_boinc_projects` returns, not only before calling it — the same distinction
  3.8.5 drew for a stop during initialization.

## Shipped alongside `boinc` 3.10.0 — repo tooling, not an add-on

- [x] **`supervisor.sh` could not be run twice (2026-08-15).** Three failures, all hit while
  validating the `projects` schema against a real Supervisor:
  - `install <addon>` refused with `App … is already installed`, so every iteration needed a manual
    uninstall. It uninstalls first now — which is also the only way to make Supervisor re-read
    `config.yaml` and `translations/`, since it snapshots them into `apps.json` at install time.
    **That discards the app's `/data`**, so an *upgrade* still has to be tested by bumping the
    version and running `ha apps update` by hand, which is how the 3.9.1 → 3.10.0 check above ran.
  - `up` treated an existing-but-stopped container as running, because `docker inspect` succeeds for
    a stopped one, and then died on the first `docker exec`.
  - After an unclean stop, `supervisor_run` reads a stale `/var/run/docker.pid`, concludes dockerd
    is up, fails to connect and gives up — leaving only `Cannot connect to the Docker daemon` and a
    `SIGTERM` aimed at a pid from the previous boot. `up` now clears that pidfile and starts dockerd
    itself.

  Between them, the recovery that gotcha 6 in `SKILL.md` documents actually works unattended now.

## Shipped as `boincui`, 0.1.0 → 1.0.0

- [x] **"Graphical web UI" — built, and most of its design questions are now answered rather than
  open.** The item used to be the largest in this file; what it planned, `boincui` does. Kept
  condensed because the reasoning still guides the remaining items above, and the full argument with
  its evidence lives in `boincui/DEVELOPMENT.md`:
  - **Ingress compatibility decided build-over-wrap.** Served under `/api/hassio_ingress/<token>/`
    with a token generated at install time and never passed on, so every emitted URL — `href`,
    `action` *and* `Location` — must be relative. Server-rendered Flask, no SPA, no `url_for`;
    `test_app.py` and `smoke.sh` both assert it. The "evaluate an existing web UI first" experiment
    was never run: writing the page cost less than auditing a third-party SPA for baked-in absolute
    asset paths.
  - **`boinccmd` was rejected as a backend, as predicted** — one process spawn per call against
    human-readable text. `boincui` speaks GUI RPC over TCP 31416 through vendored `pyboinc`, which
    also settles the separate "pick a library rather than writing one" item: `boinc-client`
    (synchronous, no licence metadata) lost to `nielstron/pyboinc` (MIT, asyncio, already used by
    SpuelMett's integration), vendored rather than depended on because it was never published to
    PyPI. See `boincui/server/pyboinc/VENDOR.md` and the open item on publishing a fork.
  - **Host + credential storage went to add-on options**, the declarative fork: visible, backed up,
    validated by Supervisor, and one writer instead of two. A list of dicts cannot be optional, hence
    `options: clients: []`.
  - **Partial failure is handled by construction**, not by a retry policy: a background refresher
    polls on its own thread and views only read its snapshot, so a machine that is switched off costs
    a log line and a per-machine error state instead of a stalled page.
  - **"Query" and "configure" remain two products.** `boincui` is the configure half through ingress;
    the query half — HA entities, history, automations — is still unbuilt and still best served by
    linking SpuelMett's integration.

- [x] **`boincui`'s deprecated single-client options removed — in 1.0.0, not 0.6.0.** Held back from
  0.5.0 because they had been deprecated for a single released version and Supervisor **silently
  discards options that disappear from the schema**. Brought forward to 1.0.0 rather than pushed
  further out, because that release also drops `stage: experimental`: once an add-on is stable,
  removing an option from its schema is a breaking change that would call for a 2.0, so 1.0 was the
  last cheap moment. The landing is soft — an unmigrated install starts with no machines and the page
  says exactly that — and the `CHANGELOG.md` entry warns before the update. Both paths were exercised
  against a real Supervisor: a migrated install is untouched, and Supervisor keeps the removed keys
  in its own `apps.json` rather than destroying them.
