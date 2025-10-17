# Home Assistant BOINC add-ons repository

This repository allows to install the [Home Assistant BOINC Add-on](./boinc) and other related add-ons in your Home Assistant installation to contribute to scientific research projects using the [BOINC](https://boinc.berkeley.edu) platform.

The BOINC [BOINC](https://boinc.berkeley.edu) platform enables individuals to contribute their computer's idle processing power to various scientific research projects, such as climate modeling, medical research, and astrophysics.

## Installation

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fhectorespert%2Fboinc-addons)

To install the add-ons provided by this repository in your Home Assistant instance, click on the button above or follow these steps:

1. Open your Home Assistant instance.
2. Go to the Supervisor panel.
3. Click on the "Add-on Store" tab.
4. Click on the three dots in the top right corner and select "Repositories".
5. Add the repository URL: `https://github.com/hectorespert/boinc-addons`.
6. Install the desired add-ons from the store.

## Usage

This repository contains the following add-ons, enable them as needed:

### [BOINC add-on](./boinc)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

[BOINC](https://boinc.berkeley.edu) is an open-source software platform for computing using volunteered resources. 

This add-on configures and executes the BOINC client in your Home Assistant instance, downloads scientific computing jobs and runs them invisibly in the background.

### [boinctui add-on](./boinctui)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

[boinctui](https://github.com/suleman1971/boinctui) is a fullscreen text mode manager for the BOINC client.

It provides a terminal user interface (TUI) to monitor and control the BOINC client.

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
