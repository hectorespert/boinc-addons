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

## The page is mobile first and grows into a desktop, with no breakpoint anywhere

One section per machine reads well on a phone and wasted a desktop: at 1920px the old `max-width:
48rem` used **768 of 1920 pixels — 40%** — and four machines made the page **1848px tall**, so the
fourth was below the fold on a monitor with room for all four at once. Widening the column alone
would have bought almost nothing, because a machine's own content is already capped well below it
(`.modes` at 27rem, `progress` at 8rem); the column would just have stretched the task table.

So the machines are a grid, and the whole of it is this:

```css
grid-template-columns: repeat(auto-fill, minmax(min(24rem, 100%), 1fr));
```

There is **no media query in this file, and there should not be one**. `auto-fill` lays down as many
24rem columns as fit and never makes one narrower, which is the same rule at every size — a phone
gets one column because only one fits, not because a breakpoint said so. Measured:

| viewport | columns | column width | page height |
|---|---|---|---|
| 390px | 1 | 358px | 2028px |
| 768px | 1 | 736px | 1788px |
| 1024px | 2 | 476px | 1212px |
| 1920px | 3 | 506px | 953px |
| 2560px | 3 | 517px | 953px |

**Those are viewport widths, and through ingress the viewport is not the monitor.** Home Assistant
renders this app in an iframe beside its own sidebar — 256px expanded, 56px collapsed, hidden
entirely on a narrow screen — so a 1920px monitor gives the page **1664px** and the column count
drops a step earlier than the table suggests. That costs nothing here precisely because there are no
breakpoints: the rule reads whatever width the iframe has. A layout tuned to monitor sizes would have
been wrong by a sidebar. Measured at the real panel widths: 1664px → 3 columns, 1184px → 2, 1024px →
2, 768px (a 1024px screen with the sidebar out) → 1, which is what that case already got.

At 1664px the page fills the panel exactly, with no margin either side: `max-width: 102rem` is a
content-box width, so the body totals 104rem with its padding — 1664px. Coincidence, but a
convenient one, and a reason not to switch this file to `border-box` without re-measuring.

Three pieces of that declaration are load-bearing and each was got wrong first:

- **`min(24rem, 100%)`, not `24rem`.** Below 24rem a bare minimum overflows the viewport instead of
  collapsing to one column, and the page scrolls sideways on a small phone.
- **`auto-fill`, not `auto-fit`.** `auto-fit` collapses the empty tracks, so a single machine stretches
  across the whole page — a three-column task table 1500px wide. `auto-fill` keeps the tracks and the
  lone machine stays one column, left-aligned.
- **`1fr` as the maximum, not a fixed width.** A fixed 32rem maximum left a column *narrower than the
  page used to be* whenever only one fits, which is a tablet held upright: 512px where it had been
  736px. What stops a fourth column appearing is the body's own `max-width: 102rem`, which has room
  for exactly three — a fourth would need 105.5rem.

Past three the eye has to travel across an ultrawide monitor to compare two machines, which is the
thing this layout exists to make easy.

### A lone machine keeps the width it had

`.machines:has(> .machine:only-child)` gives a single machine a 48rem track, exactly the old page
width. Without it the commonest setup of all — one Home Assistant, one BOINC client running on it —
would come out of a change meant to use more space **narrower than it went in**, at one column of a
three-column grid. In a browser too old for `:has()` that is what happens, which is a worse page but
not a broken one.

It also means the wrapper must contain machines and nothing else: one machine plus one stray element
stops being an only child and the page silently widens. `test_app.py` asserts the wrapper's children,
because nothing about that is visible in the stylesheet.

### The stacked activity buttons are untouched, and the reason still holds

The obvious follow-on — lay the three modes across the row now that there is width — does not apply:
a column is about 30rem, no wider than the single column the stacking decision was made for. Three
labels with their descriptions still do not fit across one. The argument above about phones is
unchanged, not overridden.

### What it costs

Grid rows are as tall as their tallest machine, so a short machine in the last row leaves the rest of
that row empty. Masonry would fix it and is not portable enough to rely on. Accepted: the alternative
is measuring heights in JavaScript, in an app that deliberately ships none.

## The progress bar gives up width before the percentage moves

They are one reading, so they stay on one line, and `.bar` is a flex row that shrinks the bar down to
2rem before anything wraps. A bar can lose most of its length and still say roughly how far along a
task is; a percentage pushed onto the next line reads as belonging to the row below it.

