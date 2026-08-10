# Changelog

## 3.9.1

The Account Manager URL field now rejects an address that is not a valid URL as you type it, instead of failing later when the app starts

The app icon is no longer slightly squashed in the app store

## 3.9.0

`max_ncpus` and `cpu_usage_limit` now also limit CPU usage while the computer is in use, instead of only while it is not in use

Added `max_ncpus_idle` and `cpu_usage_limit_idle` to set a different CPU limit for while the computer is not in use

## 3.8.5

Always stop BOINC when the app is asked to stop, instead of leaving it running in some cases

Avoid reporting a misleading account manager failure when the app is stopped while BOINC is still starting up

Re-attach to the account manager when you correct its address, instead of continuing to sync with the previous one

## 3.8.4

Stop the app with an error, visible in the Log tab, when only some of the three account manager options are set

## 3.8.3

Ignore an incomplete computing schedule instead of silently starting it at midnight

Ignore a computing schedule whose start and end hours are equal, since BOINC treats that as no restriction at all

## 3.8.2

Let the BOINC client generate its own GUI RPC password when none is configured, instead of leaving it blank

Restrict access to the file that stores the GUI RPC password, matching what the BOINC client itself does, including one written by an older version of the app

Guarantee the GUI RPC password is always written inside the app's own data, never followed out through a symlink

## 3.8.1

Keep preferences set from boinctui or a remote BOINC Manager instead of resetting them on every restart

Fix a deleted custom preferences override file being silently recreated, so removing it now works and the app's own scheduling and CPU options apply again

Fix the documented filename for a custom preferences override, which was wrong

## 3.8.0

Fix a custom preferences override file being overwritten on every start

Keep an account manager attached when it was set up outside the app's configuration, instead of detaching it

Report app startup failures clearly instead of showing them as a normal stop

Stop passwords from appearing in the app's logs

Fix the Spanish translation not applying

Fix the app failing to build from source

## 3.7.0

Update base from Debian 13.5 to Debian 13.6

## 3.6.3

Maintenance update with minor improvements

## 3.6.2

Fix problem downloading ARM images

## 3.6.1

Fix image publishing to GitHub Container Registry

## 3.6.0

Update BOINC client from 8.2.11 to 8.2.15

## 3.5.0

Update base from Debian 13.4 to Debian 13.5

## 3.4.0

Update BOINC client from 8.2.9 to 8.2.11

## 3.3.0

Update BOINC client from 8.2.8 to 8.2.9
Update base from Debian 13.3 to Debian 13.4

## 3.2.0

Update base from Debian 13.2 to Debian 13.3

## 3.1.0

Install BOINC client from BOINC project releases instead of Debian version.
Add Docker support to allow using Docker containers as applications in BOINC.

## 3.0.0

Breaking: Drop support of armhf, armv7 and i386.
Breaking: Drop untested support of OpenCL.

## 2.8.1

Configure addon to use cold backups instead of hot backups

## 2.8.0

Update base from Debian 13.1 to Debian 13.2

## 2.7.2

Codenotary is now deprecated and has been removed from the configuration

## 2.7.1

Add warning message when Protection Mode is enabled

## 2.7.0

Add documentation for connecting to the BOINC add-on using the boinctui add-on

## 2.6.0

Update base from Debian 13.0 to Debian 13.1

## 2.5.0

Update base from Debian 12.10 to Debian 13.0

## 2.4.0

Update base from Debian 12.9 to Debian 12.10

## 2.3.0

Add configuration options to limit CPU usage and the number of CPUs used by the BOINC client.

## 2.2.0

Update Docker base from Debian 12.8 to Debian 12.9

## 2.1.0

Reduce addon size

## 2.0.2

Improve Account Manager configuration to fix problem with url comparasion

## 2.0.1

Fix addon sign

## 2.0.0

Major rework to support suspending the BOINC client when the CPU is being used by other applications.

To allow suspending the BOINC client based on the CPU usage from other processes, this addon requires running in privileged mode.

## 1.5.0

Fix GUI password
Read hostname from host

## 1.4.3

Fix GUI password

## 1.4.2

Improve addon operator

## 1.4.1

Fix translation

## 1.4.0

Support the configuration of the start and end time of computing.
First version of the BOINC addon operator, if there are any problems with it, please notify me.

## 1.3.7

Fix Rosseta@Home libGL.so error

## 1.3.6

Improve build using linters

## 1.3.5

Fix preferences override

## 1.3.0

Support preferences override

## 1.2.1

Sign image

## 1.2.0

Cosing image configuration
Improve docs
Enable video support to detect GPUs

## 1.1.1

Fix locale folder error

## 1.1.0

Support remote connections

## 1.0.1

Fix Account Manager attach

## 1.0.0

First stable release
Account manager support
