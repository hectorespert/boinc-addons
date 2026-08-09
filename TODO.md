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

- [x] **Fixed in `boinc` 3.8.2** — the module was rewritten for the empty-password fix above and
  now uses `logging` throughout.
  **`gui_rpc_auth.py` imports `logger` from the stdlib `venv` module.**
  `boinc/operator/gui_rpc_auth.py:3` does `from venv import logger` and calls `logger.debug(...)`
  at line 9, instead of using its own `logging.getLogger(__name__)` like every other module in
  `operator/`. It happens to work because CPython's `venv` package exposes a module-level
  `logger`, but that's an implementation detail of an unrelated stdlib module, not a public API —
  it's not guaranteed stable across Python versions. Looks like an autocomplete/typo accident
  rather than an intentional import.

- [x] **Fixed in `boinc` 3.8.5** — `action='store_true'`, so the flag now takes no value at all
  (default `False`, present means `True`), which removes the possibility of a truthy string
  entirely instead of guarding against one. Updated the three call sites that passed the literal
  `true` to just pass the bare flag: `build-addons.yaml:116`,
  `.claude/skills/run-boinc-addons/smoke.sh:27`, `.claude/skills/run-boinc-addons/SKILL.md:44`.
  No live incident either before or after, as the write-up below already noted — this closes the
  landmine, not a bug anyone hit.
  **`--exit-immediately` is parsed with `type=bool`, so any non-empty string is truthy.**
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

- [x] **Fixed in `boinc` 3.8.5** — the `number != signal.SIGINT` exclusion is gone; all four
  signals are now forwarded identically. Verified against BOINC's own client source
  (`client/main.cpp:157-175`): it treats `SIGINT` exactly like `SIGTERM`, a clean shutdown with
  checkpointing, so forwarding it is correct and idempotent even if something else already
  delivered the signal to the whole process group.
  **Correction to the write-up below, measured against a container built from `main` before this
  fix — the claimed symptom was backwards.** Interactive Ctrl-C (`docker run -it`, a real pty)
  already worked, by accident: the terminal delivers `SIGINT` to the whole foreground process
  group, so the BOINC client receives it directly and shuts down cleanly regardless of what the
  operator does with its own copy of the signal. The real failure was any `SIGINT` that reaches
  *only* the operator process — `docker kill -s INT`, a bare `kill -INT <pid>`, an orchestrator
  signalling the container's PID 1 without a foreground pty in the mix. In that case the operator
  logs that it caught the signal and then does nothing else: BOINC is never signaled (no matching
  line in its own log) and the container runs forever. So "Ctrl-C hangs the container" below is
  not what was actually observed; "a `SIGINT` delivered to the operator alone is swallowed and
  BOINC is never asked to stop" is. The fix is correct either way, since forwarding is what both
  cases need.
  **`SIGINT` is caught but neither forwarded nor acted on — Ctrl-C hangs the container.**
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

