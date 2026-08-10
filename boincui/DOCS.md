# Home Assistant BOINC UI App

BOINC UI shows what a BOINC client is doing — its tasks and the projects it is attached to — on a
page inside Home Assistant. It is **experimental**, and this version can only look: it cannot
suspend, resume or abort anything yet.

## Connecting it to the BOINC app

Two apps have to agree, so there are settings on both sides.

**First, in the BOINC app's configuration:**

1. Set `gui_rpc_password` to a password of your choice.
2. Allow the connection: either turn on `allow_remote_gui_rpc`, or add this app's hostname — shown
   on **this** app's Info page — to `remote_hosts`.
3. Restart the BOINC app so the changes take effect.

**Then, in this app's configuration:**

1. **BOINC client address** — the hostname shown on the **BOINC app's** Info page.
2. **BOINC client password** — the same password you set in step 1 above.
3. **BOINC client port** — leave it empty.

Start this app and open it with **Open Web UI**. If you would rather reach it from the Home
Assistant menu, turn on **Show in sidebar** on this app's page.

## Connecting to BOINC on another machine

The same fields work for a BOINC client running anywhere else on your network: use its address, and
the password from its own configuration. That machine also has to be set up to accept remote
connections, which is a setting in BOINC itself rather than in Home Assistant.

## When something is wrong

The page tells you which of the three usual problems it hit:

- **No BOINC client is configured** — the address or the password is still empty.
- **Cannot reach the BOINC client** — the address is wrong, the BOINC app is stopped, or it has not
  been told to accept connections from this app.
- **The BOINC client rejected the password** — the two passwords do not match. They have to be
  identical, and the BOINC app needs a restart after changing its own.

The page checks the client once a minute. **Refresh now** checks immediately, which is the quickest
way to see whether a change you just made worked.

## What this app cannot do yet

Change anything. Suspending a task, resuming it or attaching a project all have to be done from the
**boinctui** app for now.
