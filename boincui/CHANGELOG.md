# Changelog

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