- [x] **Fixed in `boinc` 3.8.3** — the two hours are now written as a pair or not at all, which is
  what BOINC Manager does (`clientgui/DlgAdvPreferences.cpp` sets
  `mask.start_hour = mask.end_hour = true`, so a half window is unreachable from its UI). An
  incomplete pair, *and* an equal pair, are ignored with a warning and BOINC computes all the
  time — which is what an unset schedule already means and what `DOCS.md` already promised.
  The equal-pair case was found while answering "what does BOINC Manager do here?": BOINC reads
  `start_hour == end_hour` as no restriction at all (`TIME_SPAN::suspended` returns false), so
  `22:00`–`22:00` is not a 24-hour window but the opposite of a schedule. Confirmed against a
  live client, and BOINC Manager rejects that combination outright with an error dialog
  (`if (startTime == endTime) ShowErrorMessage(invMsgTimeSpan, ...)`).
  Deliberately *not* a startup failure: a soft config mistake should not crash-loop the app now
  that exit codes propagate (3.8.0). It composes with the three-way merge from 3.8.1 — a window
  the operator previously wrote is withdrawn when the config becomes incomplete, rather than
  leaving half of it behind.
  **`start_hour` and `end_hour` are documented as a pair but nothing enforces it, and setting
  one alone silently creates a different schedule than the user asked for.**
  `boinc/DOCS.md:90` says end_hour "Must be used together with `start_hour`", but
  `global_prefs_override.py` writes whichever option is set and BOINC fills the missing one with
  its default of 0 — midnight. Neither the schema (`boinc/config.yaml:23-24`, both plain
  `match(...)?`) nor the operator validates the pair or warns. Verified against a live client with
  `boinccmd --get_cc_status` at 09:02 UTC (2026-08-09):

  | options | effective window | status at 09:02 |
  |---|---|---|
  | neither | always | `suspended: CPU is busy` (no time restriction) |
  | `start_hour: 22:00` alone | **22:00 → 00:00** | `suspended: time of day` |
  | `start_hour: 08:00` alone | **08:00 → 00:00** | no time-of-day suspension |
  | `end_hour: 20:00` alone | **00:00 → 20:00** | no time-of-day suspension |

  So a user who sets only `start_hour: 22:00`, meaning "compute from 22:00 onwards", gets computing
  that **stops at midnight** — no error, no warning in the log, nothing visible in the Supervisor
  UI. This is the most likely of the open bugs to bite a normal configuration. Fix has two halves:
  the operator should warn (and probably refuse to write a half-window) when exactly one of the two
  is set, and the docs should say what the missing half defaults to.

- [x] **Fixed in `boinc` 3.8.2** — three states instead of two, which a real Supervisor confirms
  are distinguishable (2026-08-09): an unset option arrives as `{}` while `gui_rpc_password: ""`
  reaches `options.json` intact as an empty string. Unset → the operator does not create the file
  and BOINC generates its own password; explicitly empty → an empty file, opting into no password
  on purpose; set → written as before, now with 0600 permissions. An empty file left by an older
  version is removed so upgrading closes the hole, while a password BOINC generated itself is kept
  so it does not rotate on every restart. `test_gui_rpc_auth.py` grew from 3 cases to 8, and the
  `from venv import logger` import at the top of the module (its own open item below) went with the
  rewrite.
  **`gui_rpc_password` left unset writes an *empty* `gui_rpc_auth.cfg`, disabling BOINC's own
  secure default.** `gui_rpc_auth.py` always creates the file and only writes content
  `if password:`, so leaving the option blank — a legitimate and probably common configuration,
  it is `password?` in `boinc/config.yaml:16` — produces a 0-byte file. That is not "no
  authentication", it is *the empty password*. Verified end to end (2026-08-09) against the real
  image with `allow_remote_gui_rpc: true`, connecting from a second container:

  ```
  attacker: boinccmd --host <ip> --passwd "" --set_run_mode never 300

  empty gui_rpc_auth.cfg   -> no error, and the target's own get_cc_status then reports
                              `current mode: never` -- the attacker really did take control
  BOINC-generated password -> Operation failed: authentication error, target unchanged
  configured password      -> Operation failed: authentication error, target unchanged
  ```

  Measure this with a *privileged* RPC and check the effect on the target. `--get_cc_status` is
  answered without authentication by design, so it shows "success" against a password-protected
  client and proves nothing; `boinccmd` also exits 0 on an auth failure, and the message is
  `Operation failed: authentication error`, not the `Authorization failure: -155` that a *wrong*
  password produces. Two false positives to avoid when re-checking this.

  And the counterfactual, running `boinc` with no operator against an empty data dir:

  ```
  -rw------- 32 bytes  b786c9882cdd189d4649a9a8430acb9d
  ```

  BOINC generates a random 32-character password and creates the file 0600 when it is *absent*. So
  the operator is not failing to add a protection, it is **removing one** by creating the file
  first. Fix: do not create `gui_rpc_auth.cfg` at all when no password is configured (and delete a
  previously written one, since a leftover empty file would keep the hole open).

  Scope: with the defaults (`allow_remote_gui_rpc` unset, `remote_hosts` empty) only localhost can
  connect, so there is no exposure. The dangerous combination is no password *plus* remote RPC —
  which is exactly the path `boinctui/DOCS.md:7-9` walks users through to connect the two add-ons.

  Related, smaller: the operator writes the file `-rw-r--r--` (0644) where BOINC writes it 0600.

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

