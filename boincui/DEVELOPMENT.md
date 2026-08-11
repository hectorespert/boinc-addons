# Development

## Build locally

```bash
docker build --progress=plain -t hectorespert/amd64-addon-boincui .
```

## Run locally

The container blocks until it is signalled, so a foreground run looks like it has hung — that is
deliberate: an entrypoint that returns leaves Supervisor reporting the app as stopped seconds after
the user started it. Pass `--exit-immediately` for the one-shot path CI uses.

```bash
docker run --rm -p 8099:8099 -v $(pwd)/server/options.json:/data/options.json:ro \
  hectorespert/amd64-addon-boincui
```

Running the server straight from a checkout is usually quicker. It needs `flask` and `waitress`, in
a virtualenv rather than system-wide:

```bash
cd server
python3 -m venv .venv && .venv/bin/pip install --quiet flask waitress
.venv/bin/python main.py --options /path/to/options.json --log-level DEBUG
```

## Tests

```bash
cd server && .venv/bin/python -m unittest discover -s test -t test
```

The images run whatever `python3` Debian ships, which is not what a checkout runs. To exercise the
suite on the version that actually gets published, mount it into the built image:

```bash
docker run --rm -v "$PWD/server:/src" -w /src \
  --entrypoint python3 boincui-addon-test:local -m unittest discover -s test -t test
```

## Talking to a real BOINC client

Unit tests run against a fake GUI RPC server, which cannot tell you whether a request BOINC has
never seen is one it accepts. For anything that writes, drive a real client:

```bash
docker build -t boinc-addon-test:local ../boinc
docker run -d --name boinc-probe -p 31416:31416 \
  -v "$PWD/../boinc/operator/options.json:/data/options.json:ro" boinc-addon-test:local

# Its own view, from a second tool, as a cross-check
docker exec --workdir /data/boinc boinc-probe boinccmd --get_cc_status
```

Two things will bite you:

- **`boinccmd` needs `--workdir /data/boinc`**, because it looks for `gui_rpc_auth.cfg` in the
  working directory rather than taking a path.
- **The client only listens beyond loopback when it has an allowed-hosts list or
  `allow_remote_gui_rpc`** (`client/gui_rpc_server.cpp:326`), and it then checks the caller's address
  *after* accepting the connection. Requests from the host arrive with the Docker gateway's address,
  which the client logs as `GUI RPC request from non-allowed address 192.168.65.1`; put that address
  in the `remote_hosts` option to get in.

---

# UI and UX decisions

Why the page looks and behaves the way it does. These have all been argued once already — if you
are about to change one, the reason it is here is so that you argue with the reason rather than
rediscover it.

## Everything is rendered on the server, and every URL is relative

Home Assistant serves this app under `/api/hassio_ingress/<token>/` and **strips that prefix before
forwarding, without telling the app what it was**: the only headers ingress adds are
`X-Remote-User-*` and `X-Forwarded-For` (`supervisor/api/ingress.py`, `_create_url`). The token is
generated at install time, so it is unknown when the image is built and when the container starts.

An app that cannot know its own base URL cannot emit an absolute one. A root-relative `href`,
`action` or `Location: /` sends the browser to the Home Assistant root and out of the panel. In
Flask that also rules out `url_for` for links and redirects, since `redirect(url_for('index'))`
emits `Location: /`.

This is the constraint that decided the whole shape of the app: no bundled front end, no client-side
router, no asset paths. `test_app.py` parses the rendered HTML and fails on any root-relative URL.

### Action routes stay flat because of it

`SELF = './'` is only correct for a route hanging off the root: from `/refresh`, `./` resolves to
`/`. From `/mode/2` it would resolve to `/mode/`, and the redirect would never reach the page again.
So an action takes its target in a hidden form field, not in the path.

The root-relative guard does not catch this — `./` does not start with a slash either — so there is
a separate test asserting the redirect actually lands on the index.

## Views never contact a BOINC client while rendering; actions may

A background thread polls every machine and writes a snapshot; views only read it. Render time does
not depend on how many machines are configured, and one that is switched off cannot stall the page.

An action is the deliberate exception. It runs its exchange inside the request, with a **five second**
deadline rather than the thirty the poll gets, because someone is waiting for the page to come back.
A button press with no confirmation is worse than a slow one — but it is still bounded, and what the
rule was protecting (rendering) is untouched.

