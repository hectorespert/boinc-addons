# Home Assistant BOINC App

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

[BOINC](https://boinc.berkeley.edu) is an open-source software platform for computing using volunteered resources.

The BOINC app, running on your Home Assistant, downloads scientific computing jobs and runs them invisibly in the background.

## ⚠️ Important

**This app requires Protection Mode to be disabled** to monitor system-wide CPU usage and automatically suspend computations when other services need resources.

## What else this app asks for

Home Assistant lists the permissions an app requests before you install it. Besides the CPU monitoring above, this app asks for two that are worth explaining:

- **Graphics device access** — so BOINC can use your graphics card for projects that offer GPU work. Without it those projects fall back to the processor.
- **Docker access** — some science projects ship their work as containers, and BOINC needs this to run them. It is the broadest permission this app requests: anything with Docker access can start and stop containers on your Home Assistant machine. If you would rather not grant it, this app is not for you; there is no option to turn it off separately.

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