- [x] **Fixed in `boinc` 3.8.5** — rather than inventing a new normalisation, the fix mirrors
  BOINC's own `canonicalize_master_url` (`lib/url.cpp`), which the client already applies to the
  account manager URL before storing it (`client/acct_mgr.cpp`) — so what `boinccmd --acct_mgr
  info` reports is already in this form, and comparing through the same function compares URLs
  exactly the way the client itself would. New module `boinc/operator/url.py`,
  `canonicalize_url()`, not a private helper in `boinccmd.py`, because the `projects:` item below
  needs the same function. Rules: no scheme, or any scheme other than `https`, becomes `http`;
  repeated slashes collapse to one; a trailing slash is always appended; only the host is
  lower-cased, never the path.

  | configured | stored by the client | before | after |
  |---|---|---|---|
  | `https://scienceunited.org` | `https://scienceunited.org/` | sync | sync |
  | `scienceunited.org` (no scheme) | `http://scienceunited.org/` | **detach+attach on every start** | sync |
  | `https://host/a` vs. `https://host/b` | — | **sync against the old one** | detach+attach |
  | `http://x` vs. `https://x` | — | sync | detach+attach |

  The last two rows are deliberate behavior changes; the last one is in the CHANGELOG, since
  correcting an account manager's scheme now re-attaches instead of silently staying on the old
  one.
  **Only the account-manager *host* is compared, so same-host URL changes are missed.**
  `boinc/operator/boinccmd.py:70` compares `urlparse(...).netloc` of current vs. desired. Two
  account managers on the same host but different paths compare equal, so the operator logs
  "already attached, synchronizing" and syncs against the old one. Probably deliberate leniency
  for `http`/`https` and trailing-slash differences — but netloc-only is a wider net than that
  needs. Normalising scheme + path (strip trailing `/`) would keep the leniency without the
  false match.

- [x] **Fixed in `boinc` 3.8.1** — three-way merge with the operator's own last-applied state
  (`.managed_global_prefs.json` in the data folder), the `kubectl apply` pattern also proposed for
  the `projects:` item below. Provenance *cannot* live in the XML: verified in BOINC's source that
  `GLOBAL_PREFS::write_subset` (`lib/prefs.cpp`) serializes only masked known fields with no
  "unparsed" buffer, and `handle_set_global_prefs_override` (`client/gui_rpc_server_ops.cpp`)
  writes the GUI's blob verbatim (`fprintf(f, "%s\n", buf)`) — deleting the file outright when the
  blob is empty. So any marker the operator embedded would be destroyed by the first edit from
  `boinctui`. Rule now applied per managed key: option set → write it; option unset **and the
  operator wrote it last run** → remove it; option unset and never written by the operator →
  leave it alone. Also switched the module from `dict2xml` to `xml.etree.ElementTree` so element
  order, repeated elements and unknown structure survive editing (`cc_config.py` still uses
  `dict2xml`, so the dependency stays). Verified end to end against a real client: `work_buf_min_days`
  and `disk_max_used_gb` injected into the file survive a restart and show up in BOINC's own
  "Computing preferences" dump.
  **Generated `global_prefs_override.xml` is a full overwrite, wiping TUI-set preferences.**
  Distinct from the symlink bug above, and present even when no `/config` file exists.
  `global_prefs_override.py:39-40` writes a freshly built dict containing *only* the four keys the
  operator manages (`start_hour`, `end_hour`, `niu_max_ncpus_pct`, `niu_cpu_usage_limit`). BOINC
  GUI clients write their "computing preferences" into this same file, so anything a user set from
  `boinctui` outside those four keys (disk limits, memory, network) is dropped on the next
  operator start. Reading the existing XML and merging only the managed keys would preserve them —
  and would compose correctly with the early-`return` fix for the symlink bug.

