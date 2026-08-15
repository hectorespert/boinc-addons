import logging
import re
import subprocess

from url import canonicalize_url


def get_state(data_folder: str) -> bool:
    result = subprocess.run(["boinccmd", "--get_state"], capture_output=True, text=True, cwd=data_folder)
    return result.returncode == 0

def attach_account_manager(data_folder: str, account_manager_url: str, account_manager_username: str, account_manager_password: str) -> bool:
    logging.info(f'Attaching account manager {account_manager_url}')
    result = subprocess.run(["boinccmd", "--acct_mgr", "attach", account_manager_url, account_manager_username, account_manager_password], capture_output=True, text=True, cwd=data_folder)
    if result.returncode != 0:
        logging.error(f'Failed to attach account manager: {result.stderr}')
        return False
    else:
        logging.debug(result.stdout)
        logging.info(f'Account manager attached')
        return True

def detach_account_manager(data_folder: str) -> bool:
    logging.info(f'Detaching account manager')
    result = subprocess.run(["boinccmd", "--acct_mgr", "detach"], capture_output=True, text=True, cwd=data_folder)
    if result.returncode != 0:
        logging.error(f'Failed to detach account manager: {result.stderr}')
        return False
    else:
        logging.debug(result.stdout)
        logging.info(f'Account manager detached')
        return True

def sync_account_manager(data_folder: str) -> bool:
    logging.info(f'Synchronizing account manager')
    result = subprocess.run(["boinccmd", "--acct_mgr", "sync"], capture_output=True, text=True, cwd=data_folder)
    if result.returncode != 0:
        logging.error(f'Failed to synchronize account manager: {result.stderr}')
        return False
    else:
        logging.debug(result.stdout)
        logging.info(f'Account manager synchronized')
        return True

def configure_boinc_projects(data_folder: str, account_manager_url: str | None, account_manager_username: str | None, account_manager_password: str | None) -> bool:

    result = subprocess.run(["boinccmd", "--acct_mgr", "info"], capture_output=True, text=True, cwd=data_folder)
    if result.returncode != 0:
        logging.error(f'Failed to get account manager information: {result.stderr}')
        return False

    logging.debug(f'{result.stdout}')

    match = re.search(r'URL: (\S+)', result.stdout)
    current_account_manager_url = match.group(1) if match else None
    logging.info(f'Current account manager {current_account_manager_url}')

    if any([account_manager_url, account_manager_username, account_manager_password]) and not all([account_manager_url, account_manager_username, account_manager_password]):
        # Half an account manager has no safe reading: attaching is impossible, and carrying on
        # would leave the add-on looking healthy while contributing to nothing at all. Stop instead,
        # so the mistake reaches the exit code rather than scrolling past in the log.
        logging.error(f'Incomplete account manager configuration: account_manager_url, account_manager_username and account_manager_password must all be set, or all be empty')
        return False
    elif account_manager_url is not None and account_manager_username is not None and account_manager_password is not None:
        if current_account_manager_url is None:
            logging.debug(f'Account manager {account_manager_url} configured but not attached, attaching')
            return attach_account_manager(data_folder, account_manager_url, account_manager_username, account_manager_password)

        elif canonicalize_url(current_account_manager_url) == canonicalize_url(account_manager_url):
            logging.info(f'Account manager {account_manager_url} already attached, synchronizing')
            return sync_account_manager(data_folder)

        else:
            logging.info(f'Account manager {account_manager_url} configured, but different from current account manager {current_account_manager_url}, changing')
            result = detach_account_manager(data_folder)
            if not result:
                return False

            # Nothing to wait for in between: detach is a single synchronous RPC
            # (`rpc.acct_mgr_rpc("", "", "")` in client/boinc_cmd.cpp), so the client has already
            # processed it by the time boinccmd returns. Only attach and sync poll, and they do it
            # inside boinccmd itself.
            return attach_account_manager(data_folder, account_manager_url, account_manager_username, account_manager_password)

    elif current_account_manager_url is not None:
        # No account manager is configured in the add-on options, so this is not a field the
        # operator owns: the attachment was made outside it (boinctui, a remote GUI, boinccmd).
        # Leaving it alone, detaching it here would silently undo the user's own configuration.
        logging.info(f'Account manager {current_account_manager_url} was attached outside the add-on options, leaving it unchanged')

    return True
