# Home Assistant BOINC UI App

BOINC UI shows what your BOINC clients are doing — what each machine is computing right now, and the
projects it is attached to — on a page inside Home Assistant. It is **experimental**, and this
version can only look: it cannot suspend, resume or abort anything.

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

The table lists only the tasks running at that moment, which is normally one per processor core. A
line above it counts the rest: **waiting** are downloaded and queued, **finished** are done and
waiting to be sent back. To see the full queue, use the **boinctui** app.

Each row shows the project, how far along the task is and when it is due. Hovering over a row shows
BOINC's own name for the task, which is what you would search for in boinctui.

## When something is wrong

Each machine reports its own problem, and the others keep working:

- **Cannot be reached** — wrong address, BOINC not running there, or it has not been told to accept
  connections from this app.
- **Rejected the password** — the passwords do not match. The BOINC app needs a restart after
  changing its own.
- **Not fully configured** — that entry is missing its address or password.

The page checks every machine once a minute. **Refresh now** asks for a check straight away instead
of waiting — the result appears within a few seconds, when the page next reloads.

## Upgrading from an earlier version

If you configured a single client before this version, it keeps working and appears as one machine.
Move those settings into the **BOINC clients** list when convenient: the old fields are marked as old
settings and will stop working in a future version.
