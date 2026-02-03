# Changelog

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
