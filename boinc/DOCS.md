# Home Assistant BOINC Add-on

[BOINC](https://boinc.berkeley.edu) is an open-source software platform for computing using volunteered resources.

The BOINC add-on, running on your Home Assistant, downloads scientific computing jobs and runs them invisibly in the background.

## Privileged mode

To allow suspending the BOINC client based on the CPU usage from other processes, this addon requires running in privileged mode.

## How to use

### Account Manager (Easy)

The easy way to use this addon is to attach the boicn client to a [BOINC Account Manager](https://boinc.berkeley.edu/wiki/Account_managers).

[Science United](https://scienceunited.org) is recommended to simplify the process of start computing.

If you do not have an account created in an [account manager](https://boinc.berkeley.edu/wiki/Account_managers), you need to create it and use the same username and password in the addon configuration.

For example, in [Science United](https://scienceunited.org), you could sign up in this page: [Join Science United](https://scienceunited.org/su_join.php).

After create the accountm, set the url of the account manager, your user and your password in the addon configuration or edit the yaml configuration.

```yaml
account_manager_url: "https://scienceunited.org"
account_manager_username: "youremail@email.com"
account_manager_password: "yoursecretpassword"
```

### Remote GUI RPC

[Remote GUI RPC](https://boinc.berkeley.edu/wiki/Controlling_BOINC_remotely) can be enabled in the addon configuration and use it to manage the boinc client remotely.

There is a boinctui add-on available for this purpose [here](https://github.com/hectorespert/boinc-addons/tree/main/boinctui).

Related options include:

- **remote_hosts**
By default, no remote hosts are allowed to connect. You must explicitly specify the IP addresses or hostnames of the machines you want to grant access.

- **allow_remote_gui_rpc**
It allows remote connections from any host, independent of the `remote_hosts` setting.

### Global preferences override

To override the preferences of BOINC client a `global_preferences_override.xml` file could be defined in the addon config folder: [Preferences Override](
https://github.com/BOINC/boinc/wiki/PrefsOverride)