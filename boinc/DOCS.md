# Home Assistant BOINC App

[BOINC](https://boinc.berkeley.edu) is an open-source software platform for computing using volunteered resources.

The BOINC app, running on your Home Assistant, downloads scientific computing jobs and runs them invisibly in the background.

## ⚠️ Important: Protection Mode

**This app requires Protection Mode to be disabled** so it can see CPU usage across your whole
Home Assistant host and pause BOINC computing whenever other apps need the CPU.

To disable it: **Settings → Apps → BOINC → Info**, then turn off **Protection mode**. On Home
Assistant older than 2026.2, that menu is called **Add-ons**.

**Security Note:** Disabling Protection Mode grants this app elevated access to host resources.
Only install it if you understand and accept that.

The app now ships with a security profile: a written list of everything it, and the science
applications it downloads, are expected to need. For now the list is only being checked against what
really happens, so that a later update can start enforcing it without interrupting your computing.
Until then it changes nothing — neither what Protection Mode does, nor the access described above.

## How to use

### Account Manager (Easy)

The easy way to use this app is to attach the BOINC client to a [BOINC Account Manager](https://boinc.berkeley.edu/wiki/Account_managers).

[Science United](https://scienceunited.org) is recommended to simplify the process of starting computing.

If you do not have an account created in an [account manager](https://boinc.berkeley.edu/wiki/Account_managers), you need to create it and use the same username and password in the app configuration.

For example, in [Science United](https://scienceunited.org), you could sign up on this page: [Join Science United](https://scienceunited.org/su_join.php).

After creating the account, set the URL of the account manager, your user and your password in the app configuration or edit the YAML configuration.

```yaml
account_manager_url: "https://scienceunited.org"
account_manager_username: "youremail@email.com"
account_manager_password: "yoursecretpassword"
```

### Choosing projects yourself (Advanced)

If you would rather pick the science projects yourself instead of letting an account manager choose,
list them in the app configuration. Each one needs its address and your **account key** for it.

To find your account key: sign in on the project's own website, open your account page, and look for
the account key — most projects show it there, sometimes behind a link called *account keys*. It is
not your project password.

```yaml
projects:
  - url: "https://einsteinathome.org/"
    account_key: "your account key for this project"
  - url: "https://www.worldcommunitygrid.org/"
    account_key: "your account key for that project"
```

**You cannot use this together with an account manager.** An account manager decides on its own
which projects you compute for, so the two would keep undoing each other. Set one or the other — if
both are filled in, the app will not start, and the **Log** tab says so.

**If the account key is wrong, nothing looks broken.** The project is added anyway, the app keeps
running, and it simply never receives any work. The project's website is what turns you away, not
this app, so the only sign is in the app's **Log** tab: look for the project's name next to
*Invalid or missing account key*. If you see it, correct the key and restart the app. This is worth
knowing because it is easy to copy the wrong value — the account key is a long string of letters and
numbers, not your password and not your email.

What the app does with this list:

- **Adding a project** attaches it the next time the app starts.
- **Removing a project** from the list tells BOINC to finish the work it has already downloaded and
  then leave the project. Nothing you have already computed is thrown away, so it may stay listed in
  boinctui for a while until its last tasks are done and reported.
- **Projects you attached yourself** — from the boinctui app, a remote BOINC Manager, or an account
  manager — are never removed by this list. It only manages the projects it attached.
- **Changes only take effect when the app restarts**, which Home Assistant asks you to do after you
  save the configuration.

One consequence worth knowing: if you leave a project in this list but detach it yourself from
boinctui or BOINC Manager, the app attaches it again the next time it starts, because the list still
asks for it. Remove it from the list to remove it for good.

### Remote Control (Advanced)

[Remote GUI RPC](https://boinc.berkeley.edu/wiki/Controlling_BOINC_remotely) can be enabled in the app configuration and used to manage the BOINC client remotely.

There is a boinctui app available for this purpose [here](https://github.com/hectorespert/boinc-addons/tree/main/boinctui).

There is also a BOINC UI app [here](https://github.com/hectorespert/boinc-addons/tree/main/boincui),
which shows what each machine is computing on a page inside Home Assistant and lets you start and
stop it.

### Sensors and automations (Advanced)

This app computes, but it creates no sensors: BOINC's state is something you look at, not something
you can put on a dashboard or use in an automation. If you want that, there is a third-party
integration that provides it, and it is designed to work alongside this app:
[BOINC for Home Assistant](https://github.com/SpuelMett/Boinc-Home-Assistant-Integration).

It adds sensors for the tasks a machine is running and how far along they are, and actions to start
and stop computing — so you can show BOINC on a dashboard, keep history, or stop it from an
automation when the house gets too warm.

To use it with this app:

1. In this app's configuration, set a **gui_rpc_password** and turn on **allow_remote_gui_rpc**, then
   restart the app.
2. Install the integration through HACS as a custom repository — it is not in the HACS catalogue, so
   you have to add its address yourself. Its own page has the current instructions.
3. Add it from **Settings → Devices & services**, using the hostname shown on this app's **Info**
   page as the address, and the same password you just set.

**allow_remote_gui_rpc lets any machine on your network try to connect**, so the password is the only
thing protecting the client — do not leave it empty. If you would rather not open it that widely, you
can list allowed machines in **remote_hosts** instead; when a connection is refused, this app's
**Log** tab names the address that was turned away, which is the one to add.

Publishing port 31416 is only needed for programs running outside Home Assistant, such as BOINC
Manager on another computer. Home Assistant itself and the other apps reach this one without it.

This integration is not part of this project and is maintained by someone else. It is optional —
nothing here depends on it.

## Configuration

### Configuration Options

#### Account Manager Options

- **account_manager_url** (optional)
  - A URL for a BOINC Account Manager, for example: `https://scienceunited.org`
  - This is the easiest way to get started with BOINC

- **account_manager_username** (optional)
  - A username for a user registered in the BOINC Account Manager
  - Required if `account_manager_url` is set

- **account_manager_password** (optional)
  - Password for the configured user in the BOINC Account Manager
  - Required if `account_manager_url` is set

Set all three and the app keeps the BOINC client attached to that account manager, replacing a
different one if needed. Leave all three empty and the app leaves the account manager alone: one
you attached yourself — from the boinctui app, a remote BOINC Manager, or a command-line tool —
stays attached. Detach it the same way you attached it.

**Set only one or two of the three and the app will not start.** Open the app's **Log** tab to see
why.

#### Project Options

- **projects** (optional, list)
  - The science projects to compute for, chosen by you instead of by an account manager
  - Each entry needs a **url** (the project's address, for example `https://einsteinathome.org/`)
    and an **account_key** (found on your account page on that project's website)
  - Leave the list empty to not manage projects from here at all
  - Cannot be combined with the account manager options above — set one or the other, or the app
    will not start

See [Choosing projects yourself](#choosing-projects-yourself-advanced) above for how to find an
account key and what happens when you add or remove a project.

#### Remote Control Options

- **gui_rpc_password** (optional)
  - Password required to control this BOINC client remotely, for example from the boinctui app
  - If you plan to connect from the boinctui app, set a password here and use that same password
    there
  - Leave it unset and the client makes up its own private password on first start — Home
    Assistant gives you no way to see it, so set your own here instead
  - Set it to an explicit empty string (`gui_rpc_password: ""`) to use *no* password at all. Only
    do this while remote access is off, since it would let any host allowed by `remote_hosts` or
    `allow_remote_gui_rpc` take full control of the client with no credential

- **remote_hosts** (optional)
  - List of remote hosts to allow remote connection
  - Specify IP addresses or hostnames (e.g., `192.168.1.100`, `myhost.local`)
  - By default, no remote hosts are allowed

- **allow_remote_gui_rpc** (optional, boolean)
  - Allow all remote GUI RPC connections (overrides `remote_hosts` setting)
  - Default: `false`
  - **Warning:** Enabling this allows connections from any host

#### Computing Schedule Options

- **start_hour** (optional, format: `HH:MM`)
  - Configure the hour when BOINC starts computing
  - Format: 24-hour time (e.g., `09:00`, `22:30`)
  - If not set, BOINC computes all the time

- **end_hour** (optional, format: `HH:MM`)
  - Configure the hour when BOINC stops computing
  - Format: 24-hour time (e.g., `18:00`, `06:00`)
  - Must be used together with `start_hour`

Both hours must be set together, or neither. Setting just one of them, or setting both to the same
time, is ignored — BOINC computes all the time — and a warning explaining why appears in the app's
**Log** tab.

#### Resource Usage Options

- **max_ncpus** (optional, range: 0-100)
  - Maximum percentage of CPUs to use while the computer is in use
  - Value represents the percentage of available CPU cores
  - Example: `50` means use up to 50% of available cores
  - Also applies while the computer is not in use, unless `max_ncpus_idle` is set below

- **cpu_usage_limit** (optional, range: 0-100)
  - Maximum CPU usage percentage per core while the computer is in use
  - Value represents the percentage of time each CPU can be used
  - Example: `75` means each CPU can be used up to 75% of the time
  - Also applies while the computer is not in use, unless `cpu_usage_limit_idle` is set below

- **max_ncpus_idle** (optional, range: 0-100)
  - Maximum percentage of CPUs to use while the computer is **not** in use, instead of `max_ncpus`
  - Leave unset to use the same limit in both cases

- **cpu_usage_limit_idle** (optional, range: 0-100)
  - Maximum CPU usage percentage per core while the computer is **not** in use, instead of
    `cpu_usage_limit`
  - Leave unset to use the same limit in both cases

### Example Configurations

#### Basic Setup with Account Manager

```yaml
account_manager_url: "https://scienceunited.org"
account_manager_username: "youremail@example.com"
account_manager_password: "your_password"
```

#### Choosing Projects Instead of an Account Manager

```yaml
projects:
  - url: "https://einsteinathome.org/"
    account_key: "your_account_key_for_einstein"
  - url: "https://www.worldcommunitygrid.org/"
    account_key: "your_account_key_for_wcg"
```

#### Computing Only at Night (22:00 to 07:00)

```yaml
account_manager_url: "https://scienceunited.org"
account_manager_username: "youremail@example.com"
account_manager_password: "your_password"
start_hour: "22:00"
end_hour: "07:00"
```

#### Limited Resource Usage

```yaml
account_manager_url: "https://scienceunited.org"
account_manager_username: "youremail@example.com"
account_manager_password: "your_password"
max_ncpus: 50
cpu_usage_limit: 75
```

#### Full Speed Only When the Computer Is Not in Use

```yaml
account_manager_url: "https://scienceunited.org"
account_manager_username: "youremail@example.com"
account_manager_password: "your_password"
max_ncpus: 25
cpu_usage_limit: 25
max_ncpus_idle: 100
cpu_usage_limit_idle: 100
```

#### Remote Control Setup

```yaml
gui_rpc_password: "my_secure_password"
remote_hosts:
  - "192.168.1.100"
  - "192.168.1.101"
```

#### Full Configuration Example

```yaml
account_manager_url: "https://scienceunited.org"
account_manager_username: "youremail@example.com"
account_manager_password: "your_password"
gui_rpc_password: "rpc_password"
remote_hosts:
  - "192.168.1.100"
start_hour: "22:00"
end_hour: "07:00"
max_ncpus: 50
cpu_usage_limit: 75
```

### Global Preferences Override

For full control over BOINC's preferences, you can supply your own `global_prefs_override.xml`
file — see [Preferences Override](https://github.com/BOINC/boinc/wiki/PrefsOverride) for the
format. Place it in this app's config folder, which appears as `addon_configs/…_boinc` in the
File editor and Samba apps.

When that file is present, the app uses it as-is and the `start_hour`, `end_hour`, `max_ncpus`,
`cpu_usage_limit`, `max_ncpus_idle` and `cpu_usage_limit_idle` options are ignored.

Otherwise, the app only manages those six settings. Anything else you set from boinctui or a
remote BOINC Manager — disk limits, memory, network, work buffer, even a schedule using the same
start/end time fields — is preserved across restarts and updates. Setting one of the six options
applies it, and removing it from the options clears it again, without touching preferences you set
yourself elsewhere.