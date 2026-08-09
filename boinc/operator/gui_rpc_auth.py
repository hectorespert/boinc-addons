import logging
import os

def prepare_gui_rpc_auth(data_folder: str, password: str | None) -> None:
    gui_rpc_auth = f'{data_folder}/gui_rpc_auth.cfg'

    if password is None:
        # No password configured. BOINC generates a random one, with 0600 permissions, when the
        # file is missing, so the secure thing to do is stay out of its way. An empty file left
        # by an older version is not a missing password, it *is* the empty password, so remove it.
        if os.path.exists(gui_rpc_auth) and os.path.getsize(gui_rpc_auth) == 0:
            os.remove(gui_rpc_auth)
            logging.info(f'Removed the empty BOINC GUI RPC auth file, the BOINC client will generate a password')
        else:
            logging.debug(f'No GUI RPC password configured, leaving the BOINC GUI RPC auth file to the BOINC client')
        return

    if os.path.exists(gui_rpc_auth):
        os.remove(gui_rpc_auth)
        logging.debug(f'Removing existing BOINC GUI RPC auth file')

    logging.debug(f'Writing BOINC GUI RPC auth file on {gui_rpc_auth}')
    # 0600 like the file BOINC writes itself: it holds a credential.
    with open(os.open(gui_rpc_auth, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as f:
        if password:
            f.write(f'{password}\n')
