import logging
import re
import subprocess


def configure_boinc_projects(data_folder: str, account_manager_url: str | None, account_manager_username: str | None, account_manager_password: str | None) -> bool:
    result = subprocess.run(["boinccmd", "--acct_mgr", "info"], capture_output=True, text=True, cwd=data_folder)
    if result.returncode != 0:
        logging.error(f'Failed to configure BOINC projects: {result.stderr}')
        return False

    match = re.search(r'URL: (\S+)', result.stdout)
    current_account_manager_url = match.group(1) if match else None
    logging.debug(f'Current account manager URL {current_account_manager_url}')

    if account_manager_url is not None and account_manager_username is not None and account_manager_password is not None:
        if current_account_manager_url is None:
            logging.info(f'Configured account manager {account_manager_url} not attached, configuring with username {account_manager_username}')
            result = subprocess.run(["boinccmd", "--acct_mgr", "attach", account_manager_url, account_manager_username, account_manager_password], capture_output=True, text=True, cwd=data_folder)
            if result.returncode != 0:
                logging.error(f'Failed to attach account manager: {result.stderr}')
                return False
            logging.info(f'Account manager {account_manager_url} attached with username {account_manager_username}')
            return True

        elif current_account_manager_url == account_manager_url:
            logging.info(f'Account manager {account_manager_url} already configured with username {account_manager_username}, synchronizing')
            result = subprocess.run(["boinccmd", "--acct_mgr", "sync"], capture_output=True, text=True, cwd=data_folder)
            if result.returncode != 0:
                logging.error(f'Failed to synchronize account manager: {result.stderr}')
                return False
        else:
            logging.info(f'Account manager {account_manager_url} configured, but different from current account manager {current_account_manager_url}, detaching')
            result = subprocess.run(["boinccmd", "--acct_mgr", "detach"], capture_output=True, text=True, cwd=data_folder)
            if result.returncode != 0:
                logging.error(f'Failed to detach account manager: {result.stderr}')
                return False

            logging.info(f'Account manager {account_manager_url} not configured, configuring with username {account_manager_username}')
            result = subprocess.run(["boinccmd", "--acct_mgr", "attach", account_manager_url, account_manager_username, account_manager_password], capture_output=True, text=True, cwd=data_folder)
            if result.returncode != 0:
                logging.error(f'Failed to attach account manager: {result.stderr}')
                return False

    elif current_account_manager_url is not None:
        logging.warning(f'Account manager configured, but configuration is not provided, detaching')
        result = subprocess.run(["boinccmd", "--acct_mgr", "detach"], capture_output=True, text=True, cwd=data_folder)
        if result.returncode != 0:
            logging.error(f'Failed to detach account manager: {result.stderr}')
            return False

    return True
