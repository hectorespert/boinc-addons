import logging
import os
from venv import logger

def prepare_gui_rpc_auth(data_folder: str, password: str | None) -> None:
    gui_rpc_auth = f'{data_folder}/gui_rpc_auth.cfg'
    if os.path.exists(gui_rpc_auth):
        os.remove(gui_rpc_auth)
        logger.debug(f'Removing existing BOINC GUI RPC auth file')
    if password:
        with open(gui_rpc_auth, 'w') as f:
            logging.debug(f'Writing BOINC GUI RPC auth file on {gui_rpc_auth}')
            f.write(f'{password}\n')
