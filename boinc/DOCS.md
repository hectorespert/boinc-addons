# Home Assistant BOINC App

[BOINC](https://boinc.berkeley.edu) is an open-source software platform for computing using volunteered resources.

The BOINC app, running on your Home Assistant, downloads scientific computing jobs and runs them invisibly in the background.

## ⚠️ Important: Protection Mode

**This app requires Protection Mode to be disabled** so it can see CPU usage across your whole
Home Assistant host and pause BOINC computing whenever other apps need the CPU.

To disable it: **Settings → Add-ons → BOINC → Info**, then turn off **Protection mode**.

**Security Note:** Disabling Protection Mode grants this app elevated access to host resources.
Only install it if you understand and accept that.

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

### Remote Control (Advanced)

[Remote GUI RPC](https://boinc.berkeley.edu/wiki/Controlling_BOINC_remotely) can be enabled in the app configuration and used to manage the BOINC client remotely.

There is a boinctui app available for this purpose [here](https://github.com/hectorespert/boinc-addons/tree/main/boinctui).

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