# Changelog

## 1.3.0

BOINC UI now comes with a security profile: the list of the only things it should ever need to do, which is read its own settings and talk to the machines you listed. For now the profile only watches and stops nothing, so the list can be proved right on real installations before a later version switches it on. The security rating on the Info page goes from 6 to 8 out of 8 as soon as the profile exists, so it runs ahead of the protection itself until then. Nothing changes in how the app works

## 1.2.0

Each machine now shows the processor it runs on and how many cores it has, under its name — useful when you have several and their names do not say what they are

That is how many cores the computer has, not how many BOINC is allowed to use, so a machine limited to part of its processor runs fewer tasks than it has cores. A machine that does not report its processor is shown exactly as before

## 1.1.0

On a computer screen your machines now sit side by side, up to three across, instead of in one narrow column with empty space either side of it. Several machines fit without scrolling

On a phone nothing changes: one machine after another, top to bottom. The page decides for itself how many fit, so a tablet gets two and a wide monitor three

A task's progress bar and the percentage beside it no longer split across two lines when the space is tight

## 1.0.0

The three old settings for a single BOINC client — address, port and password — are gone. If you are still using them instead of the BOINC clients list, this update leaves the app with no machines configured and the page will tell you so; add them to the list and it works again. If you already use the list, nothing changes

BOINC UI is no longer marked as experimental

## 0.5.0

You can now start and stop computing on each machine, under Activity: Run always, Run based on preferences, or Suspend. They are the same three choices, with the same names, that BOINC Manager offers

The choice takes effect immediately and sticks, surviving a restart of BOINC and of the machine

Careful with Run always: it makes that machine compute on battery, while you are using it, and outside the hours you set for it

A machine that is running BOINC but refuses to let this app in now says so, instead of being reported as unreachable — they need different fixes

## 0.4.0

You can now watch several BOINC machines at once, each with its own section on the page. Add them under BOINC clients in the Configuration tab

Each machine now says whether it is computing and, when it is not, why — usually the time of day or a busy processor

The table lists the tasks running right now and counts the ones waiting and finished, instead of every task at once

A machine that cannot be reached no longer hides the ones that can

Your previous settings keep working and appear as one machine. Move them to the client list when convenient, since the old fields will be removed later

## 0.3.0

The page now shows the tasks a BOINC client is running and the projects it is attached to

Added the settings needed to reach a BOINC client: its address, its port and its password. See the Documentation tab, the BOINC app has to be set up to accept the connection as well

When it cannot connect, the page now says which of the usual problems it hit instead of just showing nothing

## 0.2.0

Added a web page, reachable with the Open Web UI button and optionally from the sidebar

The page still reports that no BOINC client is connected, because the app cannot talk to one yet

## 0.1.0

First version of the app. It is marked experimental and does not do anything useful yet: it starts,
says hello in its log and then just sits there

Use the boinctui app to manage BOINC in the meantime