- [x] **Fixed in `boinc` 3.8.1** — `os.path.lexists` for the removal check, plus an explicit branch
  that drops a symlink whose target is gone.
  **A stale symlink made the operator recreate the file it was meant to read.**
  Found while fixing the merge bug above. `link_global_prefs_override` used `os.path.exists()` to
  decide whether to remove the previous file, and `exists()` follows symlinks — a broken one reads
  as missing. Sequence: the user supplies `/config/global_prefs_override.xml`, the operator leaves
  a symlink in the data folder, the user deletes the config file. On the next start the symlink is
  not removed (broken), the symlink branch is not taken (target gone), and `open(path, 'w')` writes
  *through* the broken link, **recreating the file in `/config`**. From then on the operator sees a
  config file again on every start and is stuck on the symlink branch permanently, freezing the
  user's preferences with generated content they never wrote.

- [ ] **The operator only ever writes the `niu_` ("not in use") CPU limits.**
  `global_prefs_override.py` maps `max_ncpus` → `niu_max_ncpus_pct` and `cpu_usage_limit` →
  `niu_cpu_usage_limit`. In BOINC those are the limits that apply **while the computer is idle**;
  the unprefixed `max_ncpus_pct` / `cpu_usage_limit` are never written, so no limit applies when
  the host counts as in use. Confirmed against a running client (2026-08-09) with
  `max_ncpus: 75.0` set — BOINC's own preferences dump reads `When computer is in use ... Use at
  most 100% of the CPU time` with no CPU cap, and `When computer is not in use ... max CPUs used: 10`.
  On a headless HA host "not in use" is the normal state so it mostly works, but `boinc/DOCS.md:94-101`
  documents both options as unconditional limits. Decide whether the `niu_` choice was deliberate
  (and document it) or whether both variants should be written.

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
  (Side note, now resolved: `network:` **is** a supported top-level translations key. Verified
  against a running Supervisor 2026-08-09 — it validates the key and rejects only bad *values*,
  as seen on another add-on: `Can't read translations from .../adguard/translations/en.yaml -
  expected str for dictionary value @ data['network']['53/udp']`. Our `31416/tcp` value is a
  plain string, so it is fine. No `ports_description:` needed.)

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
  `map: [addon_config]`. **Corrected against a running Supervisor (2026-08-09): the
  replacement is `app_config`, not the `type: addon_config` structured form recorded
  here earlier.** Supervisor says so itself on every store scan:
  ```
  WARNING [supervisor.apps.validate] App 'BOINC' uses legacy map type 'addon_config';
    use 'app_config' instead.
  ```
  The structured form with `read_only: false` is still how you opt out of the read-only
  default ("Defaults to read-only, which you can change by adding the property read_only: false"),
  so the target is presumably `- type: app_config` + `read_only: false` — verify the exact
  accepted shape against Supervisor before changing it, the same way this was caught.
  This used to interact with the `global_prefs_override.py` clobber bug at the top of this file —
  a read-only mount turned the write-through-the-symlink into an uncaught `OSError` and a startup
  crash loop rather than silent truncation. **The early-`return` fix in 3.8.0 removed both failure
  modes**, so this item is now purely about modernizing the `map:` syntax and making the
  `read_only` intent explicit rather than inherited from a default.

- [ ] **`build.yaml` itself is deprecated.** Supervisor, on every store scan:
  `App local_boinc uses build.yaml which is deprecated. Move build parameters into the
  Dockerfile directly.` Both add-ons still ship one. Note this does **not** compose with simply
  deleting the file: Supervisor passes `--build-arg BUILD_FROM=<its default>` regardless, which
  overrides the `ARG BUILD_FROM="docker.io/library/debian:13.6-slim"` default in the Dockerfile.
  Work out what the supported replacement actually is before removing anything — the
  `build_from` regex bug fixed in `boinc` 3.8.0 / `boinctui` 2.4.1 was found exactly here.

- [ ] **`boinctui` sets `panel_icon` but never `ingress_panel: true`.**
  `boinctui/config.yaml:10-12` has `ingress: true`, `ingress_port: 7681`, `panel_icon: mdi:console`.
  Under a running Supervisor the installed add-on reports `"ingress_panel": false`, so the icon
  configures a sidebar panel that is not enabled — ingress works (a real
  `/api/hassio_ingress/<token>/` URL is issued), it just isn't in the sidebar. Check in the UI
  whether a sidebar entry is wanted; if it is, add `ingress_panel: true`, if not, `panel_icon`
  is dead config.

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

## Config schema — breaking redesign, for a future major

- [ ] **Collapse `start_hour` + `end_hour` into a single `computing_window` option.** Breaking
  change to the option schema, so it belongs in the next major (`4.0.0`), not a patch.

  **Why.** There are three tiers of configuration validation available here, and only the first
  one is visible to a user who does not read logs:

  1. *The schema.* An option without `?` is required, and a value that fails its `match(...)` is
     rejected by Supervisor **before the container starts**, with the error surfaced in the UI.
  2. *A runtime hard failure.* `bashio::exit.nok` in the official add-ons, `sys.exit(1)` here.
     Measured on a running Supervisor (2026-08-09): with the Watchdog toggle off — the default —
     the app just reports `state: stopped`, indistinguishable from a stop the user asked for.
     With Watchdog on it becomes a restart loop. Either way the explanation is only in the log.
  3. *Degrade and warn.* A log line, nothing more.

  The schedule bugs fixed in 3.8.3 (half a window, and an equal pair) can only be caught at
  tier 3 today, because HA's option schema validates field by field and cannot express "these two
  go together". A single string makes the illegal state unrepresentable, moving the whole class up
  to tier 1:

  ```yaml
  computing_window: "match(^(?:[01]\\d|2[0-3]):[0-5]\\d-(?:[01]\\d|2[0-3]):[0-5]\\d$)?"
  ```

  **What it does not fix.** `22:00-22:00` still matches that regex, and BOINC reads an equal pair
  as no restriction at all. The runtime check from 3.8.3 has to stay; only the half-window class
  disappears.

  **Migration is the hard part, and the obvious assumption is wrong.** Supervisor does *not*
  reject an option that is missing from the schema — it drops it and logs a warning nobody reads.
  Verified by POSTing an unknown option to a running Supervisor:

  ```
  WARNING [supervisor.apps.options] Option 'computing_window' does not exist in the schema
    for BOINC (local_boinc)
  ```

  The add-on then started normally with `options.json` = `{}`. So a straight rename would make
  every existing user's schedule **silently vanish**, and BOINC would quietly start computing
  24/7 — the exact failure mode 3.8.3 was written to prevent, reintroduced by the migration.
  The transition therefore needs at least: keep all three keys in the schema for a full minor
  release, prefer `computing_window` when set, log a deprecation warning when the old pair is
  used, and only drop `start_hour`/`end_hour` in the major after that.

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

- [x] **Done in `boinc` 3.8.0** — `test_should_not_overwrite_a_linked_global_prefs_override`.
  `test_global_prefs_override.py` needs a case that supplies a config-dir override file
  *and* schedule/CPU options together, asserting the override file's original bytes survive —
  this is exactly the scenario the bug above breaks silently.

- [ ] **Nothing exercises the Home Assistant surface in CI**, only the container. Everything under
  "Conformance with the official HA apps docs" above is invisible to `docker build`/`docker run`:
  `config.yaml`/`build.yaml` validation, option schema, translations, ingress, protection mode,
  watchdog. There is now a local path for it —
  `.claude/skills/run-boinc-addons/supervisor.sh` boots the repo's `.devcontainer` with a real
  Supervisor and installs the add-on from the working tree — and it immediately paid for itself
  (the `build_from` bug, the `app_config` correction, the `network:` verification, the
  `ingress_panel` finding). Putting it in CI is a different question: Supervisor in
  docker-in-docker needs `--privileged`, a TTY, a health-check override, and pulls ~2GB, so it is
  slow and fragile. Realistic middle ground: keep it a documented manual step before releases that
  touch `config.yaml`/`build.yaml`/`translations/`, and revisit a nightly (not per-PR) job later.
- [x] **Done in `boinc` 3.8.2** — `test_gui_rpc_auth.py` now covers all three password states, the
  0600 permissions, and both upgrade paths (empty file removed, generated password kept).
  No test currently asserts on `gui_rpc_auth.py` logging behavior specifically (low
  priority — cosmetic — but flagging alongside the `venv.logger` import finding).
- [x] **Fixed in `boinc` 3.8.5** — `test/test_main.py`, a subprocess-based suite: two fake
  executables (`boinc`, `boinccmd`) written into a temp dir prepended to `PATH`, exercising the
  real script end to end. Covers: `--exit-immediately` stopping the client; `SIGINT` and `SIGTERM`
  sent to the operator both reaching the client; the operator exiting 1 when the client exits
  non-zero on its own; and `SIGTERM` during initialization exiting cleanly without the misleading
  "failed to configure" message (the extras fix above).
  No test covers `main.py`'s exit-code/signal behavior (the `--exit-immediately` parsing bug,
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
- [x] **Fixed in `boinc` 3.8.4** — it now logs an error and returns `False`, which `main.py` turns
  into a stopped client and `sys.exit(1)`. This is the one place in the add-on where the official
  hard-fail pattern fits: `home-assistant/addons` uses `bashio::exit.nok` in 17 places, and the
  closest precedent is `zwave_js/rootfs/etc/cont-init.d/config.sh`, which refuses to start when
  `network_key` and `s0_legacy_key` disagree — *"we are unsure which one to use. One needs to be
  removed from the configuration in order to start the app"*. Half an account manager is the same
  shape: no safe reading, and continuing leaves the app looking healthy while contributing to
  nothing. Contrast with the schedule pair in 3.8.3, which degrades instead precisely because it
  *does* have a documented safe reading ("if not set, BOINC computes all the time").
  `configure_boinc_projects` (`boinc/operator/boinccmd.py:45-90`) logs a warning and returns
  `True` (success) when account-manager options are partially set (e.g. URL without
  username/password) — `boinccmd.py:63-64`. That's arguably the right runtime behavior (don't
  tear down a running client over a config typo), but it means an invalid partial config is
  silently accepted forever, re-warned on every restart, with no schema-level validation ever
  surfacing it as an error in the Supervisor UI. Low priority; noting since it compounds the
  "always exits 0" issue above — there's currently no path from *misconfigured account manager*
  to *visible failure state*.

  Caveat worth knowing, measured on a running Supervisor (2026-08-09): a hard failure is **not**
  loud. The add-on container runs with Docker restart policy `no`, so with the Watchdog toggle off
  — the default — the app simply reports `state: stopped`, indistinguishable from a stop the user
  asked for; the only trace is the log line. With Watchdog on, Supervisor restarts it within five
  seconds (`Watchdog found app BOINC is stopped, restarting...`), so a permanent config error
  becomes a restart loop. Exiting non-zero is still the right call here — a silent healthy-looking
  app that computes nothing is worse — but do not assume the user will see an error in the UI.
