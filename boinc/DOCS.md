# Home Assistant BOINC Add-on

[BOINC](https://boinc.berkeley.edu) is an open-source software platform for computing using volunteered resources.

The BOINC add-on, running on your Home Assistant, downloads scientific computing jobs and runs them invisibly in the background.

## ⚠️ Important: Protection Mode

**This add-on requires Protection Mode to be disabled.**

Protection Mode must be turned off because the add-on needs to monitor system-wide CPU usage across all processes on the host system. This functionality is essential to automatically suspend BOINC computations when other applications need CPU resources, preventing BOINC from interfering with your Home Assistant instance or other critical services.

**Security Note:** Disabling Protection Mode grants the container elevated access to host resources. Only enable this add-on if you understand and accept the security implications.

## How to use

### Account Manager (Easy)

The easy way to use this add-on is to attach the BOINC client to a [BOINC Account Manager](https://boinc.berkeley.edu/wiki/Account_managers).

[Science United](https://scienceunited.org) is recommended to simplify the process of starting computing.

If you do not have an account created in an [account manager](https://boinc.berkeley.edu/wiki/Account_managers), you need to create it and use the same username and password in the add-on configuration.

For example, in [Science United](https://scienceunited.org), you could sign up on this page: [Join Science United](https://scienceunited.org/su_join.php).

After creating the account, set the URL of the account manager, your user and your password in the add-on configuration or edit the YAML configuration.

```yaml
account_manager_url: "https://scienceunited.org"
account_manager_username: "youremail@email.com"
account_manager_password: "yoursecretpassword"
```

### Remote Control (Advanced)

[Remote GUI RPC](https://boinc.berkeley.edu/wiki/Controlling_BOINC_remotely) can be enabled in the add-on configuration and used to manage the BOINC client remotely.

There is a boinctui add-on available for this purpose [here](https://github.com/hectorespert/boinc-addons/tree/main/boinctui).

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

#### Remote Control Options

- **gui_rpc_password** (optional)
  - Define a GUI RPC password to connect remotely

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

#### Resource Usage Options

- **max_ncpus** (optional, range: 0-100)
  - Maximum percentage of CPUs to use
  - Value represents the percentage of available CPU cores
  - Example: `50` means use up to 50% of available cores

- **cpu_usage_limit** (optional, range: 0-100)
  - Maximum CPU usage percentage per core
  - Value represents the percentage of time each CPU can be used
  - Example: `75` means each CPU can be used up to 75% of the time

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

To override the preferences of the BOINC client, a `global_preferences_override.xml` file can be defined in the add-on config folder: [Preferences Override](https://github.com/BOINC/boinc/wiki/PrefsOverride)