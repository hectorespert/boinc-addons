# Home Assistant BOINC UI App

BOINC UI shows what your BOINC clients are doing — what each machine is computing right now, and the
projects it is attached to — on a page inside Home Assistant, and lets you start and stop their
computing. It cannot yet act on individual tasks.

## Adding a machine

In this app's Configuration tab, add an entry under **BOINC clients** for each machine you want to
watch:

- **Address** — the hostname or IP address of the machine running BOINC.
- **Password** — its GUI RPC password.
- **Name** — optional, just what to call it on the page.
- **Port** — leave it empty.

Every machine also has to be told to accept the connection, and that is done on the machine itself,
not in Home Assistant.

### The BOINC app on this Home Assistant

In the **BOINC app's** configuration:

1. Set `gui_rpc_password` to a password of your choice.
2. Either turn on `allow_remote_gui_rpc`, or add this app's hostname — shown on **this** app's Info
   page — to `remote_hosts`.
3. Restart the BOINC app.

Then use the hostname from the **BOINC app's** Info page as the address here, and the same password.

### A computer elsewhere on your network

Use its address and the GUI RPC password from its own BOINC installation. That computer has to be
set up to allow remote connections, which is a BOINC setting on that machine.

One thing that may trip you up: connections from here leave through Home Assistant's own networking,
so the remote computer will most likely see **the address of your Home Assistant machine**, not this
app's. If it refuses the connection, that is the address to put in its list of allowed hosts.

## Reading the page

Each machine gets its own section, showing whether it is computing and, when it is not, why — being
outside its allowed hours and the processor being busy are the usual reasons.

Under the name is the processor that machine runs on and how many cores it has, which is handy when
several machines are listed and their names do not say what they are. That is the number of cores the
computer has, not how many BOINC is allowed to use, so a machine limited to part of its processor
runs fewer tasks than it has cores. A machine that does not report its processor simply has no such
line.

The table lists only the tasks running at that moment, which is normally one per processor core. A
line above it counts the rest: **waiting** are downloaded and queued, **finished** are done and
waiting to be sent back. To see the full queue, use the **boinctui** app.

Each row shows the project, how far along the task is and when it is due. Hovering over a row shows
BOINC's own name for the task, which is what you would search for in boinctui.

## Starting and stopping a machine

Under **Activity**, each machine has the same three choices BOINC Manager offers, with the same
names:

- **Run always** — compute regardless of that machine's preferences.
- **Run based on preferences** — compute when its own settings allow it. This is the usual choice.
- **Suspend** — stop computing.

Pick one and it takes effect immediately, and stays that way — it survives restarting BOINC and
restarting the machine, until you or someone else changes it again. The machine's line updates as
soon as the page comes back.

Two things worth knowing:

**Run always ignores that machine's own rules.** It will keep computing on battery, while you are
using the computer, and outside the hours you set. On a laptop that means a warm machine and a flat
battery. It is the right choice for a machine that exists to compute, and the wrong one for the
laptop you are typing on.

**Run always is not a promise to compute.** A machine can still pause for reasons that are not
preferences — measuring its own speed after starting up, or the operating system asking it to stop.
The line above the buttons always says what it is really doing.

If you have suspended a machine from BOINC Manager for a set amount of time, the buttons still show
its underlying setting, because the timed suspension undoes itself.

## When something is wrong

Each machine reports its own problem, and the others keep working:

- **Cannot be reached** — wrong address, or BOINC is not running there.
- **Refused the connection** — BOINC is running on that machine, but it is not letting this app in.
  On that machine, add this Home Assistant to the computers it allows to connect. See *A computer
  elsewhere on your network* above for which address it will most likely be.
- **Rejected the password** — the passwords do not match. The BOINC app needs a restart after
  changing its own.
- **Not fully configured** — that entry is missing its address or password.

If a machine cannot be reached when you press one of the **Activity** buttons, the page says the
change did not go through and nothing is altered.

The page checks every machine once a minute. **Refresh now** asks for a check straight away instead
of waiting — the result appears within a few seconds, when the page next reloads.

