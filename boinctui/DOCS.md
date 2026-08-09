# Home Assistant boinctui App

## Usage

### Connecting to the BOINC App

Do this first, in the **BOINC app's** configuration:

1. Allow the connection: either turn on `allow_remote_gui_rpc`, or add this app's hostname (shown
   on this app's Info page in Home Assistant) to `remote_hosts`.
2. Set `gui_rpc_password` to a password of your choice.

Then, in boinctui, connect using the BOINC app's hostname (shown on its Info page) and the
password from step 2.

### Connecting to Other BOINC Clients

To connect to other BOINC clients, you need their hostname, and they need to allow remote GUI RPC
connections the same way.

See: [BOINC Remote Control Documentation](https://boinc.berkeley.edu/wiki/Controlling_BOINC_remotely)