After a successful action the app re-reads **that one machine** over the same connection and swaps it
into the snapshot. Without it the page comes back looking identical for up to a poll interval, which
reads as a broken button. Re-reading all of them would put every configured machine back on the
request path.

## One section per machine, no aggregate table

Cross-machine aggregation was considered and dropped. It was written down as the thing that would
distinguish this app from `boinctui` and from the HACS integration; what distinguishes it instead is
that it is graphical and usable from a phone. That is a legitimate answer, just not the one that was
originally planned — worth knowing before someone re-adds the aggregate view expecting it to be new.

## Only running tasks are listed

`get_results()` returns every task. A machine with a normal work buffer has dozens, which is
unreadable on a phone, while the ones actually executing number about as many as it has cores. The
rest are a line of counts. `boinctui` is there for the full queue.

Task rows carry no name: BOINC's identifiers (`LATeah4013L03_925.0_0_0.0_12345_1`) say nothing to a
reader. The name goes in the row's `title`, where it is still there for anyone who wants to search
for it in `boinctui`.

## The activity control uses BOINC's own words

The three modes are labelled exactly as BOINC Manager labels them
(`clientgui/AdvancedFrame.cpp:517-529`), and `boinctui` uses the same three strings
(`src/topmenu.cpp:89-91`), under a menu both of them call *Activity*:

| request | label | description |
|---|---|---|
| `always` | Run always | Allow work regardless of preferences |
| `auto` | Run based on preferences | Allow work according to preferences |
| `never` | Suspend | Stop work regardless of preferences |

Copying them costs nothing and means anyone who has used either program recognises the control
without reading. It also supplies the warning text for `always` — *regardless of preferences* — which
is more accurate than anything invented here.

BOINC ships translations of all six strings (`locale/es/BOINC-Manager.po`: *Ejecutar siempre*,
*Ejecutar según preferencias*, *Suspender*). The page itself is not localised — only the
configuration options in `translations/` are — but if it ever is, that catalogue is where the wording
should come from rather than a third phrasing of the same idea.

### Stacked, not side by side, and with no radio marks

Each row carries its mode's description. Three of those do not fit across a phone without truncating
the longest label, and moving the descriptions out to `title` attributes hides the `always` warning
on exactly the devices that have no pointer to reveal it. BOINC Manager's own *Activity* menu is a
vertical list of radio items, so stacking is also the original shape.

Radio marks were tried and dropped: with one row filled in, the marks say the same thing twice.

## `always` is not unconditional, and the label must not imply it

`check_suspend_processing` (`client/cs_prefs.cpp:218-300`) tests benchmarks, the startup delay and an
OS-requested suspend **before** it looks at the mode, so all three suspend a client in `always` too.
What the mode skips is the user's own preferences: battery, whether the computer is in use, the
schedule, processor load, exclusive applications.

Observed rather than assumed — a real client in `always` stayed suspended with reason 16, benchmarks.

## Only permanent changes

`set_run_mode` takes a duration: zero makes the change permanent, anything else reverts on its own
(`RUN_MODE::set`, `client/client_types.cpp:1414`). A timed suspend was designed and then dropped for
being a second concept to explain in a page whose whole point is that it is glanceable. The RPC still
takes the duration, so adding it later is a parameter, not a redesign.

## The selected button follows `task_mode_perm`, not `task_mode`

A temporary mode set from BOINC Manager makes the two differ. `task_mode` is what is happening now
and will revert on its own; `task_mode_perm` is what these buttons set. Marking the temporary one
would highlight a state this control never chose and cannot restore.

## The header says what is happening, not which mode it is in

It used to append the run mode, which produced *"Computing — computing when its settings allow"*.
The control shows the mode now, so the header only reports the state and, when suspended, the reason
BOINC gives.

Expect the reason to lag by about a second after a change: **the mode updates immediately, the
suspend reason is recomputed on the client's own cycle.** Verified against a running client — it is
not a bug in the read-back.

## Unreachable and refused are different problems

A machine that is switched off and a machine that is running BOINC but does not allow this app look
alike at a glance, and need opposite advice. They are told apart by *when* the exchange fails: BOINC
checks the caller's address only after accepting the connection, so anything that breaks after the
connection was established means we were let in and then cut off.

Worth keeping because the fix for the second one is specific and otherwise invisible — the machine
has to add this Home Assistant to its own list of allowed computers.
