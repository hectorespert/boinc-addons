import logging
import os
import stat

# The file holds a credential, and it is what the BOINC client itself writes when it generates one.
FILE_MODE = 0o600

def restrict_gui_rpc_auth(gui_rpc_auth: str) -> None:
    if stat.S_IMODE(os.stat(gui_rpc_auth).st_mode) != FILE_MODE:
        os.chmod(gui_rpc_auth, FILE_MODE)
        logging.info(f'Restricted the BOINC GUI RPC auth file permissions to {oct(FILE_MODE)}')

def prepare_gui_rpc_auth(data_folder: str, password: str | None) -> None:
    gui_rpc_auth = f'{data_folder}/gui_rpc_auth.cfg'

    if password is None:
        # No password configured. BOINC generates a random one, with 0600 permissions, when the
        # file is missing, so the secure thing to do is stay out of its way.
        if not os.path.exists(gui_rpc_auth):
            logging.debug(f'No GUI RPC password configured, the BOINC client will generate one')
        elif os.path.getsize(gui_rpc_auth) == 0:
            # An empty file left by an older version is not a missing password, it *is* the empty
            # password, so it has to go for the client to generate one.
            os.remove(gui_rpc_auth)
            logging.info(f'Removed the empty BOINC GUI RPC auth file, the BOINC client will generate a password')
        else:
            # Keeping a password that is already in place, but not necessarily its permissions:
            # an older version of this operator wrote the file world-readable.
            restrict_gui_rpc_auth(gui_rpc_auth)
            logging.debug(f'No GUI RPC password configured, leaving the existing BOINC GUI RPC auth file in place')
        return

    if os.path.exists(gui_rpc_auth):
        os.remove(gui_rpc_auth)
        logging.debug(f'Removing existing BOINC GUI RPC auth file')

    logging.debug(f'Writing BOINC GUI RPC auth file on {gui_rpc_auth}')
    with open(os.open(gui_rpc_auth, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE), 'w') as f:
        if password:
            f.write(f'{password}\n')