`white-space: nowrap` was tried first and is wrong twice over. It gives the cell a minimum the table
cannot honour on a phone, so at 390px the columns **overlapped** — *"42%in 2 days"*. Making the bar
shrinkable instead fixed the overlap and then made the whole page scroll sideways, because the table's
own minimum width still exceeded the viewport. `flex-wrap: wrap` is what settles it: one line whenever
there is room, and the old two-line fallback when there genuinely is not.

Narrow columns are why this surfaced now — it was already possible in one wide column, and the first
machine in a four-machine screenshot was already doing it.

So a phone still shows the percentage under its bar, exactly as before, and a wide enough column
shows it beside. Shrinking the flex basis to 6rem to win the phone case as well was tried and
reverted: flex wraps a line before it shrinks an item, so it only moved which widths were affected.

**`.pct` has a `min-width` wide enough for `100%`, and that is what stops the table looking ragged.**
Left to size themselves, `8%` fits beside its bar at a column width where `42%` does not, so rows in
the *same table* disagreed — measured at 1440px, where three of five bars wrapped and the other two
did not. A fixed width makes every row need the same space, so they all wrap or none do. Tables still
differ from each other, which is fine: they are different machines with different project names.

Two declarations look redundant and are not. `max-width` alongside the flex basis: without it the bar
contributes its full 8rem to the table's minimum width and the page scrolls sideways on a phone.
`min-width: 2rem`: it is the floor the bar shrinks to before the line gives up and wraps.

## A machine says which processor it is, and nothing else about its hardware

The name of a machine is whatever its owner typed — *attic pc* says nothing about what it is. One
line under it, from `get_host_info`, does: the processor and its core count. It also explains the
numbers below it, since the running tasks are normally one per core.

**Everything else `host_info` offers was left out on purpose.** Memory, disk, OS version, GPUs and
the benchmark figures are a hardware sheet, and BOINC Manager already has a whole *Computer info*
panel for that. This page is read at a glance; a second machine has to fit on the screen beside the
first one.

**There is no live processor usage in this RPC, and no amount of design gets one.** `host_info` is a
static description plus stored benchmark results — GUI RPC exposes no utilisation percentage at all.
The nearest honest answer is the running-task count the page already shows.

**The core count is the computer's, not BOINC's allowance.** A client held to half the processor by
`max_ncpus` still reports every core here, so a machine can legitimately say *14 cores* with four
tasks running. Making the two agree would mean reporting a different number than every other BOINC
tool shows for that machine.

### BOINC's CPUID decoding is stripped, and the vendor is what saves the line

`get_processor_info` (`lib/hostinfo.cpp`) appends its own reading of the CPUID to the model:

```
Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz [Family 6 Model 158 Stepping 10]
```

That bracket roughly doubles the length of the line and means nothing to the reader, so it goes.

What makes the fallback to `p_vendor` load-bearing rather than defensive is that **on some machines
the model is nothing but the bracket**. Verified against a real client on Apple Silicon:

```
#CPUS: 14
CPU vendor: ARM
CPU model: [Impl 0x61 Arch 8 Variant 0x0 Part 0x000 Rev 0]
```

Stripping without falling back would have left that machine with no processor at all. It now reads
*ARM · 14 cores*. The vendor is a fallback and not a second part of the line because on a machine
that does name its processor the model already opens with the readable form of the vendor — *Intel(R)
Core(TM)* — and `GenuineIntel` in front of it is noise.

### The core count is joined by a non-breaking space

A full Intel model name plus the count does not fit one column on a phone, and measured at 390px it
broke in the worst possible place — *Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz · 12* / *cores*. A
non-breaking space inside `12 cores` moves the only available break to the separator, so the second
line reads *12 cores* whole. The line still wraps; it now wraps somewhere that reads.

### It is read in the poll, and left out when it is missing

`get_host_info` is a fourth call in `_read_state`, not a one-off at startup. Two things follow: a
machine that was switched off when the app started describes itself as soon as it answers, and an
activity change keeps its processor line, because an action re-reads state through the same function.

A client that says nothing usable — or answers this request with `<unauthorized/>`, which the library
turns into `True` rather than a dict — gets no line rather than a heading with nothing under it. It
is not an error worth a message on a status page.

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
