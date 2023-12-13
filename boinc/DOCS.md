# Home Assistant Boinc Add-on

[BOINC](https://boinc.berkeley.edu) is an open-source software platform for computing using volunteered resources.

The BOINC add-on, running on your Home Assistant, downloads scientific computing jobs and runs them invisibly in the background.

## How to use

### Account Manager (Easy)

The easy way to use this addon is to attach the boicn client to a [Boinc Account Manager](https://boinc.berkeley.edu/wiki/Account_managers).

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
