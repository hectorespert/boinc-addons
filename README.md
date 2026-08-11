# Home Assistant BOINC apps repository

This repository allows to install the [Home Assistant BOINC App](./boinc) and other related apps in your Home Assistant installation to contribute to scientific research projects using the [BOINC](https://boinc.berkeley.edu) platform.

The [BOINC](https://boinc.berkeley.edu) platform enables individuals to contribute their computer's idle processing power to various scientific research projects, such as climate modeling, medical research, and astrophysics.

## Installation

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fhectorespert%2Fboinc-addons)

To install the apps provided by this repository in your Home Assistant instance, click on the button above or follow these steps:

1. Open your Home Assistant instance.
2. Go to **Settings → Apps** (called **Add-ons** before Home Assistant 2026.2).
3. Click on the "App Store" button in the bottom right corner.
4. Click on the three dots in the top right corner and select "Repositories".
5. Add the repository URL: `https://github.com/hectorespert/boinc-addons`.
6. Install the desired apps from the store.

## Usage

This repository contains the following apps, enable them as needed:

### [BOINC app](./boinc)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

[BOINC](https://boinc.berkeley.edu) is an open-source software platform for computing using volunteered resources. 

This app configures and executes the BOINC client in your Home Assistant instance, downloads scientific computing jobs and runs them invisibly in the background.

### [boinctui app](./boinctui)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

[boinctui](https://github.com/suleman1971/boinctui) is a fullscreen text mode manager for the BOINC client.

It provides a terminal user interface (TUI) to monitor and control the BOINC client.

### [BOINC UI app](./boincui)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

A graphical web interface to monitor and control the BOINC client, as an alternative to the text mode interface boinctui provides.

It opens a page inside Home Assistant showing what each of your BOINC machines is computing and the projects it is attached to — the BOINC app on this machine, other computers on your network, or both — and each machine can be set to compute always, to follow its own preferences, or to stop.

It does not yet act on individual tasks, attach or detach projects, or change a machine's preferences. Use boinctui for those.

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
